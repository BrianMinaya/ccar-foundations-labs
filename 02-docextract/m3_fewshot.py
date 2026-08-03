"""
DocExtract — M3: Few-Shot Scoring
==================================

THE USE CASE
------------
Input:  Raw invoice text (5 docs) + ground_truth.json labels.
Output: Per-field accuracy table comparing zero-shot vs few-shot extraction,
        showing where few-shot examples measurably help.
Target: A detailed per-field accuracy breakdown — never a single headline
        number. Few-shot examples target ambiguous judgment calls (bracketed
        numbers: "Business cards (500)" = 1 pack vs "posters (x10)" = 10 units).

This module runs both zero-shot and few-shot extraction over all 5 docs,
scores each against ground truth PER FIELD, and prints a comparison table.
"""

import os
import json
import glob
import anthropic
from dotenv import load_dotenv

from m2_schema import INVOICE_TOOL, validate_extraction_payload

# ── Load environment ──────────────────────────────────────────────────────────
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

client = anthropic.Anthropic()
MODEL = "claude-haiku-4-5"

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(__file__)
DOCS_DIR = os.path.join(BASE_DIR, "docs")
GROUND_TRUTH_PATH = os.path.join(BASE_DIR, "ground_truth.json")


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


# ── Few-shot examples ───────────────────────────────────────────────────────
# These examples demonstrate JUDGMENT for ambiguous cases.
# The key insight: bracketed numbers can mean quantity OR description.
#   "Business cards (500)"  → 1 line item, description includes "(500)"
#   "Laminated posters (x10)" → 10 units, the "x10" is quantity
#   "Envelopes (C5, box of 200)" → 1 box, "(C5, box of 200)" is description

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  EXAM NOTE — Few-shot examples demonstrate JUDGMENT                    ║
# ║  They don't teach the model new facts — they show how to handle        ║
# ║  ambiguous cases where reasonable interpretations differ.              ║
# ║  ~500 tokens per call — only ship examples if they measurably help.   ║
# ╚══════════════════════════════════════════════════════════════════════════╝

FEWSHOT_EXAMPLES = """Here are examples of correct invoice extractions showing how to handle tricky cases:

EXAMPLE 1 — Bracketed numbers in descriptions:
Document text:
  "Business cards (500) - £45.00"
  "Laminated posters (x10) - £120.00"
Correct extraction:
  line_items: [
    {"description": "Business cards (500)", "amount": 45.00},
    {"description": "Laminated posters (x10)", "amount": 120.00}
  ]
Note: "(500)" is part of the description (500 cards = 1 item). "(x10)" is also part of the description. The amount is always the GBP figure.

EXAMPLE 2 — Missing fields:
Document text: (an invoice with no PO number mentioned anywhere)
Correct extraction:
  "po_number": null
Note: If a field is not present in the document, return null. Never guess or fabricate.

EXAMPLE 3 — Prose dates and OCR damage:
Document text: "Date of service: the fifteenth of February, twenty twenty-three"
Correct extraction:
  "date": "2023-02-15"
Note: Convert all date formats to YYYY-MM-DD. For UK-format dates (DD/MM/YYYY), interpret as day-first. For 2-digit years, assume 20xx.
"""


def extract_invoice(doc_text: str, use_fewshot: bool = False) -> dict:
    """Extract invoice data with optional few-shot examples."""
    prompt_parts = []

    if use_fewshot:
        prompt_parts.append(FEWSHOT_EXAMPLES)

    prompt_parts.append(
        "Extract all fields from this invoice document. "
        "Return null for any field not present — do NOT invent values. "
        "Convert dates to YYYY-MM-DD (assume UK date format DD/MM/YYYY). "
        "Correct obvious OCR errors in descriptions but preserve amounts "
        "exactly as stated in the document.\n\n"
        f"---\n\n{doc_text}"
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        tools=[INVOICE_TOOL],
        tool_choice={"type": "tool", "name": "extract_invoice"},
        messages=[
            {"role": "user", "content": "\n".join(prompt_parts)},
        ],
    )

    for block in response.content:
        if block.type == "tool_use":
            return validate_extraction_payload(block.input)

    raise RuntimeError("No tool_use block in response")


