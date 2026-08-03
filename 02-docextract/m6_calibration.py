"""
DocExtract -- M6: Calibration & Human Routing
===============================================

THE USE CASE
------------
Input:  5 invoice docs extracted via tool_use, scored against ground_truth.json.
Output: Per-field accuracy table, accuracy by segment (clean vs problematic),
        calibration table (stated confidence vs actual accuracy), and a
        human_review_queue.json prioritised for human attention.
Target: Demonstrate that self-reported confidence measures DOCUMENT DIFFICULTY,
        not SPEC COMPLIANCE. Route on VALIDATION (deterministic), not on the
        model's own confidence score.

The model is likely overconfident. The two numbers that matter:
  - Escapes:     wrong records auto-accepted (missed by validation)
  - False alarms: correct records sent to human (wasted reviewer time)
"""

import os
import json
import glob
import random
import anthropic
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
GROUND_TRUTH_PATH = os.path.join(BASE_DIR, "ground_truth.json")
REVIEW_QUEUE_PATH = os.path.join(BASE_DIR, "output", "human_review_queue.json")

# -- Segments ------------------------------------------------------------------
CLEAN_DOCS = {"invoice_01_clean", "invoice_03_prose_date", "invoice_04_missing_po"}
PROBLEMATIC_DOCS = {"invoice_02_sum_mismatch", "invoice_05_garbled"}

# -- Fields to score -----------------------------------------------------------
SCALAR_FIELDS = [
    "invoice_number", "date", "vendor", "customer",
    "po_number", "subtotal", "tax", "total",
]


def load_invoices() -> dict[str, str]:
    """Load all invoice text files from docs/ directory."""
    invoices = {}
    for filepath in sorted(glob.glob(os.path.join(DOCS_DIR, "invoice_*.txt"))):
        name = os.path.splitext(os.path.basename(filepath))[0]
        with open(filepath, "r", encoding="utf-8") as f:
            invoices[name] = f.read()
    return invoices


