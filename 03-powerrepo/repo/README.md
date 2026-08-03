# Project 03 — PowerRepo

No script to run — the **configuration** is the deliverable. Use case: you're tech
lead of a 6-person team that just adopted Claude Code. Conventions live in personal
settings, nothing stops destructive commands, CI hangs on interactive sessions.

**Done looks like:** A teammate clones, runs `claude`, and with zero personal setup
gets the team's Python conventions, `/review`, an auto-triggering deploy checklist,
and a hard block on `rm -rf` — and CI completes instead of hanging.

**Domains covered:** D3 Claude Code Configuration & Workflows (20%), enforcement half of D1, MCP half of D2.

See `SETUP.md` for the complete file map and quick reference.

---

## M1 — CLAUDE.md Hierarchy (`CLAUDE.md`, `api/CLAUDE.md`, `CLAUDE.local.md`)

**Goal:** Understand the four scopes and how they concatenate.

**What the files do:**
- `CLAUDE.md` — project scope, committed, everyone gets it; it also demonstrates
  `@standards/testing.md` imports
- `api/CLAUDE.md` — directory scope, only active under `api/`
- `CLAUDE.local.md` — local scope, gitignored, just you
- `~/.claude/CLAUDE.md` — user scope (not in this repo), just you

**Concepts (D3-3.1):**
- Scopes concatenate broad→specific — they don't override
- CLAUDE.md is context, not enforcement (for guarantees, use hooks — M4)
- ~200-line guideline max — bloated files dilute attention
- `/memory` is the diagnostic — shows what's actually loaded

**Checkpoint (signature scenario):**
Put a convention only in your user file (`~/.claude/CLAUDE.md`). Run `/memory` —
it appears. Now imagine a teammate cloning: they wouldn't get it. Fix by moving
it to `./CLAUDE.md`.

**If stuck:**
Run `/memory` and compare the output when editing files in different directories.

---

## M2 — Command vs Skill (`.claude/commands/review.md`, `.claude/skills/deploy/SKILL.md`)

**Goal:** Understand when a user explicitly invokes vs when the model auto-triggers.

**What the files do:**
- `review.md` gives `/review` — you type the command
- `SKILL.md` has `description`, `argument-hint`, `allowed-tools`, `context: fork` —
  the model matches user intent to the description and auto-fires

**Concepts (D3-3.2):**
- Command: `.claude/commands/` → user types `/review`
- Skill: `.claude/skills/` → user DESCRIBES a task, `description` matches, auto-fires
- "We want Claude to notice X and do Y automatically" → skill
- A command can't self-trigger
- `context: fork` isolates skill output from the main conversation
- `allowed-tools` restricts what tools the skill can use (least privilege)
- Project-scoped (in repo) = shared via version control
- User-scoped (`~/.claude/commands/` or `~/.claude/skills/`) = personal

**Checkpoint:**
Type `/review` — it works. Then describe a deploy task in plain English without
naming the skill — it fires anyway. That proves `description` is the router.

**If stuck:**
If the skill doesn't auto-trigger, check that the `description` field in the
frontmatter matches the kind of language a user would naturally use.

---

## M3 — Path-Specific Rules (`.claude/rules/python.md`, `.claude/rules/global-note.md`)

**Goal:** Apply conventions conditionally based on what file you're editing.

**What the files do:**
- `python.md` has `paths: ["**/*.py"]` — loaded only when editing Python files
- `global-note.md` has no `paths:` — loaded for every file (deliberate contrast)

**Concepts (D3-3.3):**
- `paths:` with glob patterns → conditional loading based on file being edited
- No `paths:` → always loaded
- `/memory` while editing `src/app.py` → both rules appear
- `/memory` while editing a `.md` → only `global-note.md` appears
- Design question:
  - Everything → no `paths:`
  - A filetype across many dirs → `paths:` with glob
  - One directory tree → `api/CLAUDE.md`
  - A task rather than a file → a skill

**Checkpoint:**
Run `/memory` while editing `src/app.py` — Python rule appears. Edit a `.md` —
it doesn't. The always-on rule appears both times.

