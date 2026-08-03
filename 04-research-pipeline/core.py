"""Offline provenance, conflict, coverage, and manifest primitives."""

import json
from pathlib import Path


def merge_claims(reports: list[dict]) -> dict:
    """Merge reports without dropping source IDs or hiding disagreements."""
    claims_by_key: dict[str, list[dict]] = {}
    errors = []
    sections = set()
    for report in reports:
        sections.update(report.get("sections", []))
        errors.extend(report.get("errors", []))
        for claim in report.get("claims", []):
            record = {
                "value": claim["value"],
                "source_id": claim["source_id"],
                "quote_or_fact": claim.get("quote_or_fact", ""),
            }
            claims_by_key.setdefault(claim["key"], []).append(record)

    conflicts = []
    for key, claims in claims_by_key.items():
        distinct_values = {json.dumps(claim["value"], sort_keys=True) for claim in claims}
        if len(distinct_values) > 1:
            conflicts.append({"key": key, "claims": claims})
    return {
        "claims": claims_by_key,
        "conflicts": conflicts,
        "sections": sorted(sections),
        "partial_errors": errors,
    }


def find_coverage_gaps(required_sections: list[str], completed_sections: list[str]) -> list[str]:
    """Return required sections that no successful worker covered."""
    return sorted(set(required_sections) - set(completed_sections))


def build_manifest(run_id: str, reports: list[dict], required_sections: list[str]) -> dict:
    """Create serializable structured state for pause/resume and audit."""
    merged = merge_claims(reports)
    return {
        "schema_version": 1,
        "run_id": run_id,
        "completed_workers": sorted(report["worker_id"] for report in reports),
        "source_ids": sorted({
            claim["source_id"]
            for claims in merged["claims"].values()
            for claim in claims
        }),
        "merged": merged,
        "coverage_gaps": find_coverage_gaps(required_sections, merged["sections"]),
        "status": "partial" if merged["partial_errors"] else "complete",
    }


def save_manifest(path: Path, manifest: dict) -> None:
    """Persist structured run state atomically enough for this local lab."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    temporary.replace(path)


def load_manifest(path: Path) -> dict:
    """Load and minimally validate a saved manifest."""
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or not manifest.get("run_id"):
        raise ValueError("Unsupported or malformed manifest")
    return manifest
