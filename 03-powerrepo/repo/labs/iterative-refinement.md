# Lab: Iterative Refinement

Ask Claude to implement one narrow change in `src/utils.py`. After each pass:

1. Run the smallest relevant test.
2. Review the diff against the acceptance criterion.
3. Give the exact failing output back to Claude.
4. Stop when the test and requirement both pass; do not add speculative scope.

Record each observation, change, and verification in `lab-notes.md` (ignored).
The exercise separates feedback-driven correction from repeatedly rewording a
prompt without new evidence.
