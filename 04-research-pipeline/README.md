# Project 04 — Research Pipeline (Claude Agent SDK)

This project closes the gap between a hand-written Messages API loop and the
real Claude Agent SDK. The live coordinator defines named `AgentDefinition`
workers, exposes only `Task` to the coordinator, gives researchers an in-process
MCP server, and requires a separate evidence-review pass.

The fixtures deliberately contain two conflicting adoption rates and one
unavailable cost source. A good result keeps both values with their source IDs,
returns useful controls evidence, records the typed partial error, and names
`costs` as a coverage gap. It must not silently average the rates or describe a
timeout as “no evidence exists.”

## Run

From the repository root, activate Python 3.12 and set `ANTHROPIC_API_KEY`:

```bash
source .venv/bin/activate
python 04-research-pipeline/pipeline.py
```

This makes paid API calls and is not part of the offline test suite. The pure
functions in `core.py` are covered offline and show manifest persistence for
pause/resume, provenance-preserving merge, conflicts, and coverage gaps.

## Checkpoints

- `AgentDefinition` gives each specialist a separate prompt and allowlist.
- `Task` is the coordinator’s only tool; worker tools remain scoped.
- Every claim retains `source_id`; provenance survives synthesis.
- Tool failure is typed partial state, not an empty successful search.
- Conflicting evidence is displayed, not flattened into false certainty.
- A structured manifest can be saved and reloaded before another live session.
- `01-miniagent/m8_sessions.py` demonstrates SDK resume plus forked exploration.
