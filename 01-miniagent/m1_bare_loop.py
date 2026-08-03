"""
MiniAgent M1 — The Bare Agentic Loop
=====================================

THE USE CASE
------------
Input:  A natural-language question that requires a tool call to answer.
Output: A final natural-language answer after the model has used the tool.
Target: "What's the weather in Paris, and should I pack a coat?"
        -> model calls get_weather("Paris") -> gets "22 C and sunny in Paris"
        -> model replies with a final answer recommending no coat needed.

This file implements the MINIMAL agentic loop: call the model, check
stop_reason, dispatch tool if needed, append results, repeat.
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
# Tool definition — one hardcoded tool: get_weather
# ---------------------------------------------------------------------------

def get_weather(city: str) -> str:
    """Fake weather implementation for demonstration."""
    return f"22°C and sunny in {city}"


# ┌──────────────────────────────────────────────────────────────────────┐
# │ EXAM NOTE: Tool schemas are plain JSON dicts sent to the API.       │
# │ The model NEVER executes tools — YOUR code does.  The schema only   │
# │ tells the model what it CAN request.                                │
# └──────────────────────────────────────────────────────────────────────┘
tools = [
    {
        "name": "get_weather",
        "description": "Get the current weather for a given city.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "The city to get the weather for."
                }
            },
            "required": ["city"]
        }
    }
]

system_prompt = "You are a helpful assistant."


def run(user_msg: str) -> str:
    """
    The bare agentic loop.

    1. Append user message to messages list.
    2. Call the API.
    3. Branch on stop_reason:
       - "end_turn" -> extract text, print, return.
       - "tool_use" -> execute tool, append results, loop.
    """

    # ┌──────────────────────────────────────────────────────────────────┐
    # │ EXAM NOTE: The `messages` list IS the memory — the API is       │
    # │ stateless.  Every call sends the FULL conversation so far.      │
    # │ There is no session, no server-side state.                      │
    # └──────────────────────────────────────────────────────────────────┘
    messages = [{"role": "user", "content": user_msg}]
    step = 0

    while True:
        step += 1
        print(f"\n--- Step {step}: Calling model ---")

        resp = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1024,
            system=system_prompt,
            tools=tools,
            messages=messages,
        )

        # ┌──────────────────────────────────────────────────────────────┐
        # │ EXAM NOTE: `stop_reason` is the ONLY signal for loop        │
        # │ control — NEVER parse the text to decide whether to loop.   │
        # │ The model explicitly signals "I want to use a tool" via     │
        # │ stop_reason == "tool_use".                                  │
        # └──────────────────────────────────────────────────────────────┘
        if resp.stop_reason == "end_turn":
            # Extract the final text answer
            final_text = ""
            for block in resp.content:
                if hasattr(block, "text"):
                    final_text += block.text
            print(f"\nFinal answer:\n{final_text}")
            return final_text

        elif resp.stop_reason == "tool_use":
            # ┌──────────────────────────────────────────────────────────┐
            # │ EXAM NOTE: Always append the FULL assistant response    │
            # │ before the tool_result.  The API requires alternating   │
            # │ user/assistant turns, and the tool_result is a "user"   │
            # │ message.  Skipping the assistant message breaks the     │
            # │ conversation structure.                                 │
            # └──────────────────────────────────────────────────────────┘
            messages.append({"role": "assistant", "content": resp.content})

            # Find and execute tool_use blocks
            for block in resp.content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input

                    # ┌──────────────────────────────────────────────────┐
                    # │ EXAM NOTE: `tool_use` blocks contain `id`,      │
                    # │ `name`, `input`.  The `id` MUST match in the    │
                    # │ corresponding `tool_result` — it is the link    │
                    # │ between request and response.                   │
                    # └──────────────────────────────────────────────────┘
                    tool_use_id = block.id

                    print(f"  Tool call: {tool_name}({json.dumps(tool_input)})")

                    # Dispatch to the hardcoded function
                    if tool_name == "get_weather":
                        result = get_weather(**tool_input)
                    else:
                        result = f"Unknown tool: {tool_name}"

                    print(f"  Tool result: {result}")

                    # Append the tool result as a user message
                    messages.append({
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_use_id,
                                "content": result,
                            }
                        ],
                    })
        else:
            print(f"Unexpected stop_reason: {resp.stop_reason}")
            break

    return ""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 70)
    print("M1 — Bare Agentic Loop")
    print("=" * 70)
    run("What's the weather in Paris, and should I pack a coat?")


# ┌─────────────────────────────────────────────────────────────────────────┐
# │ ✅ CHECKPOINT                                                          │
# │                                                                        │
# │ Expected behaviour:                                                    │
# │  • Step 1: model returns stop_reason="tool_use", calls get_weather     │
# │    with city="Paris".                                                  │
# │  • Step 2: model returns stop_reason="end_turn" with a natural-        │
# │    language answer incorporating "22°C and sunny" and advising          │
# │    no coat is needed.                                                  │
# │  • The loop executes exactly TWICE — one tool call, one final answer.  │
# │  • If you see step 3+, something is wrong with the append logic.       │
# │                                                                        │
# │ Key takeaways:                                                         │
# │  1. stop_reason is the ONLY loop-control signal.                       │
# │  2. messages list is the memory (API is stateless).                    │
# │  3. Full assistant response must be appended before tool_result.       │
# │  4. tool_use_id must match between request and result.                 │
# └─────────────────────────────────────────────────────────────────────────┘
