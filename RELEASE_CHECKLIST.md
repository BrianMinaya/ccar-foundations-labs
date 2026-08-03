# Open-Source Release Checklist

Before publishing a tag or pushing to a public repository:

- [ ] Run `pytest -q`, `ruff check .`, and `claude doctor` in the PowerRepo lab.
- [ ] Run secret scanning and inspect all staged files, including Git history.
- [ ] Confirm `.env`, `.venv`, generated queues, caches, and personal Claude
      settings are ignored.
- [ ] Confirm no official guide, exam questions, answer dumps, customer data, or
      third-party copyrighted course material is included.
- [ ] Verify current model names, CLI/SDK compatibility, certification URL, and
      eligibility wording against official Anthropic sources.
- [ ] Review live-call budget caps and mark every paid exercise clearly.
- [ ] Enable GitHub private vulnerability reporting and branch protection.
- [ ] Require the offline CI check before merge.
- [ ] Update `CHANGELOG.md`, `COMPATIBILITY.md`, and the project version together.
- [ ] Create a signed `v0.2.0` tag only after a clean-clone smoke test.
