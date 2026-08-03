# Project 03 — PowerRepo: Setup & File Map

No script to run — the **configuration** is the deliverable.

## File Map

| File | Milestone | Purpose | Scope |
|---|---|---|---|
| `CLAUDE.md` | M1 | Project conventions | Committed, everyone |
| `api/CLAUDE.md` | M1 | API-specific conventions | Directory, committed |
| `CLAUDE.local.md` | M1 | Personal preferences | Local, gitignored |
| `.claude/commands/review.md` | M2 | `/review` slash command | Project, committed |
| `.claude/skills/deploy/SKILL.md` | M2 | Auto-triggering deploy skill | Project, committed |
| `.claude/rules/python.md` | M3 | Python file conventions | Path-scoped: `**/*.py` |
| `.claude/rules/global-note.md` | M3 | Always-on team rules | No paths = always loaded |
| `.claude/settings.json` | M4 | Hook registration | Committed, team-wide |
| `.claude/hooks/block-dangerous.sh` | M4 | PreToolUse enforcement hook | Committed |
| `.claude/settings.local.json` | M4/M5 | Local hook overrides | Gitignored |
| `.claude/SETTINGS-NOTES.md` | — | Exam notes for JSON configs | Reference |
| `.mcp.json` | M5 | MCP server configuration | Project, committed |
| `.github/workflows/claude-review.yml` | M6 | Headless CI pipeline | Committed |
| `.github/claude-review-schema.json` | M6 | Strict CI review contract | Committed |
| `mcp-servers/study_server.py` | M5 | Local MCP tool + resource, no secrets | Committed |
| `labs/*.md` | M6 | Plan/direct, refinement, independent review | Committed |
| `standards/testing.md` | M1 | `@import` target for shared guidance | Committed |
| `src/app.py` | M5 | Main application (scavenger hunt) | — |
| `src/utils.py` | M5 | Utilities with `compute_total` | — |
| `api/routes.py` | M5 | API route definitions | — |
| `api/handlers.py` | M5 | API handlers (calls compute_total) | — |
| `tests/test_app.py` | M5 | App tests | — |
| `tests/test_utils.py` | M5 | Utility tests | — |

## Quick Reference

### Scopes (broad → specific, they concatenate)
1. **User** (`~/.claude/CLAUDE.md`) — just you, not shared
2. **Project** (`CLAUDE.md` at repo root) — committed, everyone
3. **Directory** (`api/CLAUDE.md`) — only under that directory
4. **Local** (`CLAUDE.local.md`) — gitignored, just you

### Key Commands
- `/memory` — see what's actually loaded (the diagnostic)
- `/review` — run the team code review checklist (M2)

### Scavenger Hunt (M5)
- **Grep** challenge: find all callers of `compute_total` (searches contents)
- **Glob** challenge: find all test files (matches names: `**/test_*.py`)

### The 12 Core Ideas This Project Teaches
10. CLAUDE.md is context; a hook is enforcement. "ensure/guarantee/must never" → hook.
11. PreToolUse can block; PostToolUse cannot.
12. Scope decides who gets a rule; `/memory` shows what actually loaded.
