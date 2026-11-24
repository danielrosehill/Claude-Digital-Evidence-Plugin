#!/usr/bin/env python3
"""Extract a ProofMode zip, verify its proofs, file media + proofs on Drive and in WORM. The zip itself is not changed.
  unzip_proof.py CASE ZIP [--name NAME]     NAME = original zip name if the local file was renamed
Stops before uploading anything if a hash, proof set or PGP signature fails. PGP check = signed by the key inside the zip
(shows integrity, not who owns the key). OpenTimestamps files are kept, not verified here.
"""
import argparse, json, re, subprocess, sys, tempfile, zipfile
from pathlib import Path
import clip
from clip import sh, hashes, drive_entry, CFG, WORM, REMOTE, RECEIPTS
from batch import start_of
KIND = {".mp4": "video", ".jpg": "image", ".jpeg": "image", ".m4a": "audio", ".wav": "audio", ".mp3": "audio"}
ap = argparse.ArgumentParser(); ap.add_argument("case", choices=CFG["cases"]); ap.add_argument("zip"); ap.add_argument("--name"); a = ap.parse_args()
pm = CFG["cases"][a.case]["proofmode"]; zp = Path(a.zip); zname = re.sub(r"[^\w.+-]+", "_", a.name or zp.name)
out = Path(tempfile.mkdtemp(prefix="proofzip-", dir="/var/tmp")); home = tempfile.mkdtemp(prefix="gpg-", dir="/var/tmp")
with zipfile.ZipFile(zp) as z:
    if z.testzip(): sys.exit("corrupt zip")
    for n in z.namelist():
        if n.startswith("/") or ".." in Path(n).parts or Path(n).name != n: sys.exit(f"unexpected path in zip: {n}")
    z.extractall(out)
gpg = ["gpg", "--homedir", home, "--batch", "--quiet"]
sh([*gpg, "--import", str(out / "pubkey.asc")])
items, media = [], [p for p in sorted(out.iterdir()) if p.suffix.lower() in KIND]
for p in media:
    s, m = hashes(p); need = [out / f"{s}{x}" for x in (".asc", ".proof.csv", ".proof.csv.asc", ".proof.json", ".proof.json.asc")]
    miss = [q.name for q in need if not q.exists()]
    if miss: sys.exit(f"{p.name}: proof files missing {miss}")
    for sig, data in ((f"{s}.asc", p), (f"{s}.proof.csv.asc", out / f"{s}.proof.csv"), (f"{s}.proof.json.asc", out / f"{s}.proof.json")):
        if subprocess.run([*gpg, "--verify", str(out / sig), str(data)], capture_output=True).returncode: sys.exit(f"BAD SIGNATURE {sig}")
    if not (out / f"{s}.ots").exists(): print("no .ots:", p.name, file=sys.stderr)
    k = KIND[p.suffix.lower()]; t, dur = start_of(p, k); day = f"{t:%Y-%m-%d}"
    wd = pm["worm"].get(k) or CFG["cases"][a.case]["audio"]["worm"]; dd = pm["dirs"].get(k, "ProofMode/Audio")
    items.append({"path": p, "name": p.name, "kind": k, "sha256": s, "md5": m, "start": t.strftime("%Y-%m-%d %H:%M:%S"), "seconds": dur, "ots": (out / f"{s}.ots").exists(), "worm": f"{wd}/{day}", "rel": f"{dd}/{day}/{p.name}"})
if not items: sys.exit("no media in zip")
stem = re.sub(r"\.zip$", "", zname); rest = [p for p in sorted(out.iterdir()) if p not in media and p.stat().st_size]
up = [(p, f"{pm.get('proofs_dir', 'ProofMode/Proofs')}/{stem}/{p.name}") for p in rest] + [(i["path"], i["rel"]) for i in items] + [(zp, f"{pm['dirs']['zip']}/{zname}")]
for p, rel in up:
    sh(["rclone", "copyto", "--immutable", str(p), f"{REMOTE}:{rel}", "--drive-root-folder-id", pm["drive_folder_id"]])
    d = drive_entry(pm["drive_folder_id"], rel)
    if d["Hashes"].get("sha256") != hashes(p)[0]: sys.exit(f"Drive mismatch {rel}")
    for i in items:
        if i["path"] == p: i["drive_url"] = f"https://drive.google.com/file/d/{d['ID']}/view"
groups = {}
for i in items: groups.setdefault(i["worm"], []).append(i["path"])
groups[f"{pm['worm'].get('proofs', a.case + '/proofs')}/{stem}"] = rest
for pre, ps in groups.items() if WORM else []:
    r = sh([WORM, "put", pre, *map(str, ps)], timeout=3600)
    for p in ps:
        if not re.search(r"(OK|content:) " + re.escape(f"{pre}/{p.name}") + " ", r): sys.exit(f"WORM did not confirm {p.name}: {r[-300:]}")
for i in items: i.pop("path")
rec = {"case": a.case, "zip": zname, "zip_sha256": hashes(zp)[0], "items": items, "proof_files": [p.name for p in rest], "extracted": str(out)}
rf = RECEIPTS / f"zip_{stem[-60:]}.json"; rf.write_text(json.dumps(rec, indent=1)); print(json.dumps({"receipt": str(rf), **rec}, indent=1))
