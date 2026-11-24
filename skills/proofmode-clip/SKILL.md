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

## Pipeline for a ProofMode zip (the standard route)

1. **Zip to WORM first:** into `<case>/zips/`. The user's sync app does it, or on request `<worm_script> put <case>/zips ZIP`.
   Check it is complete (no multipart upload still open), locked, and opens.
2. **Unzip into WORM:** download the locked zip **under its exact stored name** and run `scripts/unzip_proof.py CASE ZIP`. Videos go to
   `video/`, photos to `photos/`, audio to `audio/`, proofs to `proofs/<zip name>/`. Anything already locked is skipped by hash.
3. **Then copy to Google Drive:** same items and the zip. The script does this after WORM and checks each hash.
4. **Log it** (sheet, case repo), then delete the phone originals that match the locked copies.

A zip may hold one item or many: list its contents and say which phone files it does *not* cover.

## Standard case layout

Every case has the same folders, in the WORM bucket and on Drive. Keep the original zip **and** its extracted contents:

```
<case>/
  zips/                        original ProofMode zips, untouched (phone sync target)
  video/YYYY-MM-DD/            photos/YYYY-MM-DD/    audio/YYYY-MM-DD/    calls/YYYY-MM-DD/
  proofs/<zip name>/           proof files, pubkey.asc, certificate, HowToVerify from that zip
```

One zip can hold mixed media. Zip contents seen 2026-11-24: media at the top level; per item `<sha256>.proof.csv`,
`.proof.json`, their `.asc`, `<sha256>.asc`, `<sha256>.ots`; plus `*batchproof.csv`, `pubkey.asc`, `cr.cert`,
`HowToVerifyProofData.txt`. Extract into a new empty directory, sort by type, and match each media file's SHA-256
to its proof set; report any item without one. `scripts/unzip_proof.py CASE ZIP` does this: checks hashes, proof sets and PGP signatures, then Drive and WORM. Pass `--name` as the
exact stored zip name.

New case: create `<case>/zips/` as an empty object in the bucket (so a phone sync app can pick it), add the case block to
`cases.json`, then point the sync app at `<case>/zips` one-way, with folder objects disabled. Folder markers are locked too:
check the name first. Turn on delete-after-upload only after a first zip is confirmed stored and locked.

## Batch: everything in the ProofMode folder

`scripts/batch.py ingest CASE [--stage DIR]` pulls all finished videos and photos (and any `*proofmode*.zip` in Downloads or
Documents), compares each with the phone's own SHA-256, files them under `dirs` and locks them under `worm`:

```json
"proofmode": {"drive_folder_id": "<id>", "dirs": {"video": "ProofMode/Videos", "image": "ProofMode/Photos", "zip": "ProofMode/Zips"},
              "worm": {"video": "<case>/video", "image": "<case>/photos", "zip": "<case>/zips"}}
```

Make a contact sheet of the stills and look at it before ingest. `batch.py delete RECEIPT` re-hashes the stored copies, compares the
phone files again, and only then removes them. **Deleting the media without an exported bundle may make it impossible to
export the PGP/OpenTimestamps proof later**; the C2PA manifest inside each file survives. If `proof_zip` is false in the
ingest output, tell the user and get a yes first.

A phone app exposes no supported ADB or CLI export that we found (2026-11-24). On a computer, the Rust
[`proofmode`](https://lib.rs/crates/proofmode) crate lists `check`, `generate` and `sign` commands (not tried here), and `gpg --verify` works
on bundle signatures.

To keep the app alive in the background (tested on Android 16):
`dumpsys deviceidle whitelist +org.witness.proofmode`, `am set-standby-bucket org.witness.proofmode active`,
`cmd appops set org.witness.proofmode RUN_ANY_IN_BACKGROUND allow`. Location must be on phone-wide for GPS in the proof.

## Local audio

`scripts/audio_files.py CASE DATE FILE...` uploads WAVs with their seal files (Drive, then WORM). Needs an `audio` block in the case:
`{"drive_folder_id", "dir", "worm"}`. Use `--dry-run` first.

## Reading the proof

`clip.py inspect FILE` reports whether a C2PA manifest and a timestamp-authority marker are *present*. It does
not validate them; use `c2patool FILE` or https://proofmode.org/verify for that. Observed 2026-11-24, ProofMode 2.6.0-RC-2 on
Android 16: the manifest is embedded in the MP4, with the claim time, a per-user certificate under a
`ProofMode-Root`, and a DigiCert RFC 3161 timestamp chain. A certificate under the app's own root may show as
untrusted in generic C2PA viewers. Any re-encode (YouTube, WhatsApp) loses the proof: share the original.

It shows the file is unaltered since signing and when it was signed. It does not prove what was making the noise,
nor calibrated loudness. This is not legal advice.
