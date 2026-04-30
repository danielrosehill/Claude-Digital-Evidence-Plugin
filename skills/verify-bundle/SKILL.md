---
name: verify-bundle
description: Use when re-hashing evidence and verifying against recorded hashes and OpenTimestamps proofs.
model: haiku
---

# Verify Bundle

Re-hash files and compare against recorded hashes, validate BagIt manifests, and verify OpenTimestamps proofs.

## When to use

- Confirming evidence integrity after transfer or archival
- Detecting accidental or malicious file modifications
- Auditing chain-of-custody milestones before handoff
- Validating OpenTimestamps anchors for immutability proof

## Inputs to gather

- Path to evidence directory, BagIt bag, or individual file (required)

## Procedure

1. If input is a BagIt bag (contains `bagit.txt`): run `bagit.py --validate <dir>`.
2. If input is a directory with a `.sha256` manifest: re-run `find <dir> -type f -exec sha256sum {} \;`, compare output against manifest entries using `diff`.
3. For any `.ots` files found in or near the evidence: run `ots verify <file>` on each.
4. Aggregate results into a single PASS/FAIL report:
   - All files match recorded hashes: PASS
   - Any divergence: FAIL with per-file diff detail
   - All OpenTimestamps proofs valid: noted
   - Any OTS verify failure: FAIL with reason
5. Report to user: overall status, per-file divergence (if any), OTS proof validity, and recommendation (re-bag if needed, or escalate if tampering suspected).

## Output / side effects

- Verification results printed to stdout (no files modified).
- User sees: PASS/FAIL status, detailed divergence if any, OTS validity.
- Read-only on all input files.

## Safety / constraints

- This is a forensic read-only operation; it does not modify evidence.
- Verification failure does not imply intentional tampering; check for accidental overwrites, encoding changes (e.g., video transcoding), or filesystem timestamp updates.
- For large evidence sets, verification may take several minutes; inform user.
- OpenTimestamps verification requires the `.ots` files to be present alongside originals.
