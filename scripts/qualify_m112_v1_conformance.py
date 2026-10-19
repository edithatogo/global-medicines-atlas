"""Build the v1 conformance manifest for the exact M-112 eligible raw B2 cohort.

This is metadata-only. It binds existing rights, lineage, and digest evidence,
keeps every B2 object as a candidate, and records v4 admission as blocked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from operator import itemgetter
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
ROLE_REPORT = (
    "quality/qualifications/"
    "australian-m112-v4-contract-role-evidence-qualification-20261019.json"
)
V1_SCHEMA = "contracts/medallion/v1/medallion-conformance.schema.json"
OUTPUT = "quality/qualifications/australian-m112-v1-conformance-20261019.json"
EXPECTED_OBJECT_COUNT = 16
RIGHTS_BASIS = {
    "authorized_exact_source_release_permitted": (
        "exact_source_release_authorization"
    ),
    "approved_exact_scope_CC_BY_3_0_AU_publicly_readback_verified": (
        "exact_scope_CC_BY_3_0_AU_authorization"
    ),
}


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_json(root: Path, relative: str) -> dict[str, Any]:
    value: Any = json.loads((root / relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected a JSON object: {relative}")
    return cast("dict[str, Any]", value)


def _verify_reference(root: Path, reference: dict[str, Any]) -> None:
    path = reference.get("path")
    expected = reference.get("sha256")
    if not isinstance(path, str) or not isinstance(expected, str):
        raise TypeError("evidence reference needs a path and SHA-256")
    candidate = root / path
    if not candidate.is_file() or _digest(candidate.read_bytes()) != expected:
        raise ValueError(f"evidence reference digest mismatch: {path}")


def _verify_references(root: Path, value: Any) -> None:
    if isinstance(value, dict):
        reference = cast("dict[str, Any]", value)
        if "path" in reference and "sha256" in reference:
            _verify_reference(root, reference)
        for nested in reference.values():
            _verify_references(root, nested)
    elif isinstance(value, list):
        for nested in cast("list[Any]", value):
            _verify_references(root, nested)


def _identity(candidate: dict[str, Any]) -> tuple[str, str, str, str]:
    values = tuple(
        candidate.get(key) for key in ("dataset", "revision", "path", "sha256")
    )
    if not all(isinstance(value, str) and value for value in values):
        raise ValueError("M-112 object identity is incomplete")
    dataset, revision, path, content_sha256 = values
    return (
        cast("str", dataset),
        cast("str", revision),
        cast("str", path),
        cast("str", content_sha256),
    )


def _qualify_candidate(
    root: Path, candidate: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    dataset, revision, path, content_sha256 = _identity(candidate)
    if candidate.get("anonymous_digest_readback") is not True:
        raise ValueError("M-112 object lacks anonymous digest evidence")
    lineage_states_value = candidate.get("contract_role_states", {})
    if not isinstance(lineage_states_value, dict):
        raise TypeError("M-112 lineage role state is not an object")
    lineage_states = cast("dict[str, Any]", lineage_states_value)
    if lineage_states.get("lineage.inputs") != "qualified_b1_b2_only":
        raise ValueError("M-112 object lacks complete B1/B2 lineage")
    rights_state = candidate.get("rights_state")
    if not isinstance(rights_state, str):
        raise TypeError("M-112 rights state is not text")
    rights_basis = RIGHTS_BASIS.get(rights_state)
    if rights_basis is None:
        raise ValueError("M-112 object lacks exact-scope rights evidence")

    references = (
        candidate.get("rights_decision"),
        candidate.get("lineage_evidence"),
        candidate.get("digest_evidence"),
    )
    if not all(isinstance(reference, dict) for reference in references):
        raise ValueError("M-112 object lacks a bound evidence reference")
    for reference in references:
        _verify_references(root, reference)

    acquisition_id = candidate.get("acquisition_id")
    if not isinstance(acquisition_id, str) or not acquisition_id:
        raise ValueError("M-112 object lacks its B1 acquisition identity")
    artifact_id = f"m112:{dataset}@{revision}:{path}"
    rights_decision = {
        "decision_id": f"m112-rights:{dataset}:{path}:{content_sha256}",
        "status": "approved",
        "scope": f"{dataset}@{revision}:{path} sha256:{content_sha256}",
        "reason_codes": [rights_basis],
    }
    artifact = {
        "artifact_id": artifact_id,
        "layer": "bronze_b2",
        "sha256": content_sha256,
        "lineage": {
            "input_artifact_ids": [f"b1-acquisition:{acquisition_id}"],
            "input_sha256": [content_sha256],
        },
        "rights_decision": rights_decision,
        "promotion_status": "candidate",
    }
    promotion = {
        "decision_id": f"m112-v4-blocked:{content_sha256}:{path}",
        "subject_artifact_id": artifact_id,
        "from_layer": "bronze_b2",
        "to_layer": "silver",
        "input_sha256": [content_sha256],
        "required_gate_ids": [
            "v4_publication",
            "v4_clean_room_verification",
            "v1_v3_lineage",
            "v4_discovery",
            "v4_recovery_cache",
            "consumer_canary",
        ],
        "passed_gate_ids": [
            "exact_scope_rights",
            "b1_b2_lineage",
            "anonymous_digest_readback",
        ],
        "rights_decision": rights_decision,
        "status": "blocked",
        "fail_closed": True,
        "reason_codes": ["v4_contract_roles_incomplete"],
    }
    return artifact, promotion


def qualify(root: Path = ROOT) -> dict[str, Any]:
    """Return the deterministic v1 manifest from currently bound evidence."""
    role_report = _read_json(root, ROLE_REPORT)
    if role_report.get("contract", {}).get("version") != "4.1":
        raise ValueError("M-112 role report is not bound to v4.1")
    if role_report.get("cohort", {}).get("v4_admissions") != 0:
        raise ValueError("M-112 v4 admission count changed")

    candidates_value = role_report.get("objects")
    if not isinstance(candidates_value, list):
        raise TypeError("M-112 role report has no object list")
    candidates = cast("list[Any]", candidates_value)
    if len(candidates) != EXPECTED_OBJECT_COUNT:
        raise ValueError("the approved exact-rights MBS raw cohort changed")

    identities: set[tuple[str, str, str, str]] = set()
    artifacts: list[dict[str, Any]] = []
    promotions: list[dict[str, Any]] = []
    for candidate_value in candidates:
        if not isinstance(candidate_value, dict):
            raise TypeError("malformed M-112 cohort member")
        candidate = cast("dict[str, Any]", candidate_value)
        identity = _identity(candidate)
        if identity in identities:
            raise ValueError("duplicate M-112 path identity")
        identities.add(identity)
        artifact, promotion = _qualify_candidate(root, candidate)
        artifacts.append(artifact)
        promotions.append(promotion)

    document = {
        "vocabulary_version": "1.0.0",
        "repository": "edithatogo/global-medicines-atlas",
        "artifacts": sorted(artifacts, key=itemgetter("artifact_id")),
        "promotion_decisions": sorted(
            promotions, key=itemgetter("decision_id")
        ),
    }
    schema = json.loads((root / V1_SCHEMA).read_bytes())
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(document)  # pyright: ignore[reportUnknownMemberType]
    return document


def _canonical_bytes(document: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            document, ensure_ascii=False, sort_keys=True, indent=2
        ).encode("utf-8")
        + b"\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = _canonical_bytes(qualify())
    if args.check:
        if not args.output.is_file() or args.output.read_bytes() != expected:
            raise SystemExit(f"v1 conformance output is stale: {args.output}")
        print("v1 conformance passed: 16 exact M-112 raw B2 identities")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(expected)
    print(f"wrote {args.output} sha256={_digest(expected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
