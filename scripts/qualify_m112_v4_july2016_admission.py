"""Build and independently admit one exact M-112 raw B2 v4.1 contract.

The target is the July 2016 MBS Group workbook. Its source-native workbook
layout remains explicitly unqualified; this contract admits only the exact
immutable raw B2 bytes and records no interpretation or processing promotion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

import httpx
from jsonschema import Draft202012Validator, FormatChecker

from global_medicines_atlas.acquisition import (
    AcquisitionPolicy,
    BoundIPAddressTransport,
)
from global_medicines_atlas.federation import validate_federation_semantics
from global_medicines_atlas.federation_admission import (
    TrustedAdmissionProfile,
    admit_closed_contract,
)
from global_medicines_atlas.federation_consumer import bind_consumer_contract
from global_medicines_atlas.federation_identity import AdmissionRecord
from global_medicines_atlas.federation_reader import HOSTS as READER_HOSTS
from global_medicines_atlas.federation_reader import FederatedReader
from global_medicines_atlas.federation_receipt_closure import (
    MAX_RECEIPT_BYTES,
    MAX_TOTAL_BYTES,
    ReceiptPayload,
    ReceiptRole,
    contract_receipt_roles,
    verify_receipt_closure,
)

ROOT = Path(__file__).resolve().parents[1]
ROLE_REPORT = Path(
    "quality/qualifications/"
    "australian-m112-v4-contract-role-evidence-qualification-20261020.json"
)
OUTPUT = Path(
    "quality/qualifications/australian-m112-v4-july2016-raw-b2-contract.json"
)
CSV_OUTPUT = Path(
    "quality/qualifications/"
    "australian-m112-v4-group2016-csv-raw-b2-contract.json"
)
SCHEMA_PATH = Path("contracts/medallion/v4.1/federation.schema.json")
EVIDENCE_COMMIT = "90dea68ec6ff3d4d07b43860631742728cf40ff5"
TARGET_DATASET = "edithatogo/australian-mbs-utilisation-archive"
TARGET_REVISION = "dee9a5b0580dfe394474dc26b372559462e157e7"
TARGET_PATH = "raw/mbs/utilisation/group/mbs-group-2016hr-july.xlsx"
TARGET_SHA256 = (
    "9f2f28b69f58a0aa05a0b56b09515651b1e0b50a634234ce7f6f6c8426373285"
)
TARGET_BYTES = 6_857_437
APPROVED_DENOMINATOR = 1_759
SOURCE_ID = "au-data-gov-mbs-group"
ACQUISITION_ID = (
    "7b46430b1a5ec2c1b6b1617244aa6e983902004ab082aa314bfb7e3a9503663b"
)
RIGHTS_COMMENT = 5857784415
RESTORE_COMMENT = 5857784489
PUBLICATION_SHA256 = (
    "6bce093347564588b320f81344c4903c038f4659d5aeb96bca4b2802073c9c1d"
)
RESTORE_SHA256 = (
    "5069e57b54a2c3d2aff9901389738998a8944de006505a8f3ac0e02bb4e87a15"
)
V3_RUN_ID = 39289077989
V3_RUN_STARTED = "2026-10-19T16:51:27Z"
V3_RUN_TIMEOUT_MINUTES = 15
EXPECTED_RIGHTS_STATE = (
    "approved_exact_scope_CC_BY_3_0_AU_publicly_readback_verified"
)
ISSUE_COMMENT_PATTERN = re.compile(
    r"^https://github\.com/edithatogo/global-medicines-atlas/issues/340"
    r"#issuecomment-(\d+)$"
)
TARGET_IDENTITIES: dict[str, dict[str, Any]] = {
    TARGET_PATH: {
        "dataset": TARGET_DATASET,
        "revision": TARGET_REVISION,
        "sha256": TARGET_SHA256,
        "bytes": TARGET_BYTES,
        "source_id": SOURCE_ID,
        "acquisition_id": ACQUISITION_ID,
    },
    "raw/mbs/utilisation/group/mbs-group-2016-july.csv": {
        "dataset": TARGET_DATASET,
        "revision": TARGET_REVISION,
        "sha256": "62ad118d94cd565a051164aa645eff1fef84a5beb74d501e3dc64344fcf16d3b",
        "bytes": 12_291_303,
        "source_id": SOURCE_ID,
        "acquisition_id": "5ba53ad638c557864f7c6b4f6a50cff44e7df26d7e7eed63cdeff38855ac9967",
    },
}


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_json(root: Path, path: Path) -> dict[str, Any]:
    value: Any = json.loads((root / path).read_bytes())
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return cast("dict[str, Any]", value)


def _raw_url(path: Path, *, commit: str = EVIDENCE_COMMIT) -> str:
    return (
        "https://raw.githubusercontent.com/edithatogo/global-medicines-atlas/"
        f"{commit}/{path.as_posix()}"
    )


def _file_receipt(root: Path, path_value: str) -> dict[str, str]:
    path = Path(path_value)
    return {
        "url": _raw_url(path),
        "sha256": _sha256((root / path).read_bytes()),
    }


def _comment_receipt(comment_id: int, digest: str) -> dict[str, str]:
    return {
        "url": (
            "https://github.com/edithatogo/global-medicines-atlas/issues/340"
            f"#issuecomment-{comment_id}"
        ),
        "sha256": digest,
    }


def _target_identity(target_path: str) -> dict[str, Any]:
    identity = TARGET_IDENTITIES.get(target_path)
    if identity is None:
        raise ValueError(
            "M-112 target is not in the exact qualified object set"
        )
    return identity


def _find_target(
    report: dict[str, Any], *, target_path: str = TARGET_PATH
) -> dict[str, Any]:
    objects = report.get("objects")
    if not isinstance(objects, list):
        raise TypeError("M-112 role report has no object list")
    found: list[dict[str, Any]] = []
    for item in cast("list[Any]", objects):
        if not isinstance(item, dict):
            continue
        candidate = cast("dict[str, Any]", item)
        if (
            candidate.get("dataset") == TARGET_DATASET
            and candidate.get("revision") == TARGET_REVISION
            and candidate.get("path") == target_path
        ):
            found.append(candidate)
    if len(found) != 1:
        raise ValueError("exact July 2016 M-112 target is not unique")
    return found[0]


def _validate_inputs(  # ruff: ignore[too-many-locals]
    root: Path,
    report: dict[str, Any],
    *,
    target_path: str = TARGET_PATH,
) -> dict[str, Any]:
    if (
        report.get("cohort", {}).get("approved_denominator")
        != APPROVED_DENOMINATOR
    ):
        raise ValueError("approved M-112 denominator changed")
    expected = _target_identity(target_path)
    candidate = _find_target(report, target_path=target_path)
    identity = (
        candidate.get("dataset"),
        candidate.get("revision"),
        candidate.get("path"),
        candidate.get("sha256"),
        candidate.get("bytes"),
        candidate.get("source_id"),
        candidate.get("acquisition_id"),
    )
    if identity != (
        expected["dataset"],
        expected["revision"],
        target_path,
        expected["sha256"],
        expected["bytes"],
        expected["source_id"],
        expected["acquisition_id"],
    ):
        raise ValueError("target identity differs from the approved pin")
    if (
        candidate.get("rights_state") != EXPECTED_RIGHTS_STATE
        or candidate.get("anonymous_digest_readback") is not True
        or candidate.get("contract_role_states", {}).get("lineage.inputs")
        != "qualified_b1_b2_only"
    ):
        raise ValueError(
            "target lacks the approved rights, digest, or B1/B2 gates"
        )

    evidence = candidate.get("lineage_evidence")
    if not isinstance(evidence, dict):
        raise TypeError("target B1/B2 evidence references are missing")
    evidence = cast("dict[str, Any]", evidence)
    source_receipt_path = evidence.get("source_receipt_path")
    event_path = evidence.get("acquisition_event_path")
    b2_path = evidence.get("b2_manifest_path")
    if not all(
        isinstance(path, str)
        for path in (
            source_receipt_path,
            event_path,
            b2_path,
        )
    ):
        raise ValueError("target B1/B2 file references are incomplete")
    source_receipt = _read_json(root, Path(cast("str", source_receipt_path)))
    event = _read_json(root, Path(cast("str", event_path)))
    b2 = _read_json(root, Path(cast("str", b2_path)))
    retrieval_value = source_receipt.get("retrieval")
    payload_value = source_receipt.get("payload")
    retrieval = (
        cast("dict[str, Any]", retrieval_value)
        if isinstance(retrieval_value, dict)
        else {}
    )
    payload = (
        cast("dict[str, Any]", payload_value)
        if isinstance(payload_value, dict)
        else {}
    )
    receipt_matches = (
        retrieval.get("status") == "succeeded"
        and payload.get("sha256") == expected["sha256"]
        and payload.get("byte_count") == expected["bytes"]
    )
    event_retrieval = event.get("retrieval")
    event_matches = (
        event.get("acquisition_id") == expected["acquisition_id"]
        and event.get("payload_sha256") == expected["sha256"]
        and isinstance(event_retrieval, dict)
        and cast("dict[str, Any]", event_retrieval).get("status") == "succeeded"
    )
    if not receipt_matches or not event_matches:
        raise ValueError("source receipt or B1 event differs from target pin")
    rows = b2.get("rows")
    if not isinstance(rows, list) or len(cast("list[Any]", rows)) != 1:
        raise ValueError("B2 manifest must contain exactly the target object")
    row_value = cast("list[Any]", rows)[0]
    if not isinstance(row_value, dict):
        raise TypeError("B2 manifest row is not an object")
    row = cast("dict[str, Any]", row_value)
    if (
        row.get("source_id") != expected["source_id"]
        or row.get("acquisition_id") != expected["acquisition_id"]
        or row.get("content_id") != expected["sha256"]
        or row.get("stratum") != "B2"
        or row.get("state") != "external_reference_only"
    ):
        raise ValueError("B2 manifest differs from target pin")
    candidate["_verified_source_receipt_path"] = cast(
        "str", source_receipt_path
    )
    candidate["_verified_event_path"] = cast("str", event_path)
    candidate["_verified_b2_path"] = cast("str", b2_path)
    retrieved_at = retrieval.get("retrieved_at")
    if not isinstance(retrieved_at, str):
        raise TypeError("source receipt retrieval time is missing")
    candidate["_verified_retrieved_at"] = retrieved_at
    return candidate


def build_contract(
    root: Path = ROOT,
    *,
    target_path: str = TARGET_PATH,
    evidence_commit: str = EVIDENCE_COMMIT,
) -> dict[str, Any]:  # ruff: ignore[too-many-locals, too-many-statements]
    """Construct one exact July 2016 raw B2 contract from qualified evidence."""
    report = _read_json(root, ROLE_REPORT)
    candidate = _validate_inputs(root, report, target_path=target_path)
    identity = _target_identity(target_path)
    authority = candidate.get("authority_candidate")
    source_candidate = candidate.get("source_candidate_receipt")
    publication = candidate.get("publication_candidate_receipt")
    verification = candidate.get("verification_candidate_receipt")
    recovery = candidate.get("recovery_candidate_receipt")
    discovery = candidate.get("discovery_candidate_receipt")
    v1 = candidate.get("v1_conformance_candidate_receipt")
    v3 = candidate.get("v3_replay_candidate_receipt")
    cache = candidate.get("cache_candidate_receipt")
    rights = candidate.get("rights_decision")
    if not all(
        isinstance(value, dict)
        for value in (
            authority,
            source_candidate,
            publication,
            verification,
            recovery,
            discovery,
            v1,
            v3,
            cache,
            rights,
        )
    ):
        raise ValueError("target candidate role evidence is incomplete")
    authority = cast("dict[str, Any]", authority)
    source_candidate = cast("dict[str, Any]", source_candidate)
    publication = cast("dict[str, Any]", publication)
    verification = cast("dict[str, Any]", verification)
    recovery = cast("dict[str, Any]", recovery)
    discovery = cast("dict[str, Any]", discovery)
    v1 = cast("dict[str, Any]", v1)
    v3 = cast("dict[str, Any]", v3)
    cache = cast("dict[str, Any]", cache)
    rights = cast("dict[str, Any]", rights)

    if (
        publication.get("contract_role_state")
        != "candidate_receipt_available_unbound"
        or verification.get("contract_role_state")
        != "candidate_receipt_available_unbound"
        or source_candidate.get("native_schema_layout_qualified") is not False
        or v3.get("temporary_source_bytes_removed") is not True
        or cache.get("contract_role_state")
        != "candidate_receipt_available_unbound"
        or cache.get("state") != "removed"
    ):
        raise ValueError("required candidate roles or boundaries changed")
    if authority.get("schema_sha256") != _sha256(
        (root / SCHEMA_PATH).read_bytes()
    ):
        raise ValueError("authority schema digest differs from v4.1 schema")

    source_receipt_path = cast(
        "str", candidate["_verified_source_receipt_path"]
    )
    event_path = cast("str", candidate["_verified_event_path"])
    b2_path = cast("str", candidate["_verified_b2_path"])
    source_receipt_url = _file_receipt(root, source_receipt_path)
    event_url = _file_receipt(root, event_path)
    b2_url = _file_receipt(root, b2_path)
    rights_path = cast("str", rights.get("path"))
    rights_sha256 = cast("str", rights.get("sha256"))
    if _sha256((root / rights_path).read_bytes()) != rights_sha256:
        raise ValueError("exact-scope rights decision digest changed")
    rights_receipt = {
        "url": _raw_url(Path(rights_path)),
        "sha256": rights_sha256,
    }

    publication_receipt = _comment_receipt(RIGHTS_COMMENT, PUBLICATION_SHA256)
    restore_receipt = _comment_receipt(RESTORE_COMMENT, RESTORE_SHA256)
    v1_receipt = {
        "url": cast("str", v1.get("url")),
        "sha256": cast("str", v1.get("sha256")),
    }
    v3_path = Path(cast("str", v3["receipt"]["path"]))
    v3_sha256 = cast("str", v3["receipt"]["sha256"])
    if _sha256((root / v3_path).read_bytes()) != v3_sha256:
        raise ValueError("M-112 replay receipt digest changed")
    v3_receipt = {
        "url": _raw_url(v3_path, commit=evidence_commit),
        "sha256": v3_sha256,
    }

    estate = cast("dict[str, Any]", discovery.get("estate_entry"))
    estate_url = cast("str", estate.get("url"))
    estate_revision = estate_url.rsplit("/", 2)[-2]
    estate_receipt = {
        "url": (
            "https://huggingface.co/datasets/edithatogo/"
            "dataset-estate-registry/resolve/"
            f"{estate_revision}/catalog.json"
        ),
        "sha256": cast("str", estate.get("sha256")),
    }
    manifest = cast("dict[str, Any]", recovery["checksum_inventory"])
    cache_created_at = cast("str", cache.get("created_at"))
    cache_expires_at = cast("str", cache.get("expires_at"))
    run_started = datetime.fromisoformat(
        cache_created_at.replace("Z", "+00:00")
    )
    cache_expires = datetime.fromisoformat(
        cache_expires_at.replace("Z", "+00:00")
    )
    if cache_expires != run_started + timedelta(minutes=V3_RUN_TIMEOUT_MINUTES):
        raise ValueError("temporary cache expiry differs from hosted timeout")
    cache_cleanup_receipt = v3_receipt

    temporal = cast(
        "dict[str, Any]", source_candidate.get("temporal_semantics")
    )
    source_schema_era = cast("str", source_candidate.get("schema_era"))
    document: dict[str, Any] = {
        "version": "4.1.0",
        "evidence_kind": "live",
        "authority": {
            "producer_repository": cast(
                "str", authority.get("producer_repository")
            ),
            "contract_repository": cast(
                "str", authority.get("contract_repository")
            ),
            "contract_commit": cast("str", authority.get("contract_commit")),
            "schema_sha256": cast("str", authority.get("schema_sha256")),
        },
        "source": {
            "source_id": identity["source_id"],
            "acquisition_id": identity["acquisition_id"],
            "layer": "bronze",
            "bronze_stratum": "B2",
            "representation": "raw",
            "schema_era": source_schema_era,
            "comparison_cohort": cast("str", temporal.get("cohort")),
            "effective_date": cast("str", temporal.get("effective_date")),
            "retrieved_at": cast("str", candidate["_verified_retrieved_at"]),
        },
        "location": {
            "dataset": identity["dataset"],
            "revision": identity["revision"],
            "path": target_path,
            "bytes": identity["bytes"],
            "sha256": identity["sha256"],
            "private": False,
            "gated": False,
            "xet_hash": None,
            "lfs_oid": None,
        },
        "publication": {
            "origin": "github_actions",
            "workflow": cast("str", publication.get("workflow")),
            "run": cast("str", publication.get("workflow_run")),
            "commit": cast("str", publication.get("workflow_commit")),
            "receipt": publication_receipt,
        },
        "verification": {
            "dataset": identity["dataset"],
            "revision": identity["revision"],
            "path": target_path,
            "sha256": identity["sha256"],
            "bytes": identity["bytes"],
            "anonymous": True,
            "clean_room": True,
            "status": "passed",
            "verified_at": cast("str", verification.get("verified_at")),
            "receipt": restore_receipt,
        },
        "rights": {
            "authorization": rights_receipt,
            "subject_sha256": identity["sha256"],
            "dataset": identity["dataset"],
            "path": target_path,
            "basis": "exact_scope_CC_BY_3_0_AU_authorization",
            "sensitivity": "non_sensitive",
            "publication": "approved_exact_scope",
        },
        "discovery": {
            "collections": [cast("str", discovery.get("collection"))],
            "estate_entry": estate_receipt,
        },
        "lineage": {
            "inputs": [source_receipt_url, event_url, b2_url],
            "v1_conformance": v1_receipt,
            "v2_field_lineage": None,
            "v3_replay": v3_receipt,
            "promotion_receipt": None,
            "v2_field_lineage_applicability": "not_applicable_raw_b2",
        },
        "recovery": {
            "role": cast("str", recovery.get("role")),
            "independent": False,
            "administrative_domain": cast(
                "str", recovery.get("administrative_domain")
            ),
            "primary_administrative_domain": cast(
                "str", recovery.get("primary_administrative_domain")
            ),
            "region": cast("str", recovery.get("region")),
            "primary_region": cast("str", recovery.get("primary_region")),
            "rpo_seconds": None,
            "rto_seconds": None,
            "checksum_inventory": {
                "url": cast("str", manifest.get("url")),
                "sha256": cast("str", manifest.get("sha256")),
            },
            "restore_receipt": restore_receipt,
            "authorization_receipt": None,
        },
        "cache": {
            "origin": "github_actions",
            "state": "removed",
            "max_bytes": identity["bytes"],
            "created_at": cache_created_at,
            "expires_at": cache_expires
            .astimezone(UTC)
            .isoformat()
            .replace("+00:00", "Z"),
            "cleanup_receipt": cache_cleanup_receipt,
            "offline_behavior": "fail_closed",
        },
        "consumers": [],
    }
    validate_contract(document, root=root)
    return document


def validate_contract(document: dict[str, Any], *, root: Path = ROOT) -> bytes:
    """Apply the pinned schema and semantic checks before any admission."""
    schema = (root / SCHEMA_PATH).read_bytes()
    Draft202012Validator(  # pyright: ignore[reportUnknownMemberType]
        json.loads(schema), format_checker=FormatChecker()
    ).validate(document)
    validate_federation_semantics(document)
    return (
        json.dumps(
            document, ensure_ascii=False, sort_keys=True, indent=2
        ).encode("utf-8")
        + b"\n"
    )


def _download_receipt(url: str, client: httpx.Client) -> bytes:
    comment = ISSUE_COMMENT_PATTERN.fullmatch(url)
    if comment:
        response = client.get(
            f"https://api.github.com/repos/edithatogo/"
            f"global-medicines-atlas/issues/comments/{comment.group(1)}",
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        response.raise_for_status()
        body: Any = response.json().get("body")
        if not isinstance(body, str):
            raise ValueError("public issue receipt has no text body")
        return body.encode("utf-8")
    response = client.get(url)
    response.raise_for_status()
    return response.content


def verify_and_admit(  # ruff: ignore[too-many-locals]
    raw_contract: bytes,
    *,
    root: Path = ROOT,
    target_path: str = TARGET_PATH,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Verify every external receipt then independently admit the exact pin."""
    schema = (root / SCHEMA_PATH).read_bytes()
    roles = contract_receipt_roles(raw_contract, schema=schema)
    host_set = set(READER_HOSTS) | {
        "raw.githubusercontent.com",
        "api.github.com",
    }
    hosts = tuple(sorted(host_set))
    policy = AcquisitionPolicy(
        allowed_hosts=hosts,
        max_bytes=MAX_RECEIPT_BYTES,
        timeout_seconds=30,
        max_attempts=1,
        max_redirects=3,
    )
    receipts: dict[str, bytes] = {}
    total = 0
    with httpx.Client(
        transport=BoundIPAddressTransport(policy=policy),
        follow_redirects=True,
        timeout=30,
        trust_env=False,
    ) as client:
        for role in roles:
            if role.url in receipts:
                continue
            if urlsplit(role.url).scheme != "https":
                raise ValueError("v4 receipt URL must use HTTPS")
            payload = _download_receipt(role.url, client)
            if len(payload) > MAX_RECEIPT_BYTES:
                raise ValueError("receipt exceeds the v4 per-object limit")
            total += len(payload)
            if total > MAX_TOTAL_BYTES:
                raise ValueError("receipt set exceeds the v4 aggregate limit")
            receipts[role.url] = payload
    closure = verify_receipt_closure(
        raw_contract,
        tuple(
            ReceiptPayload(url=url, payload=payload)
            for url, payload in sorted(receipts.items())
        ),
        schema=schema,
    )
    report = _read_json(root, ROLE_REPORT)
    candidate = _validate_inputs(root, report, target_path=target_path)
    identity = _target_identity(target_path)
    rights_file = cast("dict[str, Any]", candidate["rights_decision"])
    rights_path = Path(cast("str", rights_file["path"]))
    rights_url = _raw_url(rights_path)
    rights_receipt = ReceiptRole(
        role="/rights/authorization",
        url=rights_url,
        sha256=cast("str", rights_file["sha256"]),
    )
    source_receipt_url = _file_receipt(
        root, cast("str", candidate["_verified_source_receipt_path"])
    )
    event_url = _file_receipt(
        root, cast("str", candidate["_verified_event_path"])
    )
    b2_url = _file_receipt(root, cast("str", candidate["_verified_b2_path"]))
    v1 = cast("dict[str, Any]", candidate["v1_conformance_candidate_receipt"])
    v3 = cast("dict[str, Any]", candidate["v3_replay_candidate_receipt"])
    contract_document = json.loads(raw_contract)
    contract_v3 = contract_document["lineage"]["v3_replay"]
    lineage_roles = (
        ReceiptRole(
            role="/lineage/inputs/0",
            url=source_receipt_url["url"],
            sha256=source_receipt_url["sha256"],
        ),
        ReceiptRole(
            role="/lineage/inputs/1",
            url=event_url["url"],
            sha256=event_url["sha256"],
        ),
        ReceiptRole(
            role="/lineage/inputs/2",
            url=b2_url["url"],
            sha256=b2_url["sha256"],
        ),
        ReceiptRole(
            role="/lineage/v1_conformance",
            url=cast("str", v1["url"]),
            sha256=cast("str", v1["sha256"]),
        ),
        ReceiptRole(
            role="/lineage/v3_replay",
            url=cast("str", contract_v3["url"]),
            sha256=cast("str", v3["receipt"]["sha256"]),
        ),
    )
    trusted = TrustedAdmissionProfile(
        producer_repository="edithatogo/global-medicines-atlas",
        contract_repository="edithatogo/global-medicines-atlas",
        contract_commit=cast(
            "str",
            cast("dict[str, Any]", candidate["authority_candidate"])[
                "contract_commit"
            ],
        ),
        schema_sha256=cast(
            "str",
            cast("dict[str, Any]", candidate["authority_candidate"])[
                "schema_sha256"
            ],
        ),
        dataset=identity["dataset"],
        revision=identity["revision"],
        path=target_path,
        byte_count=identity["bytes"],
        sha256=identity["sha256"],
        source_id=identity["source_id"],
        acquisition_id=identity["acquisition_id"],
        layer="bronze",
        bronze_stratum="B2",
        representation="raw",
        schema_era=cast(
            "str", candidate["source_candidate_receipt"]["schema_era"]
        ),
        comparison_cohort=cast(
            "str", candidate["source_candidate_receipt"]["comparison_cohort"]
        ),
        effective_date=cast(
            "str", candidate["source_candidate_receipt"]["effective_date"]
        ),
        retrieved_at=cast("str", candidate["_verified_retrieved_at"]),
        evidence_kind="live",
        authorization=rights_receipt,
        lineage=lineage_roles,
    )
    admission = admit_closed_contract(
        raw_contract,
        closure,
        schema=schema,
        trusted=trusted,
    )
    admission_json = admission.model_dump(mode="json")
    closure_json = {
        "contract_sha256": closure.contract_sha256,
        "roles": [role.model_dump(mode="json") for role in closure.roles],
        "receipts": [
            receipt.model_dump(mode="json") for receipt in closure.receipts
        ],
        "receipt_content_retained": False,
    }
    return admission_json, closure_json


