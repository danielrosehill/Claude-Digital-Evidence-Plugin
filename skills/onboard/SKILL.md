---
name: onboard
description: Use when setting up the digital-evidence plugin for the first time.
---

# Onboard

First-run orchestrator to establish plugin state, verify dependencies, and configure defaults.

## When to use

- User's first interaction with the plugin (no `config.json` exists)
- Resetting plugin configuration

## Inputs to gather

- Confirmation to proceed with setup
- Optional: confirm whether to install missing dependencies
- Optional: configure immutable storage destinations
- Default case root directory (suggest `~/cases/` or the user's legal-investigative workspace parent)

## Procedure

1. Check if `${CLAUDE_USER_DATA:-${XDG_DATA_HOME:-$HOME/.local/share}/claude-plugins}/digital-evidence/config.json` exists. If yes, ask user whether to reconfigure or exit.
2. Run `environment-check` to probe for forensics CLIs.
3. Present results and offer to run `install-dependencies` if gaps exist. Await user confirmation.
4. Ask whether to set up immutable storage remotes now (optional — can defer). If yes, run `setup-storage-mounts`.
5. Prompt for default `case_root` directory:
   - Suggest `~/cases/` (will be expanded to absolute path)
   - Or ask for explicit path to user's legal-investigative workspace parent
6. Write `config.json` to standard location with structure:
   ```json
   {
     "case_root": "~/cases/",
     "version": "1.0.0",
     "created": "ISO-8601-timestamp"
   }
   ```
7. Print a "what's next" pointer: suggest running `legal-investigative new-workspace --variant=evidence-management` to scaffold a full case workspace, or `digital-evidence hash-evidence <path>` to begin processing.

## Output / side effects

- `config.json` written to standard location.
- Environment validated and summarized.
- User ready for evidence processing workflows.

## Safety / constraints

- If `config.json` already exists with content, do not overwrite without explicit confirmation.
- Suggest legal-investigative integration path but do not force it.
