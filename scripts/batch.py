#!/usr/bin/env python3
"""Import every finished file in the phone's ProofMode folder (videos, photos) and, if found, proof zips.

  batch.py ingest CASE [--stage DIR]     phone -> stage -> Drive (hash match) -> WORM; prints receipt
  batch.py delete RECEIPT                re-checks Drive and WORM per file, then removes from the phone
--stage reuses files already pulled; each is still compared with the phone's own SHA-256.
Case needs a "proofmode" block in cases.json: drive_folder_id, dirs{video,image,zip}, worm{video,image,zip}.
Proof zips are looked for in /sdcard/Download and /sdcard/Documents (*proofmode*.zip, last 24 h).
"""
import argparse, json, re, shlex, subprocess, sys, tempfile
from datetime import datetime, timedelta
from pathlib import Path
import clip
from clip import sh, adb, device, hashes, dev_sha, drive_entry, worm_check, CFG, PH, TZ, WORM, REMOTE, RECEIPTS, inspect

KIND = {".mp4": "video", ".jpg": "image", ".jpeg": "image", ".zip": "zip"}


def start_of(p, kind):
    """(local start, seconds or None). MP4 creation_time is the END of recording on Android."""
    if kind == "video":
        f = json.loads(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration:format_tags=creation_time", "-of", "json", str(p)]))["format"]
        dur = float(f["duration"])
        return datetime.fromisoformat(f["tags"]["creation_time"].replace("Z", "+00:00")).astimezone(TZ) - timedelta(seconds=dur), round(dur, 1)
    m = re.fullmatch(r"(\d{13})", p.stem)  # ProofMode photos are named by epoch milliseconds
    return datetime.fromtimestamp(int(m[1]) / 1000 if m else p.stat().st_mtime, TZ), None


def ingest(a):
    c = CFG["cases"][a.case]; pm = c["proofmode"]; dev = device()
    src = PH["folders"]["proofmode"]
    paths = adb(dev, f"find {shlex.quote(src)} -maxdepth 1 -type f ! -name '.*'").splitlines()
    paths += adb(dev, "find /sdcard/Download /sdcard/Documents -iname '*proofmode*.zip' -mmin -1440 2>/dev/null || true").splitlines()
    stage = Path(a.stage or tempfile.mkdtemp(prefix="proofmode-", dir="/var/tmp")); files = []
    for dp in filter(None, paths):
        p = stage / Path(dp).name; kind = KIND.get(p.suffix.lower())
        if not kind:
            print("skipping", dp, file=sys.stderr); continue
        if not p.exists():
            sh(["adb", "-s", dev, "pull", "-a", dp, str(p)])
        s, m = hashes(p)
        if dev_sha(dev, dp) != s:
            sys.exit(f"phone and local differ: {dp}")
        t, dur = start_of(p, kind)
        files.append({"device_path": dp, "name": p.name, "kind": kind, "bytes": p.stat().st_size, "start": t.strftime("%Y-%m-%d %H:%M:%S"),
                      "seconds": dur, "sha256": s, "md5": m, "rel": f"{pm['dirs'][kind]}/{t:%Y-%m-%d}/{p.name}",
                      "prefix": f"{pm['worm'][kind]}/{t:%Y-%m-%d}", "proof": inspect(p) if kind != "zip" else None})
    rf = RECEIPTS / f"{datetime.now(TZ):%Y%m%d_%H%M%S}_{a.case}_batch.json"; RECEIPTS.mkdir(parents=True, exist_ok=True)
    rec = {"case": a.case, "device": dev, "stage": str(stage), "files": files, "proof_zip": any(f["kind"] == "zip" for f in files), "complete": False}
    for f in files:
        sh(["rclone", "copyto", "--immutable", str(stage / f["name"]), f"{REMOTE}:{f['rel']}", "--drive-root-folder-id", pm["drive_folder_id"]])
        d = drive_entry(pm["drive_folder_id"], f["rel"])
        if d["Hashes"].get("sha256") != f["sha256"]:
            sys.exit(f"Drive hash mismatch {f['rel']}")
        f["drive_url"] = f"https://drive.google.com/file/d/{d['ID']}/view"
        print("drive ok", f["name"], file=sys.stderr, flush=True)
    for pre in sorted({f["prefix"] for f in files}) if WORM else []:
        g = [f for f in files if f["prefix"] == pre]
        out = sh([WORM, "put", pre, *[str(stage / f["name"]) for f in g]], timeout=5400)
        for f in g:
            key = f"{pre}/{f['name']}"
            m = re.search(r"^SKIP same content: " + re.escape(key) + r" = (.+)$", out, re.M)
            if m: f["worm_key"] = m[1]
            elif re.search(r"^OK " + re.escape(key) + " ", out, re.M): f["worm_key"] = key
            else: sys.exit(f"WORM did not confirm {key}: {out[-300:]}")
        print("worm ok", pre, len(g), file=sys.stderr, flush=True)
    rec["complete"] = True
    rf.write_text(json.dumps(rec, indent=1))
    print(json.dumps({"receipt": str(rf), "n": len(files), "proof_zip": rec["proof_zip"]}))


def delete(a):
    r = json.loads(Path(a.receipt).read_text()); c = CFG["cases"][r["case"]]; pm = c["proofmode"]
    if not r["complete"]: sys.exit("ingest incomplete")
    dev = device(); lines = []
    for pre in sorted({f["worm_key"].rsplit("/", 1)[0] for f in r["files"]}) if WORM else []:
        lines += worm_check(pre, next(f["sha256"] for f in r["files"] if f["worm_key"].startswith(pre + "/")))[1:]
    blob = "\n".join(lines)
    for f in r["files"]:
        if WORM and not any(f["sha256"] in l and "COMPLIANCE" in l for l in lines): sys.exit(f"not locked: {f['name']}")
        if drive_entry(pm["drive_folder_id"], f["rel"])["Hashes"].get("sha256") != f["sha256"]: sys.exit(f"Drive mismatch {f['rel']}")
        if dev_sha(dev, f["device_path"]) != f["sha256"]: sys.exit(f"phone file changed: {f['device_path']}")
    if WORM and c.get("worm_manifest"):
        mf = Path(c["repo"]).expanduser() / c["worm_manifest"]; old = mf.read_text().splitlines()
        rows = {l.split("\t")[0]: l for l in old[1:]}; rows.update({l.split("\t")[0]: l for l in lines})
        mf.write_text("\n".join([old[0], *(rows[k] for k in sorted(rows))]) + "\n")
    for f in r["files"]:
        adb(dev, f"rm {shlex.quote(f['device_path'])}")
        f["deleted"] = subprocess.run(["adb", "-s", dev, "shell", f"ls {shlex.quote(f['device_path'])}"], capture_output=True).returncode != 0
    Path(a.receipt).write_text(json.dumps(r, indent=1))
    print(json.dumps({"deleted": sum(f["deleted"] for f in r["files"]), "of": len(r["files"])}))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); s = ap.add_subparsers(dest="cmd", required=True)
    p = s.add_parser("ingest"); p.add_argument("case", choices=CFG["cases"]); p.add_argument("--stage")
    p = s.add_parser("delete"); p.add_argument("receipt")
    a = ap.parse_args(); {"ingest": ingest, "delete": delete}[a.cmd](a)
