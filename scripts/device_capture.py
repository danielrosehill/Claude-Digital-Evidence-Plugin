#!/usr/bin/env python3
"""Pull new evidence files off an Android device over ADB and deliver them to a target.

Pipeline per run:  list on device -> filter (new, type, date) -> adb pull to a fresh
staging dir -> rename to capture time from metadata -> SHA-256 -> upload (rclone)
-> run the target's post commands -> record what was delivered.

Targets live in the user's data dir, never in this plugin:
  ${CLAUDE_USER_DATA:-${XDG_DATA_HOME:-~/.local/share}/claude-plugins}/digital-evidence/targets.json
State (what each target has already received) sits next to it in state/<target>.json.

Usage:
  device_capture.py list
  device_capture.py run <target> [--date YYYY-MM-DD] [--types video,image,audio]
                                 [--serial HOST:PORT] [--dry-run] [--no-upload]
Prints a JSON report to stdout. Needs adb, exiftool, rclone (for upload).
"""
import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

DATA = Path(os.environ.get("CLAUDE_USER_DATA")
            or Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "claude-plugins"
            ) / "digital-evidence"
TYPES = {
    "image": {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".dng"},
    "video": {".mp4", ".mov", ".m4v", ".3gp", ".mkv", ".webm"},
    "audio": {".m4a", ".mp3", ".wav", ".ogg", ".opus", ".aac", ".amr"},
}


def log(*a):
    print(*a, file=sys.stderr)


def sh(cmd: list[str], **kw) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode:
        raise RuntimeError(f"{' '.join(cmd)}: {r.stderr.strip()[-400:]}")
    return r.stdout


# ---------------------------------------------------------------- device
def pick_device(serial: str | None, wifi: list[str]) -> str:
    def attached():
        out = sh(["adb", "devices"])
        return [l.split()[0] for l in out.splitlines()[1:] if l.strip().endswith("device")]
    devs = attached()
    if serial:
        if serial not in devs and ":" in serial:
            sh(["adb", "connect", serial], timeout=15)
            devs = attached()
        if serial not in devs:
            raise RuntimeError(f"device {serial} not attached")
        return serial
    if not devs:
        for addr in wifi:  # known Wi-Fi addresses from the target, tried in order
            try:
                if "connected" in sh(["adb", "connect", addr], timeout=15):
                    devs = attached()
                    break
            except Exception as e:  # noqa: BLE001
                log(f"adb connect {addr} failed: {e}")
    if len(devs) != 1:
        raise RuntimeError(f"need exactly one device, have {devs or 'none'}; pass --serial")
    return devs[0]


def list_remote(serial: str, folder: str) -> list[dict]:
    # toybox stat: size, mtime epoch, path
    q = shlex.quote(folder.rstrip("/"))
    out = sh(["adb", "-s", serial, "shell",
              f"find {q} -maxdepth 1 -type f -exec stat -c '%s|%Y|%n' {{}} +"])
    files = []
    for line in out.splitlines():
        parts = line.strip().split("|", 2)
        if len(parts) == 3:
            files.append({"size": int(parts[0]), "mtime": int(parts[1]), "path": parts[2]})
    return files


# ---------------------------------------------------------------- metadata
def capture_times(paths: list[Path]) -> dict[str, tuple[datetime | None, str]]:
    """Capture START time per file, local wall-clock, plus the method used."""
    if not paths:
        return {}
    meta = json.loads(sh(["exiftool", "-j", "-n", "-api", "QuickTimeUTC",
                          "-DateTimeOriginal", "-CreateDate", "-Duration",
                          *map(str, paths)]))
    res = {}
    for m in meta:
        p = m["SourceFile"]
        t, how = None, "none"
        if m.get("DateTimeOriginal"):
            t, how = datetime.strptime(str(m["DateTimeOriginal"])[:19], "%Y:%m:%d %H:%M:%S"), "exif:DateTimeOriginal"
        elif m.get("CreateDate") and not str(m["CreateDate"]).startswith("0000"):
            # Android QuickTime CreateDate marks when recording STOPPED.
            end = datetime.strptime(str(m["CreateDate"])[:19], "%Y:%m:%d %H:%M:%S")
            dur = float(m.get("Duration") or 0)
            t, how = end - timedelta(seconds=round(dur)), "quicktime:CreateDate-Duration" if dur else "quicktime:CreateDate"
        res[p] = (t, how)
    return res


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- run
def load_targets() -> dict:
    f = DATA / "targets.json"
    if not f.exists():
        raise RuntimeError(f"no targets file at {f}; see skills/capture-from-device/SKILL.md")
    return json.loads(f.read_text())


