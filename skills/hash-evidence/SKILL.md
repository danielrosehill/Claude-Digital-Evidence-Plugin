---
name: hash-evidence
description: Use when computing cryptographic hashes (SHA-256, BLAKE3) for files or directories.
model: haiku
---

# Hash Evidence

Compute SHA-256 (and optionally BLAKE3) hashes for files or directories to establish baseline integrity.

## When to use

- Initial evidence ingest and baselining
- Generating hash manifests for multiple files
- Verifying file integrity as part of chain-of-custody
- Computing alternative hash algorithms (BLAKE3) for additional assurance

## Inputs to gather

- Path to file or directory (required)
- `--blake3` flag (optional; compute BLAKE3 in addition to SHA-256)
- `--out <manifest-path>` (optional; write manifest to custom location; defaults to `<path>.sha256` or `<path>.blake3`)

## Procedure

1. If input is a file: run `sha256sum <path>` and capture output.
2. If input is a directory: run `find <path> -type f -exec sha256sum {} \;` and write results to manifest file `<path>.sha256`.
3. If `--blake3` given: also run `b3sum <path>` (for file) or `find <path> -type f -exec b3sum {} \;` (for dir), append to manifest or write to `<path>.blake3`.
4. If `--out` given: write manifest to specified path instead of default location.
5. Report to user: hash(es), manifest file path (if dir), entry count (if dir), total size.

## Output / side effects

- For files: hash(es) printed to stdout.
- For directories: manifest file(s) written (`<dir>.sha256`, `<dir>.blake3`, or custom `--out` paths).
- User sees hash digest(s) and manifest location.
- No custody log entry written; chain through `/legal-investigative log-evidence` for registration.

## Safety / constraints

- This skill produces hashes only; it does not verify them. Use `verify-bundle` for that.
- For very large directories, manifest generation may take several minutes; inform user.
- Hashes alone do not establish custody; pair with legal-investigative's `/log-evidence` for chain-of-custody.
