"""
MiniAgent M3 — Tool Description Quality Test
==============================================

THE USE CASE
------------
Input:  Ambiguous natural-language questions where the correct tool depends
        on subtle cues (like ID format).
Output: Routing accuracy scores comparing vague vs. precise tool descriptions.
Target: Round A (vague descriptions) misroutes "Can you check 8891 for me?"
        Round B (5-part checklist descriptions) fixes that misroute.

This file demonstrates that TOOL DESCRIPTIONS are the primary mechanism
LLMs use for tool selection, and that misrouting is a description bug,
not a model bug.
"""

import os
import json
import anthropic
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the shared projects root (two levels up)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

client = anthropic.Anthropic()

# ---------------------------------------------------------------------------
# Fake tool implementations (same for both rounds)
# ---------------------------------------------------------------------------

def get_customer(customer_id: str) -> str:
    return json.dumps({
        "customer_id": customer_id,
        "name": "Jane Doe",
        "email": "jane@example.com",
        "status": "active"
    })


def lookup_order(order_id: str) -> str:
    return json.dumps({
        "order_id": order_id,
        "status": "shipped",
        "total": "£85.00",
        "items": ["Widget A", "Gadget B"]
    })


TOOL_DISPATCH = {
    "get_customer": get_customer,
    "lookup_order": lookup_order,
}

# ---------------------------------------------------------------------------
# Round A — Vague descriptions
# ---------------------------------------------------------------------------

# ┌──────────────────────────────────────────────────────────────────────┐
# │ EXAM NOTE: Misrouting is a DESCRIPTION bug, not a model bug.       │
# │ The model can only choose tools based on what the descriptions     │
# │ tell it.  If descriptions are vague, the model guesses.            │
# └──────────────────────────────────────────────────────────────────────┘

TOOLS_ROUND_A = [
    {
        "name": "get_customer",
        "description": "Gets customer info.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "string",
                    "description": "The customer ID."
                }
            },
            "required": ["customer_id"]
        }
    },
    {
        "name": "lookup_order",
        "description": "Looks up order info.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "The order ID."
                }
            },
            "required": ["order_id"]
        }
    },
]

# ---------------------------------------------------------------------------
# Round B — 5-part checklist descriptions
# ---------------------------------------------------------------------------

# ┌──────────────────────────────────────────────────────────────────────┐
# │ EXAM NOTE: The 5-part checklist for tool descriptions:             │
# │  1. Purpose  — what does this tool do?                             │
# │  2. Input format — what shape/format does the input take?          │
# │  3. When to use — what user intent maps to this tool?              │
# │  4. Edge cases — what tricky situations exist?                     │
# │  5. Boundary — "Use THIS tool, NOT <other>, when..."              │
# │ Part 5 (boundary) does MOST of the disambiguation work.           │
# └──────────────────────────────────────────────────────────────────────┘

TOOLS_ROUND_B = [
    {
        "name": "get_customer",
        "description": (
            "Purpose: Retrieve a customer profile including name, email, and account status. "
            "Input format: customer_id must be a string in the format 'CUST-XXXXX' (e.g., 'CUST-12345'). "
            "When to use: Use when the user asks about a customer, account holder, or person — "
            "any request involving a person's profile, membership, or account details. "
            "Edge cases: If the customer_id is not in CUST-XXXXX format, ask the user to confirm. "
            "Boundary: Use this tool, NOT lookup_order, when the identifier starts with 'CUST-'. "
            "If the identifier is a bare number (e.g., '8891') without the CUST- prefix, it is an order ID — use lookup_order instead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "string",
                    "description": "The customer ID in CUST-XXXXX format (e.g., 'CUST-12345')."
                }
            },
            "required": ["customer_id"]
        }
    },
    {
        "name": "lookup_order",
        "description": (
            "Purpose: Look up an order's status, total, and item list. "
            "Input format: order_id must be a string containing a numeric order ID (e.g., '8891'). "
            "When to use: Use when the user asks about an order, purchase, shipment status, "
            "or tracking — any request involving a transaction or delivery. "
            "Edge cases: If the user provides just a number without context (e.g., 'check 8891'), "
            "this is almost certainly an order ID — use this tool. "
            "Boundary: Use this tool, NOT get_customer, when the identifier is a bare number "
            "without the 'CUST-' prefix. Bare numeric IDs are ALWAYS order IDs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "The numeric order ID (e.g., '8891')."
                }
            },
            "required": ["order_id"]
        }
    },
]


# ---------------------------------------------------------------------------
# Test questions
# ---------------------------------------------------------------------------

