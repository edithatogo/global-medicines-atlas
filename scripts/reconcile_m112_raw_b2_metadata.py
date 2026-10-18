"""Independently reconcile public metadata for the six deferred MBS B2 paths.

This reads only allowlisted metadata paths. It never fetches a ``raw/`` object
and never creates an M-112 admission or reader authorization.
"""

from __future__ import annotations

import hashlib
import json
from http import HTTPStatus
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote, urljoin, urlsplit

import httpx

from global_medicines_atlas.acquisition import (
    AcquisitionPolicy,
    BoundIPAddressTransport,
)
from global_medicines_atlas.federation_reader import HOSTS

ROOT = Path(__file__).resolve().parents[1]
QUAL = ROOT / "quality/qualifications"
JULY = "42d73b6facac016f14a335d36d83f1a3b630add8"
JULY_DATASET = "edithatogo/australian-mbs-source-archive"
MAX_METADATA_BYTES = 128 * 1024
MAX_REDIRECTS = 3
EXPECTED_CANDIDATE_PATHS = 6
EXPECTED_UNIQUE_PAYLOADS = 5
EXPECTED_AUGUST_ALIAS_PATHS = 2
RESOLVE_PATH_SEGMENT_COUNT = 2
AUGUST_LIFECYCLE_REVISION = "1e4971c35c0ef45026168a8e2498d1bd57a3c324"


def _metadata_path(path: str) -> None:
    if not path or path.startswith("/") or ".." in Path(path).parts:
        raise ValueError("metadata path is not a safe relative path")
    if path.startswith("raw/") or not (
        path == "manifest.json"
        or (
            path.startswith(("bronze/", "quality/"))
            and path.endswith((".json", ".jsonl"))
        )
    ):
        raise ValueError("only bounded metadata paths may be read")


def read_public_metadata(
    dataset: str,
    revision: str,
    path: str,
    *,
    client: httpx.Client | None = None,
) -> tuple[int, bytes]:
    """Read one public metadata object at a pinned revision, anonymously."""
    _metadata_path(path)
    url = (
        f"https://huggingface.co/datasets/{dataset}/resolve/{revision}/"
        f"{quote(path)}"
    )
    owns_client = client is None
    transport = BoundIPAddressTransport(
        policy=AcquisitionPolicy(
            allowed_hosts=HOSTS,
            timeout_seconds=30,
            max_bytes=MAX_METADATA_BYTES,
            max_attempts=1,
            max_redirects=MAX_REDIRECTS,
        )
    )
    active = client or httpx.Client(
        transport=transport,
        trust_env=False,
        timeout=30,
        follow_redirects=False,
        headers={"Accept-Encoding": "identity"},
    )
    try:
        for redirect_count in range(MAX_REDIRECTS + 1):
            active.cookies.clear()
            with active.stream("GET", url) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if location is None or redirect_count == MAX_REDIRECTS:
                        raise ValueError("metadata redirect bound exceeded")
                    url = urljoin(url, location)
                    continue
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes(64 * 1024):
                    size += len(chunk)
                    if size > MAX_METADATA_BYTES:
                        raise ValueError("metadata response exceeds byte bound")
                    chunks.append(chunk)
                return response.status_code, b"".join(chunks)
        raise ValueError("metadata redirect bound exceeded")
    finally:
        if owns_client:
            active.close()


