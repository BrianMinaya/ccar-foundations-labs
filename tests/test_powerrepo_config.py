"""Validate the PowerRepo configuration and enforcement sample."""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POWERREPO = ROOT / "03-powerrepo/repo"


def run_hook(command: str) -> subprocess.CompletedProcess:
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    return subprocess.run(
        [str(POWERREPO / ".claude/hooks/block-dangerous.sh")],
        input=payload,
        text=True,
        capture_output=True,
        check=False,
    )


def test_hook_settings_use_nested_command_shape():
    settings = json.loads((POWERREPO / ".claude/settings.json").read_text())
    matcher = settings["hooks"]["PreToolUse"][0]
    assert matcher["matcher"] == "Bash"
    assert matcher["hooks"][0]["type"] == "command"
    assert (POWERREPO / ".claude/hooks/block-dangerous.sh").stat().st_mode & 0o111


def test_hook_blocks_flag_variants_and_allows_safe_commands():
    for command in (
        "rm -rf build/", "rm -fr build/", "rm -r -f build/",
        'rm "-rf" build/', "rm -r --force build/",
    ):
        assert run_hook(command).returncode == 2
    assert run_hook("rm -r build/").returncode == 0
    assert run_hook("pytest -q").returncode == 0


def test_mcp_server_target_exists_and_requires_no_secret():
    config = json.loads((POWERREPO / ".mcp.json").read_text())
    server = config["mcpServers"]["study-tools"]
    assert server["command"] == "python3"
    assert "env" not in server
    assert (POWERREPO / server["args"][0]).is_file()


def test_ci_extracts_structured_output_and_has_no_fail_open_jq():
    workflow = (POWERREPO / ".github/workflows/claude-review.yml").read_text()
    assert "--json-schema" in workflow
    assert ".structured_output" in workflow
    assert "|| echo \"0\"" not in workflow
    schema = json.loads((POWERREPO / ".github/claude-review-schema.json").read_text())
    assert schema["properties"]["findings"]["type"] == "array"
