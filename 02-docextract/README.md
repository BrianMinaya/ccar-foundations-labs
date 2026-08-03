# Project 02 — DocExtract

Structured extraction + validation + batch pipeline over messy invoices. Each
milestone exposes a failure the next one fixes. Built on Project 01's API patterns.

**Domains covered:** D4 Prompt Engineering & Structured Output (20%), reliability half of D5 Context Management & Reliability (15%).

**Use case:** Accounts Payable. ~200 supplier invoices/day arrive as messy text.
Input: one messy invoice → Output: one structured record, same shape every time,
ready for a DB insert.

## Setup

```bash
cd CCAR-F/02-docextract   # repo root, then into this project
source ../.venv/bin/activate   # shared venv from Project 01
# .env should already have your key (at repo root)
```

## Test Corpus

Each doc plants exactly one trap:

| Doc | Trap |
|---|---|
| `invoice_01_clean.txt` | VAT gap — items sum to £446, total is £535.20 (difference is 20% VAT) |
| `invoice_02_sum_mismatch.txt` | Items sum to £392, doc states £500 — a genuine conflict |
| `invoice_03_prose_date.txt` | "the third of March two thousand twenty-four" |
| `invoice_04_missing_po.txt` | No PO number anywhere — model should return null, not invent |
| `invoice_05_garbled.txt` | OCR damage (`16.oo`, `l` for `I`), ambiguous date `07/06/24` |

---

## M1 — Explicit Criteria (`m1_explicit_criteria.py`)

**Goal:** Demonstrate that prose instructions don't constrain output format.

**What the code does:**
Asks Claude to extract fields from each invoice, including "output ONLY the JSON
object, no markdown fences." Then runs `json.loads()` with no cleanup.

**Concepts (D4-4.1):**
- A prose instruction shifts probabilities; it does not constrain output
- The failure is silent until parse time — every response looks fine to a human

**Checkpoint:**
`PARSEABLE: 0/5` — every doc comes back in markdown fences despite being told
not to. **This is the intended failure.**

**If stuck:**
If some parse, you got lucky. Run again — it's probabilistic, not deterministic.
That's the point.

---

## M2 — Force Structure with tool_use (`m2_schema.py`, `m2_structured_output.py`)

**Goal:** Eliminate parse errors with constrained decoding. Discover that valid ≠ correct.

**What the code does:**
`m2_schema.py` defines the `extract_invoice` tool with top-level `strict: true` and a Pydantic
model. `m2_structured_output.py` changes three lines vs M1: `tools=`, `tool_choice=`,
and reads `block.input` (already a dict — no parsing needed).

**Concepts (D4-4.3):**
- `strict: true` requires every property in `required` + `additionalProperties: false`
- Under strict mode, there is no "optional" — express it as `"type": ["string", "null"]`
- `tool_choice` options: `"auto"` (may return text), `"any"` (must call a tool),
  `{"type":"tool","name":"..."}` (must call that specific tool)
- Constrained decoding eliminates SYNTAX errors only
- Pydantic validation still runs after decoding for semantic bounds and the
  enum-with-`other` detail invariant

**Checkpoint:**
Zero parse errors. `invoice_04.po_number` is `null` (not invented). But
`invoice_02` is perfectly valid JSON — and still wrong. **Valid ≠ correct.**

**If stuck:**
If you get parse errors, verify `tool_choice` forces the specific tool, not `"auto"`.

---

## M3 — Few-Shot the Stubborn Cases (`m3_fewshot.py`)

**Goal:** Improve extraction quality with few-shot examples. Learn to evaluate per-field.

**What the code does:**
Runs zero-shot and few-shot over all 5 docs, scores both against `ground_truth.json`
per field. Examples target a real judgment call: `"Business cards (500)"` is 1 pack,
`"Laminated posters (x10)"` is 10 units — both bracketed numbers, opposite meanings.

**Concepts (D4-4.2):**
- Few-shot examples demonstrate JUDGMENT for ambiguous cases
- Always read the per-field table, never just the overall number
- ~500 tokens per call — only ship examples if they measurably help

**Checkpoint:**
Read the per-field accuracy table. If few-shot doesn't win on the specific fields
you targeted, don't ship the examples.