def run_reader_canary(
    raw_contract: bytes,
    admission_value: dict[str, Any],
    *,
    workflow_commit: str,
    workflow_run_id: str,
    workflow_run_attempt: str,
    root: Path = ROOT,
) -> dict[str, Any]:
    """Use the production bounded reader on the admitted exact public object."""
    schema = (root / SCHEMA_PATH).read_bytes()
    if _sha256(raw_contract) != admission_value.get("contract_sha256"):
        raise ValueError("consumer canary contract differs from admission")
    contract_document = json.loads(raw_contract)
    location = contract_document["location"]
    target_dataset = location["dataset"]
    target_revision = location["revision"]
    target_path = location["path"]
    target_bytes = location["bytes"]
    target_sha256 = location["sha256"]
    cache_expires_at = datetime.fromisoformat(
        contract_document["cache"]["expires_at"]
    )
    admission = AdmissionRecord.model_validate(admission_value)
    consumer_binding = bind_consumer_contract(
        raw_contract,
        consumer_repository="edithatogo/global-medicines-atlas",
        consumer_commit=workflow_commit,
    )
    if (
        consumer_binding.contract_sha256 != admission.contract_sha256
        or consumer_binding.object_sha256 != target_sha256
        or consumer_binding.byte_count != target_bytes
        or consumer_binding.path != target_path
    ):
        raise ValueError("consumer binding differs from admitted identity")
    policy = AcquisitionPolicy(
        allowed_hosts=READER_HOSTS,
        max_bytes=target_bytes,
        timeout_seconds=30,
        max_attempts=1,
        max_redirects=3,
    )
    digest = hashlib.sha256()
    byte_count = 0
    origin: str | None = None
    cache_after_read: int | None = None
    with FederatedReader(
        schema=schema,
        admission_records=(admission,),
        max_object_bytes=target_bytes,
        cache_bytes=target_bytes,
        max_entries=1,
        max_open_reads=1,
        timeout_seconds=30,
        transport_factory=lambda: BoundIPAddressTransport(policy=policy),
    ) as reader:
        with reader.open(raw_contract) as result:
            origin = result.origin
            if (
                result.sha256 != target_sha256
                or result.byte_count != target_bytes
                or result.contract_sha256 != admission.contract_sha256
            ):
                raise ValueError("reader identity differs from admission")
            while chunk := result.stream.read(64 * 1024):
                digest.update(chunk)
                byte_count += len(chunk)
        cache_after_read = reader.cached_bytes
        cached_after_read = reader.has_cached(admission.contract_sha256)
        cache_observed_at = datetime.now(UTC)
    if reader.cached_bytes != 0:
        raise ValueError("reader cache was not cleaned after close")
    observed_sha256 = digest.hexdigest()
    if (
        origin != "remote"
        or observed_sha256 != target_sha256
        or byte_count != target_bytes
        or cache_after_read
        != expected_cache_bytes(cache_expires_at, cache_observed_at)
        or cached_after_read != (cache_after_read > 0)
    ):
        raise ValueError("consumer stream or bounded cache result differs")
    if not _valid_workflow_identity(
        workflow_commit, workflow_run_id, workflow_run_attempt
    ):
        raise ValueError("hosted consumer canary identity is invalid")
    return {
        "schema_id": "global-medicines-atlas.m112-v4-consumer-canary",
        "schema_version": 1,
        "status": "passed",
        "consumer": {
            "repository": "edithatogo/global-medicines-atlas",
            "commit": workflow_commit,
            "binding_module": "global_medicines_atlas.federation_consumer.bind_consumer_contract",
            "module": "global_medicines_atlas.federation_reader.FederatedReader",
        },
        "contract_sha256": admission.contract_sha256,
        "object": {
            "dataset": target_dataset,
            "revision": target_revision,
            "path": target_path,
            "bytes": byte_count,
            "sha256": observed_sha256,
        },
        "verification": {
            "origin": origin,
            "remote_digest_match": True,
            "consumer_stream_digest_match": True,
            "reader_cache_bytes_after_read": cache_after_read,
            "reader_cache_bytes_after_close": 0,
            "expired_cache_not_retained": cache_after_read == 0,
            "source_values_or_rows_interpreted": False,
        },
        "hosted_workflow": {
            "repository": "edithatogo/global-medicines-atlas",
            "commit": workflow_commit,
            "run_id": int(workflow_run_id),
            "run_attempt": int(workflow_run_attempt),
            "run_url": (
                "https://github.com/edithatogo/global-medicines-atlas/"
                f"actions/runs/{workflow_run_id}"
            ),
        },
        "boundaries": {
            "admission_performed": False,
            "admission_used": True,
            "public_dataset_mutated": False,
            "source_payload_bytes_retained": False,
            "source_values_or_rows_included": False,
        },
    }


