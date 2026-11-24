#!/usr/bin/env python3
"""Upload local audio evidence (WAV and its seal files) to a case: Drive with hash match, then WORM.
  audio_files.py CASE DATE FILE... [--dry-run]     DATE = local recording date YYYY-MM-DD
Case needs "audio": {"drive_folder_id", "dir", "worm"} in cases.json. Nothing local is deleted.
"""
import argparse, json, re, sys
from pathlib import Path
from clip import sh, hashes, drive_entry, CFG, WORM, REMOTE

ap = argparse.ArgumentParser(); ap.add_argument("case", choices=CFG["cases"]); ap.add_argument("date")
ap.add_argument("files", nargs="+"); ap.add_argument("--dry-run", action="store_true"); a = ap.parse_args()
c = CFG["cases"][a.case]["audio"]; files = [Path(f) for f in a.files]; out = []
if not re.fullmatch(r"\d{4}-\d\d-\d\d", a.date): sys.exit("DATE must be YYYY-MM-DD")
if len({f.name for f in files}) != len(files): sys.exit("two files share a name")
for f in files:
    s, m = hashes(f); rel = f"{c['dir']}/{a.date}/{f.name}"; out.append({"name": f.name, "sha256": s, "md5": m, "rel": rel})
    if a.dry_run: continue
    sh(["rclone", "copyto", "--immutable", str(f), f"{REMOTE}:{rel}", "--drive-root-folder-id", c["drive_folder_id"]])
    d = drive_entry(c["drive_folder_id"], rel)
    if d["Hashes"].get("sha256") != s: sys.exit(f"Drive hash mismatch: {rel}")
    out[-1]["drive_url"] = f"https://drive.google.com/file/d/{d['ID']}/view"
if WORM and not a.dry_run:
    r = sh([WORM, "put", f"{c['worm']}/{a.date}", *map(str, files)], timeout=3600)
    for f in files:
        if not re.search(r"(OK|content:) " + re.escape(f"{c['worm']}/{a.date}/{f.name}") + r" ", r): sys.exit(f"WORM did not confirm {f.name}: {r}")
print(json.dumps(out, indent=1))
