"""Offline checks for provenance-preserving research state."""

from jsonschema import Draft202012Validator

from core import build_manifest, load_manifest, save_manifest
from pipeline import OUTPUT_SCHEMA


def reports() -> list[dict]:
    return [
        {
            "worker_id": "adoption-a",
            "sections": ["adoption"],
            "claims": [{
                "key": "adoption_rate", "value": 0.62,
                "source_id": "survey-a", "quote_or_fact": "n=800",
            }],
            "errors": [],
        },
        {
            "worker_id": "adoption-b",
            "sections": ["adoption", "risk_controls"],
            "claims": [
                {
                    "key": "adoption_rate", "value": 0.48,
                    "source_id": "survey-b", "quote_or_fact": "n=1200",
                },
                {
                    "key": "recommended_controls", "value": ["allowlists", "hooks"],
                    "source_id": "controls-note",
                },
            ],
            "errors": [{
                "source_id": "outage-source", "error_category": "transient",
                "message": "timed out",
            }],
        },
    ]


def test_manifest_preserves_conflict_provenance_partial_error_and_gap(tmp_path):
    manifest = build_manifest(
        "run-1", reports(), ["adoption", "risk_controls", "costs"]
    )
    conflict = manifest["merged"]["conflicts"][0]
    assert conflict["key"] == "adoption_rate"
    assert {claim["source_id"] for claim in conflict["claims"]} == {
        "survey-a", "survey-b"
    }
    assert manifest["coverage_gaps"] == ["costs"]
    assert manifest["status"] == "partial"
    assert manifest["merged"]["partial_errors"][0]["source_id"] == "outage-source"

    path = tmp_path / "manifest.json"
    save_manifest(path, manifest)
    assert load_manifest(path) == manifest


def test_live_pipeline_output_contract_is_valid_json_schema():
    Draft202012Validator.check_schema(OUTPUT_SCHEMA)
