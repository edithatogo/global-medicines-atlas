"""Contract tests for the existing July 2026 MBS metadata cohort."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
import scripts.refresh_m112_july_metadata_readback as m112_july_refresh
from jsonschema import Draft202012Validator, FormatChecker

import global_medicines_atlas.australian_mbs_july_lifecycle_append as contract_module
from global_medicines_atlas.australian_mbs_july_lifecycle_append import (
    build_july_metadata_additions,
    build_updated_manifest,
    validate_july_contract,
)
from global_medicines_atlas.bronze_admission import (
    BronzeAdmissionRecord,
    BronzeAdmissionState,
)
from global_medicines_atlas.bronze_raw_evidence import (
    RawEvidenceManifest,
    RawEvidenceState,
)
from global_medicines_atlas.mbs_historical_lifecycle import (
    build_historical_mbs_lifecycle,
)
from global_medicines_atlas.receipts import (
    AcquisitionEvent,
    EvidenceClass,
    SourceReceipt,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = Path(
    "quality/qualifications/"
    "australian-m112-july-metadata-append-contract-20261018.json"
)
READBACK_PATH = Path(
    "quality/qualifications/"
    "australian-mbs-july-source-sidecar-readback-20261018.json"
)
AUTHORIZATION_PATH = Path(
    "quality/qualifications/australian-mbs-harvest-publication-authorization.json"
)
REPORT_PATH = Path(
    "quality/qualifications/"
    "australian-m112-per-object-gate-reconciliation-20261018.json"
)
SCHEMA_PATH = Path(
    "schemas/australian-m112-july-metadata-append-contract-v1.json"
)
HOSTED_READBACK_PATH = Path(
    "quality/qualifications/"
    "australian-mbs-july-metadata-hosted-readback-20261018.json"
)
SOURCE_REPORT_PATH = Path(
    "quality/qualifications/"
    "australian-m112-per-object-gate-reconciliation-20261018.json"
)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads((ROOT / path).read_bytes())
    assert isinstance(value, dict)
    return cast("dict[str, Any]", value)


def _private_call(name: str, *args: Any) -> Any:
    function = cast("Callable[..., Any]", getattr(contract_module, name))
    return function(*args)


def _refresh_private_call(name: str, *args: Any) -> Any:
    function = cast("Callable[..., Any]", getattr(m112_july_refresh, name))
    return function(*args)


@pytest.mark.unit
def test_contract_binds_exact_authorized_july_sidecars_and_m112_paths() -> None:
    contract = _load(CONTRACT_PATH)
    schema = _load(SCHEMA_PATH)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(  # pyright: ignore[reportUnknownMemberType] -- jsonschema types are partially unannotated
        contract
    )
    readback = _load(READBACK_PATH)
    authorization_bytes = (ROOT / AUTHORIZATION_PATH).read_bytes()
    report_bytes = (ROOT / REPORT_PATH).read_bytes()
    report = json.loads(report_bytes)

    assert (
        hashlib.sha256(authorization_bytes).hexdigest()
        == contract["authorization"]["sha256"]
    )
    assert (
        hashlib.sha256(report_bytes).hexdigest()
        == contract["m112_gate_report"]["sha256"]
    )
    assert (
        hashlib.sha256((ROOT / READBACK_PATH).read_bytes()).hexdigest()
        == (contract["source_sidecar_readback"]["sha256"])
    )
    assert readback["revision"] == contract["expected_parent_revision"]
    assert (
        readback["manifest"]["sha256"]
        == contract["expected_parent_manifest_sha256"]
    )
    assert (
        readback["manifest"]["file_count"]
        == contract["expected_parent_file_count"]
    )
    assert readback["boundaries"]["metadata_only"] is True
    assert readback["boundaries"]["raw_payload_bytes_read"] is False
    assert len(contract["objects"]) == 4

    approved_rows = {
        (item["dataset"], item["path"]): item
        for item in report["objects"]
        if item["approved_denominator_member"] is True
    }
    readback_rows = {item["archive_path"]: item for item in readback["objects"]}
    assert set(readback_rows) == {
        item["archive_path"] for item in contract["objects"]
    }
    for item in contract["objects"]:
        key = (contract["dataset"], item["archive_path"])
        report_row = approved_rows[key]
        observed_row = readback_rows[item["archive_path"]]
        assert report_row["identity"]["git_blob_oid"] == item["git_blob_oid"]
        assert report_row["identity"]["byte_count"] == item["bytes"]
        assert observed_row["archive_blob_oid"] == item["git_blob_oid"]
        assert observed_row["sidecar_path"] == item["sidecar_path"]
        assert observed_row["sidecar_sha256"] == item["sidecar_sha256"]
        assert observed_row["sidecar_bytes"] == item["sidecar_bytes"]
        assert observed_row["sidecar"]["sha256"] == item["sha256"]
        assert observed_row["sidecar"]["byte_count"] == item["bytes"]
        assert observed_row["sidecar"]["category"] == item["category"]
        assert observed_row["sidecar"]["source_url"] == item["source_url"]
        assert observed_row["sidecar"]["retrieved_at"] == item["retrieved_at"]


@pytest.mark.unit
def test_exact_july_cohort_builds_only_historical_landed_b1_b2_records() -> (
    None
):
    contract = _load(CONTRACT_PATH)
    readback = _load(READBACK_PATH)
    authorization = _load(AUTHORIZATION_PATH)
    observed = {item["archive_path"]: item for item in readback["objects"]}
    bundle: dict[str, bytes] = {}

    for item in contract["objects"]:
        row = observed[item["archive_path"]]
        assert item["sidecar_sha256"] == row["sidecar_sha256"]
        bundle.update(
            build_historical_mbs_lifecycle(
                row["sidecar"],
                authorization=authorization,
                authorization_commit=contract["authorization"][
                    "reference_commit"
                ],
                archive_revision=contract["expected_parent_revision"],
                observed_sha256=item["sha256"],
                observed_byte_count=item["bytes"],
                decided_at=datetime(2026, 10, 18, 7, 0, tzinfo=UTC),
            )
        )

    assert len(bundle) == 16
    receipts = [
        SourceReceipt.model_validate_json(value)
        for path, value in bundle.items()
        if path.startswith("bronze/receipts/")
    ]
    events = [
        AcquisitionEvent.model_validate_json(value)
        for path, value in bundle.items()
        if path.startswith("bronze/acquisitions/")
    ]
    b2_manifests = [
        RawEvidenceManifest.model_validate_json(value)
        for path, value in bundle.items()
        if path.startswith("bronze/raw-evidence/")
    ]
    admissions = [
        BronzeAdmissionRecord.model_validate_json(value)
        for path, value in bundle.items()
        if path.startswith("bronze/admissions/")
    ]

    assert (
        len(receipts)
        == len(events)
        == len(b2_manifests)
        == len(admissions)
        == 4
    )
    assert all(
        item.evidence_class is EvidenceClass.HISTORICAL for item in receipts
    )
    assert all(item.state is BronzeAdmissionState.LANDED for item in admissions)
    assert all(item.reviewer_status == "unreviewed" for item in admissions)
    assert all(
        item.rows[0].state is RawEvidenceState.EXTERNAL_REFERENCE_ONLY
        and item.rows[0].byte_count is None
        and item.rows[0].payload_sha256 is None
        for item in b2_manifests
    )
    assert all(
        item.sensitivity is not None
        and item.sensitivity.publication.value == "review_required"
        for item in receipts
    )


@pytest.mark.unit
def test_append_contract_builder_preserves_manifest_and_only_adds_metadata() -> (
    None
):
    contract, readback, authorization = validate_july_contract(
        (ROOT / CONTRACT_PATH).read_bytes(),
        (ROOT / SCHEMA_PATH).read_bytes(),
        (ROOT / READBACK_PATH).read_bytes(),
        (ROOT / AUTHORIZATION_PATH).read_bytes(),
        (ROOT / REPORT_PATH).read_bytes(),
    )
    anonymous_digests = {
        item["archive_path"]: (item["sha256"], item["bytes"])
        for item in contract["objects"]
    }
    additions = build_july_metadata_additions(
        contract,
        readback,
        authorization,
        anonymous_digests=anonymous_digests,
        decided_at=datetime(2026, 10, 18, 7, 0, tzinfo=UTC),
    )
    assert len(additions) == 16
    assert all(path.startswith("bronze/") for path in additions)
    assert all(len(payload) < 4096 for payload in additions.values())

    original_row = {"bytes": 3, "path": "README.md", "sha256": "c" * 64}
    manifest = {
        "dataset": contract["dataset"],
        "file_count": 1,
        "files": [original_row],
        "generated_at": "2026-10-17T03:50:56Z",
        "schema_id": "global-medicines-atlas.harvest-manifest",
        "schema_version": 1,
    }
    manifest_bytes = json.dumps(manifest, sort_keys=True).encode()
    updated_bytes = build_updated_manifest(
        manifest_bytes,
        additions,
        generated_at=datetime(2026, 10, 18, 7, 0, tzinfo=UTC),
        expected_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        expected_file_count=1,
    )
    updated = json.loads(updated_bytes)
    assert updated["file_count"] == 17
    assert original_row in updated["files"]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("payload", "label"),
    [(b"[]", "M-112 contract"), (b"null", "M-112 gate report")],
)
def test_json_reader_rejects_non_object_documents(
    payload: bytes, label: str
) -> None:
    with pytest.raises(TypeError, match="JSON object"):
        _private_call("_read_json", payload, label)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("document", "message"),
    [
        ({"objects": None}, "object list"),
        ({"objects": [None]}, "non-object row"),
    ],
)
def test_object_reader_rejects_malformed_collections(
    document: dict[str, Any], message: str
) -> None:
    with pytest.raises(TypeError, match=message):
        _private_call("_objects", document, "fixture")


@pytest.mark.unit
@pytest.mark.parametrize(
    ("section", "key", "value", "message"),
    [
        ("root", "dataset", "other/dataset", "dataset differs"),
        ("root", "revision", "a" * 40, "revision differs"),
        ("manifest", "sha256", "0" * 64, "manifest digest differs"),
        ("manifest", "file_count", 1, "manifest count differs"),
        ("boundaries", "metadata_only", False, "not metadata-only"),
        ("boundaries", "raw_payload_bytes_read", True, "raw payload access"),
    ],
)
def test_parent_readback_rejects_changed_identity_and_boundaries(
    section: str, key: str, value: Any, message: str
) -> None:
    contract = _load(CONTRACT_PATH)
    readback = _load(READBACK_PATH)
    target = readback if section == "root" else readback[section]
    target[key] = value
    with pytest.raises(ValueError, match=message):
        _private_call("_validate_parent_readback", contract, readback)


@pytest.mark.unit
def test_parent_readback_rejects_missing_sections() -> None:
    with pytest.raises(TypeError, match="missing manifest or boundaries"):
        _private_call("_validate_parent_readback", {}, {})


@pytest.mark.unit
@pytest.mark.parametrize(
    ("observed", "report_row", "message"),
    [
        (None, {}, "missing from evidence"),
        ({}, None, "missing from evidence"),
        ({"sidecar": {}}, {"identity": None}, "no identity"),
    ],
)
def test_object_binding_rejects_missing_evidence(
    observed: Any, report_row: Any, message: str
) -> None:
    item = _load(CONTRACT_PATH)["objects"][0]
    with pytest.raises(TypeError, match=message):
        _private_call("_validate_object_binding", item, observed, report_row)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("approved_denominator_member", False, "outside approved denominator"),
        ("git_blob_oid", "f" * 40, "blob identity differs"),
        ("byte_count", 1, "byte count differs"),
    ],
)
def test_m112_identity_rejects_unapproved_or_changed_payload(
    field: str, value: Any, message: str
) -> None:
    item = _load(CONTRACT_PATH)["objects"][0]
    report_row: dict[str, Any] = {
        "approved_denominator_member": True,
        "identity": {
            "byte_count": item["bytes"],
            "git_blob_oid": item["git_blob_oid"],
        },
    }
    if field == "approved_denominator_member":
        report_row[field] = value
    else:
        report_row["identity"][field] = value
    with pytest.raises(ValueError, match=message):
        _private_call(
            "_validate_gate_identity", item, report_row["identity"], report_row
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("target", "field", "value", "message"),
    [
        ("observed", "archive_blob_oid", "f" * 40, "tree payload identity"),
        ("observed", "sidecar_path", "wrong.json", "sidecar path differs"),
        ("observed", "sidecar_blob_oid", "f" * 40, "sidecar blob identity"),
        ("observed", "sidecar_sha256", "0" * 64, "sidecar digest differs"),
        ("observed", "sidecar_bytes", 1, "sidecar size differs"),
        ("sidecar", "archive_path", "wrong.xml", "sidecar raw path"),
        ("sidecar", "sha256", "0" * 64, "sidecar payload digest"),
        ("sidecar", "byte_count", 1, "sidecar payload size"),
        ("sidecar", "category", "unknown", "source category"),
        ("sidecar", "source_url", "https://wrong.example", "source URL"),
        ("sidecar", "retrieved_at", "2026-01-01T00:00:00Z", "timestamp"),
    ],
)
def test_sidecar_binding_rejects_changed_public_identity(
    target: str, field: str, value: Any, message: str
) -> None:
    item = _load(CONTRACT_PATH)["objects"][0]
    observed = next(
        row
        for row in _load(READBACK_PATH)["objects"]
        if row["archive_path"] == item["archive_path"]
    )
    sidecar = observed["sidecar"]
    (observed if target == "observed" else sidecar)[field] = value
    with pytest.raises(ValueError, match=message):
        _private_call("_validate_sidecar_identity", item, observed, sidecar)


@pytest.mark.unit
def test_contract_rejects_unpinned_readback_and_unapproved_rights() -> None:
    contract_bytes = (ROOT / CONTRACT_PATH).read_bytes()
    schema_bytes = (ROOT / SCHEMA_PATH).read_bytes()
    readback_bytes = (ROOT / READBACK_PATH).read_bytes()
    authorization_bytes = (ROOT / AUTHORIZATION_PATH).read_bytes()
    report_bytes = (ROOT / REPORT_PATH).read_bytes()

    with pytest.raises(
        ValueError, match="pinned source_sidecar_readback bytes"
    ):
        validate_july_contract(
            contract_bytes,
            schema_bytes,
            readback_bytes + b" ",
            authorization_bytes,
            report_bytes,
        )

    contract = json.loads(contract_bytes)
    authorization = json.loads(authorization_bytes)
    authorization["allowed_sources"] = []
    changed_authorization = json.dumps(authorization, sort_keys=True).encode()
    schema = cast("dict[str, Any]", json.loads(schema_bytes))
    schema["properties"]["authorization"]["properties"]["sha256"]["const"] = (
        hashlib.sha256(changed_authorization).hexdigest()
    )
    contract["authorization"]["sha256"] = hashlib.sha256(
        changed_authorization
    ).hexdigest()
    with pytest.raises(ValueError, match="authorization no longer applies"):
        validate_july_contract(
            json.dumps(contract, sort_keys=True).encode(),
            json.dumps(schema, sort_keys=True).encode(),
            readback_bytes,
            changed_authorization,
            report_bytes,
        )


@pytest.mark.unit
@pytest.mark.parametrize("case", ["unexpected_object", "extra_row"])
def test_contract_rejects_changed_readback_cohort(case: str) -> None:
    contract = _load(CONTRACT_PATH)
    schema_bytes = (ROOT / SCHEMA_PATH).read_bytes()
    readback = _load(READBACK_PATH)
    if case == "extra_row":
        extra = json.loads(json.dumps(readback["objects"][-1]))
        extra["archive_path"] = "raw/mbs/unapproved.xml"
        readback["objects"].append(extra)
        message = "cohort denominator differs"
    else:
        readback["objects"][-1]["archive_path"] = "raw/mbs/unapproved.xml"
        message = "unexpected object"
    readback_bytes = json.dumps(readback, sort_keys=True).encode()
    contract["source_sidecar_readback"]["sha256"] = hashlib.sha256(
        readback_bytes
    ).hexdigest()
    schema = cast("dict[str, Any]", json.loads(schema_bytes))
    schema["properties"]["source_sidecar_readback"]["properties"]["sha256"][
        "const"
    ] = contract["source_sidecar_readback"]["sha256"]
    with pytest.raises(ValueError, match=message):
        validate_july_contract(
            json.dumps(contract, sort_keys=True).encode(),
            json.dumps(schema, sort_keys=True).encode(),
            readback_bytes,
            (ROOT / AUTHORIZATION_PATH).read_bytes(),
            (ROOT / REPORT_PATH).read_bytes(),
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("digests", "message"),
    [
        ({}, "cohort differs"),
        ({"wrong/path": ("0" * 64, 1)}, "cohort differs"),
    ],
)
def test_metadata_builder_rejects_different_digest_cohort(
    digests: dict[str, tuple[str, int]], message: str
) -> None:
    contract, readback, authorization = validate_july_contract(
        (ROOT / CONTRACT_PATH).read_bytes(),
        (ROOT / SCHEMA_PATH).read_bytes(),
        (ROOT / READBACK_PATH).read_bytes(),
        (ROOT / AUTHORIZATION_PATH).read_bytes(),
        (ROOT / REPORT_PATH).read_bytes(),
    )
    with pytest.raises(ValueError, match=message):
        build_july_metadata_additions(
            contract,
            readback,
            authorization,
            anonymous_digests=digests,
            decided_at=datetime(2026, 10, 18, 7, 0, tzinfo=UTC),
        )


@pytest.mark.unit
@pytest.mark.parametrize("case", ["digest", "size"])
def test_metadata_builder_rejects_changed_anonymous_payload_identity(
    case: str,
) -> None:
    contract, readback, authorization = validate_july_contract(
        (ROOT / CONTRACT_PATH).read_bytes(),
        (ROOT / SCHEMA_PATH).read_bytes(),
        (ROOT / READBACK_PATH).read_bytes(),
        (ROOT / AUTHORIZATION_PATH).read_bytes(),
        (ROOT / REPORT_PATH).read_bytes(),
    )
    digests = {
        item["archive_path"]: (item["sha256"], item["bytes"])
        for item in contract["objects"]
    }
    first_path = contract["objects"][0]["archive_path"]
    digest, size = digests[first_path]
    digests[first_path] = (
        (digest, size + 1) if case == "size" else ("0" * 64, size)
    )
    with pytest.raises(ValueError, match="anonymous payload identity"):
        build_july_metadata_additions(
            contract,
            readback,
            authorization,
            anonymous_digests=digests,
            decided_at=datetime(2026, 10, 18, 7, 0, tzinfo=UTC),
        )


@pytest.mark.unit
def test_july_hosted_metadata_readback_refreshes_four_m112_rows_only() -> None:
    original_report_bytes = (ROOT / SOURCE_REPORT_PATH).read_bytes()
    source = _load(SOURCE_REPORT_PATH)
    original_rows = {row["path"]: row for row in source["objects"]}
    contract = _load(CONTRACT_PATH)
    authorization = _load(AUTHORIZATION_PATH)
    hosted_readback = _load(HOSTED_READBACK_PATH)

    refreshed = m112_july_refresh.build_report(
        source,
        contract,
        authorization,
        hosted_readback,
    )
    refreshed_rows = {row["path"]: row for row in refreshed["objects"]}
    july_paths = {item["archive_path"] for item in contract["objects"]}

    assert len(refreshed["objects"]) == 1759
    assert refreshed["scope"]["approved_denominator"] == 1759
    assert refreshed["scope"]["preserved_deferrals"] == 1759
    assert (
        refreshed["aggregate_gates"]["paths_with_sha256_metadata_or_binding"]
        == 1655
    )
    assert (
        refreshed["aggregate_gates"]["paths_with_anonymous_digest_readback"]
        == 29
    )
    assert (
        refreshed["aggregate_gates"][
            "paths_with_exact_scope_rights_decision_and_public_readback"
        ]
        == 14
    )
    assert (
        refreshed["aggregate_gates"]["paths_with_exact_source_release_rights"]
        == 6
    )
    assert (
        refreshed["aggregate_gates"]["paths_with_complete_b1_b2_lineage"] == 6
    )
    assert refreshed["aggregate_gates"]["paths_admitted_to_v4"] == 0
    assert refreshed["aggregate_gates"]["paths_with_consumer_canary"] == 0
    assert (
        refreshed["deferral_group_counts"]["au-mbs-july-2026-raw-object-paths"]
        == 4
    )
    assert (
        refreshed["deferral_group_counts"][
            "au-mbs-six-exact-receipt-and-authorization-gaps"
        ]
        == 2
    )
    assert (
        refreshed["july_metadata_readback"]["revision"]
        == hosted_readback["revision"]
    )
    assert (
        refreshed["july_metadata_readback"]["metadata_objects_verified"] == 16
    )
    assert refreshed["boundaries"]["m112_federation_accepted"] is False

    for path in original_rows.keys() - july_paths:
        assert refreshed_rows[path] == original_rows[path]
    for spec in contract["objects"]:
        row = refreshed_rows[spec["archive_path"]]
        assert row["revision"] == hosted_readback["revision"]
        assert row["identity"]["sha256"] == spec["sha256"]
        assert row["identity"]["anonymous_digest_readback"] is True
        assert (
            row["rights"]["state"]
            == "authorized_exact_source_release_permitted"
        )
        assert row["b1_b2_lineage"]["complete"] is True
        assert row["v4_admission"] is False
        assert row["consumer_canary"] is False
        assert row["disposition"] == "deferred_not_admitted"

    serialized = _refresh_private_call("_serialize_report", refreshed)
    assert json.loads(serialized) == refreshed
    assert (ROOT / SOURCE_REPORT_PATH).read_bytes() == original_report_bytes


@pytest.mark.unit
@pytest.mark.parametrize(
    ("target", "value", "message"),
    [
        ("status", "failed", "not anonymously verified"),
        ("digest", "0" * 64, "hosted raw digest or identity differs"),
        ("admission", "accepted", "July B1/B2 lifecycle state differs"),
    ],
)
def test_july_hosted_readback_refresh_rejects_forged_evidence(
    target: str,
    value: str,
    message: str,
) -> None:
    source = _load(SOURCE_REPORT_PATH)
    contract = _load(CONTRACT_PATH)
    authorization = _load(AUTHORIZATION_PATH)
    readback = _load(HOSTED_READBACK_PATH)
    if target == "status":
        readback["workflow"]["status"] = value
    elif target == "digest":
        readback["objects"][0]["sha256"] = value
    else:
        readback["objects"][0]["landed_admission"]["state"] = value

    with pytest.raises(ValueError, match=message):
        m112_july_refresh.build_report(
            source,
            contract,
            authorization,
            readback,
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("target", "field", "value", "message"),
    [
        ("contract", "m112_gate_report", {}, "does not bind the frozen"),
        ("readback", "dataset", "other/dataset", "different dataset"),
        ("readback", "parent_revision", "0" * 40, "parent revision differs"),
        ("workflow", "contract_sha256", "0" * 64, "does not bind the contract"),
        (
            "workflow",
            "authorization_sha256",
            "0" * 64,
            "does not bind authorization",
        ),
        (
            "authorization",
            "external_publication_authorized",
            False,
            "authorization is absent",
        ),
        (
            "manifest",
            "parent_rows_preserved",
            False,
            "manifest readback diverges",
        ),
        ("manifest", "new_paths_count", 15, "manifest readback diverges"),
        (
            "gates",
            "anonymous_metadata_readback",
            "failed",
            "different publication state",
        ),
        ("gates", "accepted_admissions", 1, "different publication state"),
        (
            "boundaries",
            "rights_scope_expanded",
            True,
            "crosses an M-112 boundary",
        ),
        ("report_scope", "approved_denominator", 1758, "denominator changed"),
        (
            "report_objects",
            "truncate",
            True,
            "object denominator is incomplete",
        ),
        ("contract_objects", "truncate", True, "contract cohort"),
        ("metadata_additions", "truncate", True, "metadata addition cohort"),
        (
            "metadata_addition",
            "manifest_row_matches",
            False,
            "does not match its manifest",
        ),
        ("raw_digest", "bytes", 1, "raw digest or identity differs"),
        ("raw_object", "category", "other", "raw digest or identity differs"),
        (
            "raw_object",
            "raw_manifest_row_preserved",
            False,
            "raw digest or identity differs",
        ),
        (
            "source_report_row",
            "approved_denominator_member",
            False,
            "expected deferred row",
        ),
        (
            "metadata_link",
            "sha256",
            "0" * 64,
            "metadata identity or digest differs",
        ),
        (
            "metadata_addition",
            "kind",
            "wrong_kind",
            "metadata identity or digest differs",
        ),
        (
            "metadata_addition",
            "source_id",
            "other-source",
            "metadata identity or digest differs",
        ),
        ("lifecycle", "rights_state", "unknown", "lifecycle state differs"),
    ],
)
def test_july_hosted_readback_refresh_rejects_inconsistent_bindings(  # ruff: ignore[too-many-branches] -- mutation targets are explicit adversarial cases
    target: str,
    field: str,
    value: Any,
    message: str,
) -> None:
    source = _load(SOURCE_REPORT_PATH)
    contract = _load(CONTRACT_PATH)
    authorization = _load(AUTHORIZATION_PATH)
    readback = _load(HOSTED_READBACK_PATH)
    path = contract["objects"][0]["archive_path"]
    observed = next(
        row for row in readback["objects"] if row["archive_path"] == path
    )

    if target == "contract":
        contract[field] = value
    elif target == "readback":
        readback[field] = value
    elif target == "workflow":
        readback["workflow"][field] = value
    elif target == "authorization":
        authorization[field] = value
    elif target == "manifest":
        readback["manifest_readback"][field] = value
    elif target in {"gates", "boundaries"}:
        readback[target][field] = value
    elif target == "report_scope":
        source["scope"][field] = value
    elif target == "report_objects":
        source["objects"].pop()
    elif target == "contract_objects":
        contract["objects"].pop()
    elif target == "metadata_additions":
        readback["metadata_additions"].pop()
    elif target == "metadata_addition":
        next(
            row
            for row in readback["metadata_additions"]
            if row["path"] == observed["b1_acquisition"]["path"]
        )[field] = value
    elif target == "raw_digest":
        next(
            row for row in readback["raw_object_digests"] if row["path"] == path
        )[field] = value
    elif target == "raw_object":
        observed[field] = value
    elif target == "source_report_row":
        row = next(row for row in source["objects"] if row["path"] == path)
        row[field] = value
    elif target == "metadata_link":
        link_path = observed["b1_acquisition"]["path"]
        link = next(
            row
            for row in readback["metadata_additions"]
            if row["path"] == link_path
        )
        link[field] = value
    else:
        observed["b1_acquisition"][field] = value

    with pytest.raises(ValueError, match=message):
        m112_july_refresh.build_report(
            source, contract, authorization, readback
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("collection", "identity_key", "value_key"),
    [
        ("contract", "archive_path", "sha256"),
        ("objects", "archive_path", "sha256"),
        ("raw_object_digests", "path", "sha256"),
        ("metadata_additions", "path", "sha256"),
        ("report", "path", "disposition"),
    ],
)
@pytest.mark.parametrize("duplicate_first", [False, True])
def test_july_hosted_readback_refresh_rejects_conflicting_duplicate_identities(
    collection: str,
    identity_key: str,
    value_key: str,
    *,
    duplicate_first: bool,
) -> None:
    source = _load(SOURCE_REPORT_PATH)
    contract = _load(CONTRACT_PATH)
    authorization = _load(AUTHORIZATION_PATH)
    readback = _load(HOSTED_READBACK_PATH)

    if collection == "contract":
        rows = contract["objects"]
    elif collection == "report":
        rows = source["objects"]
    else:
        rows = readback[collection]
    first, second = rows[0], rows[1]
    second[identity_key] = first[identity_key]
    if value_key == "disposition":
        second[value_key] = "conflicting-disposition"
    else:
        second[value_key] = "0" * 64
    if duplicate_first:
        rows[0], rows[1] = rows[1], rows[0]

    message = (
        "duplicate identities"
        if collection == "report"
        else "not exact and unique"
    )
    with pytest.raises(ValueError, match=message):
        m112_july_refresh.build_report(
            source, contract, authorization, readback
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("collection", "identity_key"),
    [
        ("contract", "archive_path"),
        ("objects", "archive_path"),
        ("raw_object_digests", "path"),
        ("metadata_additions", "path"),
    ],
)
def test_july_hosted_readback_refresh_rejects_widened_cohorts(
    collection: str,
    identity_key: str,
) -> None:
    source = _load(SOURCE_REPORT_PATH)
    contract = _load(CONTRACT_PATH)
    authorization = _load(AUTHORIZATION_PATH)
    readback = _load(HOSTED_READBACK_PATH)

    if collection == "contract":
        rows = contract["objects"]
    else:
        rows = readback[collection]
    extra = json.loads(json.dumps(rows[0]))
    extra[identity_key] = f"{extra[identity_key]}-unexpected"
    rows.append(extra)

    with pytest.raises(ValueError, match="not exact and unique"):
        m112_july_refresh.build_report(
            source, contract, authorization, readback
        )


@pytest.mark.unit
def test_july_hosted_readback_refresh_rejects_source_identity_and_json_shape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_bytes = (ROOT / SOURCE_REPORT_PATH).read_bytes()
    contract_bytes = (ROOT / CONTRACT_PATH).read_bytes()
    authorization_bytes = (ROOT / AUTHORIZATION_PATH).read_bytes()
    readback_bytes = (ROOT / HOSTED_READBACK_PATH).read_bytes()
    contract = _load(CONTRACT_PATH)
    readback = _load(HOSTED_READBACK_PATH)
    first = contract["objects"][0]
    valid = _load(SOURCE_REPORT_PATH)
    source_row = next(
        row for row in valid["objects"] if row["path"] == first["archive_path"]
    )
    source_row["path"] = "raw/mbs/unmatched.xml"
    with pytest.raises(ValueError, match="expected deferred row"):
        m112_july_refresh.build_report(
            valid,
            contract,
            _load(AUTHORIZATION_PATH),
            readback,
        )

    identity_source = _load(SOURCE_REPORT_PATH)
    identity_row = next(
        row
        for row in identity_source["objects"]
        if row["path"] == first["archive_path"]
    )
    identity_row["identity"]["git_blob_oid"] = "0" * 40
    with pytest.raises(ValueError, match="July raw identity differs"):
        _refresh_private_call(
            "_apply_july_rows",
            identity_source,
            contract,
            {first["archive_path"]: {"revision": readback["revision"]}},
        )

    monkeypatch.setattr(m112_july_refresh, "ROOT", tmp_path)
    tmp_report = tmp_path / m112_july_refresh.SOURCE_REPORT
    tmp_report.parent.mkdir(parents=True)
    for relative, content in (
        (m112_july_refresh.SOURCE_REPORT, source_bytes),
        (m112_july_refresh.CONTRACT, contract_bytes),
        (m112_july_refresh.AUTHORIZATION, authorization_bytes),
        (m112_july_refresh.READBACK, readback_bytes),
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    json_path = tmp_path / "not-object.json"
    json_path.write_text("[]", encoding="utf-8")
    with pytest.raises(TypeError, match="expected a JSON object"):
        _refresh_private_call("_read", "not-object.json")

    m112_july_refresh.main()
    output = tmp_path / m112_july_refresh.OUTPUT
    assert (
        json.loads(output.read_text(encoding="utf-8"))["scope"][
            "preserved_deferrals"
        ]
        == 1759
    )


@pytest.mark.unit
def test_metadata_builder_rejects_duplicate_generated_paths() -> None:
    contract, readback, authorization = validate_july_contract(
        (ROOT / CONTRACT_PATH).read_bytes(),
        (ROOT / SCHEMA_PATH).read_bytes(),
        (ROOT / READBACK_PATH).read_bytes(),
        (ROOT / AUTHORIZATION_PATH).read_bytes(),
        (ROOT / REPORT_PATH).read_bytes(),
    )
    first = contract["objects"][0]
    duplicate = json.loads(json.dumps(first))
    contract["objects"] = [first, duplicate]
    digests = {first["archive_path"]: (first["sha256"], first["bytes"])}
    with pytest.raises(ValueError, match="duplicate lifecycle metadata"):
        build_july_metadata_additions(
            contract,
            readback,
            authorization,
            anonymous_digests=digests,
            decided_at=datetime(2026, 10, 18, 7, 0, tzinfo=UTC),
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("expected_sha", "expected_count", "message"),
    [
        ("0" * 64, 1, "manifest digest differs"),
        (None, 2, "file count differs"),
    ],
)
def test_updated_manifest_rejects_wrong_parent_identity(
    expected_sha: str | None, expected_count: int, message: str
) -> None:
    manifest: dict[str, Any] = {
        "file_count": 1,
        "files": [],
        "schema_id": "global-medicines-atlas.harvest-manifest",
        "schema_version": 1,
    }
    encoded = json.dumps(manifest, sort_keys=True).encode()
    with pytest.raises(ValueError, match=message):
        contract_module.build_updated_manifest(
            encoded,
            {},
            generated_at=datetime(2026, 10, 18, 7, 0, tzinfo=UTC),
            expected_sha256=expected_sha or hashlib.sha256(encoded).hexdigest(),
            expected_file_count=expected_count,
        )
