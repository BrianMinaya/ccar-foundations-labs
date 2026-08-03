"""
MiniAgent M4 — Error-as-Data Pattern (Structured Errors)
=========================================================

THE USE CASE
------------
Input:  Order IDs that trigger different error categories.
Output: The model handles each category appropriately — retries transient
        errors, reports validation/permission errors, and correctly states
        "no order found" for not_found (without retrying).
Target:
  - order "abc"  -> validation error, no retry, model reports invalid format
  - order "7777" -> transient error on first call, retry succeeds, model
                    reports order details
  - order "9999" -> permission error, no retry, model reports access denied
  - order "5555" -> not_found (status: success, data: None), model says
                    "there is no order 5555" — no retry, no error

This file demonstrates that tool errors should be DATA (structured dicts),
never exceptions and never bare strings.
"""

import os
import json
import time
import anthropic
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the shared projects root (two levels up)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

client = anthropic.Anthropic()

# ---------------------------------------------------------------------------
# Stateful transient-error simulation
# ---------------------------------------------------------------------------

_transient_call_counts: dict[str, int] = {}


def lookup_order(order_id: str) -> dict:
    """
    Look up an order by ID.  Returns a structured dict in EVERY case —
    never a bare string, never raises an exception.
    """
    global _transient_call_counts

    # ┌──────────────────────────────────────────────────────────────────┐
    # │ EXAM NOTE: Errors are data, not exceptions.                    │
    # │  - Raising kills the run.                                      │
    # │  - except:pass produces a confident wrong answer (WORSE).      │
    # │  - Structured error dicts let the model reason about what      │
    # │    happened and respond appropriately.                         │
    # └──────────────────────────────────────────────────────────────────┘

    # Category 1: VALIDATION — malformed input
    if not order_id.isdigit():
        return {
            "status": "error",
            "error_category": "validation",
            "is_retryable": False,
            "message": "Invalid order ID format. Expected numeric ID.",
        }

    # Category 2: TRANSIENT — temporary failure, succeeds on retry
    if order_id == "7777":
        _transient_call_counts[order_id] = _transient_call_counts.get(order_id, 0) + 1
        if _transient_call_counts[order_id] <= 1:
            return {
                "status": "error",
                "error_category": "transient",
                "is_retryable": True,
                "message": "Service temporarily unavailable. Please retry.",
            }
        else:
            # Second call succeeds
            return {
                "status": "success",
                "data": {
                    "order_id": "7777",
                    "customer": "Alice Smith",
                    "total": "£142.50",
                    "status": "delivered",
                    "items": ["Bluetooth Speaker", "USB-C Cable"],
                },
                "count": 1,
                "message": "Order found.",
            }

    # Category 3: PERMISSION — access denied
    if order_id == "9999":
        return {
            "status": "error",
            "error_category": "permission",
            "is_retryable": False,
            "message": "Access denied. Insufficient permissions for this order.",
        }

    # Category 4: NOT FOUND — valid query, no results
    # ┌──────────────────────────────────────────────────────────────────┐
    # │ EXAM NOTE: "I couldn't look" != "I looked, there's nothing"    │
    # │ This is the MOST-TESTED distinction on the exam.               │
    # │                                                                │
    # │ not_found is status: "success" with data: None, count: 0.     │
    # │ It is NOT an error — the tool successfully executed and the    │
    # │ answer is "nothing exists."                                    │
    # │                                                                │
    # │ isError: false for not_found — it's a valid result, not a     │
    # │ failure.                                                       │
    # └──────────────────────────────────────────────────────────────────┘
    if order_id == "5555":
        return {
            "status": "success",
            "data": None,
            "count": 0,
            "message": "No order found with ID 5555",
        }

    # Default: found
    return {
        "status": "success",
        "data": {
            "order_id": order_id,
            "customer": "John Doe",
            "total": "£85.00",
            "status": "processing",
            "items": ["Widget A"],
        },
        "count": 1,
        "message": "Order found.",
    }


def execute_with_retry(
    tool_name: str,
    tool_input: dict,
    *,
    max_retries: int = 2,
    base_delay: float = 0.25,
    sleep=time.sleep,
) -> tuple[dict, int]:
    """Execute a tool and locally recover retryable failures with backoff."""
    if tool_name not in TOOL_DISPATCH:
        return ({
            "status": "error",
            "error_category": "system",
            "is_retryable": False,
            "message": f"Unknown tool: {tool_name}",
        }, 1)

    attempts = 0
    while True:
        attempts += 1
        result = TOOL_DISPATCH[tool_name](**tool_input)
        retryable = result.get("status") == "error" and result.get("is_retryable")
        if not retryable or attempts > max_retries:
            return result, attempts

        delay = base_delay * (2 ** (attempts - 1))
        print(f"  Transient error — retrying locally in {delay:.2f}s")
        sleep(delay)


