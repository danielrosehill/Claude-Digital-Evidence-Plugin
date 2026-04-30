---
name: environment-check
description: Use when assessing whether forensics CLI tools are installed and available.
model: haiku
---

# Environment Check

Probe the host for forensics CLIs required by the digital-evidence plugin and report availability status.

## When to use

- First run of the plugin (called by `onboard`)
- After installing packages (to verify success)
- Troubleshooting missing tools before attempting evidence processing

## Inputs to gather

- None required (non-interactive probe)

## Procedure

1. For each tool — `exiftool`, `mediainfo`, `sha256sum`, `b3sum`, `ots` (opentimestamps-client), `single-file`, `bagit`, `mat2`, `rclone`, `aws` — run `which <tool>` and `<tool> --version` (or equivalent).
2. Capture: tool name, present (bool), version string, full path.
3. Write a JSON snapshot to `${CLAUDE_USER_DATA:-${XDG_DATA_HOME:-$HOME/.local/share}/claude-plugins}/digital-evidence/state/env.json` with one object per tool.
4. Parse results and generate a summary table, grouped by present/missing.
5. Print to user: tool name, version, path (if present) or "not found" (if absent).

## Output / side effects

- `state/env.json` — written with tool inventory snapshot.
- User sees a formatted table (present tools grouped above missing tools).
- No installations performed.

## Safety / constraints

- Run as unprivileged user (no sudo).
- If a tool's `--version` flag fails, try `--help` or note as "version unavailable."
