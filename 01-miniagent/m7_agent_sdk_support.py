"""Real Claude Agent SDK support workflow with tools, hooks, and handoff."""

import asyncio
import json
from typing import Any

from claude_agent_sdk import (
    ClaudeAgentOptions,
    HookMatcher,
    ResultMessage,
    create_sdk_mcp_server,
    query,
    tool,
)

STATE: dict[str, Any] = {"verified_customer_id": None, "order_id": None}
ORDERS = {
    "8891": {"customer_id": "cust_123", "total": 320.00, "status": "delivered"},
}


def tool_response(payload: dict, *, is_error: bool = False) -> dict:
    """Build a protocol-valid SDK MCP result."""
    result = {"content": [{"type": "text", "text": json.dumps(payload)}]}
    if is_error:
        result["is_error"] = True
    return result


@tool("get_customer", "Verify a customer by email before account actions.", {"email": str})
async def get_customer(args: dict) -> dict:
    if args["email"].casefold() != "jane@example.com":
        return tool_response({
            "status": "success", "data": None, "count": 0,
            "message": "No verified customer matched.",
        })
    STATE["verified_customer_id"] = "cust_123"
    return tool_response({
        "status": "success",
        "data": {"customer_id": "cust_123", "name": "Jane Doe", "verified": True},
        "count": 1,
    })


@tool("lookup_order", "Look up an order after customer verification.", {"order_id": str})
async def lookup_order(args: dict) -> dict:
    order = ORDERS.get(args["order_id"])
    if order is None:
        return tool_response({"status": "success", "data": None, "count": 0})
    if STATE["verified_customer_id"] != order["customer_id"]:
        return tool_response({
            "status": "error",
            "error_category": "prerequisite",
            "is_retryable": False,
            "message": "Verify the order's customer first.",
        }, is_error=True)
    STATE["order_id"] = args["order_id"]
    return tool_response({"status": "success", "data": order, "count": 1})


@tool(
    "process_refund",
    "Refund a verified, looked-up order. Requires order_id, amount, and reason.",
    {"order_id": str, "amount": float, "reason": str},
)
async def process_refund(args: dict) -> dict:
    order = ORDERS.get(args["order_id"])
    if STATE["order_id"] != args["order_id"] or order is None:
        return tool_response({
            "status": "error", "error_category": "prerequisite",
            "is_retryable": False, "message": "Look up this verified order first.",
        }, is_error=True)
    if args["amount"] <= 0 or args["amount"] > order["total"]:
        return tool_response({
            "status": "error", "error_category": "validation",
            "is_retryable": False, "message": "Refund amount is outside the order total.",
        }, is_error=True)
    return tool_response({
        "status": "success",
        "data": {"refund_id": "ref_4417", **args, "currency": "GBP"},
    })


@tool(
    "escalate_to_human",
    "Create a structured handoff when policy, permissions, or ambiguity blocks resolution.",
    {"reason": str, "attempted_actions": list[str]},
)
async def escalate_to_human(args: dict) -> dict:
    return tool_response({
        "status": "success",
        "handoff": {
            "reason": args["reason"],
            "attempted_actions": args["attempted_actions"],
            "case_facts": {
                "customer_id": STATE["verified_customer_id"],
                "order_id": STATE["order_id"],
            },
            "queue": "refund-specialist",
        },
    })


async def enforce_refund_prerequisites(input_data, _tool_use_id, _context) -> dict:
    """PreToolUse hook: prevent side effects unless verification is complete."""
    if input_data.get("tool_name") != "mcp__support__process_refund":
        return {}
    order_id = input_data.get("tool_input", {}).get("order_id")
    if not STATE["verified_customer_id"] or STATE["order_id"] != order_id:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    "Refund blocked: verify the customer and look up this order first."
                ),
            }
        }
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
        }
    }


support_server = create_sdk_mcp_server(
    name="support",
    version="1.0.0",
    tools=[get_customer, lookup_order, process_refund, escalate_to_human],
)


async def main() -> None:
    """Run the paid live lab; set ANTHROPIC_API_KEY before executing."""
    options = ClaudeAgentOptions(
        system_prompt=(
            "You are a support agent. Verify identity, look up the order, then act. "
            "Never invent tool results. Escalate with a structured handoff when blocked."
        ),
        mcp_servers={"support": support_server},
        allowed_tools=[
            "mcp__support__get_customer",
            "mcp__support__lookup_order",
            "mcp__support__process_refund",
            "mcp__support__escalate_to_human",
        ],
        hooks={
            "PreToolUse": [HookMatcher(
                matcher="mcp__support__process_refund",
                hooks=[enforce_refund_prerequisites],
            )]
        },
        max_turns=12,
        max_budget_usd=0.75,
    )
    prompt = (
        "Jane (jane@example.com) requests a GBP 50 refund on delivered order 8891 "
        "because one item arrived damaged. Complete the safe workflow."
    )
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            print(message.result)


if __name__ == "__main__":
    asyncio.run(main())
