# Project Conventions

@standards/testing.md

[M1] Project-scope CLAUDE.md — committed to version control, shared with all teammates.

<!-- EXAM NOTE ────────────────────────────────────────────────────
  Scope: project-level (root CLAUDE.md or .claude/CLAUDE.md)
  - Loaded for EVERY session in this repo
  - Concatenates with directory-level and user-level — does NOT override
  - This is CONTEXT, not enforcement. For guarantees, use hooks (M4)
  - ~200 lines max recommended — a bloated file dilutes attention
  - Diagnostic: /memory shows what's actually loaded
  - Trap: putting conventions in ~/.claude/CLAUDE.md means teammates don't get them
──────────────────────────────────────────────────────────────── -->

## Language & Runtime
- Python 3.12+, type hints on all public functions
- Use `pathlib.Path` over `os.path`
- Prefer f-strings over `.format()` or `%`

## Code Style
- Maximum line length: 88 characters (Black default)
- Imports: stdlib → third-party → local, separated by blank lines
- No wildcard imports (`from x import *`)

## Testing
- All tests use pytest
- Test files: `test_<module>.py`
- Minimum 80% coverage on new code
- Use fixtures over setup/teardown

## Git
- Conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`
- No force-push to main
- PRs require at least one approval

## Error Handling
- Never use bare `except:`
- Log errors before re-raising
- Use custom exception classes in `src/exceptions.py`

## Documentation
- All public functions need docstrings (Google style)
- Update CHANGELOG.md for user-facing changes
