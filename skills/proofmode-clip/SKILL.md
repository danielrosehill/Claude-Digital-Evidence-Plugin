---
name: proofmode-clip
description: Collect a ProofMode (signed, timestamped) video or any other latest phone clip over ADB as evidence - hash it on phone and host, file it on Drive, optionally lock it in a WORM bucket, log it, then delete it from the phone only after re-verification. Use on "I took a ProofMode video", "pull my ProofMode recording", "I just recorded evidence on my phone".
---

# ProofMode clip

[ProofMode](https://proofmode.org) is the preferred capture app when evidence may be challenged: it signs
at capture. Overlay apps (Timemark and similar) only burn a time into the picture.

`scripts/clip.py` does one clip per run. Cases are user data, in `<user data>/digital-evidence/cases.json`
(or `$EVIDENCE_CASES`):

```json
{"timezone": "Area/City", "rclone_remote": "<remote>", "worm_script": "<optional; supports put PREFIX FILE / verify PREFIX -o TSV>",
 "phone": {"model": "<adb model>", "wifi": ["<ip>:5555"], "folders": {"proofmode": "/sdcard/DCIM/ProofMode"}},
 "cases": {"<case>": {"repo": "<dir>", "drive_folder_id": "<id>", "day_format": "%Y-%m-%d", "worm_prefix": "<case>/video",
   "worm_manifest": "<tsv with header, in repo>", "sheet_id": "<id>", "post": ["<command run in repo>"]}}}
```

## Steps

1. `clip.py latest`: newest finished MP4. A `.pending-*` name means it is still recording or being saved: wait.
2. **Proof bundle.** Ask the user to open the clip in ProofMode, *Share Proof*, and save the zip to Downloads.
   The app's proof files are in private storage that ADB cannot read (`run-as` refused), so this needs the user.
   Find the zip: `adb shell find /sdcard/Download -name '*.zip' -mmin -30`.
3. `clip.py ingest CASE [--path P] --sidecar /sdcard/Download/<proof>.zip`. Never re-encode, trim or rename.
   With a WORM store, check a still first: a locked upload cannot be undone.
4. Append the printed `sheet_row` to the case spreadsheet with your Sheets tool, read it back, note the row number.
5. `clip.py delete RECEIPT --sheet-row N`: re-checks Drive, WORM and phone hashes, then removes that clip and its
   sidecars. Do not delete a ProofMode clip before its bundle is exported unless the user says so.

## Reading the proof

`clip.py inspect FILE` reports whether a C2PA manifest and a timestamp-authority marker are *present*. It does
not validate them; use `c2patool FILE` or https://proofmode.org/verify for that. Observed 2026-11-24, ProofMode 2.6.0-RC-2 on
Android 16: the manifest is embedded in the MP4, with the claim time, a per-user certificate under a
`ProofMode-Root`, and a DigiCert RFC 3161 timestamp chain. A certificate under the app's own root may show as
untrusted in generic C2PA viewers. Any re-encode (YouTube, WhatsApp) loses the proof: share the original.

It shows the file is unaltered since signing and when it was signed. It does not prove what was making the noise,
nor calibrated loudness. This is not legal advice.
