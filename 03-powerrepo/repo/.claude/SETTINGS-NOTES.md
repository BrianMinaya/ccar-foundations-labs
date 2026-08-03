# Settings & MCP Configuration Notes

[M4/M5] Exam notes for JSON config files — JSON doesn't support comments, so notes live here.

## Hook Settings (`.claude/settings.json`)

<!-- EXAM NOTE ────────────────────────────────────────────────────
  .claude/settings.json:
  - Committed to version control → shared with team
  - Registers hooks that run BEFORE or AFTER tool calls

  Hook event types:
  - PreToolUse: fires BEFORE the tool executes
    → CAN block execution (exit 2)
    → This is where enforcement belongs
  - PostToolUse: fires AFTER the tool executes
    → CANNOT undo what already ran
    → Useful for logging, notification, data normalization
    → USELESS for blocking dangerous commands

  Hook protocol (exit codes):
  - exit 0: allow (tool proceeds / no action)
  - exit 2: BLOCK (tool call is prevented, stderr becomes the reason shown)
  - exit 1: non-blocking error (logged but doesn't block)

  Pick exit codes OR JSON output, never both.

  The matcher field: matches tool names
  - "Bash" matches all Bash tool calls
  - Can match specific tools like "Read", "Write", etc.

  CRITICAL TRAP (most valuable thing in Project 03):
  - Same hook script in PreToolUse → blocks rm -rf BEFORE execution ✓
  - Same hook script in PostToolUse → rm -rf runs first, hook fires after ✗
  - Same script, different event, works vs worthless

  .claude/settings.local.json:
  - Gitignored → personal to you
  - Same format as settings.json
  - Use for personal hook overrides or experimental hooks
──────────────────────────────────────────────────────────────── -->

## MCP Configuration (`.mcp.json`)

<!-- EXAM NOTE ────────────────────────────────────────────────────
  .mcp.json:
  - Project scope (committed) → shared with team
  - Contains MCP server configurations
  - Tools from ALL configured servers are discovered at connection time

  Scoping:
  - .mcp.json (project, committed) → team-wide servers
  - ~/.claude.json (user, NOT committed) → personal/experimental servers
  - MCP is an open standard, not Claude-only

  Secrets:
  - NEVER hardcode tokens in .mcp.json — it's committed!
  - Use env-var expansion: "${MY_SERVICE_TOKEN}"
  - Exam scenario: "a teammate committed a token"
    Fix: env-var expansion or user scope
    NOT .gitignore (that removes config from the whole team)

  Built-in tools vs MCP tools:
  - Grep: searches file CONTENTS (find all callers of compute_total)
  - Glob: matches file NAMES/PATHS (find all test files)
  - Enhance MCP tool descriptions to prevent agents from preferring
    built-in tools over more capable MCP tools

  This repository's actual server is deliberately credential-free and local,
  so a fresh clone does not fail because an example token is missing.
──────────────────────────────────────────────────────────────── -->
