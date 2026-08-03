"""
MiniAgent M2 — Tool Registry Module
====================================

THE USE CASE
------------
Input:  (imported by other modules — no standalone execution)
Output: TOOLS list (schemas), TOOL_DISPATCH dict (name -> function),
        and MAX_ITERATIONS constant.
Target: Other scripts import `from m2_tools import TOOLS, TOOL_DISPATCH, MAX_ITERATIONS`
        and use them to drive a multi-tool agentic loop.

This module centralises tool definitions so that the agentic loop doesn't
need to know about individual tools.  Adding a new tool means adding a
schema + function here and nothing else.
"""

# ---------------------------------------------------------------------------
# Tool implementation functions
# ---------------------------------------------------------------------------

def get_weather(city: str) -> str:
    """Return fake weather data for a given city."""
    return f"22°C and sunny in {city}"


def search_docs(query: str) -> str:
    """Return fake documentation search results."""
    return f"Documentation result for: {query}"


# ---------------------------------------------------------------------------
# Tool schemas (sent to the API)
# ---------------------------------------------------------------------------

# ┌──────────────────────────────────────────────────────────────────────┐
# │ EXAM NOTE: Schemas are the ONLY thing the model sees about your     │
# │ tools.  The model never sees your Python functions.  If the schema  │
# │ is wrong or vague, the model will misuse the tool.                  │
# └──────────────────────────────────────────────────────────────────────┘

TOOLS = [
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
    },
    {
        "name": "search_docs",
        "description": "Search internal documentation for a given query string. Returns matching document excerpts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to look up in the documentation."
                }
            },
            "required": ["query"]
        }
    },
]


# ---------------------------------------------------------------------------
# Dispatch table — maps tool name to implementation function
# ---------------------------------------------------------------------------

# ┌──────────────────────────────────────────────────────────────────────┐
# │ EXAM NOTE: The dispatch dict is the bridge between the model's      │
# │ tool_use request and YOUR code.  The model says "call search_docs", │
# │ your loop looks up TOOL_DISPATCH["search_docs"] and calls it.       │
# └──────────────────────────────────────────────────────────────────────┘

TOOL_DISPATCH = {
    "get_weather": get_weather,
    "search_docs": search_docs,
}


# ---------------------------------------------------------------------------
# Safety constant
# ---------------------------------------------------------------------------

# ┌──────────────────────────────────────────────────────────────────────┐
# │ EXAM NOTE: MAX_ITERATIONS is a hard safety cap.  Without it, a     │
# │ misbehaving model (or a bug in tool_result appending) can spin      │
# │ forever, burning tokens and money.  20 is generous for most tasks.  │
# └──────────────────────────────────────────────────────────────────────┘

MAX_ITERATIONS = 20


# ┌─────────────────────────────────────────────────────────────────────────┐
# │ ✅ CHECKPOINT                                                          │
# │                                                                        │
# │ This module exports three things:                                      │
# │  • TOOLS        — list of tool schemas (len == 2)                      │
# │  • TOOL_DISPATCH — dict mapping tool name to callable (len == 2)       │
# │  • MAX_ITERATIONS — int safety cap (== 20)                             │
# │                                                                        │
# │ No API calls, no .env loading — this is a pure data/function module.   │
# │ Other scripts (m2_two_tools.py, etc.) import from here.               │
# └─────────────────────────────────────────────────────────────────────────┘
