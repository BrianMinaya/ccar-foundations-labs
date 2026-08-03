# Contributing

Thank you for improving these independent study labs. Contributions should be
original and based on public Anthropic documentation. Do not submit exam
questions, answer dumps, proprietary course material, or the official exam
guide.

## Development

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
ruff check .
```

Offline tests must pass without a real API key. Live examples should state that
they incur cost and must use explicit turn and budget limits where supported.
Add focused tests for behavior changes and update the relevant project README.

Use a small branch and a conventional commit (`fix:`, `feat:`, `docs:`,
`test:`). By contributing, you agree that your contribution is licensed under
the repository’s MIT License.
