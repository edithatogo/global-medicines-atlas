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
OBSERVED_AT = "2026-10-19T14:17:25Z"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_json(root: Path, relative: str) -> dict[str, Any]:
    value: Any = json.loads((root / relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {relative}")
    return cast("dict[str, Any]", value)


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
        if role.get("role") in {"publication", "verification"}:
            role["state"] = "candidate_receipts_available_unbound_for_14_of_16"
            role["evidence"] = (
                "14 MBS utilisation paths exactly match the 28-object published manifest and token-free anonymous restore receipt; the two August paths lack this receipt. Candidate evidence is not bound to live v4.1 contracts."
            )
    report["decision"] = (
        "Existing exact publication and token-free anonymous clean-room restore receipts now bind as unbound candidate evidence for 14 MBS utilisation paths. Two August paths and the authority, discovery, v3 replay, recovery/cache, source semantics, and consumer roles remain incomplete. Preserve zero v4 admissions and zero M-112 consumer canaries."
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
        if candidate.get("dataset") == DATASET:
            matched.append(
                _bind_candidate(candidate, verified_values, archive, root)
            )

    if len(matched) != EXPECTED_PATHS:
        raise ValueError(
            f"expected {EXPECTED_PATHS} MBS utilisation candidates, got {len(matched)}"
        )
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
