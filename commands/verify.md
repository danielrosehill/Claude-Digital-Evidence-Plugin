---
description: Re-hash a file/dir/BagIt bag and verify against recorded hashes and OpenTimestamps proofs.
allowed-tools: Bash, Read, Glob, Grep
---

Run the `verify-bundle` skill against the path provided in $ARGUMENTS (defaults to current working directory). Report PASS/FAIL with per-file divergence detail.
