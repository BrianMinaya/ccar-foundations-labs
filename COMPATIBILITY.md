# Compatibility and Version Policy

Release 0.2.0 is verified with:

| Component | Supported/tested |
|---|---|
| Python | 3.12.x (supported); 3.13+ not yet claimed |
| `anthropic` | 0.120.2 |
| `claude-agent-sdk` | 0.2.128 |
| Pydantic | 2.13.4 |
| Claude Code sample | 2.1.220 |

Dependencies are intentionally pinned for reproducible study. Automated update
PRs should run the offline suite and manually re-check `claude doctor`, hook
input/output contracts, headless JSON envelopes, and Agent SDK option names.

The labs use current public model aliases. Model availability and pricing can
change; verify them in official Anthropic documentation before paid runs.