def load_ground_truth() -> dict:
    """Load ground truth labels."""
    with open(GROUND_TRUTH_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


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


# -- Scoring -------------------------------------------------------------------

# +============================================================================+
# |  EXAM NOTE -- Self-reported confidence measures DOCUMENT DIFFICULTY,       |
# |  not SPEC COMPLIANCE                                                       |
# |                                                                            |
# |  "It can say 'this page is smudged', it cannot say 'I may have            |
# |   misunderstood your definition of subtotal'"                              |
# |                                                                            |
# |  The model knows when the input is bad (low confidence for OCR damage).   |
# |  It does NOT know when its interpretation of a valid document diverges    |
# |  from your spec (subtotal vs items_sum). That's why you route on          |
# |  VALIDATION (deterministic), not self-reported confidence.                |
# +============================================================================+


def score_field(extracted_value, truth_value) -> bool:
    """
    Score a single field against ground truth.
    - Strings: case-insensitive, stripped whitespace
    - Numbers: abs(a - b) < 0.01
    - None/null: both must be None
    """
    # Both null
    if truth_value is None and extracted_value is None:
        return True
    # One null, one not
    if truth_value is None or extracted_value is None:
        return False

    # Numeric comparison
    if isinstance(truth_value, (int, float)):
        try:
            return abs(float(extracted_value) - float(truth_value)) < 0.01
        except (ValueError, TypeError):
            return False

    # String comparison -- normalize
    return str(extracted_value).strip().lower() == str(truth_value).strip().lower()


def score_line_items(extracted_items: list, truth_items: list) -> dict:
    """
    Score line items: count match + per-item comparison.
    Returns dict with count_correct, description_matches, amount_matches,
    total_items.
    """
    result = {
        "count_correct": len(extracted_items) == len(truth_items),
        "description_matches": 0,
        "amount_matches": 0,
        "total_items": len(truth_items),
    }

    for i, truth_item in enumerate(truth_items):
        if i < len(extracted_items):
            ext_item = extracted_items[i]

            # Amount: exact match within tolerance
            ext_amount = ext_item.get("amount", -1)
            try:
                if abs(float(ext_amount) - truth_item["amount"]) < 0.01:
                    result["amount_matches"] += 1
            except (ValueError, TypeError):
                pass

            # Description: fuzzy match (case-insensitive, stripped)
            ext_desc = str(ext_item.get("description", "")).strip().lower()
            truth_desc = str(truth_item.get("description", "")).strip().lower()
            # Fuzzy: check if one contains the other or high overlap
            if ext_desc == truth_desc:
                result["description_matches"] += 1
            elif ext_desc in truth_desc or truth_desc in ext_desc:
                result["description_matches"] += 1

    return result


def score_extraction(extraction: dict, truth: dict) -> dict:
    """
    Score a full extraction against ground truth.
    Returns per-field boolean results + line_items sub-scores.
    """
    scores = {}

    for field in SCALAR_FIELDS:
        ext_val = extraction.get(field)
        truth_val = truth.get(field)
        scores[field] = score_field(ext_val, truth_val)

    # Line items
    ext_items = extraction.get("line_items", [])
    truth_items = truth.get("line_items", [])
    li = score_line_items(ext_items, truth_items)
    scores["line_items_count"] = li["count_correct"]
    scores["line_items_amounts"] = (
        li["amount_matches"] / li["total_items"]
        if li["total_items"] > 0 else 0.0
    )
    scores["line_items_descriptions"] = (
        li["description_matches"] / li["total_items"]
        if li["total_items"] > 0 else 0.0
    )

    return scores


# -- Validation (deterministic) -----------------------------------------------

def validate_extraction(extraction: dict) -> bool:
    """
    Run deterministic validation checks (same as M4).
    Returns True if all checks pass, False otherwise.
    """
    line_items = extraction.get("line_items", [])
    items_sum = sum((Decimal(str(item["amount"])) for item in line_items), Decimal("0"))
    tax_value = extraction.get("tax")
    tax = Decimal(str(tax_value)) if tax_value is not None else None
    subtotal = Decimal(str(extraction.get("subtotal")))
    total = Decimal(str(extraction.get("total")))
    tolerance = Decimal("0.01")

    # Arithmetic check
    if tax is not None:
        expected_total = items_sum + tax
        if abs(expected_total - total) >= tolerance:
            return False
    else:
        if abs(items_sum - subtotal) >= tolerance:
            return False

    # Date format
    date_str = extraction.get("date", "")
    try:
        from datetime import datetime
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return False

    # Required fields
    if not extraction.get("vendor"):
        return False
    if not extraction.get("customer"):
        return False
    if not line_items:
        return False

    return True


# -- Calibration ---------------------------------------------------------------

CONFIDENCE_BUCKETS = [
    (0.0, 0.5, "0.0-0.5"),
    (0.5, 0.7, "0.5-0.7"),
    (0.7, 0.9, "0.7-0.9"),
    (0.9, 1.01, "0.9-1.0"),  # 1.01 to include 1.0
]


def build_calibration_table(
    extractions: dict[str, dict],
    per_doc_scores: dict[str, dict],
) -> list[dict]:
    """
    Bucket stated confidence into ranges and compute actual accuracy per bucket.
    Returns a list of bucket records.
    """
    # +========================================================================+
    # |  EXAM NOTE -- Calibration is measurement, not fine-tuning              |
    # |  No weights change. We are measuring whether the model's stated       |
    # |  confidence correlates with actual accuracy. If a model says 0.95     |
    # |  and is right 70% of the time, it's overconfident. This tells you     |
    # |  HOW MUCH to discount the confidence score -- it does not fix it.     |
    # +========================================================================+
    buckets = []

    for low, high, label in CONFIDENCE_BUCKETS:
        docs_in_bucket = []
        correct_fields = 0
        total_fields = 0

        for name, extraction in extractions.items():
            conf = extraction.get("confidence", 0.0)
            if low <= conf < high:
                docs_in_bucket.append(name)
                scores = per_doc_scores[name]
                for field in SCALAR_FIELDS:
                    total_fields += 1
                    if scores.get(field, False):
                        correct_fields += 1

        accuracy = correct_fields / total_fields if total_fields > 0 else None
        avg_conf = None
        if docs_in_bucket:
            avg_conf = sum(
                extractions[n].get("confidence", 0) for n in docs_in_bucket
            ) / len(docs_in_bucket)

        buckets.append({
            "bucket": label,
            "n_docs": len(docs_in_bucket),
            "doc_ids": docs_in_bucket,
            "stated_confidence_avg": avg_conf,
            "actual_accuracy": accuracy,
            "total_fields": total_fields,
            "correct_fields": correct_fields,
        })

    return buckets


# -- Human review queue --------------------------------------------------------

def build_review_queue(
    extractions: dict[str, dict],
    validation_results: dict[str, bool],
    *,
    field_confidence_threshold: float = 0.75,
) -> list[dict]:
    """
    Build a production-usable queue without consulting ground truth labels.

    Deterministic validation is primary; low field-level confidence is a
    secondary signal. Ground truth is reserved for offline evaluation below.
    """
    queue = []
    priority = 0

    # -- Pass 1: CONFLICT docs (items_sum != stated subtotal/total) ------------
    for name, extraction in extractions.items():
        line_items = extraction.get("line_items", [])
        items_sum = sum((Decimal(str(item["amount"])) for item in line_items), Decimal("0"))
        tax_value = extraction.get("tax")
        tax = Decimal(str(tax_value)) if tax_value is not None else None
        subtotal = Decimal(str(extraction.get("subtotal")))
        total = Decimal(str(extraction.get("total")))

        is_conflict = False
        if tax is not None:
            if abs(items_sum + tax - total) >= Decimal("0.01"):
                is_conflict = True
        else:
            if abs(items_sum - subtotal) >= Decimal("0.01"):
                is_conflict = True

        if is_conflict:
            priority += 1
            queue.append({
                "doc_id": name,
                "reason": f"CONFLICT: items_sum={items_sum:.2f} vs stated value",
                "stated_confidence": extraction.get("confidence"),
                "validation_passed": False,
                "priority": priority,
            })

    # -- Pass 2: Failed validation (not already in queue) ----------------------
    queued_ids = {entry["doc_id"] for entry in queue}
    for name in sorted(extractions.keys()):
        if name not in queued_ids and not validation_results.get(name, True):
            priority += 1
            queue.append({
                "doc_id": name,
                "reason": "Validation failed (non-conflict)",
                "stated_confidence": extractions[name].get("confidence"),
                "validation_passed": False,
                "priority": priority,
            })

    # -- Pass 3: Low field confidence (production-available secondary signal) --
    queued_ids = {entry["doc_id"] for entry in queue}
    for name in sorted(extractions.keys()):
        if name not in queued_ids:
            field_confidence = extractions[name].get("field_confidence", {})
            low_fields = sorted(
                field for field, confidence in field_confidence.items()
                if confidence < field_confidence_threshold
            )
            if low_fields:
                priority += 1
                queue.append({
                    "doc_id": name,
                    "reason": "Low field confidence: " + ", ".join(low_fields),
                    "stated_confidence": extractions[name].get("confidence"),
                    "validation_passed": validation_results.get(name, False),
                    "priority": priority,
                })

    return queue


def stratified_sample(
    doc_ids: list[str],
    strata: dict[str, str],
    *,
    per_stratum: int = 1,
    seed: int = 42,
) -> list[str]:
    """Select a reproducible audit sample from every represented segment."""
    rng = random.Random(seed)
    grouped: dict[str, list[str]] = {}
    for doc_id in sorted(doc_ids):
        grouped.setdefault(strata.get(doc_id, "unknown"), []).append(doc_id)

    sample = []
    for segment in sorted(grouped):
        candidates = grouped[segment]
        sample.extend(rng.sample(candidates, min(per_stratum, len(candidates))))
    return sorted(sample)


def evaluate_routing(
    queue: list[dict],
    per_doc_scores: dict[str, dict],
    *,
    correct_threshold: float = 1.0,
) -> dict[str, int]:
    """Measure escapes and false alarms offline; never use labels to route."""
    queued = {entry["doc_id"] for entry in queue}
    actually_correct = {}
    for name, scores in per_doc_scores.items():
        accuracy = sum(bool(scores.get(f, False)) for f in SCALAR_FIELDS) / len(SCALAR_FIELDS)
        actually_correct[name] = accuracy >= correct_threshold
    return {
        "escapes": sum(not correct and name not in queued for name, correct in actually_correct.items()),
        "false_alarms": sum(correct and name in queued for name, correct in actually_correct.items()),
    }


# -- Main ----------------------------------------------------------------------

def main():
    invoices = load_invoices()
    ground_truth = load_ground_truth()

    print("=" * 70)
    print("M6: CALIBRATION & HUMAN ROUTING")
    print("=" * 70)

    # -- Phase 1: Extract all docs synchronously -------------------------------
    print("\n--- Phase 1: Extract All Documents ---")
    extractions = {}
    for name, text in invoices.items():
        print(f"  Extracting {name}...")
        extraction = extract_invoice(text)
        extractions[name] = extraction
        print(f"    confidence: {extraction.get('confidence')}")

    # -- Phase 2: Score against ground truth -----------------------------------
    print("\n--- Phase 2: Score Against Ground Truth ---")
    per_doc_scores = {}
    for name, extraction in extractions.items():
        truth = ground_truth[name]
        scores = score_extraction(extraction, truth)
        per_doc_scores[name] = scores

    # -- Phase 3: Run validation -----------------------------------------------
    validation_results = {}
    for name, extraction in extractions.items():
        validation_results[name] = validate_extraction(extraction)

    # -- Print results ---------------------------------------------------------

    # ---- 1. Headline accuracy (with caveat) ----------------------------------
    total_correct = 0
    total_fields = 0
    for name, scores in per_doc_scores.items():
        for field in SCALAR_FIELDS:
            total_fields += 1
            if scores.get(field, False):
                total_correct += 1

    headline = total_correct / total_fields if total_fields > 0 else 0
    print(f"\nHeadline Accuracy: {headline:.1%}")
    print("  DO NOT report this number alone -- see segments below")

    # +========================================================================+
    # |  EXAM NOTE -- Never report one accuracy number -- segment it           |
    # |  A single number hides failures in subgroups. "92% accuracy" could    |
    # |  mean 100% on clean docs and 50% on problematic ones. The problematic |
    # |  docs are where it matters most.                                       |
    # +========================================================================+

    # ---- 2. Accuracy by segment ----------------------------------------------
    print(f"\n{'─' * 60}")
    print("ACCURACY BY SEGMENT")
    print(f"{'─' * 60}")

    for segment_name, segment_docs in [("clean", CLEAN_DOCS), ("problematic", PROBLEMATIC_DOCS)]:
        seg_correct = 0
        seg_total = 0
        for name in segment_docs:
            if name in per_doc_scores:
                for field in SCALAR_FIELDS:
                    seg_total += 1
                    if per_doc_scores[name].get(field, False):
                        seg_correct += 1
        seg_acc = seg_correct / seg_total if seg_total > 0 else 0
        doc_list = ", ".join(sorted(segment_docs))
        print(f"  {segment_name:<15} {seg_acc:>6.1%}  ({seg_correct}/{seg_total})  [{doc_list}]")

    # ---- 3. Accuracy by field ------------------------------------------------
    print(f"\n{'─' * 60}")
    print("ACCURACY BY FIELD")
    print(f"{'─' * 60}")

    all_scored_fields = SCALAR_FIELDS + ["line_items_count", "line_items_amounts", "line_items_descriptions"]
    print(f"\n{'Field':<30} {'Correct':>8} {'Total':>6} {'Accuracy':>10}")
    print("-" * 58)

    for field in all_scored_fields:
        field_correct = 0
        field_total = 0
        for name, scores in per_doc_scores.items():
            val = scores.get(field)
            if val is not None:
                if isinstance(val, bool):
                    field_total += 1
                    if val:
                        field_correct += 1
                else:
                    # float score (e.g., line_items_amounts ratio)
                    field_total += 1
                    if val >= 0.99:  # Treat near-perfect as correct
                        field_correct += 1

        field_acc = field_correct / field_total if field_total > 0 else 0
        print(f"  {field:<28} {field_correct:>6} {field_total:>6} {field_acc:>9.1%}")

    # ---- 4. Calibration table ------------------------------------------------
    print(f"\n{'─' * 60}")
    print("CALIBRATION TABLE")
    print("  (stated confidence vs actual accuracy)")
    print(f"{'─' * 60}")

    calibration = build_calibration_table(extractions, per_doc_scores)

    print(f"\n{'Bucket':<12} {'N docs':>7} {'Avg Stated':>12} {'Actual Acc':>12} {'Gap':>8}")
    print("-" * 55)

    for bucket in calibration:
        n = bucket["n_docs"]
        if n == 0:
            print(f"  {bucket['bucket']:<10} {n:>5}       {'--':>10} {'--':>10} {'--':>6}")
            continue

        stated = bucket["stated_confidence_avg"]
        actual = bucket["actual_accuracy"]
        stated_str = f"{stated:.2f}" if stated is not None else "--"
        actual_str = f"{actual:.1%}" if actual is not None else "--"

        gap = ""
        if stated is not None and actual is not None:
            gap_val = stated - actual
            if gap_val > 0:
                gap = f"+{gap_val:.2f}"  # Overconfident
            else:
                gap = f"{gap_val:.2f}"   # Underconfident
            # +================================================================+
            # |  EXAM NOTE -- Positive gap = overconfident                     |
            # |  stated 0.95, actual 0.70 -> gap = +0.25 (overconfident)      |
            # |  The model thinks it did better than it actually did.          |
            # |  This is the normal case for self-reported confidence.         |
            # +================================================================+

        print(f"  {bucket['bucket']:<10} {n:>5} {stated_str:>12} {actual_str:>12} {gap:>8}")

    # ---- 5. Per-doc detail ---------------------------------------------------
    print(f"\n{'─' * 60}")
    print("PER-DOCUMENT DETAIL")
    print(f"{'─' * 60}")
    print(f"\n{'Document':<35} {'Confidence':>11} {'Accuracy':>10} {'Validation':>12}")
    print("-" * 70)

    for name in sorted(extractions.keys()):
        conf = extractions[name].get("confidence", 0)
        scores = per_doc_scores[name]
        correct = sum(1 for f in SCALAR_FIELDS if scores.get(f, False))
        accuracy = correct / len(SCALAR_FIELDS)
        val_passed = validation_results[name]
        val_str = "PASS" if val_passed else "FAIL"

        print(f"  {name:<33} {conf:>9.2f} {accuracy:>9.1%} {val_str:>12}")

    # ---- 6. Build and write human review queue -------------------------------
    print(f"\n{'─' * 60}")
    print("HUMAN REVIEW QUEUE")
    print(f"{'─' * 60}")

    queue = build_review_queue(extractions, validation_results)

    # Audit a balanced slice even when validation passes, so silent failures
    # remain observable. Segment labels are operational metadata, not answers.
    strata = {
        name: "clean" if name in CLEAN_DOCS else "problematic"
        for name in extractions
    }
    already_queued = {entry["doc_id"] for entry in queue}
    audit_sample = stratified_sample(
        [name for name in extractions if name not in already_queued],
        strata,
        per_stratum=1,
    )
    for name in audit_sample:
        queue.append({
            "doc_id": name,
            "reason": f"Stratified quality audit: {strata[name]}",
            "stated_confidence": extractions[name].get("confidence"),
            "validation_passed": validation_results.get(name, False),
            "priority": len(queue) + 1,
        })

    if queue:
        for entry in queue:
            print(f"  P{entry['priority']}: {entry['doc_id']}")
            print(f"      reason:     {entry['reason']}")
            print(f"      confidence: {entry['stated_confidence']}")
            print(f"      validation: {'PASS' if entry['validation_passed'] else 'FAIL'}")
    else:
        print("  No documents queued for review.")

    routing_metrics = evaluate_routing(queue, per_doc_scores)
    print(f"  escapes: {routing_metrics['escapes']}")
    print(f"  false alarms: {routing_metrics['false_alarms']}")

    # Write generated output outside the source tree's tracked artifacts.
    os.makedirs(os.path.dirname(REVIEW_QUEUE_PATH), exist_ok=True)
    with open(REVIEW_QUEUE_PATH, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2)
    print(f"\n  Written to: {REVIEW_QUEUE_PATH}")

    # +========================================================================+
    # |  EXAM NOTE -- The two numbers that matter                              |
    # |                                                                        |
    # |  Escapes:     wrong records auto-accepted (missed by validation)       |
    # |  False alarms: correct records sent to human (wasted reviewer time)    |
    # |                                                                        |
    # |  Self-reported confidence tells you about DOCUMENT DIFFICULTY:         |
    # |    - "This page is smudged" (low confidence) -- it CAN say this       |
    # |    - "I may have misunderstood your definition of subtotal"            |
    # |      (spec compliance) -- it CANNOT say this                           |
    # |                                                                        |
    # |  Route on VALIDATION (deterministic checks you control), not on       |
    # |  the model's own confidence number. The confidence number is useful   |
    # |  as a SECONDARY signal, not the primary routing decision.             |
    # +========================================================================+

    # +========================================================================+
    # |  CHECKPOINT                                                            |
    # |                                                                        |
    # |  The model is likely overconfident: high stated confidence even on     |
    # |  docs where it got fields wrong. This is EXPECTED behavior.            |
    # |                                                                        |
    # |  Key observations:                                                     |
    # |    - "clean" segment accuracy > "problematic" segment accuracy         |
    # |    - invoice_02 may show high confidence despite the subtotal being    |
    # |      wrong (the model doesn't know the doc is internally inconsistent)|
    # |    - invoice_05 may show lower confidence (OCR damage is visible)      |
    # |      but the extraction might actually be correct (model fixes OCR)   |
    # |    - Calibration gap is typically positive (overconfident)              |
    # |                                                                        |
    # |  Route on VALIDATION (deterministic), not self-reported confidence.   |
    # |  Calibration is measurement, not fine-tuning -- no weights change.    |
    # +========================================================================+

    return {
        "extractions": extractions,
        "scores": per_doc_scores,
        "validation": validation_results,
        "calibration": calibration,
        "review_queue": queue,
        "routing_metrics": routing_metrics,
    }


if __name__ == "__main__":
    main()
