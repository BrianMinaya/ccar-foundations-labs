# CCAR-F — Claude Certified Architect, Foundations: Hands-On Study Projects

Four small, runnable projects built to learn — by breaking things on purpose —
the concepts covered by Anthropic's **Claude Certified Architect: Foundations**
exam. Each milestone in each project demonstrates a specific failure mode first,
then fixes it, so the concept sticks.

## Guided walkthrough

For a staged learning sequence with environment setup, milestone checkpoints,
troubleshooting guidance, and a recommended project order, see
[GUIDED-WALKTHROUGH.md](GUIDED-WALKTHROUGH.md).

> **Disclaimer:** This is an independent, unofficial study project. It is not
> created by, affiliated with, or endorsed by Anthropic. "Claude," "Anthropic,"
> and "Claude Certified Architect" are trademarks of Anthropic PBC and are used
> here only to describe the subject matter being studied. No official exam
> content, questions, or answers are reproduced anywhere in this repo — these
> are original example programs written against the public exam domain list.
>
> Code in this repo is provided **as-is, for educational purposes**, under the
> [MIT License](LICENSE). It is not production-ready: several scripts contain
> deliberately broken code to illustrate failure modes (see each project's
> README for details). Running the examples calls the Anthropic API and will
> incur costs on your account — see [Costs](#costs) below.

## What's inside

| Project | Focus | Exam domains |
|---|---|---|
| [`01-miniagent/`](01-miniagent/) | Agentic loop, tools, multi-agent coordination | D1 Agentic Architecture & Orchestration, D2 Tool Design, D5 Reliability |
| [`02-docextract/`](02-docextract/) | Structured extraction, validation, batch processing | D4 Prompt Engineering & Structured Output, D5 Context Management & Reliability |
| [`03-powerrepo/`](03-powerrepo/) | Claude Code configuration (CLAUDE.md, hooks, skills, MCP) | D3 Claude Code Configuration & Workflows, D1/D2 enforcement half |
| [`04-research-pipeline/`](04-research-pipeline/) | Real Agent SDK subagents, provenance, conflicts, partial recovery | D1 Agentic Architecture & Orchestration, D2 Tool Design, D5 Reliability |

Each project folder has its own README with a milestone-by-milestone walkthrough,
what each script demonstrates, a checkpoint to verify you got it, and an
"if stuck" hint.

## Prerequisites

- Python 3.12+
- An [Anthropic API key](https://console.anthropic.com/settings/keys) (pay-as-you-go)

## Setup

```bash
git clone https://github.com/dennismyself/CCAR-F.git
cd CCAR-F

python3.12 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements-dev.txt

cp .env.example .env             # then edit .env and paste in your real key
```

`.env` (gitignored) should contain:

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

Never commit your real `.env` file or paste your API key into an issue, PR, or
screenshot — treat it like a password. If a key is ever exposed, revoke it
immediately in the [Anthropic Console](https://console.anthropic.com/settings/keys).

Then run any milestone script from inside its project folder, e.g.:

```bash
cd 01-miniagent
python m1_bare_loop.py
```

## Costs

These scripts make real calls to the Claude API. Model calls, batch jobs, and
repeated runs (M3–M6 in each project loop over multiple trials/documents) all
consume tokens and cost money against your Anthropic account. Costs here are
small (typically cents per run) but not zero — check the
[Anthropic pricing page](https://www.anthropic.com/pricing) and keep an eye on
your usage dashboard, especially before running batch or multi-trial scripts.

## About the certification

This repo is study material, not the exam itself. For the official exam guide,
syllabus, and registration, go directly to Anthropic's page:

**https://anthropic-partners.skilljar.com/claude-certified-architect-foundations-certification**

As of this repository's 0.2.0 review, Anthropic's certification FAQ describes
certification access as limited to eligible partner-program participants. That
eligibility can change, so check the official page before planning an exam date.
The code and explanations here remain open to everyone regardless of exam access.

The official exam guide PDF is not included in this repo — it's Anthropic's
copyrighted material, distributed through their own registration flow. Get it
from the link above.

## License

Code in this repo is licensed under the [MIT License](LICENSE) — use it,
fork it, adapt it for your own study. This license covers the code and
original written explanations only; it does not extend to Anthropic's
trademarks or any official exam materials.

## Contributing

Issues and PRs are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md), the
[security policy](SECURITY.md), and the [code of conduct](CODE_OF_CONDUCT.md)
first. Never contribute confidential exam content or official guide files.
