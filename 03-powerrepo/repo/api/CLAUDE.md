# API Conventions

[M1] Directory-scope CLAUDE.md — loaded only when working in `api/` or its subdirectories.

<!-- EXAM NOTE ────────────────────────────────────────────────────
  Scope: directory-level
  - Concatenates WITH the project-level CLAUDE.md (both are active)
  - Use for conventions specific to one part of the codebase
  - Alternative to path-scoped rules in .claude/rules/ — see M3
  - Design question: one directory tree → directory CLAUDE.md
                     a filetype across many dirs → .claude/rules/ with paths:
──────────────────────────────────────────────────────────────── -->

## API-Specific Standards
- All endpoints return JSON with `{"data": ..., "error": ...}` envelope
- Use HTTP status codes correctly: 200 OK, 201 Created, 400 Bad Request, 404 Not Found, 500 Internal
- Rate limiting headers on every response
- Request validation with Pydantic models
- All routes registered in `api/routes.py`
- Handler logic in `api/handlers.py` — routes file only does routing
