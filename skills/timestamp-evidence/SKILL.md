---
name: timestamp-evidence
description: Use when anchoring a file hash to Bitcoin via OpenTimestamps for immutable proof-of-existence.
model: haiku
---

# Timestamp Evidence

Create or verify OpenTimestamps proofs for files, anchoring their hash to Bitcoin's immutable ledger.

## When to use

- Establishing cryptographic proof-of-existence for evidence at a specific time
- Creating tamper-evident timestamps for chain-of-custody milestones
- Verifying existing OpenTimestamps proofs
- Long-term archival requiring immutable time anchors

## Inputs to gather

- File path (required)
- `--verify-only` flag (optional; verify existing `.ots` proof instead of creating new one)

## Procedure

1. If `--verify-only` not given: run `ots stamp <file>` to create `<file>.ots` proof file.
2. If `--verify-only` given: run `ots verify <file>` (which checks the existing `<file>.ots` against the file's current hash and local timestamp cache).
3. After stamping, inform user that OTS proofs are initially "pending" (the calendar server has accepted the hash but Bitcoin confirmation is not yet complete, typically 1–4 hours).
4. Advise user to re-run `ots upgrade <file>.ots` later (after several hours/days) to fold in Bitcoin attestations once blocks are confirmed.
5. Report to user: `.ots` file path, current verification state (pending, valid, or failure reason), and a pointer to the OpenTimestamps documentation for understanding the proof.

## Output / side effects

- `<file>.ots` created (stamping) or verified (verify-only).
- User sees verification status and guidance on next steps (upgrade for Bitcoin anchor).

## Safety / constraints

- Stamping requires internet connectivity to contact OpenTimestamps calendar servers.
- Pending proofs do not yet have Bitcoin confirmation; upgrade later for immutable anchor.
- The `.ots` proof file must be kept alongside the original file for verification to work.
- Altering the original file will cause verification to fail; this is by design.
