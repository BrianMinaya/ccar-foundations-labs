# Project 01 — MiniAgent

Build an agentic loop from raw `messages.create`, add tools, then a multi-agent
coordinator. Each milestone exposes the failure the next one fixes.

**Domains covered:** D1 Agentic Architecture & Orchestration, D2 Tool Design, parts of D5 Reliability.

## Setup

```bash
cd CCAR-F   # repo root
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your real key
cd 01-miniagent
```

---

## M1 — The Bare Loop (`m1_bare_loop.py`)

**Goal:** Build the minimal agentic loop — one tool, one question, pure API.

**What the code does:**
`run(user_msg)` maintains a `messages` list, calls `client.messages.create`, and
branches on `stop_reason`: `end_turn` → print and return; `tool_use` → execute
`get_weather`, append the result, loop.

**Concepts (Exam Domain 1, Task 1.1):**
- The API is stateless — the `messages` list IS the memory
- Branch on `stop_reason`, never on the text
- Always append the full assistant response before the `tool_result`
- The `tool_use` block's `id` must match in the `tool_result`

**Checkpoint:**
"What's the weather in Paris, and should I pack a coat?" loops exactly twice
(one tool call, one final answer).

**If stuck:**
Print `resp.stop_reason` at each iteration. If you see `end_turn` on the first
loop, check that your tool schema is in the `tools=` parameter.

---

## M2 — Two Tools + Stop Guard (`m2_tools.py`, `m2_two_tools.py`)

**Goal:** Prove the loop doesn't change when you add tools; add a circuit breaker.

**What the code does:**
Tools move to `m2_tools.py` (schemas + implementations + dispatch dict). The runner
in `m2_two_tools.py` handles MULTIPLE `tool_use` blocks in one response, tracks a
`steps` counter, and has `MAX_ITERATIONS = 20` that logs loudly when hit.

**Concepts (D1-1.1, D2-2.3):**
- The loop body is tool-count-agnostic — adding a tool means adding a schema + function
- The iteration cap is a circuit breaker, not an exit
- One response can contain multiple `tool_use` blocks — iterate over all content blocks

**Checkpoint:**
A two-part question makes 2 tool calls. `steps == 2` not 20.

**Experiment:**
Comment out the `tool_results` append → the "forgetting loop". The model calls the
same tool forever because it never sees the result.

**If stuck:**
Check that you iterate over `resp.content` (a list), not just `resp.content[0]`.

---

## M3 — Tool Descriptions (`m3_descriptions.py`)

**Goal:** Show that misrouting is a description bug, and fix it for free.

**What the code does:**
Two confusable tools: `get_customer(CUST-12345)` and `lookup_order(8891)`. Round A
uses vague descriptions. Round B applies the 5-part checklist: purpose / input format /
when to use / edge cases / boundary ("use this NOT that"). 4 questions x 5 trials.

**Concepts (D2-2.1):**
- Tool descriptions are the primary mechanism LLMs use for tool selection
- Part 5 (boundary) does most of the work
- Ambiguous tool descriptions cause misrouting — the fix is free (no code change)

**Checkpoint:**
Round B fixes "Can you check 8891 for me?" — the ambiguous query where the only
cue is the ID format.

**If stuck:**
Compare the accuracy on question 3 between rounds. If Round B doesn't improve it,
make the boundary statement more explicit: "Use lookup_order for bare numeric IDs."

---

## M4 — Structured Errors (`m4_structured_errors.py`)

**Goal:** Errors are data, not exceptions. Every tool return is a structured dict.

**What the code does:**
`lookup_order` returns a dict in every case — never a bare string, never raises.
Four categories: `validation` (not retryable), `transient` (retried with backoff),
`permission` (not retryable), `not_found` (`isError: false`, `count: 0`).

**Concepts (D2-2.2, D5-5.3):**
- "I couldn't look" ≠ "I looked, there's nothing" — the most-tested distinction
- Raising kills the run; `except: pass` produces a confident wrong answer (worse)
- `not_found` is a valid result, not a failure — `isError: false`
- Structured metadata: `errorCategory`, `isRetryable`, human-readable message

**Checkpoint:**
Order 5555 → "there is no order 5555" with no retry.
Order 7777 → fails once, retried in code, succeeds.

**If stuck:**
If order 7777 isn't retrying, check that your `is_retryable` check is in the
dispatch function, not in the prompt.

---

## M5 — Coordinator + Subagents (`m5_coordinator.py`)

**Goal:** Build a multi-agent pattern manually before comparing it with the real
Agent SDK in M7.

**What the code does:**
`subagent(brief)` is the agentic loop but `messages` starts as
`[{"role":"user","content":brief}]` and nothing else — that one line is the isolation
principle. `decompose(question)` uses a `plan_subtasks` tool; the coordinator maps
each subtask to a `subagent()` call. Subagents run concurrently.

**Concepts (D1-1.2, D1-1.3, D1-1.6):**
- In this raw Messages API implementation, your dispatch table maps a planned
  subtask to another loop. The Agent SDK provides `AgentDefinition` and `Task`.
- Isolation is WHY you split agents; parallelism is a bonus
- Hub-and-spoke: all communication through the coordinator
- Brief in is the only channel, final message out the only return

**Checkpoint:**
"Compare our refund, shipping and warranty terms" → 3 blank-slate subagents in
parallel, one merged answer.

**Experiment:**
`BREAK_DECOMPOSITION = True` → two of three subagents run, both succeed, nothing
errors, answer is confidently incomplete. **Multi-agent systems fail at the plan,
not the workers.**

**If stuck:**
If subagents share context, check that `messages` is initialized fresh per call,
not shared by reference.

---

## M6 — Context Hygiene (`m6_context_hygiene.py`)

**Goal:** "It's in the context" ≠ "the model will use it." Fix with trimming
and case-facts blocks.

**What the code does:**
(a) Trims a 40-field tool response to 4 relevant fields — 1005 chars → 87, a 91%
cut, identical answer.
(b) Maintains a case-facts block (order 8891, £320.00, TICK-4417) restated at top
AND end of every request. Filler turns bury the early facts mid-context.

**Concepts (D5-5.1, D5-5.4):**
- Lost-in-the-middle: models attend to the start and end, not the middle
- Trim verbose payloads, NEVER ground truth
- A scratchpad (agent's working notes) ≠ case-facts block (fixed protected truths)
- Place key facts at beginning AND end to mitigate position effects

**Checkpoint:**
After padding turns, the agent still cites order 8891, £320.00, TICK-4417 exactly.

**If stuck:**
If the facts drift, check that the case-facts block appears at BOTH the start
and end of the user message, not just the start.

---

## M7 — Real Agent SDK Support Workflow (`m7_agent_sdk_support.py`)

Defines in-process MCP tools for customer verification, order lookup, refunds,
and structured human escalation. A programmatic `PreToolUse` hook denies refund
side effects until the customer and order prerequisites are satisfied; the tool
also re-checks the invariant as defense in depth.

Checkpoint: the live agent verifies Jane, looks up order 8891, and only then can
refund GBP 50. Changing the prompt to skip verification is denied by the hook.

## M8 — Session Resume and Fork (`m8_sessions.py`)

Captures a `ResultMessage.session_id`, resumes it, and sets `fork_session=True`
for a divergent design path. This is a paid live exercise; it is excluded from
offline CI.
