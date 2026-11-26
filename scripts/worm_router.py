#!/usr/bin/env python3
"""Route new objects in an Object Lock (WORM) bucket to each case's Drive folder. Made for a phone app that writes
straight to WORM (e.g. ProofMode WORM Uploader): it locks the evidence, this copies it to Drive.

  worm_router.py run [--dry-run]       one pass: route every object not seen before, then exit
  worm_router.py baseline              mark everything now in the bucket as seen (first deploy), route nothing
  worm_router.py put PREFIX FILE...    worm.py-compatible upload (used as cases.json "worm_script" by unzip_proof.py)

Per case in cases.json (EVIDENCE_CASES), from its "proofmode" block (and "audio" block, if any):
- a new zip under proofmode.worm.zip  -> download, check SHA-256, unzip_proof.py: verifies the PGP proofs, locks the
  media and proof files in WORM, copies media, proofs and the zip to Drive (proofmode.dirs, dated subfolders)
- a new video/photo under proofmode.worm.{video,image}/<rest> -> Drive proofmode.dirs.{video,image}/<rest>
- a new audio file under audio.worm/<rest> -> Drive audio.dir/<rest> in audio.drive_folder_id
Every Drive copy is checked by SHA-256 against the object's `sha256` metadata (or, without it, the downloaded bytes).
A failure is logged and retried on the next pass; nothing is marked seen until its Drive copy is verified.
Never deletes, overwrites or changes retention.

Env: WORM_BUCKET, WORM_ENDPOINT, WORM_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY.
State and log: <user data>/digital-evidence/router/{seen.json,log.jsonl} (CLAUDE_USER_DATA as in clip.py).
"""
import hashlib, json, os, subprocess, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path

import boto3

HERE = Path(__file__).resolve().parent
DATA = Path(os.environ.get("CLAUDE_USER_DATA")
            or Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "claude-plugins") / "digital-evidence"
CF = Path(os.environ.get("EVIDENCE_CASES") or DATA / "cases.json").expanduser()
STATE = DATA / "router"
B = os.environ.get("WORM_BUCKET", "")
s3 = boto3.client("s3", endpoint_url=os.environ.get("WORM_ENDPOINT"), region_name=os.environ.get("WORM_REGION"))


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log(**kw):
    STATE.mkdir(parents=True, exist_ok=True)
    line = json.dumps({"at": now(), **kw}, ensure_ascii=False)
    print(line, flush=True)
    with open(STATE / "log.jsonl", "a") as f:
        f.write(line + "\n")


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def listing(prefix):
    out = {}
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=B, Prefix=prefix):
        for o in page.get("Contents", []):
            if not o["Key"].endswith("/"):
                out[o["Key"]] = o
    return out


def routes(cfg):
    """[(case, kind, worm_prefix/, drive_folder_id, drive_dir)] for every routed prefix."""
    r = []
    for case, c in cfg["cases"].items():
        pm = c.get("proofmode")
        if pm:
            for kind in ("zip", "video", "image"):
                if pm["worm"].get(kind):
                    r.append((case, kind, pm["worm"][kind].rstrip("/") + "/", pm["drive_folder_id"], pm["dirs"][kind]))
        au = c.get("audio")
        if au and au.get("worm"):
            r.append((case, "audio", au["worm"].rstrip("/") + "/", au["drive_folder_id"], au.get("dir", ".")))
    return r


def drive_sha(remote, folder, rel):
    r = subprocess.run(["rclone", "lsjson", "--hash", "--stat", f"{remote}:{rel}", "--drive-root-folder-id", folder],
                       capture_output=True, text=True)
    return json.loads(r.stdout)["Hashes"].get("sha256") if r.returncode == 0 else None


def fetch(key, d):
    p = Path(d) / Path(key).name
    s3.download_file(B, key, str(p))
    want = s3.head_object(Bucket=B, Key=key)["Metadata"].get("sha256")
    got = sha_file(p)
    if want and want != got:
        raise RuntimeError(f"download hash {got} != object metadata {want}")
    return p, got


