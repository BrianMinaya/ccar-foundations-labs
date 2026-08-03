"""
MiniAgent M5 — Multi-Agent Coordinator
========================================

THE USE CASE
------------
Input:  A broad question that requires reading multiple policy documents.
Output: A merged summary comparing all policies.
Target: "Compare our refund, shipping and warranty terms"
        -> coordinator decomposes into 3 subtasks
        -> 3 blank-slate subagents run in parallel, each reading one policy
        -> coordinator merges their outputs into a single comparative answer.

This file demonstrates the multi-agent pattern: a coordinator that
decomposes a task, spawns isolated subagents, and merges results.
"""

import os
import json
import anthropic
import concurrent.futures
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the shared projects root (two levels up)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

client = anthropic.Anthropic()

POLICIES_DIR = Path(__file__).resolve().parent / "policies"
POLICY_FILES = {"refund.md", "shipping.md", "warranty.md"}

# ---------------------------------------------------------------------------
# Flag to demonstrate failure mode
# ---------------------------------------------------------------------------
# When True, artificially drops one subtask to show: two of three subagents
# run, both succeed, nothing errors, answer is confidently INCOMPLETE.
BREAK_DECOMPOSITION = False

MAX_ITERATIONS = 15


# ---------------------------------------------------------------------------
# Tool: read_policy — available to subagents
# ---------------------------------------------------------------------------

def read_policy(filename: str) -> str:
    """Read a policy document from the policies/ directory."""
    if filename not in POLICY_FILES:
        return json.dumps({
            "status": "error",
            "message": f"Policy '{filename}' is not in the allowlist.",
        })
    filepath = (POLICIES_DIR / filename).resolve()
    if filepath.parent != POLICIES_DIR.resolve() or not filepath.is_file():
        return json.dumps({
            "status": "error",
            "message": f"Policy file '{filename}' not found.",
        })
    return filepath.read_text(encoding="utf-8")


SUBAGENT_TOOLS = [
    {
        "name": "read_policy",
        "description": (
            "Read a policy document from the policies directory. "
            "Available files: refund.md, shipping.md, warranty.md. "
            "Returns the full text of the requested policy document."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "enum": sorted(POLICY_FILES),
                    "description": "The filename of the policy to read (e.g., 'refund.md')."
                }
            },
            "required": ["filename"]
        }
    }
]

SUBAGENT_DISPATCH = {
    "read_policy": read_policy,
}


# ---------------------------------------------------------------------------
# Tool: plan_subtasks — available to the coordinator for decomposition
# ---------------------------------------------------------------------------

COORDINATOR_TOOLS = [
    {
        "name": "plan_subtasks",
        "description": (
            "Decompose a complex question into independent subtasks. "
            "Each subtask will be handled by an isolated subagent that has access "
            "to a read_policy tool. Return a list of brief strings, one per subtask. "
            "Each brief should be a self-contained instruction for the subagent."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "subtasks": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of subtask briefs, one per subagent."
                }
            },
            "required": ["subtasks"]
        }
    }
]


# ---------------------------------------------------------------------------
# subagent() — the M1 agentic loop in isolation
# ---------------------------------------------------------------------------