# ── Scoring ──────────────────────────────────────────────────────────────────

SCALAR_FIELDS = [
    "invoice_number", "date", "vendor", "customer",
    "po_number", "subtotal", "tax", "total",
]


def score_field(extracted_value, truth_value, field_name: str) -> bool:
    """Score a single field against ground truth."""
    # Handle None/null
    if truth_value is None and extracted_value is None:
        return True
    if truth_value is None or extracted_value is None:
        return False

    # Numeric fields — compare with tolerance
    if isinstance(truth_value, (int, float)):
        try:
            return abs(float(extracted_value) - float(truth_value)) < 0.01
        except (ValueError, TypeError):
            return False

    # String fields — case-insensitive, strip whitespace
    return str(extracted_value).strip().lower() == str(truth_value).strip().lower()


def score_line_items(extracted_items: list, truth_items: list) -> dict:
    """
    Score the ambiguity the examples target: count, amount, and description.
    """
    result = {
        "count_correct": len(extracted_items) == len(truth_items),
        "amounts_correct": 0,
        "descriptions_correct": 0,
        "total_items": len(truth_items),
    }

    # Match by position (since order should be preserved)
    for i, truth_item in enumerate(truth_items):
        if i < len(extracted_items):
            ext_amount = extracted_items[i].get("amount", -1)
            if abs(float(ext_amount) - truth_item["amount"]) < 0.01:
                result["amounts_correct"] += 1
            ext_description = str(extracted_items[i].get("description", ""))
            truth_description = str(truth_item.get("description", ""))
            if ext_description.strip().casefold() == truth_description.strip().casefold():
                result["descriptions_correct"] += 1

    return result


def score_extraction(extraction: dict, truth: dict) -> dict:
    """Score a full extraction against ground truth. Returns per-field results."""
    scores = {}

    for field in SCALAR_FIELDS:
        ext_val = extraction.get(field)
        truth_val = truth.get(field)
        scores[field] = score_field(ext_val, truth_val, field)

    # Line items
    ext_items = extraction.get("line_items", [])
    truth_items = truth.get("line_items", [])
    li_scores = score_line_items(ext_items, truth_items)
    scores["line_items_count"] = li_scores["count_correct"]
    scores["line_items_amounts"] = (
        li_scores["amounts_correct"] / li_scores["total_items"]
        if li_scores["total_items"] > 0 else 0.0
    )
    scores["line_items_descriptions"] = (
        li_scores["descriptions_correct"] / li_scores["total_items"]
        if li_scores["total_items"] > 0 else 0.0
    )

    return scores


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  EXAM NOTE — Before trusting any eval, ask:                            ║
# ║  "If the bug I care about were present, would this number move?"       ║
# ║  A single accuracy number can hide important failures in subgroups.    ║
# ║  That's why we print per-field, not just overall.                      ║
# ╚══════════════════════════════════════════════════════════════════════════╝


