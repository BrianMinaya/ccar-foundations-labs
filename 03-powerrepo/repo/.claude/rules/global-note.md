# Team Communication Standards

[M3] Always-on rule — no `paths:` frontmatter means this loads for EVERY file.

<!-- EXAM NOTE ────────────────────────────────────────────────────
  Location: .claude/rules/global-note.md
  Frontmatter: NONE (no paths: field)

  - No paths: → always loaded, regardless of which file is being edited
  - Deliberate contrast with python.md which has paths: ["**/*.py"]
  - /memory shows this rule in BOTH cases:
    · editing src/app.py → python.md + global-note.md both appear
    · editing README.md → only global-note.md appears
  - Use for rules that genuinely apply to all file types
──────────────────────────────────────────────────────────────── -->

- When making changes, explain what you changed and why in your response
- Preserve existing code comments unless they're clearly wrong
- Don't remove TODO comments — they track known technical debt
- Ask before making changes outside the scope of the current request
