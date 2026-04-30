---
name: bag-evidence
description: Use when packaging evidence into a BagIt-compliant archival container.
---

# Bag Evidence

Package a directory as a BagIt bag for standardized archival transfer and integrity tracking.

## When to use

- Preparing evidence for transfer between systems or custody handoff
- Creating standardized containers for long-term archival
- Bundling evidence with machine-readable manifests and metadata

## Inputs to gather

- Directory path to bag (required)
- Optional confirmation before bagging (operation is in-place; adds manifest files to the directory)

## Procedure

1. Run `bagit.py --processes 4 --sha256 <dir>` to create BagIt structure in-place:
   - Adds `bagit.txt` (BagIt version declaration)
   - Adds `bag-info.txt` (metadata: Bagging-Date, Bag-Size, etc.)
   - Generates `manifest-sha256.txt` (hash entries for all payload files)
   - Optionally adds `tagmanifest-sha256.txt` (hashes of bag metadata files)
2. After bagging completes, run `bagit.py --validate <dir>` to verify bag integrity.
3. Report to user: bag root path, manifest entry count, total payload size, validation status.
4. Recommend further hardening: run `/timestamp-evidence` on `bag-info.txt` and `manifest-sha256.txt` for tamper-evident archival (OpenTimestamps proof).

## Output / side effects

- BagIt structure added to input directory in-place (not moved).
- Files `bagit.txt`, `bag-info.txt`, `manifest-sha256.txt` created.
- User sees validation result and next-step guidance.

## Safety / constraints

- Operation is in-place; original files are not moved or copied, only metadata added.
- After bagging, do not manually modify payload files without updating manifests (use `bagit.py` to re-validate).
- For evidence custody, ensure bag-info.txt documents the bagging event (who, when, why); add entries via `--bag-info` if available.
- Large directories may take several minutes to process; inform user.
