---
description: Anchor a file's hash to Bitcoin via OpenTimestamps (creates .ots proof) or verify an existing proof.
allowed-tools: Bash, Read, Glob
---

Run the `timestamp-evidence` skill on the path in $ARGUMENTS. Create the `.ots` proof, or verify if `--verify-only` is passed. Remind the user that fresh proofs need `ots upgrade` after the Bitcoin attestation lands (~hours).
