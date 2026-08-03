"""
DocExtract — M2 Schema: Pydantic Model + Tool Definition
=========================================================

THE USE CASE
------------
Input:  (imported by other modules — no direct I/O)
Output: A Pydantic model (InvoiceExtraction) and a tool definition dict
        (INVOICE_TOOL) that enforces structured output via Anthropic's
        tool_use with strict mode.
Target: Every extraction response is guaranteed to be valid JSON matching
        the schema — no parse errors, no missing fields, no extra fields.

This module defines the shared schema used by M2, M3, M4, M5, and M6.
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Pydantic models ──────────────────────────────────────────────────────────

class LineItem(BaseModel):
    """A single line item on an invoice."""

    model_config = ConfigDict(extra="forbid")

    description: str = Field(description="Description of the item or service")
    amount: float = Field(description="Amount in the document's currency")


class FieldConfidence(BaseModel):
    """Per-field confidence used for production review routing."""

    model_config = ConfigDict(extra="forbid")

    invoice_number: float = Field(ge=0.0, le=1.0)
    date: float = Field(ge=0.0, le=1.0)
    vendor: float = Field(ge=0.0, le=1.0)
    customer: float = Field(ge=0.0, le=1.0)
    po_number: float = Field(ge=0.0, le=1.0)
    line_items: float = Field(ge=0.0, le=1.0)
    subtotal: float = Field(ge=0.0, le=1.0)
    tax: float = Field(ge=0.0, le=1.0)
    total: float = Field(ge=0.0, le=1.0)


class InvoiceExtraction(BaseModel):
    """Structured extraction of all fields from an invoice document."""

    model_config = ConfigDict(extra="forbid")

    invoice_number: Optional[str] = Field(
        description="Invoice number/ID. Null if not present in the document."
    )
    date: str = Field(
        description="Invoice date in YYYY-MM-DD format. Convert prose dates."
    )
    vendor: str = Field(description="Name of the vendor/supplier/seller")
    customer: str = Field(description="Name of the customer/buyer/bill-to party")
    po_number: Optional[str] = Field(
        description=(
            "Purchase order number. Null if not present in the document. "
            "Do NOT invent or guess a PO number."
        )
    )
    line_items: list[LineItem] = Field(
        description="List of line items with description and amount"
    )
    subtotal: float = Field(description="Subtotal before tax")
    tax: Optional[float] = Field(
        description="Tax/VAT amount. Null if no tax is listed."
    )
    total: float = Field(description="Total amount due")
    invoice_kind: Literal["goods", "services", "mixed", "other", "unclear"] = Field(
        description="Controlled invoice category. Use 'other' only with other_kind_detail."
    )
    other_kind_detail: Optional[str] = Field(
        description="Category detail when invoice_kind is 'other'; otherwise null."
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Self-assessed confidence in the extraction, 0.0 to 1.0. "
            "Lower confidence for OCR-damaged, ambiguous, or incomplete documents."
        )
    )
    field_confidence: FieldConfidence = Field(
        description="Confidence for each extracted field, from 0.0 to 1.0."
    )


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  EXAM NOTE — strict mode schema rules                                 ║
# ║                                                                        ║
# ║  Under strict: true, the Anthropic API enforces:                       ║
# ║    1. Every property MUST appear in "required"                         ║
# ║    2. "additionalProperties": false must be set                        ║
# ║    3. There is no "optional" — nullable fields are expressed as        ║
# ║       "type": ["string", "null"]                                       ║
# ║                                                                        ║
# ║  This is CONSTRAINED DECODING: the model's token probabilities are     ║
# ║  masked so only schema-valid tokens can be emitted. This eliminates    ║
# ║  SYNTAX errors (malformed JSON, missing fields) but NOT SEMANTIC       ║
# ║  errors (wrong values, hallucinated content).                          ║
# ╚══════════════════════════════════════════════════════════════════════════╝


# ── Tool definition ──────────────────────────────────────────────────────────
# Built to match the Pydantic model exactly, with strict: true.

INVOICE_TOOL = {
    "name": "extract_invoice",
    "description": (
        "Extract structured data from an invoice document. "
        "Return null for fields not present — never invent values. "
        "Convert all dates to YYYY-MM-DD. Correct obvious OCR errors in text "
        "but preserve the original amounts exactly as stated in the document."
    ),
    # strict belongs on the tool definition, not inside input_schema.
    "strict": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "invoice_number",
            "date",
            "vendor",
            "customer",
            "po_number",
            "line_items",
            "subtotal",
            "tax",
            "total",
            "invoice_kind",
            "other_kind_detail",
            "confidence",
            "field_confidence",
        ],
        "properties": {
            "invoice_number": {
                "type": ["string", "null"],
                "description": "Invoice number/ID. Null if not present.",
            },
            "date": {
                "type": "string",
                "description": "Invoice date in YYYY-MM-DD format.",
            },
            "vendor": {
                "type": "string",
                "description": "Name of the vendor/supplier/seller.",
            },
            "customer": {
                "type": "string",
                "description": "Name of the customer/buyer/bill-to party.",
            },
            "po_number": {
                "type": ["string", "null"],
                "description": (
                    "Purchase order number. Null if not present. "
                    "Do NOT invent or guess a PO number."
                ),
            },
            "line_items": {
                "type": "array",
                "description": "List of line items.",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["description", "amount"],
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "Item/service description.",
                        },
                        "amount": {
                            "type": "number",
                            "description": "Amount for this line item.",
                        },
                    },
                },
            },
            "subtotal": {
                "type": "number",
                "description": "Subtotal before tax.",
            },
            "tax": {
                "type": ["number", "null"],
                "description": "Tax/VAT amount. Null if no tax listed.",
            },
            "total": {
                "type": "number",
                "description": "Total amount due.",
            },
            "invoice_kind": {
                "type": "string",
                "enum": ["goods", "services", "mixed", "other", "unclear"],
                "description": "Controlled invoice category.",
            },
            "other_kind_detail": {
                "type": ["string", "null"],
                "description": "Required detail for 'other'; null for known categories.",
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Self-assessed confidence, 0.0 to 1.0.",
            },
            "field_confidence": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "invoice_number", "date", "vendor", "customer", "po_number",
                    "line_items", "subtotal", "tax", "total"
                ],
                "properties": {
                    field: {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "description": f"Confidence for {field}, 0.0 to 1.0.",
                    }
                    for field in [
                        "invoice_number", "date", "vendor", "customer", "po_number",
                        "line_items", "subtotal", "tax", "total"
                    ]
                },
            },
        },
    },
}


def validate_extraction_payload(payload: dict) -> dict:
    """Apply semantic Pydantic validation after constrained decoding."""
    extraction = InvoiceExtraction.model_validate(payload)
    if extraction.invoice_kind == "other" and not extraction.other_kind_detail:
        raise ValueError("other_kind_detail is required when invoice_kind is 'other'")
    if extraction.invoice_kind != "other" and extraction.other_kind_detail is not None:
        raise ValueError("other_kind_detail must be null unless invoice_kind is 'other'")
    return extraction.model_dump()


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  CHECKPOINT                                                            ║
# ║  This module exports InvoiceExtraction (Pydantic) and INVOICE_TOOL     ║
# ║  (dict). The tool schema mirrors the Pydantic model exactly:           ║
# ║    - Every property appears in "required"                              ║
# ║    - additionalProperties: false at every object level                 ║
# ║    - Nullable fields use ["string", "null"] or ["number", "null"]      ║
# ║    - top-level tool strict: true enables constrained decoding          ║
# ║                                                                        ║
# ║  Import with:                                                          ║
# ║    from m2_schema import InvoiceExtraction, INVOICE_TOOL               ║
# ╚══════════════════════════════════════════════════════════════════════════╝
