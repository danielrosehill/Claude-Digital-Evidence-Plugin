---
name: setup-storage-mounts
description: Use when configuring immutable storage destinations (S3, Wasabi, etc.) for evidence archival.
---

# Setup Storage Mounts

Configure rclone remotes and validate connectivity for immutable evidence destinations.

## When to use

- Initial plugin setup (called by `onboard`)
- Adding a new immutable storage endpoint
- Validating existing remote configurations

## Inputs to gather

- User runs `rclone config` interactively to add a remote and provides credentials
- Remote alias name (e.g., "s3-objectlock-primary", "wasabi-cold")
- Remote purpose / human-readable description
- For S3 Object Lock: confirmation that the bucket has Object Lock enabled at creation, and preferred retention mode (Compliance recommended for evidence)

## Procedure

1. Instruct user to run `rclone config` interactively (in a separate terminal) to create or edit a remote. Wait for completion.
2. Prompt for the remote alias name and its intended purpose.
3. Run `rclone lsd <remote>:` to validate remote connectivity and list buckets.
4. Create a small test file (e.g., 1 KB), run `rclone copy <test_file> <remote>:<test_bucket>/<test_prefix>/`, then `rclone check <remote>:<test_bucket>/<test_prefix>/ …` to verify round-trip integrity.
5. If using S3 Object Lock: remind user that the bucket must have Object Lock enabled at creation time, and recommend Compliance mode with a 10–30 year retention period for forensic evidence.
6. Persist the remote alias and purpose to `${CLAUDE_USER_DATA:-${XDG_DATA_HOME:-$HOME/.local/share}/claude-plugins}/digital-evidence/state/remotes.json` as a list of objects: `{alias, purpose, remote_type, bucket, prefix}`.
7. Report success with a summary of configured remotes.

## Output / side effects

- `state/remotes.json` created or updated with remote registry.
- Test file uploaded and verified (then cleaned up if desired).
- User sees validation results and readiness confirmation.

## Safety / constraints

- Do not store credentials directly in `remotes.json`; rclone manages them in `~/.config/rclone/rclone.conf`.
- For Object Lock buckets, emphasize that Compliance mode is irreversible and should align with retention policy.
- Validate read+write permissions before marking a remote as active.