# ---------------------------------------------------------------------------
# Anti-pattern comment
# ---------------------------------------------------------------------------
# ANTI-PATTERN: Returning {results: [], status: "success"} on a real failure
# silently produces a confident wrong answer.  The model sees "success" and
# "no results" and fabricates an answer like "your order is on its way!"
# instead of saying "I couldn't retrieve that information."
# ALWAYS distinguish between "success with no data" and "failure."
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Tool schema and dispatch
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "lookup_order",
        "description": (
            "Look up an order by its numeric ID. Returns a structured response with "
            "status, data, and error information. The status field will be 'success' or "
            "'error'. On error, check error_category and is_retryable to decide next steps. "
            "On success with data=None and count=0, the order simply does not exist."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "The numeric order ID to look up (e.g., '8891')."
                }
            },
            "required": ["order_id"]
        }
    }
]

TOOL_DISPATCH = {
    "lookup_order": lookup_order,
}

system_prompt = (
    "You are a helpful assistant that looks up orders. "
    "When you receive a tool response, examine the 'status', 'error_category', "
    "and 'is_retryable' fields carefully. "
    "If is_retryable is true, retry the tool call. "
    "If the status is 'success' but data is null/None, tell the user the order was not found. "
    "Never guess or fabricate order information."
)

MAX_ITERATIONS = 10


def run(user_msg: str) -> str:
    """Agentic loop with structured error handling."""
    messages = [{"role": "user", "content": user_msg}]
    steps = 0

    while True:
        steps += 1
        if steps > MAX_ITERATIONS:
            print(f"\n!!! MAX_ITERATIONS ({MAX_ITERATIONS}) reached — aborting !!!")
            return "[ERROR] Max iterations exceeded."

        print(f"\n--- Step {steps}: Calling model ---")

        resp = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1024,
            system=system_prompt,
            tools=TOOLS,
            messages=messages,
        )

        if resp.stop_reason == "end_turn":
            final_text = ""
            for block in resp.content:
                if hasattr(block, "text"):
                    final_text += block.text
            print(f"\nFinal answer:\n{final_text}")
            return final_text

        elif resp.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": resp.content})

            tool_results = []
            for block in resp.content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input
                    tool_use_id = block.id

                    print(f"  Tool call: {tool_name}({json.dumps(tool_input)})")

                    result_dict, attempts = execute_with_retry(tool_name, tool_input)
                    result_dict["attempts"] = attempts
                    result_str = json.dumps(result_dict)

                    print(f"  Tool result: {result_str}")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": result_str,
                        # Protocol-level signal: failures are still structured data.
                        "is_error": result_dict.get("status") == "error",
                    })

            messages.append({"role": "user", "content": tool_results})

        else:
            print(f"Unexpected stop_reason: {resp.stop_reason}")
            break

    return ""


# ---------------------------------------------------------------------------
# Main — Test all four error categories
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 70)
    print("M4 — Structured Errors")
    print("=" * 70)

    test_cases = [
        ("Validation error", "Look up order abc"),
        ("Transient error (retry)", "Look up order 7777"),
        ("Permission error", "Look up order 9999"),
        ("Not found", "Look up order 5555"),
    ]

    for label, query in test_cases:
        print(f"\n{'='*70}")
        print(f"  TEST: {label}")
        print(f"  Query: \"{query}\"")
        print(f"{'='*70}")
        # Reset transient counter for each test
        _transient_call_counts.clear()
        run(query)


# ┌─────────────────────────────────────────────────────────────────────────┐
# │ ✅ CHECKPOINT                                                          │
# │                                                                        │
# │ Expected behaviour:                                                    │
# │  • order "abc"  -> validation error, model says "invalid format",     │
# │    no retry.                                                           │
# │  • order "7777" -> first call returns transient error (is_retryable:  │
# │    true), model retries, second call succeeds, model reports order    │
# │    details (Alice Smith, £142.50, delivered).                          │
# │  • order "9999" -> permission error, model says "access denied",     │
# │    no retry.                                                           │
# │  • order "5555" -> status:"success", data:None, count:0.             │
# │    Model says "there is no order 5555" — NOT an error, NOT retried.  │
# │    This is the critical distinction: the tool SUCCEEDED, the answer   │
# │    is simply "nothing exists."                                        │
# │                                                                        │
# │ Key takeaways:                                                         │
# │  1. "I couldn't look" != "I looked, there's nothing"                 │
# │  2. Errors are data, not exceptions.                                  │
# │  3. isError: false for not_found — it's a valid result.              │
# │  4. Anti-pattern: {results:[], status:"success"} on real failure     │
# │     silently produces confident wrong answers.                        │
# └─────────────────────────────────────────────────────────────────────────┘
