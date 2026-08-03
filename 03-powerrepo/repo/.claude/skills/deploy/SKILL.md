---
description: "Run the pre-deployment checklist and verify all systems are ready for deployment"
argument-hint: "target environment (e.g., staging, production)"
allowed-tools:
  - Bash
  - Read
  - Glob
  - Grep
context: fork
---

# Deploy Readiness Skill

[M2] Skill — the MODEL invokes this automatically based on the `description` field.

<!-- EXAM NOTE ────────────────────────────────────────────────────
  Location: .claude/skills/deploy/SKILL.md
  Key frontmatter fields:
  - description: The ROUTER. Claude matches user intent to this text.
    If the user describes a deploy task without naming the skill, it fires anyway.
  - argument-hint: Prompts user for required parameters
  - allowed-tools: Restricts what tools the skill can use (least privilege)
  - context: fork — runs in an isolated sub-agent context, preventing
    skill outputs from polluting the main conversation

  The distinction:
  - Command (.claude/commands/): user explicitly types /review → runs
  - Skill (.claude/skills/): user DESCRIBES a task, description matches → auto-fires
  - "We want Claude to notice X and do Y automatically" → skill
  - A command can't self-trigger

  Personal variants: create in ~/.claude/skills/ with different names
  to avoid affecting teammates
──────────────────────────────────────────────────────────────── -->

Run the pre-deployment checklist for the specified environment:

## Pre-Deploy Checks
1. Run the full test suite: `pytest tests/ -v`
2. Check for uncommitted changes: `git status`
3. Verify the target branch is up to date: `git fetch && git status`
4. Search for TODO/FIXME/HACK comments: scan all source files
5. Check for debug prints or breakpoints: search for `print(`, `breakpoint()`, `pdb`
6. Verify no `.env` files are staged: `git diff --cached --name-only`

## Environment-Specific Checks
- **staging**: Verify staging config exists, check staging DB migrations
- **production**: Require approval tag in latest commit, verify rollback plan exists

## Output
Report each check as PASS / FAIL / WARN with details.
Fail the deployment if any critical check fails.

$ARGUMENTS
