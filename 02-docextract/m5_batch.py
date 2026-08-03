"""
DocExtract -- M5: Batch API
============================

THE USE CASE
------------
Input:  5 invoice text files, packed into a single Anthropic Batch API job.
Output: Structured extractions for all 5 docs, collected asynchronously,
        then validated as a second pass.
Target: Demonstrate the Batch API workflow -- create, poll, collect, validate.
        Same extraction quality as M2/M4, but ~50% cheaper and async.

The Batch API is for workloads where nothing is BLOCKED waiting for the
answer: overnight ingestion, backfills, eval runs, bulk document processing.
"""

import anthropic
import os
import time
import json
import glob
import argparse
from decimal import Decimal
from pathlib import Path
from dotenv import load_dotenv

from m2_schema import INVOICE_TOOL, validate_extraction_payload

# -- Load environment ----------------------------------------------------------
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

client = anthropic.Anthropic()
MODEL = "claude-haiku-4-5"

# -- Paths ---------------------------------------------------------------------
BASE_DIR = os.path.dirname(__file__)
DOCS_DIR = os.path.join(BASE_DIR, "docs")


def load_invoices() -> dict[str, str]:
    """Load all invoice text files from docs/ directory."""
    invoices = {}
    for filepath in sorted(glob.glob(os.path.join(DOCS_DIR, "invoice_*.txt"))):
        name = os.path.splitext(os.path.basename(filepath))[0]
        with open(filepath, "r", encoding="utf-8") as f:
            invoices[name] = f.read()
    return invoices


# +============================================================================+
# |  EXAM NOTE -- Batch API economics and constraints                          |
# |                                                                            |
# |  - ~50% cheaper on both input and output tokens                            |
# |  - Async processing, up to 24-hour window, no SLA                          |
# |  - Unfinished work expires after the window closes                         |
# |  - Decision rule: is anything BLOCKED waiting for the answer?              |
# |      Yes -> use synchronous Messages API                                   |
# |      No  -> use Batch API (overnight ingestion, backfills, eval runs)      |
# |                                                                            |
# |  - Batch API does NOT support multi-turn tool calling within a single      |
# |    request (no agentic loop). Each request is a single-turn exchange.      |
# |  - custom_id fields are for correlating request/response pairs.            |
# +============================================================================+


def build_batch_requests(invoices: dict[str, str]) -> list[dict]:
    """
    Build the list of batch request dicts.
    Each request has a custom_id and params matching the Messages API.
    """
    requests = []
    for name, text in invoices.items():
        # +====================================================================+
        # |  EXAM NOTE -- custom_id for correlating request/response pairs     |
        # |  The Batch API returns results tagged with the custom_id you set.  |
        # |  This is how you match results back to the original documents.     |
        # +====================================================================+
        request = {
            "custom_id": name,
            "params": {
                "model": MODEL,
                "max_tokens": 2048,
                "tools": [INVOICE_TOOL],
                "tool_choice": {"type": "tool", "name": "extract_invoice"},
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "Extract all fields from this invoice document. "
                            "Return null for any field not present -- do NOT "
                            "invent values. Convert dates to YYYY-MM-DD. "
                            "Correct obvious OCR errors in descriptions but "
                            "preserve amounts exactly as stated.\n\n"
                            f"---\n\n{text}"
                        ),
                    }
                ],
            },
        }
        requests.append(request)
    return requests


def build_synthetic_workload(
    invoices: dict[str, str],
    *,
    size: int = 100,
) -> dict[str, str]:
    """Repeat the fixture set into a uniquely keyed load-test workload."""
    if size < 1 or not invoices:
        return {}
    source = sorted(invoices.items())
    return {
        f"synthetic_{index + 1:03d}_{source[index % len(source)][0]}":
            source[index % len(source)][1]
        for index in range(size)
    }


def select_resubmissions(
    requests: list[dict],
    outcome_by_id: dict[str, str],
) -> list[dict]:
    """Return only errored, canceled, or expired requests for a new batch."""
    retryable_terminal_states = {"errored", "canceled", "expired"}
    return [
        request for request in requests
        if outcome_by_id.get(request["custom_id"]) in retryable_terminal_states
    ]


def choose_processing_mode(*, blocking: bool, deadline_hours: float | None) -> str:
    """Use sync when callers block or a hard deadline conflicts with no Batch SLA."""
    if blocking or (deadline_hours is not None and deadline_hours <= 24):
        return "synchronous"
    return "batch"


def create_batch(requests: list[dict]) -> str:
    """Create a batch job and return the batch ID."""
    print(f"  Creating batch with {len(requests)} requests...")
    batch = client.messages.batches.create(requests=requests)
    print(f"  Batch ID: {batch.id}")
    print(f"  Status:   {batch.processing_status}")
    return batch.id


