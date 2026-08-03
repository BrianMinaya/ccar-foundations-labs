# Lab: Independent Multi-Pass Review

Review the same diff in three fresh headless sessions. Keep their contexts
independent so one reviewer’s framing does not anchor the next.

1. Correctness pass: edge cases, invariants, and error handling.
2. Security pass: trust boundaries, unsafe inputs, and secret exposure.
3. Test pass: missing assertions and regressions the suite would not detect.

Use the JSON schema in `.github/claude-review-schema.json` for every pass, then
merge findings by `(file, line, description)`. Resolve conflicts with evidence
from the code and tests, not majority vote.
