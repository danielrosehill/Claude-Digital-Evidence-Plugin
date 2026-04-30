---
name: capture-webpage
description: Use when archiving a URL as a self-contained offline HTML file with hash verification.
model: haiku
---

# Capture Webpage

Archive a URL as a self-contained HTML file (via single-file), compute its hash, and report metadata.

## When to use

- Capturing evidence web pages, online documents, or screenshots for chain-of-custody
- Archiving public web content before it changes or is removed
- Creating offline, tamper-evident copies of online material

## Inputs to gather

- URL to capture (required)
- Destination directory (optional; defaults to current working directory)

## Procedure

1. Invoke `single-file <url> <dest_dir>/<sanitised-title>-<timestamp>.html` where:
   - `<sanitised-title>` is the page title with spaces and special chars removed (or a sanitised URL slug)
   - `<timestamp>` is ISO-8601 or Unix epoch (e.g., `2026-04-30T22-18-00Z`)
2. Wait for single-file to complete (may take 10–60 seconds depending on page complexity).
3. After success, compute `sha256sum <output.html>` and capture the hash.
4. Report to user: output file path, SHA-256 hash, file size in bytes, and final URL (after redirects, as captured by single-file's `--browser-args`).
5. Suggest piping the hash + path through `/legal-investigative log-evidence` for custody registration.

## Output / side effects

- `<dest_dir>/<sanitised-title>-<timestamp>.html` — self-contained webpage archive.
- User sees: output path, SHA-256 hash, byte size.
- No custody log entry written (suggest user chain through legal-investigative's `/log-evidence` for that).

## Safety / constraints

- single-file requires a browser (Chrome/Chromium) to be available; ensure it's installed.
- URLs with invalid characters or redirects may produce unexpected output filenames; show user the final path.
- Large, media-heavy pages may produce very large HTML files; warn if >100 MB.
