---
description: Run the team's standard code review checklist
---

# Code Review Command

[M2] Project-scoped slash command — invoked by typing `/review` in Claude Code.

<!-- EXAM NOTE ────────────────────────────────────────────────────
  Location: .claude/commands/review.md → user types /review
  - Project-scoped (in repo) = shared with team via version control
  - User-scoped (~/.claude/commands/) = personal, not shared
  - A command is EXPLICITLY invoked by the user
  - Contrast with a skill (M2 below): a skill can self-trigger based on description
  - The `description` frontmatter is what appears in the command list
──────────────────────────────────────────────────────────────── -->

Review the current changes against this checklist:

## Security
- [ ] No hardcoded secrets or API keys
- [ ] Input validation on all external data
- [ ] SQL queries use parameterized statements
- [ ] No `eval()` or `exec()` on user input

## Code Quality
- [ ] Functions are under 50 lines
- [ ] No code duplication (DRY)
- [ ] Error handling follows project conventions
- [ ] Type hints on all public functions

## Testing
- [ ] New code has corresponding tests
- [ ] Edge cases are covered
- [ ] Tests are deterministic (no flaky tests)

## Documentation
- [ ] Public APIs have docstrings
- [ ] CHANGELOG updated if user-facing
- [ ] Complex logic has inline comments

Report findings grouped by category. For each finding, include:
- File and line number
- Issue description
- Severity: CRITICAL / WARNING / INFO
- Suggested fix