def subagent(brief: str, tools: list, tool_dispatch: dict) -> str:
    """
    Run an isolated agentic loop for a single subtask.

    The subagent starts with a BLANK messages list containing only the brief.
    It has NO access to the coordinator's conversation or other subagents'
    conversations.  That isolation is the whole point.
    """

    # ┌──────────────────────────────────────────────────────────────────┐
    # │ EXAM NOTE: In this raw Messages API lab there is no built-in     │
    # │ subagent primitive. The later Agent SDK lab uses AgentDefinition │
    # │ and Task; here YOUR dispatch starts another isolated loop.       │
    # │                                                                │
    # │ Isolation is WHY you split agents; parallelism is a bonus.     │
    # │ Each subagent sees ONLY its brief — nothing else.  This        │
    # │ prevents cross-contamination between tasks.                    │
    # └──────────────────────────────────────────────────────────────────┘

    # The brief is the ONLY input — that one line is the isolation principle
    messages = [{"role": "user", "content": brief}]

    system_prompt = (
        "You are a helpful assistant that reads and summarises policy documents. "
        "Use the read_policy tool to access the policy file, then provide a clear summary."
    )

    steps = 0
    while True:
        steps += 1
        if steps > MAX_ITERATIONS:
            return "[ERROR] Subagent max iterations exceeded."

        resp = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1024,
            system=system_prompt,
            tools=tools,
            messages=messages,
        )

        if resp.stop_reason == "end_turn":
            final_text = ""
            for block in resp.content:
                if hasattr(block, "text"):
                    final_text += block.text
            return final_text

        elif resp.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": resp.content})

            tool_results = []
            for block in resp.content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input
                    tool_use_id = block.id

                    if tool_name in tool_dispatch:
                        result = tool_dispatch[tool_name](**tool_input)
                    else:
                        result = f"Unknown tool: {tool_name}"

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": result,
                    })

            messages.append({"role": "user", "content": tool_results})

        else:
            return f"[ERROR] Unexpected stop_reason: {resp.stop_reason}"


# ---------------------------------------------------------------------------
# decompose() — asks the model to plan subtasks
# ---------------------------------------------------------------------------

def decompose(question: str) -> list[str]:
    """
    Ask the model to break a complex question into independent subtasks.
    Returns a list of subtask briefs.
    """

    # ┌──────────────────────────────────────────────────────────────────┐
    # │ EXAM NOTE: Multi-agent systems fail at the PLAN, not the       │
    # │ workers.  If decompose() produces bad subtasks, the subagents  │
    # │ will each succeed individually but the merged answer will be   │
    # │ wrong or incomplete.  This is the hardest failure to debug     │
    # │ because nothing errors.                                        │
    # └──────────────────────────────────────────────────────────────────┘

    messages = [
        {
            "role": "user",
            "content": (
                f"Break this question into independent subtasks that can be handled "
                f"in parallel. Each subtask should focus on one specific policy document. "
                f"Available policy files: refund.md, shipping.md, warranty.md.\n\n"
                f"Question: {question}"
            ),
        }
    ]

    resp = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1024,
        system="You are a task planner. Use the plan_subtasks tool to decompose the question.",
        tools=COORDINATOR_TOOLS,
        messages=messages,
    )

    # The coordinator gets stop_reason == "tool_use" and YOUR CODE maps
    # each subtask into a subagent() call
    if resp.stop_reason == "tool_use":
        for block in resp.content:
            if block.type == "tool_use" and block.name == "plan_subtasks":
                subtasks = block.input.get("subtasks", [])

                if BREAK_DECOMPOSITION and len(subtasks) > 2:
                    # Artificially drop one subtask to demonstrate the failure mode:
                    # two of three subagents run, both succeed, nothing errors,
                    # but the answer is confidently INCOMPLETE.
                    dropped = subtasks.pop()
                    print(f"\n  [BREAK_DECOMPOSITION] Dropped subtask: \"{dropped}\"")
                    print(f"  Only {len(subtasks)} of 3 subtasks will run.")

                return subtasks

    # Fallback: if the model doesn't use the tool, return a default plan
    return [
        "Read refund.md and summarise the refund policy.",
        "Read shipping.md and summarise the shipping policy.",
        "Read warranty.md and summarise the warranty policy.",
    ]


# ---------------------------------------------------------------------------
# run() — the coordinator
# ---------------------------------------------------------------------------

