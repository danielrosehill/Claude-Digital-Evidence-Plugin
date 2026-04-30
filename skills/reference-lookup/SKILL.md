---
name: reference-lookup
description: Use when searching vendored Digital-Evidence-Toolkit guidance for tool recommendations and legal-procedural context.
model: haiku
---

# Reference Lookup

Search the vendored Digital-Evidence-Toolkit references and surface relevant guidance.

## When to use

- Deciding which redaction/anonymization tool to use for a media type
- Understanding legal-procedural context (subpoenas, chain-of-custody, jurisdictional rules)
- Learning storage and archival best practices
- Troubleshooting forensics workflows

## Inputs to gather

- Free-text query (e.g., "redact video", "S3 Object Lock compliance", "GPS metadata removal")

## Procedure

1. Search the `references/` directory recursively using `grep -rli <query>` (case-insensitive) to find matching files.
2. For each match, extract relevant context lines using `grep -n <query> <file>` and capture 5–10 lines of surrounding context.
3. Rank results by relevance (number of matches per file, proximity to query terms).
4. Return top 3 matching files to user with:
   - File name (without path)
   - Excerpt (5–10 lines) containing the query match and context
   - Brief summary of what the file covers
5. If `rg` (ripgrep) is available, use it instead of `grep` for faster search and richer context.

## Output / side effects

- User sees ranked list of relevant references with excerpts.
- No files modified.

## Safety / constraints

- Search is read-only on the vendored references.
- Excerpts are informational; user should read full references for complete guidance.
- If no matches found, suggest broadening the query or browsing available reference files manually.
