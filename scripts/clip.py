#!/usr/bin/env python3
"""Phone clip -> Drive + WORM, hash-checked at every step; phone deletion is a separate, gated step.

  clip.py latest [--folder timemark|proofmode|camera]
  clip.py ingest CASE [--folder F | --path DEVICE_PATH] [--sidecar DEVICE_PATH]...
                                      prints receipt path + sheet row; sidecar = ProofMode proof zip
  clip.py delete RECEIPT --sheet-row N                    re-verifies everything, then removes from phone
  clip.py inspect FILE                                    C2PA / timestamp markers in a ProofMode clip
Config: $EVIDENCE_CASES, else <user data>/digital-evidence/cases.json (format: skills/proofmode-clip/SKILL.md).
Needs adb, ffprobe, exiftool, rclone; optional worm_script for an Object Lock copy.
"""
import argparse, hashlib, json, os, re, shlex, subprocess, sys, tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

DATA = Path(os.environ.get("CLAUDE_USER_DATA")
            or Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "claude-plugins") / "digital-evidence"
CF = Path(os.environ.get("EVIDENCE_CASES") or DATA / "cases.json").expanduser()
CFG = json.loads(CF.read_text()) if CF.exists() else {
    "phone": {"model": "", "wifi": [], "folders": {"proofmode": "/sdcard/DCIM/ProofMode"}}, "cases": {}}
PH = CFG["phone"]
TZ = ZoneInfo(CFG.get("timezone", "UTC"))
REMOTE = CFG.get("rclone_remote", "")
WORM = str(Path(CFG["worm_script"]).expanduser()) if CFG.get("worm_script") else None
RECEIPTS = DATA / "receipts"


