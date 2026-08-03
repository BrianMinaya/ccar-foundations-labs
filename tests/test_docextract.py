"""Offline schema, eval, calibration, and batch policy tests."""

from jsonschema import Draft202012Validator
import pytest

from m2_schema import INVOICE_TOOL, validate_extraction_payload
from m3_fewshot import score_line_items
from m5_batch import (
    build_batch_requests,
    build_synthetic_workload,
    choose_processing_mode,
    select_resubmissions,
)
from m6_calibration import build_review_queue, evaluate_routing, stratified_sample


def valid_payload() -> dict:
    confidence = {
        "invoice_number": 0.9,
        "date": 0.9,
        "vendor": 0.9,
        "customer": 0.9,
        "po_number": 0.8,
        "line_items": 0.9,
        "subtotal": 0.9,
        "tax": 0.9,
        "total": 0.9,
    }
    return {
        "invoice_number": "INV-1",
        "date": "2026-08-03",
        "vendor": "Vendor",
        "customer": "Customer",
        "po_number": None,
        "line_items": [{"description": "Design (x10)", "amount": 100.0}],
        "subtotal": 100.0,
        "tax": 20.0,
        "total": 120.0,
        "invoice_kind": "services",
        "other_kind_detail": None,
        "confidence": 0.9,
        "field_confidence": confidence,
    }


def test_strict_is_on_tool_and_schema_is_valid():
    assert INVOICE_TOOL["strict"] is True
    assert "strict" not in INVOICE_TOOL["input_schema"]
    Draft202012Validator.check_schema(INVOICE_TOOL["input_schema"])
    Draft202012Validator(INVOICE_TOOL["input_schema"]).validate(valid_payload())


def test_pydantic_enforces_enum_other_contract_and_bounds():
    payload = valid_payload()
    payload["invoice_kind"] = "other"
    with pytest.raises(ValueError, match="other_kind_detail"):
        validate_extraction_payload(payload)

    payload = valid_payload()
    payload["confidence"] = 1.2
    with pytest.raises(ValueError):
        validate_extraction_payload(payload)


def test_fewshot_metric_moves_when_target_description_is_wrong():
    truth = [{"description": "Business cards (500)", "amount": 45.0}]
    wrong = [{"description": "Business cards", "amount": 45.0}]
    score = score_line_items(wrong, truth)
    assert score["amounts_correct"] == 1
    assert score["descriptions_correct"] == 0


def test_batch_workload_resubmission_and_sla_policy():
    workload = build_synthetic_workload({"a": "A", "b": "B"}, size=100)
    assert len(workload) == 100
    assert len(set(workload)) == 100
    requests = build_batch_requests({"a": "A", "b": "B"})
    retry = select_resubmissions(requests, {"a": "succeeded", "b": "expired"})
    assert [request["custom_id"] for request in retry] == ["b"]
    assert choose_processing_mode(blocking=True, deadline_hours=None) == "synchronous"
    assert choose_processing_mode(blocking=False, deadline_hours=12) == "synchronous"
    assert choose_processing_mode(blocking=False, deadline_hours=48) == "batch"


def test_review_routing_uses_validation_and_field_confidence_not_labels():
    low = valid_payload()
    low["field_confidence"]["po_number"] = 0.4
    high = valid_payload()
    queue = build_review_queue(
        {"low": low, "high": high},
        {"low": True, "high": False},
    )
    reasons = {item["doc_id"]: item["reason"] for item in queue}
    assert reasons["high"].startswith("Validation failed")
    assert "po_number" in reasons["low"]

    sample = stratified_sample(
        ["a1", "a2", "b1", "b2"],
        {"a1": "a", "a2": "a", "b1": "b", "b2": "b"},
        per_stratum=1,
    )
    assert len(sample) == 2
    assert {item[0] for item in sample} == {"a", "b"}

    metrics = evaluate_routing(
        [{"doc_id": "wrong"}],
        {
            "wrong": {field: False for field in (
                "invoice_number", "date", "vendor", "customer",
                "po_number", "subtotal", "tax", "total"
            )},
            "right": {field: True for field in (
                "invoice_number", "date", "vendor", "customer",
                "po_number", "subtotal", "tax", "total"
            )},
        },
    )
    assert metrics == {"escapes": 0, "false_alarms": 0}