def _json(path: str) -> dict[str, Any]:
    value: object = json.loads((ROOT / path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return cast("dict[str, Any]", value)


def _input_binding(path: str) -> dict[str, str]:
    body = (ROOT / path).read_bytes()
    return {"path": path, "sha256": hashlib.sha256(body).hexdigest()}


def manifest_summary(
    body: bytes, expected_paths: tuple[str, ...]
) -> tuple[object, int]:
    parsed: object = json.loads(body)
    if not isinstance(parsed, dict):
        raise TypeError("root manifest is not a JSON object")
    manifest = cast("dict[str, Any]", parsed)
    file_count = manifest.get("file_count")
    files_value: object = manifest.get("files")
    listed: set[str] = set()
    if isinstance(files_value, list):
        entries = cast("list[object]", files_value)
        for entry in entries:
            if isinstance(entry, dict):
                typed_entry = cast("dict[str, object]", entry)
                candidate_path = typed_entry.get("path")
                if isinstance(candidate_path, str):
                    listed.add(candidate_path)
    return file_count, sum(path in listed for path in expected_paths)


def require_august_lifecycle_locator(readback: dict[str, Any]) -> None:
    """Bind the August lifecycle revision to its recorded dataset identity."""
    if (
        readback.get("dataset") != JULY_DATASET
        or readback.get("dataset_revision") != AUGUST_LIFECYCLE_REVISION
        or readback.get("dataset_visibility", {}).get("http_status")
        != HTTPStatus.OK
    ):
        raise ValueError(
            "August lifecycle dataset locator is not independently bound"
        )


def _fetch_record(  # ruff: ignore[too-many-locals,too-many-branches] -- each metadata claim is summarized in one exact readback row
    client: httpx.Client,
    dataset: str,
    revision: str,
    path: str,
    expected_bytes: int | None = None,
    expected_sha256: str | None = None,
    local_path: str | None = None,
    expected_manifest_paths: tuple[str, ...] = (),
) -> dict[str, Any]:
    status, body = read_public_metadata(dataset, revision, path, client=client)
    sha256 = hashlib.sha256(body).hexdigest()
    matches = (
        status == HTTPStatus.OK
        and (expected_bytes is None or len(body) == expected_bytes)
        and (expected_sha256 is None or sha256 == expected_sha256)
    )
    result: dict[str, Any] = {
        "dataset": dataset,
        "revision": revision,
        "path": path,
        "http_status": status,
        "observed_bytes": len(body),
        "observed_sha256": sha256,
        "expected_bytes": expected_bytes,
        "expected_sha256": expected_sha256,
        "pinned_digest_match": matches,
    }
    if status == HTTPStatus.OK and (
        path != "manifest.json" or path.startswith("bronze/")
    ):
        parsed: object = json.loads(body)
        if not isinstance(parsed, dict):
            raise TypeError("metadata receipt is not a JSON object")
        document = cast("dict[str, Any]", parsed)
        nested_payload = document.get("payload", {})
        if not isinstance(nested_payload, dict):
            nested_payload = {}
        rows_value: object = document.get("rows", [])
        first_value: object = {}
        if isinstance(rows_value, list) and rows_value:
            first_value = cast("object", rows_value[0])
        if not isinstance(first_value, dict):
            first_value = {}
        first_row = cast("dict[str, Any]", first_value)
        reference_value: object = first_row.get(
            "external_reference", document.get("external_reference")
        )
        reference = (
            reference_value if isinstance(reference_value, str) else None
        )
        locator = urlsplit(reference) if reference is not None else None
        path_revision = None
        path_name = None
        if locator is not None:
            parts = locator.path.split("/resolve/", 1)
            if len(parts) == RESOLVE_PATH_SEGMENT_COUNT:
                revision_path = parts[1].split("/", 1)
                if len(revision_path) == RESOLVE_PATH_SEGMENT_COUNT:
                    path_revision, path_name = revision_path
        claims: dict[str, Any] = {
            key: document.get(key)
            for key in (
                "schema_id",
                "schema_version",
                "source_id",
                "archive_path",
                "category",
                "acquisition_id",
                "content_id",
                "payload_sha256",
                "sha256",
                "byte_count",
                "state",
                "decision_id",
                "supersedes_decision_id",
                "receipt_id",
                "receipt_type",
            )
            if key in document
        }
        claims.update({
            key: nested_payload[key]
            for key in ("sha256", "byte_count")
            if key in nested_payload
        })
        if first_row:
            claims.update({
                key: first_row[key]
                for key in (
                    "source_id",
                    "acquisition_id",
                    "content_id",
                    "external_reference",
                    "state",
                )
                if key in first_row
            })
        if path_revision is not None:
            claims["b2_locator_revision"] = path_revision
            claims["b2_locator_path"] = path_name
        result["claims"] = claims
    if local_path is not None:
        local_body = (ROOT / local_path).read_bytes()
        result["local_copy"] = {
            "path": local_path,
            "sha256": hashlib.sha256(local_body).hexdigest(),
            "bytes": len(local_body),
            "exact_bytes_match": local_body == body,
        }
    if path == "manifest.json" and status == HTTPStatus.OK:
        file_count, expected_paths_count = manifest_summary(
            body, expected_manifest_paths
        )
        result["manifest_file_count"] = file_count
        if expected_manifest_paths:
            result["expected_manifest_paths"] = len(expected_manifest_paths)
            result["expected_paths_listed_count"] = expected_paths_count
    return result


def _validate_july_path_joins(
    july_readback: dict[str, Any], rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Join each public July source sidecar to its exact B1 and B2 metadata."""
    metadata_by_path = {row["path"]: row for row in rows}
    bindings: list[dict[str, Any]] = []
    for object_row in july_readback["objects"]:
        candidate = next(
            item
            for item in july_readback["raw_object_digests"]
            if item["path"] == object_row["archive_path"]
        )
        sidecar = metadata_by_path[object_row["sidecar_path"]]["claims"]
        acquisition = metadata_by_path[object_row["b1_acquisition"]["path"]][
            "claims"
        ]
        source_receipt = metadata_by_path[
            object_row["b1_source_receipt"]["path"]
        ]["claims"]
        b2 = metadata_by_path[object_row["b2_raw_reference"]["path"]]["claims"]
        admission = metadata_by_path[object_row["landed_admission"]["path"]][
            "claims"
        ]
        acquisition_id = Path(object_row["b1_acquisition"]["path"]).stem
        role_matches = {
            "path_receipt": (
                sidecar.get("archive_path") == candidate["path"]
                and sidecar.get("byte_count") == candidate["bytes"]
                and sidecar.get("sha256") == candidate["sha256"]
            ),
            "acquisition": (
                acquisition.get("source_id") == "au-mbs"
                and acquisition.get("acquisition_id") == acquisition_id
                and acquisition.get("content_id") == candidate["sha256"]
                and acquisition.get("payload_sha256") == candidate["sha256"]
            ),
            "source_receipt": (
                source_receipt.get("receipt_type") == "source"
                and source_receipt.get("sha256") == candidate["sha256"]
                and source_receipt.get("byte_count") == candidate["bytes"]
            ),
            "b2_reference": (
                b2.get("source_id") == "au-mbs"
                and b2.get("acquisition_id") == acquisition_id
                and b2.get("content_id") == candidate["sha256"]
                and b2.get("b2_locator_path") == candidate["path"]
            ),
            "landed_admission": (
                admission.get("acquisition_id") == acquisition_id
                and admission.get("content_id") == candidate["sha256"]
                and admission.get("decision_id")
                == object_row["landed_admission"]["decision_id"]
                and admission.get("state") == "landed"
            ),
        }
        if not all(role_matches.values()):
            raise ValueError("July path does not join across B1/B2 metadata")
        bindings.append({
            "path": candidate["path"],
            "bytes": candidate["bytes"],
            "sha256": candidate["sha256"],
            "acquisition_id": acquisition_id,
            "b2_locator_revision": b2["b2_locator_revision"],
            "role_matches": role_matches,
        })
    return bindings


def _validate_august_lifecycle(
    august: dict[str, Any], rows: list[dict[str, Any]]
) -> dict[str, Any]:
    """Join the five August lifecycle records to one B2 payload identity."""
    by_path = {row["path"]: row for row in rows}
    roles = {
        role: by_path[entry["path"].removeprefix("quality/")]["claims"]
        for role, entry in august["files"].items()
    }
    acquisition_id = august["acquisition_id"]
    content_id = august["content_id"]
    acquisition = roles["acquisition_event"]
    source_receipt = roles["source_receipt"]
    b2 = roles["b2_manifest"]
    landed = roles["landed_admission"]
    accepted = roles["accepted_admission"]
    decisions = august["admission_lifecycle"]["observed_decisions"]
    matches = {
        "acquisition": (
            acquisition.get("source_id") == "au-mbs"
            and acquisition.get("acquisition_id") == acquisition_id
            and acquisition.get("content_id") == content_id
            and acquisition.get("payload_sha256") == content_id
        ),
        "source_receipt": (
            source_receipt.get("receipt_type") == "source"
            and source_receipt.get("receipt_id") == august["receipt_id"]
            and source_receipt.get("sha256") == content_id
            and source_receipt.get("byte_count") == august["b2"]["byte_count"]
        ),
        "b2_reference": (
            b2.get("source_id") == "au-mbs"
            and b2.get("acquisition_id") == acquisition_id
            and b2.get("content_id") == content_id
            and b2.get("b2_locator_revision")
            == "abdf414cdea0127d3edda6f8af402d1a01139623"
            and b2.get("b2_locator_path")
            == "raw/mbs/releases/2026-08-01/"
            "c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565.xml"
        ),
        "landed_admission": (
            landed.get("acquisition_id") == acquisition_id
            and landed.get("content_id") == content_id
            and landed.get("state") == "landed"
            and landed.get("decision_id") == decisions[0]["decision_id"]
        ),
        "accepted_admission": (
            accepted.get("acquisition_id") == acquisition_id
            and accepted.get("content_id") == content_id
            and accepted.get("state") == "accepted"
            and accepted.get("decision_id") == decisions[1]["decision_id"]
            and accepted.get("supersedes_decision_id")
            == decisions[0]["decision_id"]
        ),
    }
    if not all(matches.values()) or not all(
        row.get("local_copy", {}).get("exact_bytes_match") for row in rows
    ):
        raise ValueError("August lifecycle roles do not bind one payload")
    return {
        "acquisition_id": acquisition_id,
        "content_id": content_id,
        "old_b2_locator_revision": b2["b2_locator_revision"],
        "current_candidate_path_revision": "40891976f77ee5e7688edceed25c9ac98a77547e",
        "path_count_for_digest": EXPECTED_AUGUST_ALIAS_PATHS,
        "role_matches": matches,
        "all_five_roles_match_local_and_pinned_metadata": True,
    }


def reconcile() -> dict[str, Any]:  # ruff: ignore[too-many-locals] -- six identities and independent metadata roles are explicit
    july_readback = _json(
        "quality/qualifications/australian-mbs-july-metadata-hosted-readback-20261018.json"
    )
    sidecars = _json(
        "quality/qualifications/australian-mbs-july-source-sidecar-readback-20261018.json"
    )
    august = _json(
        "quality/qualifications/australian-mbs-bronze-source-receipt-20261004.json"
    )
    august_readback = _json(
        "quality/qualifications/australian-m112-root-manifest-readback-20261005.json"
    )
    require_august_lifecycle_locator(august_readback)
    august_path_readback = _json(
        "quality/qualifications/australian-m112-root-manifest-path-readback-20261017.json"
    )
    august_source_readback = _json(
        "quality/qualifications/australian-m112-mbs-hosted-receipt-20261003.json"
    )
    if (
        august_source_readback["dataset"] != JULY_DATASET
        or august_source_readback["dataset_revision"]
        != "40891976f77ee5e7688edceed25c9ac98a77547e"
    ):
        raise ValueError("August candidate path revision changed")
    july_paths = [
        {
            "dataset": JULY_DATASET,
            "revision": JULY,
            "path": item["path"],
            "bytes": item["bytes"],
            "sha256": item["sha256"],
        }
        for item in july_readback["raw_object_digests"]
    ]
    august_paths = [
        {
            "dataset": august_path_readback["dataset"],
            "revision": august_source_readback["dataset_revision"],
            "path": item["path"],
            "bytes": item["manifest_row"]["bytes"],
            "sha256": item["manifest_row"]["sha256"],
        }
        for item in august_path_readback["objects"]
    ]
    candidates = july_paths + august_paths
    if (
        len(candidates) != EXPECTED_CANDIDATE_PATHS
        or len({item["sha256"] for item in candidates})
        != EXPECTED_UNIQUE_PAYLOADS
    ):
        raise ValueError("the six MBS path and five-payload scope changed")
    rows: list[dict[str, Any]] = []
    policy = AcquisitionPolicy(
        allowed_hosts=HOSTS,
        timeout_seconds=30,
        max_bytes=MAX_METADATA_BYTES,
        max_attempts=1,
        max_redirects=3,
    )
    with httpx.Client(
        transport=BoundIPAddressTransport(policy=policy),
        trust_env=False,
        timeout=30,
        follow_redirects=False,
        headers={"Accept-Encoding": "identity"},
    ) as client:
        rows.append(
            _fetch_record(
                client,
                JULY_DATASET,
                JULY,
                "manifest.json",
                expected_sha256=july_readback["manifest_readback"]["sha256"],
            )
        )
        rows.extend([
            _fetch_record(
                client,
                JULY_DATASET,
                JULY,
                item["path"],
                item["bytes"],
                item["sha256"],
            )
            for item in july_readback["metadata_additions"]
        ])
        rows.extend([
            _fetch_record(
                client,
                JULY_DATASET,
                JULY,
                item["sidecar_path"],
                item["sidecar_bytes"],
                item["sidecar_sha256"],
            )
            for item in sidecars["objects"]
        ])
        current_manifest = _fetch_record(
            client,
            JULY_DATASET,
            "40891976f77ee5e7688edceed25c9ac98a77547e",
            "manifest.json",
        )
        old_locator_manifest = _fetch_record(
            client,
            JULY_DATASET,
            "abdf414cdea0127d3edda6f8af402d1a01139623",
            "manifest.json",
        )
        rows.extend((current_manifest, old_locator_manifest))
        august_revision = AUGUST_LIFECYCLE_REVISION
        lifecycle_manifest = _fetch_record(
            client,
            JULY_DATASET,
            august_revision,
            "manifest.json",
            august_readback["root_manifest"]["byte_count"],
            august_readback["root_manifest"]["sha256"],
            expected_manifest_paths=tuple(
                role["path"].removeprefix("quality/")
                for role in august["files"].values()
            ),
        )
        if (
            lifecycle_manifest.get("manifest_file_count")
            != august_readback["root_manifest"]["file_count"]
        ):
            raise ValueError("August lifecycle root manifest count changed")
        rows.append(lifecycle_manifest)
        # All requests are anonymous, pinned, and restricted to metadata paths.
        for role in august["files"].values():
            path = role["path"].removeprefix("quality/")
            rows.append(
                _fetch_record(
                    client,
                    JULY_DATASET,
                    august_revision,
                    path,
                    expected_sha256=role["sha256"],
                    local_path=role["path"],
                )
            )

    july_object = july_readback["objects"][0]
    old_claim = july_object["b1_acquisition"]
    matching_addition = next(
        item
        for item in july_readback["metadata_additions"]
        if item["path"] == old_claim["path"]
    )
    august_metadata_rows = rows[-len(august["files"]) :]
    august_b2 = next(
        row for row in august_metadata_rows if "/raw-evidence/" in row["path"]
    )
    expected_old_b2_path = (
        "raw/mbs/releases/2026-08-01/"
        "c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565.xml"
    )
    if (
        not all(
            row.get("local_copy", {}).get("exact_bytes_match")
            for row in august_metadata_rows
        )
        or august_b2.get("claims", {}).get("b2_locator_revision")
        != "abdf414cdea0127d3edda6f8af402d1a01139623"
        or august_b2.get("claims", {}).get("b2_locator_path")
        != expected_old_b2_path
    ):
        raise ValueError(
            "August lifecycle metadata identity or locator changed"
        )
    july_bindings = _validate_july_path_joins(july_readback, rows)
    august_binding = _validate_august_lifecycle(august, august_metadata_rows)
    august_binding["path_count_for_digest"] = sum(
        item["sha256"] == august_binding["content_id"] for item in candidates
    )
    if august_binding["path_count_for_digest"] != EXPECTED_AUGUST_ALIAS_PATHS:
        raise ValueError("August canonical path and alias identities changed")
    return {
        "schema_id": "global-medicines-atlas.m112-raw-b2-metadata-reconciliation",
        "schema_version": 1,
        "observed_at": "2026-10-18",
        "scope": {
            "candidate_paths": EXPECTED_CANDIDATE_PATHS,
            "unique_payload_digests": EXPECTED_UNIQUE_PAYLOADS,
            "raw_payload_bytes_fetched": False,
            "m112_denominator": 1759,
            "v4_admissions": 0,
            "consumer_canaries": 0,
        },
        "candidate_paths": candidates,
        "metadata_bindings": {
            "july_path_level_b1_b2_joins": july_bindings,
            "august_lifecycle_payload_identity": august_binding,
            "august_lifecycle_manifest_membership": {
                "revision": AUGUST_LIFECYCLE_REVISION,
                "root_manifest_file_count": lifecycle_manifest[
                    "manifest_file_count"
                ],
                "lifecycle_paths_checked": lifecycle_manifest[
                    "expected_manifest_paths"
                ],
                "lifecycle_paths_listed": lifecycle_manifest[
                    "expected_paths_listed_count"
                ],
                "direct_pinned_reads_passed": all(
                    row["pinned_digest_match"] for row in august_metadata_rows
                ),
                "interpretation": "lifecycle metadata paths are directly resolvable and digest-bound but absent from this archive root manifest; no v4 discovery role is inferred",
            },
        },
        "input_bindings": [
            _input_binding(
                "quality/qualifications/australian-mbs-july-metadata-hosted-readback-20261018.json"
            ),
            _input_binding(
                "quality/qualifications/australian-mbs-july-source-sidecar-readback-20261018.json"
            ),
            _input_binding(
                "quality/qualifications/australian-mbs-bronze-source-receipt-20261004.json"
            ),
            _input_binding(
                "quality/qualifications/australian-m112-root-manifest-readback-20261005.json"
            ),
            _input_binding(
                "quality/qualifications/australian-m112-root-manifest-path-readback-20261017.json"
            ),
            _input_binding(
                "quality/qualifications/australian-m112-mbs-hosted-receipt-20261003.json"
            ),
        ],
        "readbacks": rows,
        "findings": {
            "july_acquisition_size_claim": {
                "prior_object_claim_bytes": old_claim["bytes"],
                "independent_metadata_addition_bytes": matching_addition[
                    "bytes"
                ],
                "resolution": "prior object summary undercounts by one byte; independently pinned acquisition metadata and digest agree",
            },
            "july_root_manifest": {
                "readback_sha256": rows[0]["observed_sha256"],
                "recorded_sha256": july_readback["manifest_readback"]["sha256"],
                "file_count": rows[0].get("manifest_file_count"),
                "recorded_file_count": july_readback["manifest_readback"][
                    "file_count"
                ],
                "digest_matches": rows[0]["pinned_digest_match"],
                "count_matches": rows[0].get("manifest_file_count")
                == july_readback["manifest_readback"]["file_count"],
            },
            "august_anonymous_lifecycle_access": {
                "dataset": august_readback["dataset"],
                "revision": august_revision,
                "status_counts": {
                    str(status): sum(
                        row["http_status"] == status
                        for row in august_metadata_rows
                    )
                    for status in sorted({
                        row["http_status"] for row in august_metadata_rows
                    })
                },
                "all_five_pinned_digest_matches": all(
                    row["pinned_digest_match"]
                    and row["local_copy"]["exact_bytes_match"]
                    for row in august_metadata_rows
                ),
                "prior_wrong_dataset_locator": {
                    "dataset": "edithatogo/global-medicines-atlas",
                    "status": HTTPStatus.UNAUTHORIZED,
                    "interpretation": "superseded locator error; not evidence of restricted lifecycle metadata",
                },
            },
            "old_and_current_august_source_revisions": {
                "old_b2_locator_revision": "abdf414cdea0127d3edda6f8af402d1a01139623",
                "current_path_readback_revision": "40891976f77ee5e7688edceed25c9ac98a77547e",
                "kept_distinct": True,
            },
            "status": "metadata_reconciliation_only; not a raw B2 contract, rights conclusion, admission, or canary",
        },
    }


def main() -> None:
    result = reconcile()
    output = (
        QUAL / "australian-m112-raw-b2-metadata-reconciliation-20261018.json"
    )
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(output.relative_to(ROOT))


if __name__ == "__main__":
    main()