def poll_batch(batch_id: str, max_wait: int = 600) -> bool:
    """
    Poll for batch completion with exponential backoff.
    Returns True if the batch ended, False if timed out.
    """
    # +========================================================================+
    # |  EXAM NOTE -- "ended" describes the JOB, not the requests              |
    # |  A batch can end with every request errored. The processing_status     |
    # |  tells you the job is done; you must inspect each result.type to       |
    # |  know if individual requests succeeded or failed.                      |
    # +========================================================================+
    delay = 2  # Start with 2 seconds
    elapsed = 0

    while elapsed < max_wait:
        batch = client.messages.batches.retrieve(batch_id)
        status = batch.processing_status

        if status == "ended":
            print(f"  Batch ended after ~{elapsed}s")
            # Print request counts if available
            counts = batch.request_counts
            print(f"  Request counts: "
                  f"succeeded={counts.succeeded}, "
                  f"errored={counts.errored}, "
                  f"canceled={counts.canceled}, "
                  f"expired={counts.expired}")
            return True

        print(f"  Status: {status} (waited ~{elapsed}s, next check in {delay}s)")
        time.sleep(delay)
        elapsed += delay
        delay = min(delay * 2, 60)  # Exponential backoff, cap at 60s

    print(f"  Timed out after {max_wait}s")
    return False


def collect_results(batch_id: str) -> dict[str, dict]:
    """
    Collect results from a completed batch.
    Returns a dict mapping custom_id -> extraction dict.
    """
    results = {}
    error_count = 0

    for result in client.messages.batches.results(batch_id):
        custom_id = result.custom_id

        # +====================================================================+
        # |  EXAM NOTE -- Always check result.result.type                      |
        # |  A batch ending does NOT mean every request succeeded. Each result |
        # |  can be "succeeded", "errored", "canceled", or "expired".          |
        # |  Always inspect before accessing the message.                      |
        # +====================================================================+
        if result.result.type == "succeeded":
            message = result.result.message
            extraction = None
            for block in message.content:
                if block.type == "tool_use":
                    extraction = validate_extraction_payload(block.input)
                    break

            if extraction:
                results[custom_id] = extraction
            else:
                print(f"  WARNING: {custom_id} succeeded but no tool_use block")
                error_count += 1
        else:
            print(f"  ERROR: {custom_id} result type = {result.result.type}")
            error_count += 1

    print(f"\n  Collected: {len(results)} succeeded, {error_count} failed")
    return results


# -- Validation (second pass) -------------------------------------------------

def validate_extraction(name: str, extraction: dict) -> dict:
    """
    Validate a single extraction. Returns a validation report dict.
    Same logic as M4 but returns a structured report for batch processing.
    """
    line_items = extraction.get("line_items", [])
    items_sum = sum((Decimal(str(item["amount"])) for item in line_items), Decimal("0"))
    tax_value = extraction.get("tax")
    tax = Decimal(str(tax_value)) if tax_value is not None else None
    subtotal = Decimal(str(extraction.get("subtotal")))
    total = Decimal(str(extraction.get("total")))
    tolerance = Decimal("0.01")

    report = {
        "doc_id": name,
        "items_sum": items_sum,
        "issues": [],
        "status": "PASS",
    }

    # Arithmetic check
    if tax is not None:
        expected_total = items_sum + tax
        if abs(expected_total - total) >= tolerance:
            report["issues"].append({
                "type": "CONFLICT",
                "message": (
                    f"items_sum ({items_sum:.2f}) + tax ({tax:.2f}) = "
                    f"{expected_total:.2f} != total ({total:.2f})"
                ),
                "items_sum": items_sum,
                "stated_total": total,
            })
            report["status"] = "CONFLICT"
    else:
        if abs(items_sum - subtotal) >= tolerance:
            report["issues"].append({
                "type": "CONFLICT",
                "message": (
                    f"items_sum ({items_sum:.2f}) != "
                    f"subtotal ({subtotal:.2f})"
                ),
                "items_sum": items_sum,
                "stated_subtotal": subtotal,
            })
            report["status"] = "CONFLICT"

    # Date format check
    date_str = extraction.get("date", "")
    try:
        from datetime import datetime
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        report["issues"].append({
            "type": "FORMAT_ERROR",
            "message": f"Date '{date_str}' is not YYYY-MM-DD",
        })
        if report["status"] == "PASS":
            report["status"] = "WARNING"

    # Required fields check
    for field in ["vendor", "customer"]:
        if not extraction.get(field):
            report["issues"].append({
                "type": "MISSING_REQUIRED",
                "message": f"Required field '{field}' is missing",
            })
            if report["status"] == "PASS":
                report["status"] = "WARNING"

    if not line_items:
        report["issues"].append({
            "type": "MISSING_REQUIRED",
            "message": "No line items found",
        })
        if report["status"] == "PASS":
            report["status"] = "WARNING"

    return report


