---
name: capture-from-device
description: Pull new photos, videos or audio off a connected Android phone over ADB (USB or Wi-Fi) into a named evidence target - renamed to true capture time, SHA-256 hashed, custody record written, uploaded to the target's destination and post-processed. Use on "pull the new videos off my phone", "get today's recordings from Timemark", "sync the phone captures to <case>", "keep <case> folder updated from the phone".
---

# Capture from device

Moves evidence from a phone to where a case keeps it, in one repeatable run, without
re-sending what the target already has. All the work is `scripts/device_capture.py`;
this skill picks the target and the filters, and checks the result.

## Targets (user data, not in this plugin)

`${CLAUDE_USER_DATA:-${XDG_DATA_HOME:-~/.local/share}/claude-plugins}/digital-evidence/targets.json`:

```json
{
 "<target>": {
  "description": "what this case is",
  "device": {"folders": ["/sdcard/DCIM/<App>"], "wifi": ["<phone-ip>:5555"]},
  "types": ["video", "image"],
  "since": "YYYY-MM-DD",
  "rename": "%Y-%m-%d %H.%M.%S_",
  "upload": {"dest": "<rclone-remote>:<path>", "flags": ["..."]},
  "cwd": "<dir the post commands run in>",
  "post": ["<command run after a successful upload>"]
 }
}
```

`state/<target>.json` beside it records every device path already delivered (with
name and SHA-256); a delivered file is never offered again. No target yet: ask the
user for the device folder, destination and any post step, write it, then dry-run.

## Run

```bash
P=${CLAUDE_PLUGIN_ROOT}/scripts/device_capture.py
python3 $P list                                   # targets
python3 $P run <target> --dry-run                 # what is new
python3 $P run <target> [--date YYYY-MM-DD] [--types video] [--serial IP:PORT]
```

1. **Dry-run first, always**, and show the user the count per type and day. Pass
   only what they asked for: "just the videos" is `--types video`, "today's" is
   `--date <today>`. A photo burst of hundreds is easy to sweep up unasked.
2. Run for real. Output is JSON: per file `device_path`, `name`, `captured`,
   `time_source`, `sha256`; plus `uploaded_to` and each `post` command's exit code
   and tail.
3. Check `post[].rc` is 0 and relay what the post step printed (e.g. coverage gaps).
   The script already verifies every renamed file is listed at the destination
   before it records state; an `error` key means nothing was recorded as delivered.

## Behaviour worth knowing

- **Device:** uses the one attached device; if none, tries the target's `wifi`
  addresses with `adb connect`. Wireless debugging must be on. If the phone's
  pairing port changed, `avahi-browse -rtp _adb-tls-connect._tcp` shows it
  (adb's own `mdns services` often lists nothing).
- **Capture time comes from metadata, not the filename or mtime.** Photos: EXIF
  `DateTimeOriginal`. Videos: QuickTime `CreateDate` **minus `Duration`**, because
  Android writes `CreateDate` when recording *stops* (verified 2026-11-23 on a
  an Android phone running Timemark: a 55 s clip named `..._1617` had CreateDate 16:18:23,
  true start 16:17:28). `time_source` says which was used; a file with neither
  keeps its phone name.
- Same-second collisions get `2`, `3`, ... appended to the base name.
- `rename: null` keeps phone names.
- Staging is a fresh `/tmp/evidence-<target>-*` dir holding the pulled files and
  `custody.json` (pull time, device serial, per-file hash and original path). It is
  not uploaded; hand it to `hash-evidence` / `timestamp-evidence` /
  `legal-investigative:log-evidence` if the case needs a formal custody chain, then
  delete it.
- Needs `adb`, `exiftool`, `rclone` (see `environment-check`).
