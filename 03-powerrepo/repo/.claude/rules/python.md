---
paths:
  - "**/*.py"
---

# Python Conventions

[M3] Path-specific rule — loaded ONLY when editing files matching `**/*.py`.

<!-- EXAM NOTE ────────────────────────────────────────────────────
  Location: .claude/rules/python.md
  Frontmatter: paths: ["**/*.py"]

  - Loads ONLY when editing matching files → reduces irrelevant context
  - /memory while editing src/app.py → this rule appears
  - /memory while editing a .md file → this rule does NOT appear
  - Advantage over directory CLAUDE.md: applies to .py files in ANY directory
  - Design question:
    · Everything → no paths: (always-on, see global-note.md)
    · A filetype across many dirs → paths: with glob (this file)
    · One directory tree → api/CLAUDE.md
    · A task rather than a file → a skill
──────────────────────────────────────────────────────────────── -->

When writing or modifying Python files:

- Use type hints for all function parameters and return types
- Prefer `dataclass` or `pydantic.BaseModel` over plain dicts for structured data
- Use `logging` module, never `print()` for operational output
- Context managers (`with`) for all file and connection handling
- List comprehensions over `map()`/`filter()` when readable
- `isinstance()` over `type()` for type checking
- Import sorting: `isort` compatible (stdlib / third-party / local)
