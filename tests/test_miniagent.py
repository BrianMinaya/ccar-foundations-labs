"""Offline checks for tool recovery and coordinator boundaries."""

import asyncio
import json

import m4_structured_errors as errors
import m5_coordinator as coordinator
import m7_agent_sdk_support as sdk_support


def test_retryable_error_retries_locally_with_exponential_delay():
    delays = []
    errors._transient_call_counts.clear()
    result, attempts = errors.execute_with_retry(
        "lookup_order", {"order_id": "7777"}, sleep=delays.append
    )
    assert result["status"] == "success"
    assert attempts == 2
    assert delays == [0.25]


def test_non_retryable_error_does_not_sleep():
    delays = []
    result, attempts = errors.execute_with_retry(
        "lookup_order", {"order_id": "abc"}, sleep=delays.append
    )
    assert result["error_category"] == "validation"
    assert attempts == 1
    assert delays == []


def test_not_found_is_successful_empty_result():
    result = errors.lookup_order("5555")
    assert result == {
        "status": "success",
        "data": None,
        "count": 0,
        "message": "No order found with ID 5555",
    }


def test_policy_reader_rejects_traversal():
    rejected = json.loads(coordinator.read_policy("../README.md"))
    assert rejected["status"] == "error"
    assert "allowlist" in rejected["message"]
    assert "Refund" in coordinator.read_policy("refund.md")


def test_agent_sdk_hook_enforces_refund_prerequisite():
    sdk_support.STATE.update({"verified_customer_id": None, "order_id": None})
    hook_result = asyncio.run(sdk_support.enforce_refund_prerequisites(
        {
            "tool_name": "mcp__support__process_refund",
            "tool_input": {"order_id": "8891", "amount": 50.0},
        },
        None,
        {"signal": None},
    ))
    output = hook_result["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"
    assert output["hookEventName"] == "PreToolUse"