def sh(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode:
        sys.exit(f"FAILED {cmd}: {(r.stdout + r.stderr).strip()[-800:]}")
    return r.stdout


def device():
    def found():
        out = []
        for line in sh(["adb", "devices", "-l"]).splitlines()[1:]:
            if " device " in line and f"model:{PH['model']}" in line:
                out.append(line.split()[0])
        return out
    d = found()
    if not d:
        for a in PH["wifi"]:
            subprocess.run(["adb", "connect", a], capture_output=True, timeout=20)
        d = found()
    if not d:
        sys.exit("phone not reachable over USB or Wi-Fi: use skill adb-ops:wireless-adb")
    return d[0]  # several = the same phone on USB and Wi-Fi


def adb(dev, cmd):
    return sh(["adb", "-s", dev, "shell", cmd])


def newest(dev, folder):
    # ".pending-*" names are recordings still in progress: skipped by the glob, reported separately
    d = shlex.quote(PH["folders"][folder])
    pend = adb(dev, f"ls -a {d} | grep '^.pending' || true").split("\n")
    out = adb(dev, f"find {d} -maxdepth 1 -type f -name '[!.]*.mp4' -exec stat -c '%Y|%s|%n' {{}} +").strip()
    rows = sorted((l.split("|", 2) for l in out.splitlines()), key=lambda r: int(r[0]))
    if not rows:
        sys.exit(f"no finished .mp4 in {folder}; pending: {pend}")
    m, s, p = rows[-1]
    return {"path": p, "bytes": int(s), "saved": datetime.fromtimestamp(int(m), TZ).isoformat(),
            "in_progress": [x for x in pend if x]}


def hashes(p):
    a, b = hashlib.sha256(), hashlib.md5()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            a.update(c); b.update(c)
    return a.hexdigest(), b.hexdigest()


def dev_sha(dev, path):
    return adb(dev, f"sha256sum {shlex.quote(path)}").split()[0]


def drive_entry(folder_id, rel):
    o = json.loads(sh(["rclone", "lsjson", "--hash", "--stat", f"{REMOTE}:{rel}", "--drive-root-folder-id", folder_id]))
    return o


def worm_check(prefix, sha):
    """Re-download and hash everything under prefix; return header and rows; require sha among them."""
    if not WORM:
        return [""]
    t = tempfile.mktemp(suffix=".tsv")
    sh([WORM, "verify", prefix, "-o", t])
    lines = Path(t).read_text().splitlines()
    if not any(sha in l and "COMPLIANCE" in l for l in lines[1:]):
        sys.exit(f"WORM: {sha} not locked under {prefix}")
    return lines


def inspect(p):
    """Report what is embedded. Presence only: this does not validate signatures."""
    ex = subprocess.run(["exiftool", "-j", "-a", "-Claim_generator", "-JUMDLabel", str(p)], capture_output=True, text=True).stdout
    m = re.search(r'"Claim_generator": "([^"]+)"', ex)
    raw = Path(p).read_bytes()
    return {"c2pa_present": bool(m) or b"c2pa.claim" in raw, "claim_generator": m[1] if m else None,
            "rfc3161_tsa_marker": bool(re.search(rb"DigiCert[^\x00]{0,60}Timestamp", raw)), "validated": False}


def ingest(a):
    c = CFG["cases"][a.case]
    dev = device()
    path = a.path or newest(dev, a.folder)["path"]
    name = Path(path).name
    tmp = Path(tempfile.mkdtemp(prefix="noise-clip-"))
    loc = tmp / name
    sh(["adb", "-s", dev, "pull", "-a", path, str(loc)])
    sha, md5 = hashes(loc)
    if dev_sha(dev, path) != sha:
        sys.exit("phone and pulled copy differ (still recording?)")
    f = json.loads(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration:format_tags=creation_time", "-of", "json", str(loc)]))["format"]
    dur = float(f["duration"])
    end = datetime.fromisoformat(f["tags"]["creation_time"].replace("Z", "+00:00")).astimezone(TZ)
    start = end - timedelta(seconds=dur)  # MP4 creation_time is the END of recording on this phone
    day = start.strftime(c["day_format"])
    rel = f"{day}/{name}"
    sh(["rclone", "copyto", "--immutable", str(loc), f"{REMOTE}:{rel}", "--drive-root-folder-id", c["drive_folder_id"]])
    d = drive_entry(c["drive_folder_id"], rel)
    if d["Hashes"].get("sha256") != sha or d["Hashes"].get("md5") != md5:
        sys.exit(f"Drive hash mismatch: {d['Hashes']}")
    prefix = f"{c.get('worm_prefix', a.case)}/{day}"
    worm_out = sh([WORM, "put", prefix, str(loc)]).strip() if WORM else ""
    lines = worm_check(c.get("worm_prefix", "") if worm_out.startswith("SKIP") else prefix, sha)
    side = []
    for sp in a.sidecar:
        sl = tmp / Path(sp).name
        sh(["adb", "-s", dev, "pull", "-a", sp, str(sl)])
        ss = hashes(sl)[0]
        if dev_sha(dev, sp) != ss:
            sys.exit(f"sidecar differs from phone: {sp}")
        srel = f"{day}/{sl.name}"
        sh(["rclone", "copyto", "--immutable", str(sl), f"{REMOTE}:{srel}", "--drive-root-folder-id", c["drive_folder_id"]])
        if drive_entry(c["drive_folder_id"], srel)["Hashes"].get("sha256") != ss:
            sys.exit(f"sidecar Drive hash mismatch: {srel}")
        sw = sh([WORM, "put", prefix, str(sl)]).strip() if WORM else ""
        sl_lines = worm_check(c.get("worm_prefix", "") if sw.startswith("SKIP") else prefix, ss)
        lines += sl_lines[1:]
        side.append({"device_path": sp, "name": sl.name, "sha256": ss, "drive_rel": srel, "worm": sw})
    repo = Path(c.get("repo", ".")).expanduser()
    if WORM and c.get("worm_manifest"):
        mf = repo / c["worm_manifest"]
        old = mf.read_text().splitlines()
        rows = {l.split("\t")[0]: l for l in old[1:]}
        rows.update({l.split("\t")[0]: l for l in lines[1:]})
        mf.write_text("\n".join([old[0], *(rows[k] for k in sorted(rows))]) + "\n")
    if c.get("also"):
        x = c["also"]
        sh(["rclone", "copyto", "--immutable", str(loc), f"{REMOTE}:{x['dest']}/{start.strftime(x['name'])}{loc.suffix}",
            "--drive-root-folder-id", x["drive_folder_id"]])
    post = []
    for cmd in c.get("post", []):
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=repo)
        post.append({"cmd": cmd, "rc": r.returncode, "tail": (r.stdout + r.stderr)[-400:]})
    url = f"https://drive.google.com/file/d/{d['ID']}/view"
    rec = {"case": a.case, "device_path": path, "local": str(loc), "name": name, "bytes": loc.stat().st_size,
           "start": start.strftime("%Y-%m-%d %H:%M:%S"), "seconds": round(dur, 1), "sha256": sha, "md5": md5,
           "drive_rel": rel, "drive_url": url, "worm_prefix": prefix, "worm": worm_out, "sidecars": side, "post": post,
           "ingested": datetime.now(TZ).isoformat(timespec="seconds"), "sheet_id": c.get("sheet_id"), "proof": inspect(loc),
           "sheet_row": [start.strftime("%Y-%m-%d %H:%M:%S"), name, str(round(dur, 1)), f'=HYPERLINK("{url}","Play")',
                         "", "", "", sha, md5]}
    RECEIPTS.mkdir(parents=True, exist_ok=True)
    rf = RECEIPTS / f"{start:%Y%m%d_%H%M%S}_{a.case}.json"
    rf.write_text(json.dumps(rec, indent=1))
    print(json.dumps({"receipt": str(rf), **rec}, indent=1))
    if any(p["rc"] for p in post):
        sys.exit("a post step failed; do not delete from the phone yet")


def delete(a):
    r = json.loads(Path(a.receipt).read_text())
    c = CFG["cases"][r["case"]]
    if any(p["rc"] for p in r["post"]):
        sys.exit("receipt has a failed post step: re-run ingest first")
    if drive_entry(c["drive_folder_id"], r["drive_rel"])["Hashes"].get("sha256") != r["sha256"]:
        sys.exit("Drive copy no longer matches; not deleting")
    worm_check(c.get("worm_prefix", "") if r["worm"].startswith("SKIP") else r["worm_prefix"], r["sha256"])
    dev = device()
    if dev_sha(dev, r["device_path"]) != r["sha256"]:
        sys.exit("file on the phone is not the one ingested; not deleting")
    for x in r["sidecars"]:
        if drive_entry(c["drive_folder_id"], x["drive_rel"])["Hashes"].get("sha256") != x["sha256"]:
            sys.exit("sidecar on Drive no longer matches; not deleting")
        worm_check(c.get("worm_prefix", "") if x["worm"].startswith("SKIP") else r["worm_prefix"], x["sha256"])
        if dev_sha(dev, x["device_path"]) != x["sha256"]:
            sys.exit("sidecar on the phone is not the one ingested; not deleting")
    for x in r["sidecars"]:
        adb(dev, f"rm {shlex.quote(x['device_path'])}")
    adb(dev, f"rm {shlex.quote(r['device_path'])}")
    gone = subprocess.run(["adb", "-s", dev, "shell", f"ls {shlex.quote(r['device_path'])}"], capture_output=True).returncode != 0
    adb(dev, "content call --uri content://media --method scan_volume --arg external_primary >/dev/null 2>&1 || true")
    r.update(sheet_row_number=a.sheet_row, deleted_from_phone=datetime.now(TZ).isoformat(timespec="seconds") if gone else None)
    Path(a.receipt).write_text(json.dumps(r, indent=1))
    loc = Path(r["local"])
    if gone and loc.exists():
        for x in loc.parent.iterdir():
            x.unlink()
        loc.parent.rmdir()
    print(json.dumps({"deleted": gone, "path": r["device_path"]}))
    sys.exit(not gone)


ap = argparse.ArgumentParser(); s = ap.add_subparsers(dest="cmd", required=True)
p = s.add_parser("latest"); p.add_argument("--folder", default="proofmode", choices=PH["folders"])
p = s.add_parser("ingest"); p.add_argument("case", choices=CFG["cases"]); p.add_argument("--folder", default="proofmode", choices=PH["folders"]); p.add_argument("--path"); p.add_argument("--sidecar", action="append", default=[])
p = s.add_parser("inspect"); p.add_argument("file")
p = s.add_parser("delete"); p.add_argument("receipt"); p.add_argument("--sheet-row", type=int, required=True)
a = ap.parse_args()
if a.cmd == "inspect": print(json.dumps(inspect(a.file), indent=1))
elif a.cmd == "latest": print(json.dumps(newest(device(), a.folder), indent=1))
else: {"ingest": ingest, "delete": delete}[a.cmd](a)
