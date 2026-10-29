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

if __package__:
    from . import m112_pbs_utilisation_replay as pbs_replay
else:
    import m112_pbs_utilisation_replay as pbs_replay

ROOT = Path(__file__).resolve().parents[1]
ROLE_REPORT = (
    "quality/qualifications/"
    "australian-m112-v4-contract-role-evidence-qualification-20261019.json"
)
V1_SCHEMA = "contracts/medallion/v1/medallion-conformance.schema.json"
OUTPUT = "quality/qualifications/australian-m112-v1-conformance-20261019.json"
PBS_OUTPUT = (
    "quality/qualifications/"
    "australian-m112-pbs-utilisation-v1-conformance-20261028.json"
)
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
    root: Path,
    candidate: dict[str, Any],
    *,
    rights_basis: dict[str, str] | None = None,
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
    permitted_bases = RIGHTS_BASIS if rights_basis is None else rights_basis
    selected_basis = permitted_bases.get(rights_state)
    if selected_basis is None:
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
        "reason_codes": [selected_basis],
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


def _pbs_candidates(root: Path) -> list[dict[str, Any]]:
    rights = _read_json(root, pbs_replay.RIGHTS_LINEAGE)
    lineage = _read_json(root, pbs_replay.LINEAGE)
    by_path = {row["path"]: row for row in lineage["objects"]}
    if (
        len(rights["objects"]) != pbs_replay.OBJECT_COUNT
        or len(by_path) != pbs_replay.OBJECT_COUNT
    ):
        raise ValueError(
            "PBS v1 conformance requires the exact six-object cohort"
        )
    candidates: list[dict[str, Any]] = []
    for row in rights["objects"]:
        snapshot, _ = pbs_replay.build_snapshot(root, target_path=row["path"])
        candidates.append({
            "dataset": pbs_replay.DATASET,
            "revision": pbs_replay.REVISION,
            "path": row["path"],
            "sha256": snapshot["payload_sha256"],
            "source_id": snapshot["source_id"],
            "acquisition_id": by_path[row["path"]]["acquisition_id"],
            "rights_state": pbs_replay.RIGHTS_STATE,
            "anonymous_digest_readback": True,
            "contract_role_states": {"lineage.inputs": "qualified_b1_b2_only"},
            "rights_decision": {
                "path": pbs_replay.RIGHTS_ATTESTATION,
                "sha256": pbs_replay.INPUT_DIGESTS[
                    pbs_replay.RIGHTS_ATTESTATION
                ],
            },
            "lineage_evidence": {
                "path": pbs_replay.LINEAGE,
                "sha256": pbs_replay.INPUT_DIGESTS[pbs_replay.LINEAGE],
            },
            "digest_evidence": {
                "path": pbs_replay.DIGEST_REPORT,
                "sha256": pbs_replay.INPUT_DIGESTS[pbs_replay.DIGEST_REPORT],
            },
        })
    return candidates


def qualify(root: Path = ROOT, *, cohort: str = "mbs") -> dict[str, Any]:
    """Return the deterministic v1 manifest from currently bound evidence."""
    if cohort == "pbs":
        return _build_document(
            root,
            _pbs_candidates(root),
            rights_basis={
                pbs_replay.RIGHTS_STATE: (
                    "maintainer_attested_exact_scope_permission_not_independently_reviewed"
                ),
            },
        )
    if cohort != "mbs":
        raise ValueError("unsupported M-112 conformance cohort")
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
    return _build_document(root, candidates)


def _build_document(
    root: Path,
    candidates: list[Any],
    *,
    rights_basis: dict[str, str] | None = None,
) -> dict[str, Any]:
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
        artifact, promotion = _qualify_candidate(
            root,
            candidate,
            rights_basis=rights_basis,
        )
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
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cohort", choices=("mbs", "pbs"), default="mbs")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    document = qualify(cohort=args.cohort)
    expected = _canonical_bytes(document)
    output = args.output or ROOT / (
        PBS_OUTPUT if args.cohort == "pbs" else OUTPUT
    )
    if args.check:
        if not output.is_file() or output.read_bytes() != expected:
            raise SystemExit(f"v1 conformance output is stale: {output}")
        print(
            f"v1 conformance passed: {len(document['artifacts'])} "
            "exact M-112 raw B2 identities"
        )
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(expected)
    print(f"wrote {output} sha256={_digest(expected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
