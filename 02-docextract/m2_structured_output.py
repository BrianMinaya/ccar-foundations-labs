"""
DocExtract — M2: Structured Output via tool_use
================================================

THE USE CASE
------------
Input:  Raw invoice text (5 docs with different traps).
Output: Structured JSON extraction guaranteed to match the schema — every
        field present, correct types, no markdown fences, no parse errors.
Target: 5/5 docs produce valid, parseable extractions. invoice_04.po_number
        is null (not invented). invoice_02's subtotal says 500.00 — matching
        the document, which is WRONG. Valid JSON does not mean correct data.

Changes vs M1 (three lines):
  1. tools=[INVOICE_TOOL]
  2. tool_choice={"type": "tool", "name": "extract_invoice"}
  3. Read block.input (already a dict — no json.loads needed)
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


# ── Extraction with forced tool_use ──────────────────────────────────────────

def extract_invoice_structured(doc_text: str) -> dict:
    """
    Extract invoice data using forced tool_use.
    Returns the extraction as a plain dict (block.input is already parsed).
    """
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        # ╔════════════════════════════════════════════════════════════════╗
        # ║  CHANGE 1: Provide the tool definition                       ║
        # ╚════════════════════════════════════════════════════════════════╝
        tools=[INVOICE_TOOL],
        # ╔════════════════════════════════════════════════════════════════╗
        # ║  CHANGE 2: Force the model to call this specific tool        ║
        # ║                                                              ║
        # ║  EXAM NOTE — tool_choice options:                            ║
        # ║    "auto"  → model may return text OR call a tool            ║
        # ║    "any"   → model MUST call a tool, but can choose which    ║
        # ║    {"type": "tool", "name": "X"} → MUST call tool X         ║
        # ╚════════════════════════════════════════════════════════════════╝
        tool_choice={"type": "tool", "name": "extract_invoice"},
        messages=[
            {
                "role": "user",
                "content": (
                    "Extract all fields from this invoice document. "
                    "Return null for any field not present — do NOT invent values. "
                    "Convert dates to YYYY-MM-DD. Correct obvious OCR errors in "
                    "descriptions but preserve amounts exactly as stated.\n\n"
                    f"---\n\n{doc_text}"
                ),
            }
        ],
    )

    # ╔════════════════════════════════════════════════════════════════════╗
    # ║  CHANGE 3: Read block.input — already a dict, no json.loads()   ║
    # ║                                                                  ║
    # ║  EXAM NOTE — Constrained decoding eliminates SYNTAX errors only ║
    # ║  The output is guaranteed to be valid JSON matching the schema.  ║
    # ║  But valid != correct. invoice_02's subtotal will say 500.00    ║
    # ║  because the DOCUMENT says 500.00 — the model faithfully        ║
    # ║  extracted the wrong number from the source.                     ║
    # ╚════════════════════════════════════════════════════════════════════╝
    for block in response.content:
        if block.type == "tool_use":
            return validate_extraction_payload(block.input)

    raise RuntimeError("No tool_use block in response")


def main():
    invoices = load_invoices()
    results = {}
    parse_successes = 0

    print("=" * 70)
    print("M2: STRUCTURED OUTPUT VIA TOOL_USE")
    print("=" * 70)

    for name, text in invoices.items():
        print(f"\n--- {name} ---")
        try:
            extraction = extract_invoice_structured(text)
            parse_successes += 1
            results[name] = extraction

            # Highlight key fields
            print(f"  invoice_number: {extraction.get('invoice_number')}")
            print(f"  date:           {extraction.get('date')}")
            print(f"  vendor:         {extraction.get('vendor')}")
            print(f"  po_number:      {extraction.get('po_number')}")
            print(f"  subtotal:       {extraction.get('subtotal')}")
            print(f"  tax:            {extraction.get('tax')}")
            print(f"  total:          {extraction.get('total')}")
            print(f"  confidence:     {extraction.get('confidence')}")
            print(f"  line_items:     {len(extraction.get('line_items', []))} items")

            # ╔════════════════════════════════════════════════════════════╗
            # ║  EXAM NOTE — valid JSON, still wrong                     ║
            # ║  invoice_02: subtotal will say 500.00 (document's claim) ║
            # ║  but items actually sum to 392.00. The structure is      ║
            # ║  perfect; the CONTENT is wrong. Structure != correctness.║
            # ╚════════════════════════════════════════════════════════════╝

        except Exception as e:
            print(f"  ERROR: {e}")
            results[name] = None

    total = len(invoices)
    print("\n" + "=" * 70)
    print(f"PARSE SUCCESS RATE: {parse_successes}/{total}")
    print("=" * 70)

    # Specific checks
    if results.get("invoice_04_missing_po"):
        po = results["invoice_04_missing_po"].get("po_number")
        print(f"\ninvoice_04 po_number = {po!r}  (should be null/None)")

    if results.get("invoice_02_sum_mismatch"):
        sub = results["invoice_02_sum_mismatch"].get("subtotal")
        items = results["invoice_02_sum_mismatch"].get("line_items", [])
        computed = sum(item["amount"] for item in items)
        print(f"invoice_02 stated subtotal = {sub}, computed sum = {computed}")
        if sub != computed:
            print("  ^ Valid JSON, but subtotal does NOT match item sum!")

    # ╔══════════════════════════════════════════════════════════════════════╗
    # ║  CHECKPOINT                                                        ║
    # ║  Expected: 5/5 parse successes (zero parse errors)                 ║
    # ║                                                                    ║
    # ║  - Even the garbled OCR doc (invoice_05) parses perfectly.         ║
    # ║  - invoice_04.po_number is null — not invented.                    ║
    # ║  - invoice_02's extraction is perfectly valid JSON AND still wrong ║
    # ║    (subtotal says 500.00 matching the doc, not the real sum).      ║
    # ║                                                                    ║
    # ║  EXAM NOTE — strict mode requires:                                 ║
    # ║    - Every property listed in "required"                           ║
    # ║    - "additionalProperties": false                                 ║
    # ║    - No "optional" — use "type": ["string", "null"] instead        ║
    # ╚══════════════════════════════════════════════════════════════════════╝

    return results


if __name__ == "__main__":
    main()