def main():
    invoices = load_invoices()
    ground_truth = load_ground_truth()

    print("=" * 70)
    print("M3: FEW-SHOT SCORING — Zero-shot vs Few-shot Comparison")
    print("=" * 70)

    all_scores = {"zero_shot": {}, "few_shot": {}}

    for mode_label, use_fewshot in [("zero_shot", False), ("few_shot", True)]:
        print(f"\n{'─' * 35}")
        print(f"  Running: {mode_label.replace('_', '-')}")
        print(f"{'─' * 35}")

        for name, text in invoices.items():
            print(f"  Extracting {name}...")
            extraction = extract_invoice(text, use_fewshot=use_fewshot)
            truth = ground_truth[name]
            scores = score_extraction(extraction, truth)
            all_scores[mode_label][name] = scores

    # ── Print per-field accuracy table ───────────────────────────────────
    all_fields = SCALAR_FIELDS + [
        "line_items_count", "line_items_amounts", "line_items_descriptions"
    ]

    print("\n" + "=" * 70)
    print("PER-FIELD ACCURACY TABLE")
    print("=" * 70)
    print(f"\n{'Field':<25} {'Zero-shot':>12} {'Few-shot':>12} {'Delta':>8}")
    print("-" * 60)

    for field in all_fields:
        # Compute accuracy across all docs for this field
        zs_vals = []
        fs_vals = []
        for name in invoices:
            zs_val = all_scores["zero_shot"][name].get(field, 0)
            fs_val = all_scores["few_shot"][name].get(field, 0)
            # Convert bool to float
            zs_vals.append(float(zs_val) if isinstance(zs_val, bool) else zs_val)
            fs_vals.append(float(fs_val) if isinstance(fs_val, bool) else fs_val)

        zs_acc = sum(zs_vals) / len(zs_vals) if zs_vals else 0
        fs_acc = sum(fs_vals) / len(fs_vals) if fs_vals else 0
        delta = fs_acc - zs_acc
        delta_str = f"+{delta:.0%}" if delta > 0 else f"{delta:.0%}"

        print(f"{field:<25} {zs_acc:>11.0%} {fs_acc:>11.0%} {delta_str:>8}")

    # ── Per-document breakdown ───────────────────────────────────────────
    print(f"\n{'─' * 60}")
    print("PER-DOCUMENT ACCURACY")
    print(f"{'─' * 60}")
    print(f"\n{'Document':<30} {'Zero-shot':>12} {'Few-shot':>12}")
    print("-" * 56)

    for name in invoices:
        zs_scores = all_scores["zero_shot"][name]
        fs_scores = all_scores["few_shot"][name]

        zs_correct = sum(
            1 for f in SCALAR_FIELDS if zs_scores.get(f, False)
        )
        fs_correct = sum(
            1 for f in SCALAR_FIELDS if fs_scores.get(f, False)
        )
        total_fields = len(SCALAR_FIELDS)

        print(
            f"{name:<30} {zs_correct}/{total_fields:>9} "
            f"{fs_correct}/{total_fields:>9}"
        )

    # ── Overall (with caveat) ────────────────────────────────────────────
    total_zs = sum(
        float(v) if isinstance(v, bool) else v
        for doc_scores in all_scores["zero_shot"].values()
        for v in doc_scores.values()
    )
    total_fs = sum(
        float(v) if isinstance(v, bool) else v
        for doc_scores in all_scores["few_shot"].values()
        for v in doc_scores.values()
    )
    n_total = sum(len(s) for s in all_scores["zero_shot"].values())

    print(f"\nOverall zero-shot: {total_zs/n_total:.1%}")
    print(f"Overall few-shot:  {total_fs/n_total:.1%}")

    # ╔══════════════════════════════════════════════════════════════════════╗
    # ║  CHECKPOINT                                                        ║
    # ║  Read the PER-FIELD table, never the overall number.               ║
    # ║                                                                    ║
    # ║  Key things to look for:                                           ║
    # ║  - Does few-shot improve DATE accuracy? (prose date, UK format)    ║
    # ║  - Does few-shot change po_number handling? (null vs invented)     ║
    # ║  - Does few-shot affect line_items_amounts? (OCR corrections)      ║
    # ║                                                                    ║
    # ║  The overall number hides which fields improved and which didn't.  ║
    # ║  A "5% improvement" means nothing if all the gain is in one field  ║
    # ║  and another field got worse.                                      ║
    # ║                                                                    ║
    # ║  EXAM NOTE — ~500 tokens per call from few-shot examples.          ║
    # ║  Only ship examples if they measurably help on the fields you      ║
    # ║  care about.                                                       ║
    # ╚══════════════════════════════════════════════════════════════════════╝

    return all_scores


if __name__ == "__main__":
    main()
