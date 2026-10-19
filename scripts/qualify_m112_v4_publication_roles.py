"""Reconcile existing hosted MBS utilisation receipts to M-112 candidates.

This binds no v4 contract and performs no admission. It records exact-object
publication and token-free anonymous restore receipts as candidate evidence.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
ROLE_REPORT = "quality/qualifications/australian-m112-v4-contract-role-evidence-qualification-20261019.json"
DIGEST_REPORT = "quality/qualifications/australian-m112-utilisation-digest-reconciliation-20261004.json"
DISCOVERY_REPORT = "quality/qualifications/australian-m112-v4-discovery-role-evidence-20261020.json"
OUTPUT = "quality/qualifications/australian-m112-v4-contract-role-evidence-qualification-20261020.json"
DATASET = "edithatogo/australian-mbs-utilisation-archive"
PINNED_REVISION = "dee9a5b0580dfe394474dc26b372559462e157e7"
WORKFLOW_COMMIT = "979f806fcf92267f9595eb78a88707e4ec2e503c"
WORKFLOW_RUN = "36333396964"
PUBLICATION_RECEIPT_URL = "https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-5857784415"
PUBLICATION_RECEIPT_SHA256 = (
    "6bce093347564588b320f81344c4903c038f4659d5aeb96bca4b2802073c9c1d"
)
VERIFICATION_RECEIPT_URL = "https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-5857784489"
VERIFICATION_RECEIPT_SHA256 = (
    "5069e57b54a2c3d2aff9901389738998a8944de006505a8f3ac0e02bb4e87a15"
)
EXPECTED_PATHS = 14
EXPECTED_CANDIDATES = 16
EXPECTED_MANIFEST_FILES = 28
OBSERVED_AT = "2026-10-19T16:07:04Z"
CONTRACT_REPOSITORY = "edithatogo/global-medicines-atlas"
CONTRACT_COMMIT = "a5753b1c79ccedd9bb54112bf803882ffc9deb96"
CONTRACT_SCHEMA_PATH = "contracts/medallion/v4.1/federation.schema.json"
CONTRACT_SCHEMA_SHA256 = (
    "03acfbafd80daf0b8b768f7814dbb29a9bd13e7c9d5d68797b30261da29770c6"
)
PRODUCER_WORKFLOW = ".github/workflows/australian-mbs-utilisation-harvest.yml"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_json(root: Path, relative: str) -> dict[str, Any]:
    value: Any = json.loads((root / relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {relative}")
    return cast("dict[str, Any]", value)


def _verify_local_evidence_reference(
    root: Path, reference: dict[str, Any]
) -> None:
    path = reference.get("path")
    expected = reference.get("sha256")
    if not isinstance(path, str) or not isinstance(expected, str):
        raise TypeError("location digest reference needs path and SHA-256")
    evidence_path = root / path
    if (
        not evidence_path.is_file()
        or _sha256(evidence_path.read_bytes()) != expected
    ):
        raise ValueError(f"location digest evidence does not verify: {path}")


def _receipt_ref(url: str, digest: str) -> dict[str, str]:
    return {"url": url, "sha256": digest}


def _find_archive(archives: list[Any]) -> dict[str, Any]:
    for item_value in archives:
        if not isinstance(item_value, dict):
            continue
        item = cast("dict[str, Any]", item_value)
        if (
            item.get("dataset") == DATASET
            and item.get("revision") == PINNED_REVISION
        ):
            return item
    raise TypeError("exact MBS utilisation archive receipt is missing")


def _verify_archive_receipt(archive: dict[str, Any]) -> dict[str, Any]:
    historical = archive.get("historical_verification_receipt")
    if not isinstance(historical, dict):
        raise TypeError("hosted anonymous restore receipt is missing")
    historical = cast("dict[str, Any]", historical)
    expected: dict[str, Any] = {
        "workflow_run": WORKFLOW_RUN,
        "workflow_commit": WORKFLOW_COMMIT,
        "workflow_conclusion": "success",
        "anonymous_digest_verification": "passed",
        "temporary_source_bytes_removed": True,
        "verified_file_count": EXPECTED_MANIFEST_FILES,
        "issue_comment_body_sha256": VERIFICATION_RECEIPT_SHA256,
    }
    if any(historical.get(key) != value for key, value in expected.items()):
        raise ValueError("hosted publication/restore receipt does not qualify")
    if (
        archive.get("manifest_object_count") != EXPECTED_MANIFEST_FILES
        or archive.get("raw_candidate_object_count") != EXPECTED_PATHS
    ):
        raise ValueError(
            "hosted manifest no longer covers the expected raw cohort"
        )
    return historical


def _manifest_match(item_value: Any, identity: tuple[Any, ...]) -> bool:
    if not isinstance(item_value, dict):
        return False
    item = cast("dict[str, Any]", item_value)
    return (
        item.get("dataset") == identity[0]
        and item.get("revision") == identity[1]
        and item.get("path") == identity[2]
        and item.get("sha256") == identity[3]
        and item.get("byte_count") == identity[4]
        and item.get("matched_hosted_verified_manifest") is True
    )


def _bind_authority_candidate(candidate: dict[str, Any], root: Path) -> None:
    if (
        _sha256((root / CONTRACT_SCHEMA_PATH).read_bytes())
        != CONTRACT_SCHEMA_SHA256
    ):
        raise ValueError("pinned v4.1 schema digest differs from current bytes")
    states_value = candidate.get("contract_role_states")
    if not isinstance(states_value, dict):
        raise TypeError("candidate has no v4 contract role states")
    states = cast("dict[str, Any]", states_value)
    states["authority"] = "candidate_identity_available_unbound"
    candidate["authority_candidate"] = {
        "producer_repository": CONTRACT_REPOSITORY,
        "contract_repository": CONTRACT_REPOSITORY,
        "contract_commit": CONTRACT_COMMIT,
        "schema_path": CONTRACT_SCHEMA_PATH,
        "schema_sha256": CONTRACT_SCHEMA_SHA256,
        "producer_workflow": PRODUCER_WORKFLOW,
        "producer_workflow_commit": WORKFLOW_COMMIT,
        "producer_workflow_run": (
            f"https://github.com/{CONTRACT_REPOSITORY}/actions/runs/{WORKFLOW_RUN}"
        ),
        "contract_role_state": "candidate_identity_available_unbound",
    }


def _bind_candidate(
    candidate: dict[str, Any],
    verified_objects: list[Any],
    archive: dict[str, Any],
    root: Path,
) -> dict[str, Any]:
    identity = (
        candidate.get("dataset"),
        candidate.get("revision"),
        candidate.get("path"),
        candidate.get("sha256"),
        candidate.get("bytes"),
    )
    matches: list[dict[str, Any]] = [
        cast("dict[str, Any]", item)
        for item in verified_objects
        if _manifest_match(item, identity)
    ]
    if len(matches) != 1:
        raise ValueError(
            f"candidate has no unique hosted manifest match: {identity[2]}"
        )
    digest_match = matches[0]
    states_value = candidate.get("contract_role_states")
    if not isinstance(states_value, dict):
        raise TypeError("candidate has no v4 contract role states")
    states = cast("dict[str, Any]", states_value)
    states["publication"] = "candidate_receipt_available_unbound"
    states["verification"] = "candidate_receipt_available_unbound"
    candidate["authority_candidate"] = {
        "producer_repository": CONTRACT_REPOSITORY,
        "contract_repository": CONTRACT_REPOSITORY,
        "contract_commit": CONTRACT_COMMIT,
        "schema_path": CONTRACT_SCHEMA_PATH,
        "schema_sha256": CONTRACT_SCHEMA_SHA256,
        "producer_workflow": PRODUCER_WORKFLOW,
        "producer_workflow_commit": WORKFLOW_COMMIT,
        "producer_workflow_run": (
            f"https://github.com/{CONTRACT_REPOSITORY}/actions/runs/{WORKFLOW_RUN}"
        ),
        "contract_role_state": "candidate_identity_available_unbound",
    }
    candidate["publication_candidate_receipt"] = {
        "dataset": DATASET,
        "revision": PINNED_REVISION,
        "path": candidate["path"],
        "bytes": candidate["bytes"],
        "sha256": candidate["sha256"],
        "workflow": ".github/workflows/australian-mbs-utilisation-harvest.yml",
        "workflow_commit": WORKFLOW_COMMIT,
        "workflow_run": f"https://github.com/edithatogo/global-medicines-atlas/actions/runs/{WORKFLOW_RUN}",
        "receipt": _receipt_ref(
            PUBLICATION_RECEIPT_URL, PUBLICATION_RECEIPT_SHA256
        ),
        "manifest": {
            "path": "manifest.json",
            "sha256": archive["manifest_sha256"],
            "file_count": archive["manifest_object_count"],
            "exact_object_match": True,
        },
        "contract_role_state": "candidate_receipt_available_unbound",
    }
    candidate["verification_candidate_receipt"] = {
        "dataset": DATASET,
        "revision": PINNED_REVISION,
        "path": candidate["path"],
        "bytes": candidate["bytes"],
        "sha256": candidate["sha256"],
        "anonymous": True,
        "token_free": True,
        "clean_room": True,
        "status": "passed",
        "verified_at": "2026-09-27T16:44:12Z",
        "receipt": _receipt_ref(
            VERIFICATION_RECEIPT_URL, VERIFICATION_RECEIPT_SHA256
        ),
        "workflow_commit": WORKFLOW_COMMIT,
        "workflow_run": f"https://github.com/edithatogo/global-medicines-atlas/actions/runs/{WORKFLOW_RUN}",
        "verifier": "hf_hub_download(token=False) against exact just-published revision; all 28 manifest objects digest-verified",
        "temporary_source_bytes_removed": True,
        "exact_object_manifest_match": {
            "path": DIGEST_REPORT,
            "sha256": _sha256((root / DIGEST_REPORT).read_bytes()),
            "manifest_match": digest_match["matched_hosted_verified_manifest"],
        },
        "contract_role_state": "candidate_receipt_available_unbound",
    }
    return candidate


def _bind_discovery_candidate(
    candidate: dict[str, Any], discovery: dict[str, Any], root: Path
) -> None:
    identity = {
        key: candidate.get(key)
        for key in ("dataset", "revision", "path", "bytes", "sha256")
    }
    matches = [
        row
        for row_value in cast("list[Any]", discovery.get("objects", []))
        if isinstance(row_value, dict)
        for row in [cast("dict[str, Any]", row_value)]
        if all(row.get(key) == value for key, value in identity.items())
    ]
    if len(matches) != 1:
        raise ValueError(
            f"discovery evidence does not uniquely bind candidate: {candidate.get('path')}"
        )
    datasets = cast("list[Any]", discovery.get("dataset_access", []))
    access = [
        cast("dict[str, Any]", value)
        for value in datasets
        if isinstance(value, dict)
        and value.get("dataset") == candidate.get("dataset")
    ]
    if (
        len(access) != 1
        or access[0].get("private") is not False
        or access[0].get("gated") is not False
    ):
        raise ValueError(
            "discovery dataset is not confirmed public and ungated"
        )
    entries_value = discovery.get("estate_registry", {}).get("entries", [])
    entries = [
        cast("dict[str, Any]", value)
        for value in cast("list[Any]", entries_value)
        if isinstance(value, dict)
        and value.get("repo_id") == candidate.get("dataset")
    ]
    if len(entries) != 1 or entries[0].get("access") != "public":
        raise ValueError(
            "public estate entry is missing for discovery candidate"
        )
    if entries[0].get("rights_status") != "source_specific_review_required":
        raise ValueError(
            "estate rights state changed; do not infer a new decision"
        )
    collection = discovery.get("collection")
    if not isinstance(collection, dict) or candidate.get(
        "dataset"
    ) not in collection.get("matching_dataset_members", []):
        raise ValueError(
            "candidate dataset is absent from the exact collection"
        )
    states_value = candidate.get("contract_role_states")
    if not isinstance(states_value, dict):
        raise TypeError("candidate has no v4 contract role states")
    cast("dict[str, Any]", states_value)["discovery"] = (
        "candidate_receipt_available_unbound"
    )
    candidate["discovery_candidate_receipt"] = {
        "collection": collection.get("url"),
        "collection_response_sha256": collection.get("response_sha256"),
        "estate_entry": {
            "url": discovery["estate_registry"].get("catalog_url"),
            "sha256": discovery["estate_registry"].get("catalog_sha256"),
            "dataset": candidate["dataset"],
            "status": entries[0].get("status"),
            "rights_status": entries[0].get("rights_status"),
        },
        "dataset_access_response_sha256": access[0].get("response_sha256"),
        "evidence_report": {
            "path": DISCOVERY_REPORT,
            "sha256": _sha256((root / DISCOVERY_REPORT).read_bytes()),
        },
        "contract_role_state": "candidate_receipt_available_unbound",
    }


def _bind_location_candidate(
    candidate: dict[str, Any], discovery: dict[str, Any], root: Path
) -> None:
    if candidate.get("anonymous_digest_readback") is not True:
        raise ValueError(
            "location candidate lacks exact anonymous digest readback"
        )
    digest_ref = candidate.get("digest_evidence")
    if not isinstance(digest_ref, dict):
        raise TypeError(
            "location candidate lacks its digest evidence reference"
        )
    _verify_local_evidence_reference(root, cast("dict[str, Any]", digest_ref))
    access_rows = cast("list[Any]", discovery.get("dataset_access", []))
    matching_access = [
        cast("dict[str, Any]", item)
        for item in access_rows
        if isinstance(item, dict)
        and item.get("dataset") == candidate.get("dataset")
    ]
    if (
        len(matching_access) != 1
        or matching_access[0].get("private") is not False
        or matching_access[0].get("gated") is not False
    ):
        raise ValueError(
            "location repository is not confirmed public and ungated"
        )
    states_value = candidate.get("contract_role_states")
    if not isinstance(states_value, dict):
        raise TypeError("candidate has no v4 contract role states")
    cast("dict[str, Any]", states_value)["location"] = (
        "candidate_receipt_available_unbound"
    )
    candidate["location_candidate_receipt"] = {
        "dataset": candidate["dataset"],
        "revision": candidate["revision"],
        "path": candidate["path"],
        "bytes": candidate["bytes"],
        "sha256": candidate["sha256"],
        "private": False,
        "gated": False,
        "dataset_access_response_sha256": matching_access[0].get(
            "response_sha256"
        ),
        "anonymous_digest_readback": True,
        "digest_evidence": digest_ref,
        "contract_role_state": "candidate_receipt_available_unbound",
    }


def _update_summary(
    report: dict[str, Any], root: Path, matched_count: int
) -> None:
    report["cohort"]["publication_candidate_receipts"] = matched_count
    report["cohort"]["verification_candidate_receipts"] = matched_count
    report["observed_hub_revision_metadata"] = {
        "url": f"https://huggingface.co/api/datasets/{DATASET}/revision/{PINNED_REVISION}",
        "dataset": DATASET,
        "revision": PINNED_REVISION,
        "private": False,
        "gated": False,
        "observed_at": OBSERVED_AT,
    }
    for role_value in cast("list[Any]", report.get("roles", [])):
        if not isinstance(role_value, dict):
            continue
        role = cast("dict[str, Any]", role_value)
        if role.get("role") == "authority":
            role["state"] = "candidate_identity_available_unbound_for_16_of_16"
            role["evidence"] = (
                "The successful MBS utilisation producer workflow belongs to "
                "edithatogo/global-medicines-atlas. All 16 candidate objects "
                "now bind the exact v4.1 schema digest and an exact-main commit "
                "containing those schema bytes. The identity remains unbound "
                "until referenced by each complete v4 contract."
            )
        if role.get("role") in {"publication", "verification"}:
            role["state"] = "candidate_receipts_available_unbound_for_14_of_16"
            role["evidence"] = (
                "14 MBS utilisation paths exactly match the 28-object published manifest and token-free anonymous restore receipt; the two August paths lack this receipt. Candidate evidence is not bound to live v4.1 contracts."
            )
        if role.get("role") == "discovery":
            role["state"] = "candidate_receipt_available_unbound_for_16_of_16"
            role["evidence"] = (
                "All 16 exact candidate paths bind to their public dataset entry, "
                "a current collection membership, and the pinned dataset-estate "
                "catalog. The estate entries remain not_assessed and "
                "source_specific_review_required; discovery evidence is not a "
                "rights or admission conclusion."
            )
        if role.get("role") == "location":
            role["state"] = "candidate_receipt_available_unbound_for_16_of_16"
            role["evidence"] = (
                "All 16 exact dataset/revision/path/byte-count/SHA-256 identities "
                "bind to the existing anonymous digest evidence and current public, "
                "ungated repository metadata. The evidence remains unbound until "
                "referenced by each complete v4 contract."
            )
    report["authority_identity"] = {
        "producer_repository": CONTRACT_REPOSITORY,
        "contract_repository": CONTRACT_REPOSITORY,
        "contract_commit": CONTRACT_COMMIT,
        "schema_path": CONTRACT_SCHEMA_PATH,
        "schema_sha256": CONTRACT_SCHEMA_SHA256,
        "producer_workflow": PRODUCER_WORKFLOW,
        "producer_workflow_commit": WORKFLOW_COMMIT,
        "producer_workflow_run": (
            f"https://github.com/{CONTRACT_REPOSITORY}/actions/runs/{WORKFLOW_RUN}"
        ),
        "candidate_objects": EXPECTED_CANDIDATES,
        "state": "candidate_identity_available_unbound_for_16_of_16",
    }
    report["decision"] = (
        "The exact v4.1 schema identity and successful producer workflow are "
        "now bound as candidate authority evidence for all 16 MBS utilisation "
        "objects; publication and token-free anonymous restore receipts remain "
        "unbound candidate evidence for 14 of 16 paths. Authority is not yet "
        "referenced by complete v4 contracts. Two August paths, source "
        "semantics, discovery, v3 replay, recovery/cache, and consumers remain "
        "incomplete. Location and discovery evidence now cover all 16 paths but "
        "remain unbound until referenced by complete per-object v4 contracts. Preserve "
        "zero v4 admissions and zero M-112 consumer canaries."
    )
    report["recorded_at"] = OBSERVED_AT
    report["supersedes"] = {
        "path": ROLE_REPORT,
        "sha256": _sha256((root / ROLE_REPORT).read_bytes()),
    }


def qualify(root: Path = ROOT) -> dict[str, Any]:
    """Return a deterministic role report enriched with bound candidate receipts."""
    report = copy.deepcopy(_read_json(root, ROLE_REPORT))
    digest_report = _read_json(root, DIGEST_REPORT)
    discovery_report = _read_json(root, DISCOVERY_REPORT)
    candidates = report.get("objects")
    verified_objects = digest_report.get("verified_objects")
    archives = digest_report.get("archives")
    if not isinstance(candidates, list):
        raise TypeError("M-112 role report has no object list")
    candidate_values = cast("list[Any]", candidates)
    if len(candidate_values) != EXPECTED_CANDIDATES:
        raise ValueError("the frozen 16-object exact-rights MBS cohort changed")
    if report.get("cohort", {}).get("v4_admissions") != 0:
        raise ValueError(
            "M-112 admission state changed; requalify before refresh"
        )
    if report.get("cohort", {}).get("consumer_canaries") != 0:
        raise ValueError("M-112 canary state changed; requalify before refresh")
    if not isinstance(verified_objects, list) or not isinstance(archives, list):
        raise TypeError("digest reconciliation is incomplete")
    if (
        discovery_report.get("scope", {}).get("candidate_objects")
        != EXPECTED_CANDIDATES
        or discovery_report.get("scope", {}).get("discovery_objects")
        != EXPECTED_CANDIDATES
        or discovery_report.get("role_state")
        != "candidate_evidence_available_unbound_for_16_of_16"
    ):
        raise ValueError(
            "M-112 discovery evidence does not cover the frozen cohort"
        )

    verified_values = cast("list[Any]", verified_objects)
    archive = _find_archive(cast("list[Any]", archives))
    _verify_archive_receipt(archive)
    if archive.get("public") is not True or archive.get("gated") is not False:
        raise ValueError("pinned MBS archive is not public and ungated")

    matched: list[dict[str, Any]] = []
    for candidate_value in candidate_values:
        if not isinstance(candidate_value, dict):
            raise TypeError("malformed M-112 candidate")
        candidate = cast("dict[str, Any]", candidate_value)
        _bind_authority_candidate(candidate, root)
        _bind_discovery_candidate(candidate, discovery_report, root)
        _bind_location_candidate(candidate, discovery_report, root)
        if candidate.get("dataset") == DATASET:
            matched.append(
                _bind_candidate(candidate, verified_values, archive, root)
            )

    if len(matched) != EXPECTED_PATHS:
        raise ValueError(
            f"expected {EXPECTED_PATHS} MBS utilisation candidates, got {len(matched)}"
        )
    report["discovery_candidate_evidence"] = {
        "path": DISCOVERY_REPORT,
        "sha256": _sha256((root / DISCOVERY_REPORT).read_bytes()),
        "objects": EXPECTED_CANDIDATES,
        "state": "candidate_receipt_available_unbound_for_16_of_16",
    }
    report["location_candidate_evidence"] = {
        "objects": EXPECTED_CANDIDATES,
        "state": "candidate_receipt_available_unbound_for_16_of_16",
    }
    _update_summary(report, root, len(matched))
    return report


def _canonical_bytes(report: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            report, ensure_ascii=False, sort_keys=True, indent=2
        ).encode()
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
            raise SystemExit(
                f"M-112 v4 role receipt report is stale: {args.output}"
            )
        print(
            "M-112 v4 receipt reconciliation passed: 14 exact publication/restore candidate bindings"
        )
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(expected)
    print(f"wrote {args.output} sha256={_sha256(expected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
