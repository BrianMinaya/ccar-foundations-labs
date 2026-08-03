"""Shared offline test setup."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-never-sent")

for relative in ("01-miniagent", "02-docextract", "04-research-pipeline"):
    sys.path.insert(0, str(ROOT / relative))