# -- Main ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--synthetic-100",
        action="store_true",
        help="Submit 100 uniquely keyed copies of the five safe fixtures.",
    )
    args = parser.parse_args()
    invoices = load_invoices()
    if args.synthetic_100:
        invoices = build_synthetic_workload(invoices, size=100)

    print("=" * 70)
    print("M5: BATCH API -- Async Extraction + Validation")
    print("=" * 70)

    # -- Phase 1: Build and submit batch ---------------------------------------
    print("\n--- Phase 1: Submit Batch ---")
    requests = build_batch_requests(invoices)
    batch_id = create_batch(requests)

    # -- Phase 2: Poll for completion ------------------------------------------
    print("\n--- Phase 2: Poll for Completion ---")
    completed = poll_batch(batch_id, max_wait=600)

    if not completed:
        print("Batch did not complete within the time limit.")
        print(f"Batch ID for later retrieval: {batch_id}")
        return

    # -- Phase 3: Collect results ----------------------------------------------
    print("\n--- Phase 3: Collect Results ---")
    results = collect_results(batch_id)

    # Print extractions
    for name, extraction in sorted(results.items()):
        print(f"\n  {name}:")
        print(f"    vendor:    {extraction.get('vendor')}")
        print(f"    date:      {extraction.get('date')}")
        print(f"    subtotal:  {extraction.get('subtotal')}")
        print(f"    tax:       {extraction.get('tax')}")
        print(f"    total:     {extraction.get('total')}")
        items = extraction.get("line_items", [])
        print(f"    items:     {len(items)} line items")

    # -- Phase 4: Validation (second pass) -------------------------------------
    # +========================================================================+
    # |  EXAM NOTE -- Validation is a SECOND PASS                              |
    # |  Batch API does NOT support multi-turn tool calling. You cannot do     |
    # |  retry-with-feedback inside a batch request. Extract first (batch),    |
    # |  then validate (synchronous), then retry failures (synchronous M4).   |
    # +========================================================================+
    print("\n--- Phase 4: Validation (Second Pass) ---")
    validation_reports = []

    for name, extraction in sorted(results.items()):
        report = validate_extraction(name, extraction)
        validation_reports.append(report)

        status_str = report["status"]
        if report["issues"]:
            issue_types = [i["type"] for i in report["issues"]]
            print(f"  {name:<35} {status_str}  [{', '.join(issue_types)}]")
        else:
            print(f"  {name:<35} {status_str}")

    # -- Summary ---------------------------------------------------------------
    print("\n" + "=" * 70)
    print("BATCH SUMMARY")
    print("=" * 70)
    total_docs = len(invoices)
    collected = len(results)
    passed = sum(1 for r in validation_reports if r["status"] == "PASS")
    conflicts = sum(1 for r in validation_reports if r["status"] == "CONFLICT")
    warnings = sum(1 for r in validation_reports if r["status"] == "WARNING")

    print(f"  Submitted:  {total_docs}")
    print(f"  Collected:  {collected}")
    print(f"  Passed:     {passed}")
    print(f"  Conflicts:  {conflicts}")
    print(f"  Warnings:   {warnings}")

    # +========================================================================+
    # |  CHECKPOINT                                                            |
    # |                                                                        |
    # |  All 5 invoices are packed into ONE batch job and processed async.     |
    # |  Results are collected and validated as a second pass.                  |
    # |                                                                        |
    # |  Expected results mirror M2/M4:                                        |
    # |    - invoice_01: PASS (VAT gap closes)                                 |
    # |    - invoice_02: CONFLICT (items_sum=392 != subtotal=500)              |
    # |    - invoice_03: PASS                                                  |
    # |    - invoice_04: PASS                                                  |
    # |    - invoice_05: PASS                                                  |
    # |                                                                        |
    # |  EXAM NOTE -- Batch API key points:                                    |
    # |    - ~50% cheaper input and output                                     |
    # |    - Async, <=24h window, no SLA, unfinished work expires              |
    # |    - "ended" describes the JOB, not the requests -- inspect each       |
    # |      result.type before accessing the message                          |
    # |    - No multi-turn tool calling (no agentic loop inside a batch)       |
    # |    - custom_id for correlating request/response pairs                  |
    # |    - Decision rule: blocked? -> sync. Not blocked? -> batch            |
    # +========================================================================+

    return results, validation_reports


if __name__ == "__main__":
    main()