def run(question: str) -> str:
    """
    Coordinator that:
    1. Decomposes the question into subtasks.
    2. Spawns subagents in parallel.
    3. Merges their outputs into a final answer.
    """

    print(f"\n{'='*70}")
    print(f"  COORDINATOR: Decomposing question")
    print(f"{'='*70}")

    subtasks = decompose(question)
    if not subtasks:
        subtasks = [
            "Read refund.md and summarise the refund policy.",
            "Read shipping.md and summarise the shipping policy.",
            "Read warranty.md and summarise the warranty policy.",
        ]
    print(f"\n  Subtasks ({len(subtasks)}):")
    for i, st in enumerate(subtasks, 1):
        print(f"    {i}. {st}")

    # ┌──────────────────────────────────────────────────────────────────┐
    # │ EXAM NOTE: Hub-and-spoke — all communication goes through the  │
    # │ coordinator.  Subagents NEVER talk to each other directly.     │
    # │ Brief in is the only channel, final message out the only       │
    # │ return.                                                        │
    # └──────────────────────────────────────────────────────────────────┘

    # Run subagents concurrently
    print(f"\n  Spawning {len(subtasks)} subagents in parallel...")

    subagent_results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(subtasks)) as executor:
        future_to_task = {
            executor.submit(
                subagent, brief, SUBAGENT_TOOLS, SUBAGENT_DISPATCH
            ): brief
            for brief in subtasks
        }

        for future in concurrent.futures.as_completed(future_to_task):
            brief = future_to_task[future]
            try:
                result = future.result()
                subagent_results[brief] = result
                print(f"\n  Subagent completed: \"{brief[:50]}...\"")
            except Exception as e:
                subagent_results[brief] = f"[ERROR] Subagent failed: {e}"
                print(f"\n  Subagent FAILED: \"{brief[:50]}...\" -> {e}")

    # Merge results — only final messages merge into the coordinator's summary
    print(f"\n{'='*70}")
    print(f"  COORDINATOR: Merging {len(subagent_results)} subagent results")
    print(f"{'='*70}")

    merged_input = f"Original question: {question}\n\n"
    merged_input += "Here are the results from the subagents:\n\n"
    for i, (brief, result) in enumerate(subagent_results.items(), 1):
        merged_input += f"--- Subagent {i}: {brief} ---\n{result}\n\n"
    merged_input += (
        "Please synthesise these into a single comparative answer that addresses "
        "the original question."
    )

    # Final merge call
    merge_resp = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=2048,
        system="You are a helpful assistant. Synthesise the subagent reports into a clear, comparative summary.",
        messages=[{"role": "user", "content": merged_input}],
    )

    final_text = ""
    for block in merge_resp.content:
        if hasattr(block, "text"):
            final_text += block.text

    print(f"\n{'='*70}")
    print(f"  FINAL MERGED ANSWER")
    print(f"{'='*70}")
    print(final_text)

    return final_text


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 70)
    print("M5 — Multi-Agent Coordinator")
    print("=" * 70)
    run("Compare our refund, shipping and warranty terms")


# ┌─────────────────────────────────────────────────────────────────────────┐
# │ ✅ CHECKPOINT                                                          │
# │                                                                        │
# │ Expected behaviour:                                                    │
# │  • Coordinator decomposes the question into 3 subtasks.               │
# │  • 3 blank-slate subagents run in parallel, each reading one policy   │
# │    file (refund.md, shipping.md, warranty.md).                        │
# │  • Each subagent produces an independent summary.                     │
# │  • Coordinator merges all 3 into one comparative answer.              │
# │                                                                        │
# │ With BREAK_DECOMPOSITION = True:                                      │
# │  • Only 2 of 3 subtasks run.  Both succeed.  Nothing errors.         │
# │  • But the final answer is confidently INCOMPLETE — it covers only   │
# │    2 of the 3 policies.  This is the multi-agent failure mode:       │
# │    the plan was wrong, not the workers.                               │
# │                                                                        │
# │ Key takeaways:                                                         │
# │  1. A subagent is NOT a primitive — it's just another agent loop.     │
# │  2. Isolation is WHY you split agents; parallelism is a bonus.        │
# │  3. Hub-and-spoke: all communication through the coordinator.         │
# │  4. Multi-agent systems fail at the plan, not the workers.            │
# │  5. Brief in = only channel, final message out = only return.         │
# └─────────────────────────────────────────────────────────────────────────┘