def _valid_workflow_identity(commit: str, run_id: str, attempt: str) -> bool:
    return (
        bool(re.fullmatch(r"[0-9a-f]{40}", commit))
        and run_id.isdecimal()
        and int(run_id) >= 1
        and attempt.isdecimal()
        and int(attempt) >= 1
    )


def expected_cache_bytes(
    expires_at: datetime,
    observed_at: datetime,
    *,
    byte_count: int = TARGET_BYTES,
) -> int:
    return byte_count if expires_at > observed_at else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--target-path", choices=sorted(TARGET_IDENTITIES), default=TARGET_PATH
    )
    parser.add_argument("--evidence-commit", default=EVIDENCE_COMMIT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--consumer-canary", action="store_true")
    parser.add_argument("--workflow-commit")
    parser.add_argument("--workflow-run-id")
    parser.add_argument("--workflow-run-attempt")
    parser.add_argument("--verification-report", type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    output_value = args.output or (
        CSV_OUTPUT if args.target_path != TARGET_PATH else OUTPUT
    )
    output = root / output_value
    expected = validate_contract(
        build_contract(
            root,
            target_path=args.target_path,
            evidence_commit=args.evidence_commit,
        ),
        root=root,
    )
    if args.check:
        if not output.is_file() or output.read_bytes() != expected:
            raise SystemExit(f"M-112 raw B2 contract is stale: {output}")
    elif not output.is_file() or output.read_bytes() != expected:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(expected)
    if args.verify:
        admission, closure = verify_and_admit(
            expected, root=root, target_path=args.target_path
        )
        canary = None
        if args.consumer_canary:
            if not all((
                args.workflow_commit,
                args.workflow_run_id,
                args.workflow_run_attempt,
            )):
                raise SystemExit(
                    "consumer canary requires exact hosted workflow identity"
                )
            canary = run_reader_canary(
                expected,
                admission,
                workflow_commit=cast("str", args.workflow_commit),
                workflow_run_id=cast("str", args.workflow_run_id),
                workflow_run_attempt=cast("str", args.workflow_run_attempt),
                root=root,
            )
        result = {
            "schema_id": "global-medicines-atlas.m112-v4-admission-qualification",
            "schema_version": 1,
            "status": "admitted_with_consumer_canary"
            if canary is not None
            else "admitted_pending_consumer_canary",
            "approved_denominator": 1759,
            "admissions": 1,
            "consumer_canaries": 1 if canary is not None else 0,
            "contract_path": output_value.as_posix(),
            "contract_sha256": _sha256(expected),
            "admission": admission,
            "receipt_closure": closure,
            "consumer_canary": canary,
            "source_values_or_payload_bytes_retained": False,
            "native_workbook_layout_qualified": False,
        }
        if args.verification_report is not None:
            report_path = root / args.verification_report
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(
                json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)
                + "\n",
                encoding="utf-8",
            )
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "admissions": 1,
                    "consumer_canaries": result["consumer_canaries"],
                    "contract_sha256": result["contract_sha256"],
                    "receipt_roles": len(closure["roles"]),
                    "verified_receipts": len(closure["receipts"]),
                },
                sort_keys=True,
            )
        )
    else:
        print(
            "M-112 July 2016 raw B2 contract passed schema and semantic checks; "
            "source-native workbook layout remains unqualified"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