def run(args) -> dict:
    tgt = load_targets()[args.target]
    state_f = DATA / "state" / f"{args.target}.json"
    state = json.loads(state_f.read_text()) if state_f.exists() else {"delivered": {}}
    types = set((args.types or ",".join(tgt.get("types", TYPES))).split(","))
    exts = set().union(*(TYPES[t] for t in types))

    serial = pick_device(args.serial, tgt.get("device", {}).get("wifi", []))
    wanted = []
    for folder in tgt["device"]["folders"]:
        for f in list_remote(serial, folder):
            ext = Path(f["path"]).suffix.lower()
            day = datetime.fromtimestamp(f["mtime"]).strftime("%Y-%m-%d")
            if ext not in exts:
                continue
            if args.date and day != args.date:
                continue
            if not args.date and tgt.get("since") and day < tgt["since"]:
                continue
            if f["path"] in state["delivered"]:
                continue
            wanted.append(f)

    report = {"target": args.target, "device": serial, "types": sorted(types),
              "date": args.date, "found": len(wanted), "files": [], "dry_run": args.dry_run}
    if not wanted:
        return report

    stage = Path(tempfile.mkdtemp(prefix=f"evidence-{args.target}-"))
    report["staging"] = str(stage)
    if args.dry_run:
        report["files"] = [{"device_path": f["path"], "size": f["size"]} for f in wanted]
        return report

    for f in wanted:
        sh(["adb", "-s", serial, "pull", "-a", f["path"], str(stage / Path(f["path"]).name)])

    local = [stage / Path(f["path"]).name for f in wanted]
    times = capture_times(local)
    fmt = tgt.get("rename", "%Y-%m-%d %H.%M.%S_")
    taken: set[str] = set()
    for f, p in zip(wanted, local):
        t, how = times.get(str(p), (None, "none"))
        new = p.name
        if t and fmt:
            base, ext, n = t.strftime(fmt), p.suffix.lower(), 1
            new = f"{base}{ext}"
            while new in taken:
                n += 1
                new = f"{base}{n}{ext}"
            p.rename(stage / new)
        taken.add(new)
        report["files"].append({
            "device_path": f["path"], "name": new, "size": f["size"],
            "captured": t.isoformat() if t else None, "time_source": how,
            "sha256": sha256(stage / new)})

    (stage / "custody.json").write_text(json.dumps(
        {"pulled_at": datetime.now().astimezone().isoformat(timespec="seconds"),
         "device": serial, "files": report["files"]}, indent=1))

    if not args.no_upload and tgt.get("upload"):
        up = tgt["upload"]
        cmd = ["rclone", "copy", str(stage), up["dest"], "--exclude", "custody.json", *up.get("flags", [])]
        sh(cmd, timeout=3600)
        listing = set(sh(["rclone", "lsf", up["dest"], *up.get("flags", [])]).splitlines())
        missing = [x["name"] for x in report["files"] if x["name"] not in listing]
        if missing:
            raise RuntimeError(f"upload incomplete, not at destination: {missing}")
        report["uploaded_to"] = up["dest"]
        for x in report["files"]:
            state["delivered"][x["device_path"]] = {"name": x["name"], "sha256": x["sha256"]}
        state_f.parent.mkdir(parents=True, exist_ok=True)
        state_f.write_text(json.dumps(state, indent=1))
        post = []
        for c in tgt.get("post", []):
            r = subprocess.run(c, shell=True, capture_output=True, text=True, cwd=tgt.get("cwd"))
            post.append({"cmd": c, "rc": r.returncode, "tail": (r.stdout + r.stderr)[-1500:]})
        report["post"] = post
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    r = sub.add_parser("run")
    r.add_argument("target")
    r.add_argument("--date")
    r.add_argument("--types")
    r.add_argument("--serial")
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--no-upload", action="store_true")
    a = ap.parse_args()
    try:
        if a.cmd == "list":
            out = {k: {"description": v.get("description"), "folders": v["device"]["folders"],
                       "dest": v.get("upload", {}).get("dest")} for k, v in load_targets().items()}
        else:
            out = run(a)
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"error": str(e)}))
        return 1
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
