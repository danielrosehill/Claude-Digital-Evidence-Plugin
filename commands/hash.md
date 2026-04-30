---
description: SHA-256 (and optional BLAKE3) hash a file or directory; emit a manifest.
allowed-tools: Bash, Read, Glob
---

Run the `hash-evidence` skill against the path in $ARGUMENTS. If a directory, produce a `.sha256` manifest. Report hashes and manifest path. Custody logging is handled separately by `legal-investigative:/log-evidence`.