**If stuck:**
If both rules always appear, check the `paths:` frontmatter syntax — it must
be YAML with the `---` delimiters.

---

## M4 — Enforcement Hook (`.claude/settings.json`, `.claude/hooks/block-dangerous.sh`)

**Goal:** CLAUDE.md is context; a hook is enforcement. Learn the critical Pre vs Post distinction.

**What the files do:**
- `settings.json` registers a **PreToolUse** hook matching `Bash`, running `block-dangerous.sh`
- `block-dangerous.sh` parses the pending call with `jq`, recognizes combined,
  reversed, and split recursive-force flags, and exits with code 2 to block

**Concepts (D1-1.4, D1-1.5, D3):**
- Hook protocol: `exit 0` allow · `exit 2` block (stderr = reason) · `exit 1` non-blocking error
- Pick exit codes OR JSON output, never both
- If a question says "ensure / guarantee / must never" → the answer is a hook

**Checkpoint — the most valuable thing in this project:**
Ask Claude to run `rm -rf build/` → **blocked** before execution.
Now move the same hook to **PostToolUse** in settings.json and retry →
the command **runs** and the hook fires afterwards, uselessly.
**Same script, different event, works vs worthless.**

**If stuck:**
If the hook doesn't fire, check that `block-dangerous.sh` is executable
(`chmod +x`) and that the path in `settings.json` is correct.

---

## M5 — MCP + Built-in Tool Fluency (`.mcp.json`, source files)

**Goal:** Configure MCP servers and distinguish Grep (contents) from Glob (names).

**What the files do:**
- `.mcp.json` configures the local, credential-free `study-tools` server
- `mcp-servers/study_server.py` exposes a safe project-search tool and an
  architecture resource without relying on a missing file, `npx`, or secret
- `src/`, `api/`, `tests/` contain toy source for the scavenger hunt

**Concepts (D2-2.4, D2-2.5):**
- `.mcp.json` (project, committed) vs `~/.claude.json` (user, private)
- MCP is an open standard, not Claude-only
- Tools from all configured servers are discovered at connection time
- Never hardcode secrets in `.mcp.json` — use env-var expansion
- Exam scenario: "teammate committed a token" → fix with env-var expansion
  or user scope, NOT `.gitignore` (that removes config from the whole team)

**Checkpoint — scavenger hunt:**
- Find all callers of `compute_total` → **Grep** (searches contents)
- Find all test files → **Glob** (matches names: `**/test_*.py`)

**If stuck:**
Remember: Grep = "what's INSIDE files", Glob = "what files EXIST".

---

## M6 — Headless CI, Plan Mode, Sessions (`.github/workflows/claude-review.yml`)

**Goal:** Run Claude Code in CI without hanging. Gate on structured output, not prose.

**What the file does:**
`claude-review.yml` installs a pinned CLI, runs `claude -p` with a strict JSON
schema, extracts the JSON envelope's `.structured_output`, and fails closed on
critical findings via `jq`.

**Concepts (D3-3.4, D3-3.6, D1-1.7):**
- **`-p`/`--print` is THE fix for "our CI job hangs"** — without it the CLI opens
  an interactive session with no human → hangs forever
- Gate on a structured field, never on prose
- Independent review = separate `claude -p` with fresh context (can't inherit
  blind spots from the session that wrote the code)
- Plan mode vs direct: triggered by **ambiguity/scope**, not difficulty
- `--continue`: resume most recent session
- `--resume <name>`: resume a specific named session
- `--fork-session`: divergent exploration from shared baseline
- Fresh start: when context has gone stale

**Checkpoint:**
The workflow would run to completion in CI without hanging. The `jq` step
gates on `severity == "critical"`, not on parsing the model's prose.

The `labs/` directory adds hands-on plan-vs-direct, evidence-driven refinement,
and three independent review-pass exercises.

**If stuck:**
If the CI concept is unclear, try running `claude -p "hello"` locally — note
it prints and exits, unlike interactive `claude` which waits for input.
