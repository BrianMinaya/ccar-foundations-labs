"""Local, credential-free MCP tools and resources for the PowerRepo lab."""

from pathlib import Path

from mcp.server.fastmcp import FastMCP

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SEARCH_ROOTS = tuple((PROJECT_ROOT / name).resolve() for name in ("src", "api", "tests"))

mcp = FastMCP("powerrepo-study")


@mcp.tool()
def search_project(query: str) -> dict:
    """Find a literal text fragment in safe project source directories."""
    if not query or len(query) > 120:
        return {"status": "error", "is_retryable": False, "message": "Invalid query"}

    matches = []
    for root in SEARCH_ROOTS:
        for path in root.rglob("*.py"):
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if query.casefold() in line.casefold():
                    matches.append({
                        "file": str(path.relative_to(PROJECT_ROOT)),
                        "line": line_number,
                        "text": line.strip(),
                    })
    return {"status": "success", "data": matches, "count": len(matches)}


@mcp.resource("study://architecture")
def architecture_resource() -> str:
    """Return a small provenance-tagged map of the toy application."""
    return (
        "src/app.py: entry point\n"
        "api/routes.py: API route definitions\n"
        "api/handlers.py: request handlers\n"
        "src/utils.py: shared calculations\n"
        "tests/: offline pytest coverage\n"
    )


if __name__ == "__main__":
    mcp.run()
