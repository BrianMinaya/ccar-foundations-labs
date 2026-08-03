#!/bin/bash
# [M4] PreToolUse hook — blocks dangerous commands BEFORE execution.
#
# EXAM NOTE ────────────────────────────────────────────────────
#   This script receives the pending tool call as JSON on stdin.
#   It parses JSON with jq and exits with code 2 to block.
#
#   Protocol:
#     exit 0 → allow the tool call
#     exit 2 → BLOCK the tool call (stderr = reason shown to user)
#     exit 1 → non-blocking error (logged, doesn't block)
#
#   CRITICAL: This works because it's registered as PreToolUse.
#   If you move this SAME script to PostToolUse, the command runs
#   first and the hook fires afterwards — useless for blocking.
#
#   Checkpoint: ask Claude to run `rm -rf build/` → blocked.
#   Then move hook to PostToolUse and retry → command RUNS.
# ──────────────────────────────────────────────────────────────

set -u

if ! command -v jq >/dev/null 2>&1; then
    echo "BLOCKED: jq is required to parse hook input safely." >&2
    exit 2
fi

COMMAND=$(jq -er '.tool_input.command // empty' 2>/dev/null) || {
    echo "BLOCKED: malformed Bash tool input." >&2
    exit 2
}
NORMALIZED=$(printf '%s' "$COMMAND" | tr '[:upper:]' '[:lower:]')
# Shell quoting and simple backslash escapes do not change flag semantics.
ANALYSIS=${NORMALIZED//\"/}
ANALYSIS=${ANALYSIS//\'/}
ANALYSIS=${ANALYSIS//\\/}

# Inspect rm flags independently, so -rf, -fr, -r -f, and long flags all block.
if [[ "$ANALYSIS" =~ (^|[[:space:]\;\|\&])([^[:space:]\;\|\&]*/)?rm[[:space:]] ]]; then
    RM_ARGS=${ANALYSIS#*rm }
    RM_ARGS=${RM_ARGS%%[;|&]*}
    HAS_RECURSIVE=0
    HAS_FORCE=0
    read -r -a WORDS <<< "$RM_ARGS"
    for WORD in "${WORDS[@]}"; do
        case "$WORD" in
            --recursive) HAS_RECURSIVE=1 ;;
            --force) HAS_FORCE=1 ;;
            -*)
                [[ "$WORD" == *r* ]] && HAS_RECURSIVE=1
                [[ "$WORD" == *f* ]] && HAS_FORCE=1
                ;;
        esac
    done
    if [[ "$HAS_RECURSIVE" -eq 1 && "$HAS_FORCE" -eq 1 ]]; then
        echo "BLOCKED: recursive forced deletion is not allowed." >&2
        exit 2
    fi
    if [[ "$HAS_RECURSIVE" -eq 1 && " $RM_ARGS " == *" / "* ]]; then
        echo "BLOCKED: recursive deletion from root is not allowed." >&2
        exit 2
    fi
fi

if [[ "$ANALYSIS" =~ (^|[[:space:]\;\|\&])([^[:space:]\;\|\&]*/)?mkfs([[:space:]]|$) ]]; then
    echo "BLOCKED: Filesystem formatting is not allowed." >&2
    exit 2
fi

if [[ "$ANALYSIS" =~ (^|[[:space:]\;\|\&])dd[[:space:]] ]] \
    && [[ "$ANALYSIS" == *"if="* ]] \
    && [[ "$ANALYSIS" == *"of=/dev/"* ]]; then
    echo "BLOCKED: Direct disk writes are not allowed." >&2
    exit 2
fi

# Allow everything else
exit 0
