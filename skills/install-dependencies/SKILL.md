---
name: install-dependencies
description: Use when environment-check reports missing tools and you need to install them.
---

# Install Dependencies

Install missing forensics CLIs based on environment-check results, grouped by package manager.

## When to use

- After `environment-check` reports gaps
- During initial setup (called by `onboard`)
- After host environment changes (new Python, node, system packages)

## Inputs to gather

- Optional: path to `state/env.json` (defaults to plugin's standard location)
- Confirmation per package-manager group before proceeding

## Procedure

1. Read `state/env.json` (or run `environment-check` if absent).
2. Identify missing tools and group by installer:
   - **apt**: exiftool, mediainfo, mat2, rclone, awscli
   - **pip**: opentimestamps-client, bagit
   - **npm**: single-file-cli
   - **cargo** (optional, if b3sum not in apt): b3sum
   - **brew** (macOS only, if applicable)
3. For each group, present the install command and request user confirmation.
4. Run **apt** groups with `sudo apt-get update && sudo apt-get install -y <pkg> …`
5. Run **pip** groups as user (or with `python3 -m pip install …`)
6. Run **npm** groups as user (prefer `npm install -g …` or `npx`)
7. Run **cargo** / **brew** as per platform defaults.
8. After all installs, re-run `environment-check` and diff the new `state/env.json` against the old.
9. Report summary: newly available tools, any still-missing, and next-step guidance.

## Output / side effects

- System packages installed (apt: system-wide; pip/npm: user or global scope as appropriate).
- `state/env.json` updated with new tool availability.
- User sees a diff of before/after tool status.

## Safety / constraints

- Require explicit user confirmation before running `sudo apt-get`.
- Do not attempt to install if a tool already exists (skip silently).
- mat2 may require `apt install mat2` plus `python3 -m pip install …` for extras; check package notes.
- If installation fails, report the error and do not mask it; suggest manual troubleshooting.
