# CCAR Foundations Labs: Step-by-Step Guided Walkthrough

Repository: <https://github.com/BrianMinaya/ccar-foundations-labs>

Upstream project: <https://github.com/dennismyself/ccar-foundations-labs>

## Purpose and learning approach

Most milestone code in this repository is already implemented. The exercises emphasize observation, controlled modification, and explanation rather than blank-slate development.

Use the following workflow for each milestone:

1. Read the milestone's goal.
2. Predict what the program will do.
3. Run the supplied program.
4. Compare the output with the checkpoint.
5. Make the suggested small break or change, when one is provided.
6. Run it again and explain why the behavior changed.
7. Restore the working version before continuing.

After each milestone, document the result with this reflection:

> I observed ____. It happened because ____. In a production design, I would ____.

If the reflection cannot be completed without referring to the project README, repeat the milestone before continuing.

## Forking the repository

Forking is recommended for learners who want to preserve notes and experimental changes in their own GitHub accounts.

Appropriate additions to a study fork include:

- A `lab-notes/` folder.
- Personal explanations and observations.
- Screenshots or sanitized output that contains no API keys.
- Small experimental changes.
- A checklist showing which milestones can be explained without reference material.

Open a pull request to the upstream repository only when contributing an intentional correction or improvement.

## Environment setup

### Windows PowerShell

When working from a fork, replace `YOUR-GITHUB-NAME` with the account that owns the fork.

In PowerShell:

