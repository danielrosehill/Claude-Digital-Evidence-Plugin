---
name: sync-to-immutable
description: Use when uploading evidence to immutable storage (S3 Object Lock, Wasabi) with integrity verification.
---

# Sync to Immutable

Push evidence files to immutable remote storage via rclone with Object Lock protection and integrity checks.

## When to use

- Archiving evidence to immutable cold storage for long-term retention
- Creating tamper-evident copies on remote infrastructure
- Backing up bagged evidence to off-site Object Lock buckets
- Compliance with chain-of-custody requirements for remote archival

## Inputs to gather

- Source path (file or directory) (required)
- Remote alias from `state/remotes.json` (required; e.g., "s3-objectlock-primary")
- Optional retention days (default: use remote's configured retention policy)

## Procedure

1. Read `state/remotes.json` to validate the remote alias exists and retrieve bucket/prefix.
2. Construct rclone command: `rclone copy --immutable --check-first <src> <alias>:<bucket>/<prefix>/`
3. If remote is S3 Object Lock capable, append: `--s3-object-lock-mode COMPLIANCE --s3-object-lock-retain-until-date <date>` where `<date>` is current date plus retention days.
4. Execute copy operation and monitor progress (byte count, file count, speed).
5. After copy completes, run `rclone check <alias>:<bucket>/<prefix>/ <src>` to verify remote hashes match local files.
6. Report to user: object count uploaded, total bytes, copy duration, check result (MATCH or DIVERGENCE), and confirmation that Object Lock has taken effect (for S3).

## Output / side effects

- Evidence synced to remote immutable storage.
- Object Lock policy enforced on remote (if applicable).
- User sees copy progress, byte/file counts, and verification result.
- No local files modified.

## Safety / constraints

- Require confirmation before uploading (evidence is leaving local control).
- For S3 Object Lock, ensure bucket was created with Object Lock enabled and Compliance mode is intended (it is irreversible).
- Immutability takes effect on the remote; local originals can still be modified (maintain local custody chain separately via legal-investigative logs).
- Very large evidence sets (TB+) may take hours; suggest running in a background process or screen session.
