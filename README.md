# digital-evidence

General-purpose digital-evidence processing for Claude Code: capture, hash, OpenTimestamps anchoring, ExifTool/MediaInfo metadata inspection, BagIt packaging, and immutable sync to S3 Object Lock / Wasabi / WORM media.

Designed to **layer with** [`legal-investigative`](https://github.com/danielrosehill/Claude-Code-Plugins) — that plugin owns the case workspace, custody log, brief generation, and human-driven redaction; this plugin owns the operational and metadata-handling layer.

## Skills

- `environment-check` — probe host for forensics CLIs (exiftool, mediainfo, sha256sum, ots, single-file, bagit, mat2, rclone, aws)
- `install-dependencies` — install missing CLIs via apt / pip / npm
- `setup-storage-mounts` — configure rclone remotes for immutable destinations
- `onboard` — first-run setup orchestrator
- `capture-webpage` — archive a URL via SingleFile, then hash
- `capture-from-device` — pull new captures off an Android phone over ADB, rename to true capture time, hash, upload to a named target, run its post steps
- `proofmode-clip` — collect a ProofMode (C2PA-signed) or other latest phone clip: hash, Drive, optional WORM, sheet row, verified phone deletion
- `hash-evidence` — SHA-256 / BLAKE3 hashing with manifest output
- `timestamp-evidence` — OpenTimestamps Bitcoin anchoring
- `inspect-metadata` — ExifTool + MediaInfo to merged JSON, with anomaly flags
- `bag-evidence` — package a directory as a BagIt bag
- `verify-bundle` — re-hash + OTS verify across a case or bag
- `sync-to-immutable` — rclone push to S3 Object Lock / Wasabi / WORM media
- `reference-lookup` — search the vendored Digital-Evidence-Toolkit knowledge base

## Commands

- `/digital-evidence:onboard`
- `/digital-evidence:verify [path]`
- `/digital-evidence:hash <path>`
- `/digital-evidence:capture-device [target]`
- `/digital-evidence:timestamp <path>`
- `/digital-evidence:lookup <query>`

## Installation

```bash
claude plugins install digital-evidence@danielrosehill
```

Then run `/digital-evidence:onboard`.

## Layering with legal-investigative

Typical workflow:

1. `legal-investigative:new-workspace --variant=evidence-management` — scaffold the case.
2. `digital-evidence:capture-webpage` / `inspect-metadata` / `hash-evidence` — operational ingest.
3. `legal-investigative:/log-evidence` — register the artefact in the custody log.
4. `digital-evidence:timestamp-evidence` + `bag-evidence` — tamper-evident packaging.
5. `digital-evidence:sync-to-immutable` — push to compliance storage.

## Reference wiki

The `references/` directory is a vendored copy of [danielrosehill/Digital-Evidence-Toolkit](https://github.com/danielrosehill/Digital-Evidence-Toolkit) — used by `reference-lookup` as the agent's knowledge base.

## Disclaimer

This plugin is a workflow aid, not legal advice. Admissibility of digital evidence depends on jurisdiction, process discipline, and procedural compliance well beyond hashing and timestamping. Consult counsel.

## License

MIT