```powershell
git clone https://github.com/YOUR-GITHUB-NAME/ccar-foundations-labs.git
Set-Location ccar-foundations-labs
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

### If PowerShell says “No suitable Python runtime found”

That message means Python 3.12 is not installed. The `.venv` directory was therefore not created, so its activation script cannot exist yet.

First, see which Python versions Windows currently detects:

```powershell
py --list
```

If 3.12 is not listed, install it with Windows Package Manager:

```powershell
winget install --exact --id Python.Python.3.12
```

Close PowerShell, open a new PowerShell window, return to the repository, and verify the installation:

```powershell
py -3.12 --version
```

Only after that command reports Python 3.12 should you create and activate the environment:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

The activation command begins with dot, backslash, dot:

```text
.\.venv\Scripts\Activate.ps1
```

It is not `..venv\Scripts\Activate.ps1`. If PowerShell blocks script execution, allow scripts only for the current PowerShell process and retry:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

After successful activation, the prompt should begin with `(.venv)`.

### macOS and Linux

Use the following commands in a terminal:

```bash
git clone https://github.com/YOUR-GITHUB-NAME/ccar-foundations-labs.git
cd ccar-foundations-labs
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
cp .env.example .env
```

The remaining examples use PowerShell path syntax. On macOS and Linux, use `/` as the path separator and `cd` in place of `Set-Location`. The milestone order and learning objectives are platform-independent.

The project is tested with Python 3.12. Its dependencies are pinned, so do not upgrade individual packages while completing the labs.

Open `.env` and replace the placeholder with your Anthropic API key:

```text
ANTHROPIC_API_KEY=your-real-key
```

Treat the key as a password. Never place it in notes, screenshots, commits, chat messages, or terminal output that you plan to share.

Before making paid API calls, verify that the offline suite works:

```powershell
pytest
```

## Walkthrough sequence

The sections below are arranged in the recommended completion order. Proceed from top to bottom without skipping ahead.

| Stage | Work to complete |
|---:|---|
| 1 | Project 01: MiniAgent, M1 through M4 |
| 2 | Project 02: DocExtract, M1 through M4 |
| 3 | Return to Project 01: MiniAgent, M5 through M8 |
| 4 | Project 03: PowerRepo, M1 through M6 |
| 5 | Return to Project 02: DocExtract, M5 and M6 |
| 6 | Project 04: Research Pipeline capstone |

This sequence moves from one agent and one tool, to structured output, to multiple agents, and finally to production-style configuration and orchestration.

---

## Stage 1: Project 01, MiniAgent, M1 through M4

### What this stage teaches

You are learning how an agent repeatedly calls a model, receives a tool request, executes that tool, returns the result, and asks the model what to do next.

Start from the repository root:

```powershell
.\.venv\Scripts\Activate.ps1
Set-Location 01-miniagent
```

### M1: One model, one tool, one loop

```powershell
python m1_bare_loop.py
```

Watch for two model calls: Claude first requests the weather tool, then receives its result and produces the final answer.

Learn these points:

- The API does not remember earlier calls by itself.
- The `messages` list is the agent's working memory.
- `stop_reason == "tool_use"` means execute a tool and continue.
- `stop_reason == "end_turn"` means the response is finished.
- The tool result must refer to the exact tool-use ID Claude supplied.

You are done when you can draw this from memory:

```text
user question → Claude → tool request → Python tool → tool result → Claude → final answer
```

### M2: More tools and a safety limit

```powershell
python m2_two_tools.py
```

Watch for a question that causes two tool calls. The main loop should not need to be rewritten whenever a tool is added.

Perform the suggested experiment: temporarily prevent the tool results from being appended. Observe that the model repeats the request because it never received the result. Restore the line afterward.

Remember: an iteration cap prevents an uncontrolled loop, but it does not make an incomplete result successful.

### M3: Tool descriptions control tool selection

```powershell
python m3_descriptions.py
```

This script runs multiple trials, so it makes more API calls than M1 or M2. Compare the vague descriptions in Round A with the precise descriptions in Round B. Focus on input `8891`: a clear boundary should tell the model that a bare numeric ID is an order, not a customer.

> When the wrong tool is selected, improve the tool boundary and input description before adding more infrastructure.

### M4: Errors must carry meaning

```powershell
python m4_structured_errors.py
```

Make this note table:

| Result | Retry? | Meaning |
|---|---:|---|
| Validation error | No | The input is invalid. |
| Transient error | Yes | The operation might work on another attempt. |
| Permission error | No | Retrying does not change authorization. |
| Not found | No | The lookup succeeded and found zero records. |

> “The lookup failed” is not the same as “the lookup succeeded and nothing exists.”

**Stage 1 checkpoint:** Explain the agent loop, why tool IDs must match, and why `not_found` is not a tool failure.

**Next:** Continue directly to Stage 2 below. Do not run MiniAgent M5 yet.

---

## Stage 2: Project 02, DocExtract, M1 through M4

### What this stage teaches

You are turning messy invoice text into a predictable record that software can validate and store.

Return to the repository root, then enter Project 02:

```powershell
Set-Location ..
Set-Location 02-docextract
```

Before running anything, inspect the five files in `docs/` and `ground_truth.json`. Each document contains one deliberate trap.

### M1: Prose requests do not guarantee JSON

```powershell
python m1_explicit_criteria.py
```

The expected lesson is the failure. Although the prompt requests JSON only, a probabilistic text response may still contain Markdown fences or other text and fail `json.loads()`.

Do not repair M1. Record why it is unreliable and continue.

### M2: Force a schema

```powershell
python m2_structured_output.py
```

Compare M2 with M1 and identify three changes:

1. A tool schema is supplied.
2. `tool_choice` forces the extraction tool.
3. The program reads the tool block's already-structured input.

Syntax becomes dependable, but a syntactically valid record can still contain incorrect facts.

> Valid JSON means the shape is correct. It does not mean the contents are true.

### M3: Few-shot examples for ambiguous judgment

```powershell
python m3_fewshot.py
```

Compare zero-shot and few-shot results field by field. Examples are worthwhile only if they improve the specific ambiguity they target; do not rely on one overall accuracy number.

### M4: Validate with deterministic code

```powershell
python m4_validate_retry.py
```

Separate the outcomes:

- Recoverable extraction mistake: retry with specific feedback.
- Truly absent value: accept `null`.
- Conflicting evidence: preserve both values and send to a human.

The arithmetic check must use a sum computed by Python from the line items. Do not validate one model-supplied number against another model-supplied number.

**Stage 2 checkpoint:** Explain why schema validity is not factual correctness and why deterministic code should perform arithmetic validation.

**Next:** Return to Project 01 for MiniAgent M5–M8.

---

## Stage 3: Return to Project 01, MiniAgent, M5 through M8

Return to the repository root and re-enter Project 01:

```powershell
Set-Location ..
Set-Location 01-miniagent
```

### M5: Coordinator and isolated subagents

```powershell
python m5_coordinator.py
```

Trace three stages:

1. The coordinator decomposes one question into smaller tasks.
2. Each subagent starts with a fresh message list and sees only its brief.
3. The coordinator merges their final responses.

Enable the broken-decomposition experiment. Notice that every worker can succeed while the overall answer remains incomplete. The planning layer can fail even when no worker throws an error.

### M6: Context hygiene

```powershell
python m6_context_hygiene.py
```

Look for two techniques:

- Remove irrelevant fields from large tool responses.
- Repeat protected case facts at the beginning and end of the request.

Trim noise, not evidence or ground truth.

### M7: Real Agent SDK workflow

```powershell
python m7_agent_sdk_support.py
```

Follow the prerequisite sequence:

```text
verify customer → look up order → permit refund
```

A programmatic pre-tool hook blocks an unsafe refund even if the prompt asks the agent to skip verification. Prompt instructions guide behavior; enforcement code guarantees the rule.

### M8: Resume versus fork

```powershell
python m8_sessions.py
```

- Resume continues the same line of work with the same session history.
- Fork starts a different line of exploration from a shared earlier state.

This is a paid live exercise and is not part of the offline test suite.

**Stage 3 checkpoint:** Explain isolation, decomposition failure, programmatic enforcement, and resume versus fork.

**Next:** Continue to Project 03.

---

## Stage 4: Project 03, PowerRepo, M1 through M6

### What this stage teaches

This project is not a Python program. Its configuration files are the lab.

From the repository root:

```powershell
Set-Location ..
Set-Location 03-powerrepo\repo
```

Use Claude Code interactively in this directory. Inspect `SETUP.md` first because it maps every file to a milestone.

### M1: Instruction scopes

Open the root `CLAUDE.md`, `api/CLAUDE.md`, and the local file described by the lab. Use `/memory` while working at different paths.

Prove that user scope is personal, project scope is shared, directory scope applies only inside its tree, local scope is personal and gitignored, and the scopes accumulate rather than replace one another.

### M2: Command versus skill

Run `/review` explicitly. Then describe a deployment task in ordinary language without naming the deploy skill.

- A command waits for you to invoke it.
- A skill can be selected automatically from the intent in your request.

### M3: Path-specific rules

Use `/memory` while editing a Python file and then a Markdown file. Verify that the Python rule appears only for Python work while the global rule appears for both.

### M4: Hook enforcement

Study the hook and its settings before testing it. Use only a disposable test directory, never an important path.

`PreToolUse` can block an operation before it happens. `PostToolUse` can only react afterward, which is too late for prevention.

### M5: MCP, Grep, and Glob

Complete the scavenger hunts:

- Find every caller of `compute_total` with Grep, which searches contents.
- Find every test file with Glob using `**/test_*.py`, which matches names.

Inspect `.mcp.json` and identify how the local study server starts. Secrets should come from environment variables or user-scoped configuration, not committed literal values.

### M6: Headless CI and independent review

Inspect `.github/workflows/claude-review.yml` and locate:

- The non-interactive `-p`/`--print` invocation.
- The JSON schema.
- The `jq` check that fails on a structured critical finding.

Complete the three exercises under `labs/` in this order:

1. Plan mode versus direct execution.
2. Evidence-driven iterative refinement.
3. Three independent review passes.

Use a disposable branch for exercises that modify files.

**Stage 4 checkpoint:** Explain when to use a project instruction, path rule, command, skill, hook, or MCP server.

**Next:** Return to Project 02 for its final two milestones.

---

## Stage 5: Return to Project 02, DocExtract, M5 and M6

From the repository root, enter Project 02 again:

```powershell
Set-Location ..\..
Set-Location 02-docextract
```

### M5: Batch processing

```powershell
python m5_batch.py
```

Use synchronous calls when a person or workflow is blocked waiting for the answer. Use a batch when the work can finish later. A completed batch job can still contain failed individual requests, so inspect every result.

Leave the synthetic 100-document option until you deliberately understand and accept its cost.

### M6: Calibration and human review

```powershell
python m6_calibration.py
```

Inspect the generated human-review queue and compare:

- Escape: an incorrect record was automatically accepted.
- False alarm: a correct record was unnecessarily sent to a human.

Route production work using deterministic validation evidence, not the model's statement that it feels confident.

**Stage 5 checkpoint:** Explain when batch is appropriate and why self-reported confidence is not a reliable routing control.

**Next:** Complete the Project 04 capstone.

---

## Stage 6: Project 04, Research Pipeline capstone

### What this stage teaches

A coordinator delegates to named specialists, preserves the source behind every claim, records partial failures, and refuses to flatten conflicting evidence into false certainty.

First return to the repository root and run the offline tests:

```powershell
Set-Location ..
pytest
```

Then run the paid live pipeline:

```powershell
python 04-research-pipeline\pipeline.py
```

A complete result should demonstrate all of the following:

- Each specialist has a separate prompt and tool allowlist.
- The coordinator delegates through the task mechanism.
- Every factual claim retains a source ID.
- Conflicting adoption rates remain separate instead of being averaged.
- An unavailable source is recorded as a typed partial failure.
- The missing cost evidence is named as a coverage gap.
- State can be saved to and restored from a structured manifest.

If any criterion is missing, treat the run as incomplete even if its prose appears polished.

**Stage 6 checkpoint:** Explain how provenance, conflicts, partial failure, and resumable state make a multi-agent system more reliable.

---

## Milestone study record

For each milestone, keep a note with these six fields:

```text
Milestone:
Prediction:
Observed result:
Why it happened:
Production rule:
One scenario question I could now answer:
```

After completing a project, close the README and explain the architecture aloud. If you cannot explain a milestone without using its vocabulary as a substitute for meaning, rerun it.

## Suggested study-session structure

Keep sessions small:

- 10 minutes: read and predict.
- 20 to 30 minutes: run and experiment.
- 10 minutes: write the explanation.
- 5 minutes: create one exam-style scenario question.

One deeply understood milestone is more valuable than running an entire project and remembering only the terminal commands.

## Cost control

- Run `pytest` freely; it is intended to be offline.
- M1 and M2 of MiniAgent are good first paid calls because their behavior is easy to trace.
- MiniAgent M3 runs repeated trials and therefore makes more calls.
- DocExtract M5 uses the Batch API.
- MiniAgent M7 and M8, along with Project 04, are live Agent SDK exercises.
- Do not use the 100-document synthetic batch until you deliberately choose to spend the calls.
- Check current model availability, pricing, and account usage before a paid session.

## Suggested first study session

Complete the following steps:

1. Fork and clone the repository.
2. Create the Python 3.12 virtual environment.
3. Install the pinned development dependencies.
4. Run `pytest`.
5. Run MiniAgent M1.
6. Draw the six-arrow loop shown in the M1 section.
7. Write the three-sentence milestone explanation.

End the session after these steps. The session is successful when the purpose of returning the full assistant response and matching tool-use ID can be explained without reference material.
