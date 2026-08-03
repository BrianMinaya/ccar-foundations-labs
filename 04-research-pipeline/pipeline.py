"""Real Agent SDK coordinator with Task subagents and provenance tools."""

import asyncio
import json
from pathlib import Path

from claude_agent_sdk import (
    AgentDefinition,
    ClaudeAgentOptions,
    ResultMessage,
    create_sdk_mcp_server,
    query,
    tool,
)

BASE_DIR = Path(__file__).resolve().parent
SOURCES = {item["source_id"]: item for item in json.loads(
    (BASE_DIR / "sources.json").read_text(encoding="utf-8")
)}


def result(payload: dict, *, is_error: bool = False) -> dict:
    response = {"content": [{"type": "text", "text": json.dumps(payload)}]}
    if is_error:
        response["is_error"] = True
    return response


@tool("search_sources", "Search source titles and sections; returns source IDs.", {"query": str})
async def search_sources(args: dict) -> dict:
    query_text = args["query"].casefold()
    matches = [
        {key: source[key] for key in ("source_id", "title", "section", "provenance")}
        for source in SOURCES.values()
        if query_text in json.dumps(source).casefold()
    ]
    return result({"status": "success", "data": matches, "count": len(matches)})


@tool("read_source", "Read one source by ID and preserve its provenance.", {"source_id": str})
async def read_source(args: dict) -> dict:
    source = SOURCES.get(args["source_id"])
    if source is None:
        return result({
            "status": "success", "data": None, "count": 0,
            "message": "No source with that ID.",
        })
    if source.get("available") is False:
        return result({
            "status": "error", "error_category": "transient", "is_retryable": True,
            "source_id": source["source_id"], "message": "Source timed out after retries.",
        }, is_error=True)
    return result({"status": "success", "data": source, "count": 1})


research_server = create_sdk_mcp_server(
    name="research",
    version="1.0.0",
    tools=[search_sources, read_source],
)

RESEARCH_TOOLS = ["mcp__research__search_sources", "mcp__research__read_source"]
AGENTS = {
    "adoption_researcher": AgentDefinition(
        description="Researches adoption evidence and reports every source ID.",
        prompt=(
            "Research only adoption. Read all relevant sources. Return claims as "
            "key/value/source_id records. Surface disagreement; never average it away."
        ),
        tools=RESEARCH_TOOLS,
        maxTurns=6,
    ),
    "controls_researcher": AgentDefinition(
        description="Researches operational controls and unavailable cost evidence.",
        prompt=(
            "Research risk controls and costs. Preserve provenance. If a source errors, "
            "return partial findings plus a typed error and explicit coverage gap."
        ),
        tools=RESEARCH_TOOLS,
        maxTurns=6,
    ),
    "evidence_reviewer": AgentDefinition(
        description="Checks provenance, conflicts, and coverage before synthesis.",
        prompt=(
            "Audit worker reports. Reject unsupported claims, list conflicting values "
            "side-by-side, and name required sections with no successful source."
        ),
        tools=[],
        maxTurns=4,
    ),
}

OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["claims", "conflicts", "coverage_gaps", "partial_errors", "summary"],
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["key", "value", "source_id"],
                "properties": {
                    "key": {"type": "string"},
                    "value": {"type": "string"},
                    "source_id": {"type": "string"},
                },
            },
        },
        "conflicts": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["key", "values", "source_ids"],
                "properties": {
                    "key": {"type": "string"},
                    "values": {"type": "array", "items": {"type": "string"}},
                    "source_ids": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "coverage_gaps": {"type": "array", "items": {"type": "string"}},
        "partial_errors": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["source_id", "error_category", "message"],
                "properties": {
                    "source_id": {"type": "string"},
                    "error_category": {"type": "string"},
                    "message": {"type": "string"},
                },
            },
        },
        "summary": {"type": "string"},
    },
}


async def main() -> None:
    """Run the live/paid coordinator; offline logic is tested in core.py."""
    options = ClaudeAgentOptions(
        system_prompt=(
            "You coordinate a research pipeline. Use Task to delegate adoption and "
            "controls/costs independently, preferably in parallel. Then delegate an "
            "evidence review with both reports. Preserve source IDs on every claim. "
            "Conflicting values and unavailable sources must remain visible."
        ),
        agents=AGENTS,
        allowed_tools=["Task"],
        mcp_servers={"research": research_server},
        output_format={"type": "json_schema", "schema": OUTPUT_SCHEMA},
        max_turns=14,
        max_budget_usd=1.50,
    )
    prompt = (
        "Research adoption, risk controls, and costs. Required sections: adoption, "
        "risk_controls, costs. Produce an evidence-backed synthesis."
    )
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            print(json.dumps(message.structured_output, indent=2))
            print(f"session_id={message.session_id}")


if __name__ == "__main__":
    asyncio.run(main())
