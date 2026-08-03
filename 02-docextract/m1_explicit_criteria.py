"""
DocExtract — M1: Explicit Criteria (Prose-Only Extraction)
==========================================================

THE USE CASE
------------
Input:  Raw invoice text (5 docs with different traps: VAT gap, sum mismatch,
        prose date, missing PO, OCR damage).
Output: Structured JSON with invoice_number, date, vendor, customer, po_number,
        line_items, subtotal, tax, total.
Target: Parse the raw text response with json.loads() — NO cleanup of markdown
        fences. Demonstrates that prose instructions alone cannot guarantee
        machine-parseable output.

This module asks Claude to extract fields using only prose instructions and
attempts to parse the response with json.loads() with NO post-processing.
The model almost always wraps JSON in ```json fences despite being told not to.
"""

import os
import json
import glob
import anthropic
from dotenv import load_dotenv

# ── Load environment ──────────────────────────────────────────────────────────
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

client = anthropic.Anthropic()
MODEL = "claude-haiku-4-5"

# ── Document loader ──────────────────────────────────────────────────────────
DOCS_DIR = os.path.join(os.path.dirname(__file__), "docs")


def load_invoices() -> dict[str, str]:
    """Load all invoice text files from docs/ directory."""
    invoices = {}
    for filepath in sorted(glob.glob(os.path.join(DOCS_DIR, "invoice_*.txt"))):
        name = os.path.splitext(os.path.basename(filepath))[0]
        with open(filepath, "r", encoding="utf-8") as f:
            invoices[name] = f.read()
    return invoices


# ── Extraction prompt ────────────────────────────────────────────────────────
EXTRACTION_PROMPT = (
    "Extract the following fields from this invoice: "
    "invoice_number, date (YYYY-MM-DD), vendor, customer, po_number, "
    "line_items (list with description and amount), subtotal, tax, total. "
    "Output ONLY the JSON object, no markdown fences, no explanation."
)

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  EXAM NOTE — Prose instruction shifts probability, not structure       ║
# ║  "A prose instruction shifts probabilities; it does not constrain      ║
# ║   output." The model has been trained on millions of examples where    ║
# ║   JSON is wrapped in ```json fences. Telling it "no fences" reduces   ║
# ║   the probability but cannot eliminate it. Any downstream code that    ║
# ║   relies on json.loads() without stripping fences WILL break.         ║
# ╚══════════════════════════════════════════════════════════════════════════╝


def extract_invoice_prose(doc_text: str) -> tuple[dict | None, str]:
    """
    Send invoice text to Claude with prose-only instructions.
    Returns (parsed_dict_or_None, raw_response_text).
    Deliberately does NOT strip markdown fences before parsing.
    """
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": f"{EXTRACTION_PROMPT}\n\n---\n\n{doc_text}",
            }
        ],
    )

    raw_text = response.content[0].text

    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  EXAM NOTE — No cleanup applied here                          ║
    # ║  We deliberately do NOT strip ```json ... ``` fences.         ║
    # ║  This is the point: prose instructions alone cannot guarantee  ║
    # ║  the output is bare JSON parseable by json.loads().            ║
    # ╚══════════════════════════════════════════════════════════════════╝

    try:
        parsed = json.loads(raw_text)
        return parsed, raw_text
    except json.JSONDecodeError:
        return None, raw_text


def main():
    invoices = load_invoices()
    results = {}
    parse_successes = 0

    print("=" * 70)
    print("M1: PROSE-ONLY EXTRACTION (no fence stripping)")
    print("=" * 70)

    for name, text in invoices.items():
        print(f"\n--- {name} ---")
        parsed, raw = extract_invoice_prose(text)

        if parsed is not None:
            parse_successes += 1
            print(f"  PARSED OK: {list(parsed.keys())}")
        else:
            # Show the first 120 chars to reveal the markdown fences
            preview = raw[:120].replace("\n", "\\n")
            print(f"  PARSE FAILED: {preview}...")

        results[name] = {"parsed": parsed, "raw": raw}

    total = len(invoices)
    print("\n" + "=" * 70)
    print(f"PARSE SUCCESS RATE: {parse_successes}/{total}")
    print("=" * 70)

    # ╔══════════════════════════════════════════════════════════════════════╗
    # ║  CHECKPOINT                                                        ║
    # ║  Expected: PARSEABLE: 0/5                                          ║
    # ║  Every doc comes back wrapped in ```json fences despite the        ║
    # ║  explicit instruction "no markdown fences, no explanation."         ║
    # ║                                                                    ║
    # ║  If some parse successfully, the model got lucky — it still isn't  ║
    # ║  GUARANTEED. The failure mode is non-deterministic: the same       ║
    # ║  prompt may succeed on retry and fail the next time.               ║
    # ║                                                                    ║
    # ║  Takeaway: You need STRUCTURAL guarantees (tool_use, JSON mode),   ║
    # ║  not probabilistic ones (prose instructions).                      ║
    # ╚══════════════════════════════════════════════════════════════════════╝

    return results


if __name__ == "__main__":
    main()