def route_media(cfg, key, folder, ddir, wprefix, dry):
    rel = f"{ddir.strip('/') + '/' if ddir.strip('./') else ''}{key[len(wprefix):]}"
    if dry:
        return {"drive": rel}
    with tempfile.TemporaryDirectory(prefix="wr-", dir="/var/tmp") as d:
        p, sha = fetch(key, d)
        r = subprocess.run(["rclone", "copyto", "--immutable", str(p), f"{cfg['rclone_remote']}:{rel}",
                            "--drive-root-folder-id", folder], capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError(f"rclone: {(r.stdout + r.stderr).strip()[-400:]}")
    if drive_sha(cfg["rclone_remote"], folder, rel) != sha:
        raise RuntimeError(f"Drive copy {rel} does not match {sha}")
    return {"drive": rel, "sha256": sha}


def route_zip(case, key, dry):
    if dry:
        return {"unzip": case}
    with tempfile.TemporaryDirectory(prefix="wr-", dir="/var/tmp") as d:
        p, sha = fetch(key, d)
        r = subprocess.run([sys.executable, str(HERE / "unzip_proof.py"), case, str(p), "--name", Path(key).name],
                           capture_output=True, text=True, cwd=HERE, timeout=7200)
        if r.returncode:
            raise RuntimeError(f"unzip_proof: {(r.stdout + r.stderr).strip()[-600:]}")
    rec = json.loads(r.stdout)
    return {"sha256": sha, "receipt": rec["receipt"], "items": [f"{i['worm']}/{i['name']}" for i in rec["items"]],
            "proofs": len(rec["proof_files"])}


def run(dry):
    cfg = json.loads(CF.read_text())
    STATE.mkdir(parents=True, exist_ok=True)
    sf = STATE / "seen.json"
    seen = set(json.loads(sf.read_text())) if sf.exists() else None
    if seen is None:
        sys.exit(f"no {sf}: run `worm_router.py baseline` once first, so existing objects are not all copied again")
    rts = routes(cfg)
    for case, kind, wprefix, folder, ddir in sorted(rts, key=lambda r: r[1] != "zip"):  # zips first
        for key in sorted(listing(wprefix)):
            if key in seen or key[len(wprefix):].count("/") > 1:
                continue
            try:
                res = route_zip(case, key, dry) if kind == "zip" else route_media(cfg, key, folder, ddir, wprefix, dry)
            except Exception as e:  # noqa: BLE001 - logged and retried next pass
                log(case=case, key=key, ok=False, error=str(e)[-800:])
                continue
            log(case=case, key=key, ok=True, dry_run=dry, **res)
            if dry:
                continue
            seen.add(key)
            seen.update(res.get("items", []))  # media the zip put in WORM: already copied to Drive by unzip_proof
            sf.write_text(json.dumps(sorted(seen), indent=0))


def baseline():
    cfg = json.loads(CF.read_text())
    STATE.mkdir(parents=True, exist_ok=True)
    sf = STATE / "seen.json"
    seen = set(json.loads(sf.read_text())) if sf.exists() else set()
    n = len(seen)
    for _, _, wprefix, _, _ in routes(cfg):
        seen.update(listing(wprefix))
    sf.write_text(json.dumps(sorted(seen), indent=0))
    log(baseline=True, added=len(seen) - n, total=len(seen))


def put(prefix, files):
    """Same contract and output as worm.py put: OK <key> ..., SKIP same content: <key> = <existing>."""
    prefix = prefix.strip("/")
    for f in map(Path, files):
        key, want = f"{prefix}/{f.name}", sha_file(f)
        try:
            h = s3.head_object(Bucket=B, Key=key)
        except s3.exceptions.ClientError as e:
            if e.response["Error"]["Code"] not in ("404", "NoSuchKey", "NotFound"):
                raise
            h = None
        if h is not None:
            if h["Metadata"].get("sha256") == want:
                print("SKIP same content:", key, "=", key); continue
            sys.exit(f"key taken by different content: {key}")
        s3.upload_file(str(f), B, key, ExtraArgs={"Metadata": {"sha256": want}})
        h = s3.head_object(Bucket=B, Key=key)
        if h["Metadata"].get("sha256") != want or h["ContentLength"] != f.stat().st_size or not h.get("ObjectLockMode"):
            sys.exit(f"read-back failed or not locked: {key}")
        print("OK", key, want, h["ObjectLockMode"], h["ObjectLockRetainUntilDate"].isoformat(), h.get("VersionId"))


if __name__ == "__main__":
    a = sys.argv[1:]
    if not B:
        sys.exit("WORM_BUCKET not set")
    if a[:1] == ["run"]:
        run("--dry-run" in a)
    elif a[:1] == ["baseline"]:
        baseline()
    elif a[:1] == ["put"] and len(a) > 2:
        put(a[1], a[2:])
    else:
        sys.exit(__doc__)
