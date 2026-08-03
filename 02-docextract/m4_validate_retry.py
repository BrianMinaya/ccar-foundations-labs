"""
DocExtract -- M4: Validation & Retry-with-Feedback
====================================================

THE USE CASE
------------
Input:  Raw invoice text (5 docs) extracted via tool_use.
Output: Each extraction is VALIDATED in Python (arithmetic, date format,
        required fields) and classified as PASS, RECOVERABLE, ABSENT, or
        CONFLICT. Recoverable errors trigger a retry with feedback; conflicts
        are flagged for human review; absent fields are accepted as null.
Target: invoice_01 auto-accepts (items+tax closes the VAT gap).
        invoice_02 is flagged as CONFLICT (items_sum=392 != subtotal=500).
        Retries include the original doc + failed output + specific error.

Run with --demo-retry to force a recoverable date-format error.
"""

import os
import sys
import json
import glob
import re
import anthropic
from decimal import Decimal
from datetime import datetime
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


# -- Extraction ----------------------------------------------------------------

def extract_invoice(doc_text: str) -> dict:
    """Extract invoice data using forced tool_use. Returns a plain dict."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        tools=[INVOICE_TOOL],
        tool_choice={"type": "tool", "name": "extract_invoice"},
        messages=[
            {
                "role": "user",
                "content": (
                    "Extract all fields from this invoice document. "
                    "Return null for any field not present -- do NOT invent values. "
                    "Convert dates to YYYY-MM-DD. Correct obvious OCR errors in "
                    "descriptions but preserve amounts exactly as stated.\n\n"
                    f"---\n\n{doc_text}"
                ),
            }
        ],
    )
    for block in response.content:
        if block.type == "tool_use":
            return validate_extraction_payload(block.input)
    raise RuntimeError("No tool_use block in response")


# -- Retry with feedback -------------------------------------------------------

def retry_with_feedback(doc_text: str, bad_extraction: dict, error_msg: str) -> dict:
    """
    Retry extraction by sending the original doc, the failed output,
    and the specific error message back to the model.
    """
    # +====================================================================+
    # |  EXAM NOTE -- Retry includes three pieces:                         |
    # |    1. The original document (context)                              |
    # |    2. The failed extraction (what went wrong)                      |
    # |    3. The specific error message (how to fix it)                   |
    # |  This is "feedback", not "prompt engineering" -- the model sees    |
    # |  its own mistake and the exact correction needed.                  |
    # +====================================================================+
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        tools=[INVOICE_TOOL],
        tool_choice={"type": "tool", "name": "extract_invoice"},
        messages=[
            {
                "role": "user",
                "content": (
                    "Extract all fields from this invoice document. "
                    "Return null for any field not present -- do NOT invent values. "
                    "Convert dates to YYYY-MM-DD.\n\n"
                    f"---\n\n{doc_text}"
                ),
            },
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "retry_call",
                        "name": "extract_invoice",
                        "input": bad_extraction,
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "retry_call",
                        "content": (
                            f"VALIDATION FAILED. Please fix and re-extract.\n"
                            f"Error: {error_msg}\n"
                            f"Re-read the original document and correct only "
                            f"the field(s) mentioned in the error."
                        ),
                    }
                ],
            },
        ],
    )
    for block in response.content:
        if block.type == "tool_use":
            return validate_extraction_payload(block.input)
    raise RuntimeError("No tool_use block in retry response")


# -- Validation ----------------------------------------------------------------

# +============================================================================+
# |  EXAM NOTE -- Never base a check on a value the model supplied             |
# |  The basis for arithmetic checks is ALWAYS items_sum, computed in Python   |
# |  from the individual line_item amounts. We never trust the model's own     |
# |  subtotal/total as the "correct" number -- we verify it against the        |
# |  line items it returned. "A fabricated tax can still defeat this check"    |
# |  -- this is a KNOWN, DOCUMENTED gap. The model could invent a tax value   |
# |  that makes the arithmetic pass. Validation is defense-in-depth, not      |
# |  proof.                                                                    |
# +============================================================================+


def validate_extraction(extraction: dict) -> list[dict]:
    """
    Validate an extraction IN PYTHON. Returns a list of issues found.
    Each issue is a dict: {"type": "RECOVERABLE"|"ABSENT"|"CONFLICT", ...}

    Classification:
      RECOVERABLE -- fixable by the model (e.g., wrong date format) -> retry
      ABSENT      -- field genuinely missing from source -> accept null, DON'T retry
      CONFLICT    -- source document is internally inconsistent -> human review
    """
    issues = []

    # -- 1. Compute items_sum from line_items amounts in Python ----------------
    line_items = extraction.get("line_items", [])
    items_sum = sum((Decimal(str(item["amount"])) for item in line_items), Decimal("0"))

    tax_value = extraction.get("tax")
    tax = Decimal(str(tax_value)) if tax_value is not None else None
    subtotal = Decimal(str(extraction.get("subtotal")))
    total = Decimal(str(extraction.get("total")))
    tolerance = Decimal("0.01")

    # -- 2. VAT gap check (if tax is present) ----------------------------------
    if tax is not None:
        # Check: items_sum + tax == total
        expected_total = items_sum + tax
        if abs(expected_total - total) >= tolerance:
            issues.append({
                "type": "CONFLICT",
                "field": "total",
                "message": (
                    f"items_sum ({items_sum:.2f}) + tax ({tax:.2f}) = "
                    f"{expected_total:.2f}, but stated total is {total:.2f}"
                ),
                "items_sum": items_sum,
                "tax": tax,
                "expected_total": expected_total,
                "stated_total": total,
            })
    else:
        # -- 3. No tax: items_sum should equal subtotal ------------------------
        if abs(items_sum - subtotal) >= tolerance:
            # +================================================================+
            # |  EXAM NOTE -- CONFLICT, not RECOVERABLE                        |
            # |  When items_sum != stated_subtotal, the SOURCE is wrong.       |
            # |  Retrying won't help -- the model faithfully extracted a       |
            # |  wrong number from the document. Flag for human review with    |
            # |  BOTH numbers recorded so the human can decide.               |
            # +================================================================+
            issues.append({
                "type": "CONFLICT",
                "field": "subtotal",
                "message": (
                    f"items_sum ({items_sum:.2f}) != "
                    f"stated subtotal ({subtotal:.2f})"
                ),
                "items_sum": items_sum,
                "stated_subtotal": subtotal,
            })

    # -- 4. Date format: must be valid ISO YYYY-MM-DD --------------------------
    date_str = extraction.get("date", "")
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        # This IS recoverable -- the model can reformat it
        issues.append({
            "type": "RECOVERABLE",
            "field": "date",
            "message": (
                f"Date '{date_str}' is not valid YYYY-MM-DD format. "
                f"Please convert to YYYY-MM-DD."
            ),
        })

    # -- 5. Required fields check ----------------------------------------------
    if not extraction.get("vendor"):
        issues.append({
            "type": "RECOVERABLE",
            "field": "vendor",
            "message": "Required field 'vendor' is missing or empty.",
        })
    if not extraction.get("customer"):
        issues.append({
            "type": "RECOVERABLE",
            "field": "customer",
            "message": "Required field 'customer' is missing or empty.",
        })
    if not line_items:
        issues.append({
            "type": "RECOVERABLE",
            "field": "line_items",
            "message": "At least one line_item is required.",
        })

    # -- Check for ABSENT fields (null optionals that are legitimately missing) -
    # po_number is Optional -- null is acceptable, NOT an error
    # +========================================================================+
    # |  EXAM NOTE -- ABSENT -> accept null, DON'T retry                       |
    # |  Pressure breeds fabrication. If the PO number isn't in the document,  |
    # |  retrying with "please find the PO number" will cause the model to     |
    # |  hallucinate one. Accept null and move on.                             |
    # +========================================================================+
    if extraction.get("po_number") is None:
        issues.append({
            "type": "ABSENT",
            "field": "po_number",
            "message": "po_number is null -- accepted as legitimately absent.",
        })
    if extraction.get("invoice_number") is None:
        issues.append({
            "type": "ABSENT",
            "field": "invoice_number",
            "message": "invoice_number is null -- accepted as legitimately absent.",
        })

    return issues


# -- Issue classification helpers ----------------------------------------------

def has_recoverable(issues: list[dict]) -> bool:
    """Check if any issues are RECOVERABLE (worth retrying)."""
    return any(i["type"] == "RECOVERABLE" for i in issues)


def has_conflict(issues: list[dict]) -> bool:
    """Check if any issues are CONFLICT (needs human review)."""
    return any(i["type"] == "CONFLICT" for i in issues)


def get_recoverable_message(issues: list[dict]) -> str:
    """Build a combined error message from all RECOVERABLE issues."""
    recoverable = [i for i in issues if i["type"] == "RECOVERABLE"]
    return " | ".join(i["message"] for i in recoverable)


# -- Main ----------------------------------------------------------------------

def main():
    demo_retry = "--demo-retry" in sys.argv

    invoices = load_invoices()

    print("=" * 70)
    print("M4: VALIDATION & RETRY-WITH-FEEDBACK")
    if demo_retry:
        print("     (--demo-retry: will corrupt a date to force recovery)")
    print("=" * 70)

    all_results = {}
    max_retries = 2

    for name, text in invoices.items():
        print(f"\n{'─' * 60}")
        print(f"  Processing: {name}")
        print(f"{'─' * 60}")

        # -- Extract -----------------------------------------------------------
        extraction = extract_invoice(text)

        # -- Demo mode: corrupt the date to force a RECOVERABLE error ----------
        if demo_retry and name == "invoice_01_clean":
            print("  [--demo-retry] Corrupting date to '03/03/2024' ...")
            extraction["date"] = "03/03/2024"

        # -- Validate ----------------------------------------------------------
        issues = validate_extraction(extraction)
        attempt = 0

        while has_recoverable(issues) and attempt < max_retries:
            attempt += 1
            error_msg = get_recoverable_message(issues)
            print(f"  RECOVERABLE error (attempt {attempt}): {error_msg}")
            print(f"  Retrying with feedback...")

            # +================================================================+
            # |  EXAM NOTE -- Retry includes:                                  |
            # |    1. Original document (context)                              |
            # |    2. Failed extraction (what went wrong)                      |
            # |    3. Specific error message (how to fix it)                   |
            # |  RECOVERABLE -> retry with feedback                            |
            # |  ABSENT      -> accept null                                    |
            # |  CONFLICT    -> flag for human review                          |
            # +================================================================+
            extraction = retry_with_feedback(text, extraction, error_msg)
            issues = validate_extraction(extraction)

        # -- Report results ----------------------------------------------------
        conflicts = [i for i in issues if i["type"] == "CONFLICT"]
        absent = [i for i in issues if i["type"] == "ABSENT"]
        recoverable = [i for i in issues if i["type"] == "RECOVERABLE"]

        if conflicts:
            print(f"  CONFLICT detected -- flagged for human review:")
            for c in conflicts:
                print(f"    {c['field']}: {c['message']}")
                # Print both numbers for human to compare
                if "items_sum" in c:
                    stated_key = "stated_subtotal" if "stated_subtotal" in c else "stated_total"
                    stated_val = c.get(stated_key, "N/A")
                    print(f"    -> items_sum={c['items_sum']:.2f}, {stated_key}={stated_val}")

        if absent:
            print(f"  ABSENT fields (accepted as null):")
            for a in absent:
                print(f"    {a['field']}: {a['message']}")

        if recoverable:
            print(f"  UNRESOLVED RECOVERABLE (exhausted retries):")
            for r in recoverable:
                print(f"    {r['field']}: {r['message']}")

        if not conflicts and not recoverable:
            print(f"  PASSED validation")

        # -- Store result with metadata ----------------------------------------
        all_results[name] = {
            "extraction": extraction,
            "issues": issues,
            "status": (
                "CONFLICT" if conflicts
                else "UNRESOLVED" if recoverable
                else "PASS"
            ),
            "retries": attempt,
        }

        # Print key fields
        print(f"  vendor:    {extraction.get('vendor')}")
        print(f"  date:      {extraction.get('date')}")
        print(f"  subtotal:  {extraction.get('subtotal')}")
        print(f"  tax:       {extraction.get('tax')}")
        print(f"  total:     {extraction.get('total')}")
        items = extraction.get("line_items", [])
        items_sum = sum(item["amount"] for item in items)
        print(f"  items_sum: {items_sum:.2f}  ({len(items)} items)")

    # -- Summary ---------------------------------------------------------------
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for name, result in all_results.items():
        status = result["status"]
        retries = result["retries"]
        retry_str = f" (retried {retries}x)" if retries > 0 else ""
        print(f"  {name:<35} {status}{retry_str}")

    # +========================================================================+
    # |  CHECKPOINT                                                            |
    # |                                                                        |
    # |  invoice_01: PASS -- items_sum=446 + tax=89.20 = 535.20 = total.      |
    # |    The VAT gap check PASSES because items + tax closes the gap.        |
    # |                                                                        |
    # |  invoice_02: CONFLICT -- items_sum=392.00 != stated subtotal=500.00.  |
    # |    The SOURCE document is wrong. Retrying cannot fix this -- the model |
    # |    faithfully extracted what the document says. Human must decide.      |
    # |                                                                        |
    # |  invoice_03: PASS (absent: invoice_number is null -- accepted).       |
    # |  invoice_04: PASS (absent: po_number is null -- accepted).            |
    # |  invoice_05: PASS (OCR corrected by model, amounts preserved).        |
    # |                                                                        |
    # |  EXAM NOTE -- The three-way classification:                            |
    # |    RECOVERABLE -> retry with feedback (format errors)                  |
    # |    ABSENT      -> accept null, DON'T retry (pressure breeds           |
    # |                   fabrication)                                          |
    # |    CONFLICT    -> human review (source is inconsistent)                |
    # +========================================================================+

    return all_results


if __name__ == "__main__":
    main()
