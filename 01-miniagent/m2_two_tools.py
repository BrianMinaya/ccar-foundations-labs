"""
MiniAgent M2 — Two-Tool Runner
================================

THE USE CASE
------------
Input:  A natural-language question that requires TWO different tools.
Output: A final answer that incorporates results from both tools.
Target: "What's the weather in Tokyo, and can you search our docs for the
         umbrella policy?"
        -> model calls get_weather("Tokyo") AND search_docs("umbrella policy")
           (possibly in the SAME response as two tool_use blocks)
        -> final answer merges both results.

This script imports the tool registry from m2_tools and runs an agentic
loop that handles multiple tool_use blocks per response, with a safety cap.
"""

import os
import sys
import json
import anthropic
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the shared projects root (two levels up)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Import the tool registry
from m2_tools import TOOLS, TOOL_DISPATCH, MAX_ITERATIONS

client = anthropic.Anthropic()

system_prompt = "You are a helpful assistant. You have access to weather and documentation search tools."


def run(user_msg: str) -> str:
    """
    Agentic loop with:
     - Multiple tool_use blocks per response
     - Step counter
     - MAX_ITERATIONS safety guard
    """

    messages = [{"role": "user", "content": user_msg}]
    steps = 0

    while True:
        steps += 1

        # ┌──────────────────────────────────────────────────────────────┐
        # │ EXAM NOTE: MAX_ITERATIONS is a hard safety cap.  Without    │
        # │ it, a broken tool_result append or a hallucinating model    │
        # │ will spin forever, burning tokens and money.                │
        # └──────────────────────────────────────────────────────────────┘
        if steps > MAX_ITERATIONS:
            print(f"\n{'!'*70}")
            print(f"!!! MAX_ITERATIONS ({MAX_ITERATIONS}) REACHED — ABORTING LOOP !!!")
            print(f"{'!'*70}")
            print("This usually means tool_results are not being appended correctly,")
            print("causing the model to repeat the same tool call forever.")
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
            # ┌──────────────────────────────────────────────────────────┐
            # │ EXAM NOTE: A SINGLE response can contain MULTIPLE       │
            # │ tool_use blocks.  You MUST iterate over ALL content     │
            # │ blocks, not just grab the first one.  The model may     │
            # │ decide to call get_weather AND search_docs in one turn. │
            # └──────────────────────────────────────────────────────────┘

            # Always append the full assistant response first
            messages.append({"role": "assistant", "content": resp.content})

            # Collect ALL tool results for this turn
            tool_results = []
            for block in resp.content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input
                    tool_use_id = block.id

                    print(f"  Tool call: {tool_name}({json.dumps(tool_input)})")

                    # Dispatch using the registry
                    if tool_name in TOOL_DISPATCH:
                        result = TOOL_DISPATCH[tool_name](**tool_input)
                    else:
                        result = f"Error: Unknown tool '{tool_name}'"

                    print(f"  Tool result: {result}")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": result,
                    })

            # EXPERIMENT: Comment out the tool_results append below
            #             -> the "forgetting loop"
            # Without this append, the model never sees the tool results,
            # so it keeps requesting the same tool call, looping until
            # MAX_ITERATIONS kills the run.  This is the most common bug
            # in hand-rolled agentic loops.
            messages.append({"role": "user", "content": tool_results})

        else:
            print(f"Unexpected stop_reason: {resp.stop_reason}")
            break

    return ""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 70)
    print("M2 — Two-Tool Runner")
    print("=" * 70)
    run("What's the weather in Tokyo, and can you search our docs for the umbrella policy?")


# ┌─────────────────────────────────────────────────────────────────────────┐
# │ ✅ CHECKPOINT                                                          │
# │                                                                        │
# │ Expected behaviour:                                                    │
# │  • steps == 2, NOT 20.                                                 │
# │    - Step 1: model returns two tool_use blocks (get_weather +          │
# │      search_docs) in one response.  Both are dispatched and results    │
# │      appended.                                                         │
# │    - Step 2: model returns end_turn with a merged final answer.        │
# │  • NOTE: The model MAY split them into two separate steps instead of   │
# │    bundling both tool calls in one response.  Either way, the loop     │
# │    handles it correctly because it iterates ALL content blocks.        │
# │  • If you see steps approaching 20, the tool_results append is         │
# │    broken — you've hit the "forgetting loop".                          │
# │                                                                        │
# │ EXPERIMENT: Comment out the `messages.append(...)` for tool_results    │
# │ and re-run.  Watch the model call the same tool 20 times, then abort.  │
# └─────────────────────────────────────────────────────────────────────────┘