TEST_QUESTIONS = [
    {
        "question": "Can you look up customer CUST-12345?",
        "expected_tool": "get_customer",
        "note": "Explicit CUST- prefix -> get_customer",
    },
    {
        "question": "What's the status of order 8891?",
        "expected_tool": "lookup_order",
        "note": "Explicit 'order' keyword -> lookup_order",
    },
    {
        "question": "Can you check 8891 for me?",
        "expected_tool": "lookup_order",
        "note": "Ambiguous! Bare number, no keyword. Only cue is ID format.",
    },
    {
        "question": "Find information about CUST-99999",
        "expected_tool": "get_customer",
        "note": "CUST- prefix -> get_customer",
    },
]

SYSTEM_PROMPT = (
    "You are a helpful assistant. You have access to two tools: "
    "get_customer (for customer lookups) and lookup_order (for order lookups). "
    "Always use the appropriate tool to answer the user's question."
)

NUM_TRIALS = 5


def run_trial(question: str, tools: list) -> str | None:
    """Run a single trial and return the tool name the model chose, or None."""
    messages = [{"role": "user", "content": question}]

    resp = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=512,
        system=SYSTEM_PROMPT,
        tools=tools,
        messages=messages,
        temperature=0.5,
    )

    if resp.stop_reason == "tool_use":
        for block in resp.content:
            if block.type == "tool_use":
                return block.name
    return None


def run_round(round_label: str, tools: list) -> dict:
    """Run all test questions with multiple trials. Return accuracy dict."""
    print(f"\n{'='*70}")
    print(f"  {round_label}")
    print(f"{'='*70}")

    results = {}
    total_correct = 0
    total_trials = 0

    for tq in TEST_QUESTIONS:
        question = tq["question"]
        expected = tq["expected_tool"]
        note = tq["note"]
        correct = 0

        print(f"\n  Q: \"{question}\"")
        print(f"     Expected: {expected}  ({note})")

        for trial in range(NUM_TRIALS):
            chosen = run_trial(question, tools)
            if chosen == expected:
                correct += 1
            print(f"     Trial {trial+1}: chose {chosen} {'✓' if chosen == expected else '✗'}")

        accuracy = correct / NUM_TRIALS
        results[question] = accuracy
        total_correct += correct
        total_trials += NUM_TRIALS
        print(f"     Accuracy: {correct}/{NUM_TRIALS} = {accuracy:.0%}")

    overall = total_correct / total_trials
    print(f"\n  Overall accuracy: {total_correct}/{total_trials} = {overall:.0%}")
    results["_overall"] = overall
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 70)
    print("M3 — Tool Description Quality Test")
    print("=" * 70)

    results_a = run_round("ROUND A — Vague Descriptions", TOOLS_ROUND_A)
    results_b = run_round("ROUND B — 5-Part Checklist Descriptions", TOOLS_ROUND_B)

    # ┌──────────────────────────────────────────────────────────────────┐
    # │ EXAM NOTE: Tool descriptions are the PRIMARY mechanism LLMs    │
    # │ use for tool selection.  The model doesn't see your code, your │
    # │ function names (beyond the schema name), or your comments.     │
    # │ The description is ALL it has.                                 │
    # └──────────────────────────────────────────────────────────────────┘

    ambiguous_q = "Can you check 8891 for me?"
    print(f"\n{'='*70}")
    print(f"  KEY COMPARISON: \"{ambiguous_q}\"")
    print(f"{'='*70}")
    print(f"  Round A accuracy: {results_a.get(ambiguous_q, 0):.0%}")
    print(f"  Round B accuracy: {results_b.get(ambiguous_q, 0):.0%}")


# ┌─────────────────────────────────────────────────────────────────────────┐
# │ ✅ CHECKPOINT                                                          │
# │                                                                        │
# │ Expected behaviour:                                                    │
# │  • Round A: Questions 1, 2, 4 mostly correct (explicit cues).         │
# │    Question 3 ("Can you check 8891 for me?") misroutes frequently     │
# │    — the model guesses because descriptions are too vague.            │
# │  • Round B: ALL questions route correctly, including Q3.              │
# │    The 5-part checklist, especially Part 5 (boundary: "use this NOT   │
# │    that when the ID is a bare number"), fixes the ambiguity.          │
# │                                                                        │
# │ If Round B still misroutes Q3, strengthen the boundary clause.        │
# │                                                                        │
# │ Key takeaways:                                                         │
# │  1. Misrouting = description bug, not model bug.                      │
# │  2. Part 5 (boundary) does most of the disambiguation work.           │
# │  3. Tool descriptions are the primary mechanism for tool selection.   │
# └─────────────────────────────────────────────────────────────────────────┘