**Non-obvious lesson:** Before trusting any eval, ask: "if the bug I care about
were present, would this number move?"

**If stuck:**
If scores are identical, your examples may not target the actual failure mode.
Design examples that exercise the specific ambiguity in your corpus.

---

## M4 — Validation & Retry-with-Feedback (`m4_validate_retry.py`)

**Goal:** Validate in Python, never in the prompt. Classify failures correctly.

**What the code does:**
Extracts, then validates: computes `items_sum` from line_items in Python,
checks against stated totals, verifies date format. Classifies each issue:
RECOVERABLE → retry with feedback (doc + bad output + exact error).
ABSENT → accept null, don't retry.
CONFLICT → flag for human with both numbers recorded.

**Concepts (D4-4.4, D5-5.2):**
- Arithmetic belongs in a calculator, not a text predictor
- Never base a check on a value the model supplied — basis is `items_sum` from Python
- RECOVERABLE → retry with feedback · ABSENT → accept null · CONFLICT → human
- "A fabricated tax can still defeat this check" — known, documented gap

**Checkpoint:**
`invoice_01` auto-accepts: items (£446) + tax (£89.20) = total (£535.20). A naive
`items ≠ total` check false-positives here.
`invoice_02` flagged CONFLICT: items sum to £392, doc states £500.

**Non-obvious bug this taught us:** The check originally used the model's own
`subtotal` as its basis, so a model that "helpfully" reconciled a broken invoice
silenced the conflict detector. Fixed: basis is always `items_sum`, computed in Python.

**If stuck:**
If invoice_01 is flagged, your VAT check needs to verify `items_sum + tax ≈ total`,
not just `items_sum ≈ total`.

---

## M5 — Batch (`m5_batch.py`)

**Goal:** Process in bulk with the Batch API. Discover that batch is one-shot.

**What the code does:**
Packs 5 docs with `custom_id` each, polls with exponential backoff, collects by
`custom_id`, runs M4 validation as a second pass. `--synthetic-100` creates a
100-document exercise; pure helpers choose sync vs batch and select only failed
terminal results for resubmission.

**Concepts (D4-4.5):**
- ~50% cheaper in and out; async, ≤24h window, no SLA
- Decision rule: is anything BLOCKED waiting? Yes → sync. No → batch
- `"ended"` describes the JOB, not the requests — always inspect each `result.type`
- Batch API does NOT support multi-turn tool calling (no agentic loop inside)
- `custom_id` for correlating request/response pairs

**Checkpoint:**
All 5 docs processed. Validation catches the same issues as M4.
Check that you handle `result.type != "succeeded"` — a batch can end with errors.

**If stuck:**
If the batch never ends, check that you're polling `processing_status`, not the
HTTP status code. Use exponential backoff to avoid rate limits.

---

## M6 — Calibration & Human Routing (`m6_calibration.py`)

**Goal:** Measure what you'd actually ship. Route on validation, not confidence.

**What the code does:**
Extracts with self-reported `confidence`, scores every field against labels. Prints
headline accuracy (labelled as "do not report alone"), accuracy by segment,
field-level confidence, a calibration table, stratified audit sampling, and
writes `output/human_review_queue.json`.

**Concepts (D5-5.5):**
- Ground-truth labels evaluate routing offline; they are never inputs to the
  production queue decision
- Self-reported confidence measures DOCUMENT DIFFICULTY, not SPEC COMPLIANCE
- "It can say 'this page is smudged'; it cannot say 'I misunderstood your subtotal definition'"
- The two numbers that matter: escapes (wrong auto-accepted) and false alarms (correct sent to human)
- Calibration is measurement, not fine-tuning — no weights change
- Never report one accuracy number — segment it

**Checkpoint:**
The model is likely overconfident (stated 0.96, actual 0.67 — your numbers will
vary). Route on **validation** (deterministic), not self-reported confidence.

**What the run actually showed:** The model auto-accepted a wrong document while
sending a correct one to human review. Self-reported confidence ≠ correctness.

**If stuck:**
If your calibration table shows perfect calibration, check that you're comparing
against `ground_truth.json`, not against the model's own stated values.
