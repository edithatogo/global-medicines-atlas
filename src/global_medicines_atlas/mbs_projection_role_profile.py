"""Verify same-stratum MBS projection lineage without payload I/O.

The v1 vocabulary remains immutable. A v1 document describes an existing raw
B1-to-B2 decision; the separate profile binds a rebuildable B2-associated
projection to that source and the producer's own acquisition. The v3 receipt
commits to a schema-validated plan reconstructed from retained metadata.
Nothing here grants rights, clears privacy, or performs a v4 admission.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, cast

from jsonschema import Draft202012Validator

from .federation_receipt_closure import (
    ReceiptClosure,
    ReceiptPayload,
    verify_receipt_closure,
)
from .strict_json import unique_json_object

MAX_METADATA_BYTES = 1024 * 1024
V1_SCHEMA_SHA256 = (
    "4c1ee81b026c64cf8f962d602cd64441a4a023c132346349c8b27dab0981f10e"
)
V2_SCHEMA_SHA256 = (
    "bf31ee62a3566a8fde512748b79f644e0fab760f60924e4eb9d510d3c1ef6f8a"
)
V3_SCHEMA_SHA256 = (
    "5d0f472b124701ef66dcc1a5c39670826b8e95e5faf576cc394a3cd22df9419c"
)
PROFILE_SCHEMA_SHA256 = (
    "a6aeeb7f93e6c51ac562e74ff5a1670cae88240128ad963e23762a0749f6bd27"
)
RECEIPT_SCHEMA_SHA256 = (
    "1321940f7233199c0ebdede6615aa49a6e681d89084bf51b874366a83de7d648"
)
# Frozen August 2026 producer field set; later adapter changes do not alter this profile.
MBS_AUGUST_2026_FIELDS = (
    "Anaes",
    "AnaesChange",
    "BasicUnits",
    "Benefit100",
    "Benefit75",
    "Benefit85",
    "BenefitStartDate",
    "BenefitType",
    "Category",
    "DerivedFee",
    "DerivedFeeStartDate",
    "Description",
    "DescriptionStartDate",
    "DescriptorChange",
    "EMSNCap",
    "EMSNChange",
    "EMSNChangeDate",
    "EMSNDescription",
    "EMSNEndDate",
    "EMSNFixedCapAmount",
    "EMSNMaximumCap",
    "EMSNPercentageCap",
    "EMSNStartDate",
    "FeeChange",
    "FeeStartDate",
    "FeeType",
    "Group",
    "ItemChange",
    "ItemEndDate",
    "ItemNum",
    "ItemStartDate",
    "ItemType",
    "NewItem",
    "ProviderType",
    "QFEEndDate",
    "QFEStartDate",
    "ScheduleFee",
    "SubGroup",
    "SubHeading",
    "SubItemNum",
)
SOURCE_FIELDS = 85
FROZEN_OBJECTS = 4
RECIPE_LINEAGE_REPORT = (
    "quality/qualifications/australian-mbs-august-projection-field-lineage-qualification-20261115.json",
    "e880ccded4e51b0eae7bfd9f4370824eebb3d6d8efa91bed1167a4289e8fe1f6",
)
RECIPE_PLAN_BUILDER = (
    "scripts/qualify_mbs_august_projection_replay.py",
    "fedb7199e17e2c1c58ea2d4142c2fd121d6866fd3633008bcc3d1529c967b7a0",
)
RECIPE_V3_BUILDER = (
    "scripts/qualify_m112_v3_replay.py",
    "c8ce3ef0f7aac75a01e391c993dfc8600cf07379250840e7efaa96d0f588f633",
)
RECIPE_LINEAGE_BUILDER = (
    "scripts/qualify_mbs_august_projection_field_lineage.py",
    "ab48500950766722196a2ebfbb06907e0d0588f8c153315d3b2a87bfb05de364",
)


@dataclass(frozen=True, slots=True)
class ObjectIdentity:
    """Independent exact object expectation; it is not derived from a receipt."""

    dataset: str
    revision: str
    path: str
    sha256: str
    byte_count: int


@dataclass(frozen=True, slots=True)
class MetadataReference:
    """Independent exact repository-metadata reference."""

    path: str
    sha256: str


@dataclass(frozen=True, slots=True)
class ProjectionRoleTrust:
    """Caller-owned exact identities and digests, not permission to read data."""

    source: ObjectIdentity
    projection: ObjectIdentity
    source_acquisition_id: str
    source_event: MetadataReference
    source_b2: MetadataReference
    source_authorization: MetadataReference
    source_contract: MetadataReference
    producer_acquisition_id: str
    producer_commit: str
    producer_event: MetadataReference
    producer_b2: MetadataReference
    producer_receipt: MetadataReference
    producer_event_reconstructed: bool
    source_v1: MetadataReference
    v2_lineage: MetadataReference
    source_admission: MetadataReference
    prior_replay: MetadataReference
    lineage_report: MetadataReference
    plan_builder: MetadataReference
    v3_builder: MetadataReference
    lineage_builder: MetadataReference
    projection_rights: MetadataReference
    v3_plan_sha256: str
    v3_registration_sha256: str
    profile_sha256: str
    v3_receipt_sha256: str


@dataclass(frozen=True, slots=True, repr=False)
class ProjectionEvidence:
    """Caller-supplied metadata bytes; never source or projection payloads."""

    source_v1: bytes
    v2_lineage: bytes
    source_admission: bytes
    source_event: bytes
    source_b2: bytes
    source_authorization: bytes
    source_contract: bytes
    producer_event: bytes
    producer_b2: bytes
    producer_receipt: bytes
    projection_rights: bytes
    prior_replay: bytes
    lineage_report: bytes
    plan_builder: bytes
    v3_builder: bytes
    lineage_builder: bytes


@dataclass(frozen=True, slots=True)
class ProjectionSchemas:
    """Schema bytes supplied by the caller and verified against pinned digests."""

    v1_profile: bytes
    v1: bytes
    v2: bytes
    v3_receipt: bytes
    v3: bytes
    v4: bytes


def _require(condition: object, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()


def _digest(value: object) -> str:
    return _sha(_canonical(value))


def _document(raw: bytes) -> dict[str, Any]:
    if type(raw) is not bytes or not raw or len(raw) > MAX_METADATA_BYTES:
        raise ValueError("metadata byte limit or type differs")
    try:
        result = json.loads(raw, object_pairs_hook=unique_json_object)
    except (ValueError, TypeError, RecursionError) as error:
        raise ValueError("invalid metadata JSON") from error
    if not isinstance(result, dict):
        raise TypeError("metadata document is not an object")
    return cast("dict[str, Any]", result)


def _schema(raw: bytes, expected: str) -> dict[str, Any]:
    _require(_sha(raw) == expected, "schema digest differs")
    return _document(raw)


def _validate(document: dict[str, Any], schema: dict[str, Any]) -> None:
    if not Draft202012Validator(schema).is_valid(document):  # pyright: ignore[reportUnknownMemberType]
        raise ValueError("metadata schema validation failed")


def _bound(raw: bytes, digest: str) -> dict[str, Any]:
    _require(_sha(raw) == digest, "metadata content digest differs")
    return _document(raw)


def _check_b1_b2(
    event_bytes: bytes,
    b2_bytes: bytes,
    event_ref: MetadataReference,
    b2_ref: MetadataReference,
    acquisition_id: str,
    source_sha256: str,
) -> dict[str, Any]:
    event = _bound(event_bytes, event_ref.sha256)
    b2 = _bound(b2_bytes, b2_ref.sha256)
    rows = b2.get("rows", [])
    _require(
        event.get("schema_id")
        == "global-medicines-atlas.bronze-acquisition-event"
        and event.get("source_id") == "au-mbs"
        and event.get("acquisition_id") == acquisition_id
        and event.get("content_id")
        == event.get("payload_sha256")
        == source_sha256
        and b2.get("schema_id")
        == "global-medicines-atlas.b2-raw-evidence-manifest"
        and len(rows) == 1
        and rows[0].get("acquisition_id") == acquisition_id
        and rows[0].get("source_id") == "au-mbs"
        and rows[0].get("content_id") == source_sha256
        and rows[0].get("stratum") == "B2"
        and rows[0].get("state") == "external_reference_only"
        and rows[0].get("source_native_bytes_immutable") is True
        and rows[0].get("payload_contents_in_metadata") is False,
        "B1/B2 source metadata differs",
    )
    return event


def _check_producer_inputs(
    evidence: ProjectionEvidence, trusted: ProjectionRoleTrust
) -> None:
    event = _check_b1_b2(
        evidence.producer_event,
        evidence.producer_b2,
        trusted.producer_event,
        trusted.producer_b2,
        trusted.producer_acquisition_id,
        trusted.source.sha256,
    )
    receipt = _bound(evidence.producer_receipt, trusted.producer_receipt.sha256)
    _require(
        receipt["source"]["source_id"] == "au-mbs"
        and receipt["payload"]["sha256"] == trusted.source.sha256
        and receipt["payload"]["byte_count"] == trusted.source.byte_count
        and receipt["retrieval"]["retrieved_at"] == event["retrieved_at"],
        "producer source receipt differs",
    )


def _check_projection_rights(
    evidence: ProjectionEvidence, trusted: ProjectionRoleTrust
) -> None:
    rights = _bound(
        evidence.projection_rights, trusted.projection_rights.sha256
    )
    selected = [
        row
        for row in rights["authorized_objects"]
        if row["path"] == trusted.projection.path
    ]
    boundaries = rights["boundaries"]
    _require(
        rights["dataset"] == trusted.projection.dataset
        and rights["public_release_rights_attested"] is True
        and len(rights["authorized_objects"]) == FROZEN_OBJECTS
        and len(selected) == 1
        and selected[0]["sha256"] == trusted.projection.sha256
        and selected[0]["byte_count"] == trusted.projection.byte_count
        and boundaries["scope_is_exact_four_frozen_objects_only"] is True
        and boundaries["v4_admission_or_promotion_authorized"] is False
        and boundaries["consumer_canaries_authorized"] is False,
        "existing projection rights evidence differs",
    )


def _check_source_rights(
    evidence: ProjectionEvidence, trusted: ProjectionRoleTrust
) -> None:
    authorization = _bound(
        evidence.source_authorization, trusted.source_authorization.sha256
    )
    contract = _bound(evidence.source_contract, trusted.source_contract.sha256)
    location, source, rights = (
        contract["location"],
        contract["source"],
        contract["rights"],
    )
    _require(
        authorization["dataset"] == trusted.source.dataset
        and authorization["external_publication_authorized"] is True
        and authorization["maintainer_asserted_redistribution_permission"]
        is True
        and "au-mbs" in authorization["allowed_sources"]
        and "monthly_schedule_xml" in authorization["categories"]
        and location["dataset"] == trusted.source.dataset
        and location["revision"] == trusted.source.revision
        and location["path"] == trusted.source.path
        and location["sha256"] == trusted.source.sha256
        and location["bytes"] == trusted.source.byte_count
        and source["acquisition_id"] == trusted.source_acquisition_id
        and source["representation"] == "raw"
        and source["bronze_stratum"] == "B2"
        and rights["dataset"] == trusted.source.dataset
        and rights["path"] == trusted.source.path
        and rights["subject_sha256"] == trusted.source.sha256
        and rights["authorization"]["sha256"]
        == trusted.source_authorization.sha256
        and rights["basis"]
        == "maintainer_attested_exact_scope_permission_not_independently_reviewed"
        and rights["publication"] == "approved_exact_scope",
        "existing raw source rights evidence differs",
    )


def _check_reconstruction(
    evidence: ProjectionEvidence, trusted: ProjectionRoleTrust
) -> None:
    _require(
        trusted.lineage_report == MetadataReference(*RECIPE_LINEAGE_REPORT)
        and trusted.plan_builder == MetadataReference(*RECIPE_PLAN_BUILDER)
        and trusted.v3_builder == MetadataReference(*RECIPE_V3_BUILDER)
        and trusted.lineage_builder
        == MetadataReference(*RECIPE_LINEAGE_BUILDER),
        "reconstruction recipe identity differs",
    )
    report = _bound(evidence.lineage_report, trusted.lineage_report.sha256)
    for blob, reference in (
        (evidence.plan_builder, trusted.plan_builder),
        (evidence.v3_builder, trusted.v3_builder),
        (evidence.lineage_builder, trusted.lineage_builder),
    ):
        _require(
            type(blob) is bytes
            and 0 < len(blob) <= MAX_METADATA_BYTES
            and _sha(blob) == reference.sha256,
            "reconstruction code digest differs",
        )
    selected = [
        row
        for row in report["objects"]
        if row["path"] == trusted.projection.path
    ]
    _require(
        len(selected) == 1
        and all(
            selected[0][key] == value
            for key, value in asdict(trusted.projection).items()
        )
        and selected[0]["producer_commit"] == trusted.producer_commit
        and selected[0]["frozen_member"] is True
        and selected[0]["source_receipt"] == asdict(trusted.producer_receipt)
        and selected[0]["rights_evidence"] == asdict(trusted.projection_rights)
        and report["v2_lineage"]["path"] == trusted.v2_lineage.path
        and report["v2_lineage"]["sha256"] == trusted.v2_lineage.sha256,
        "reconstruction lineage report differs",
    )


def verify_v1_projection_profile(
    profile_bytes: bytes,
    evidence: ProjectionEvidence,
    profile_schema_bytes: bytes,
    v1_schema_bytes: bytes,
    v2_schema_bytes: bytes,
    *,
    trusted: ProjectionRoleTrust,
) -> None:
    """Verify source v1 and exact v2-backed same-stratum derivation.

    The caller must separately authenticate all trust inputs and close receipt
    bytes. This profile is not itself an admission or source-rights decision.
    """
    profile = _bound(profile_bytes, trusted.profile_sha256)
    v1 = _bound(evidence.source_v1, trusted.source_v1.sha256)
    v2 = _bound(evidence.v2_lineage, trusted.v2_lineage.sha256)
    admission = _bound(
        evidence.source_admission, trusted.source_admission.sha256
    )
    _check_b1_b2(
        evidence.source_event,
        evidence.source_b2,
        trusted.source_event,
        trusted.source_b2,
        trusted.source_acquisition_id,
        trusted.source.sha256,
    )
    _check_producer_inputs(evidence, trusted)
    _check_projection_rights(evidence, trusted)
    _check_source_rights(evidence, trusted)
    _validate(profile, _schema(profile_schema_bytes, PROFILE_SCHEMA_SHA256))
    _validate(v1, _schema(v1_schema_bytes, V1_SCHEMA_SHA256))
    _validate(v2, _schema(v2_schema_bytes, V2_SCHEMA_SHA256))
    source, projection, producer = (
        profile["source"],
        profile["projection"],
        profile["producer"],
    )
    source_id = (
        f"m112:{trusted.source.dataset}@{trusted.source.revision}:"
        f"{trusted.source.path}"
    )
    _require(
        source
        == asdict(trusted.source)
        | {
            "acquisition_id": trusted.source_acquisition_id,
            "representation": "raw",
            "stratum": "B2",
            "artifact_id": source_id,
            "acquisition_event": asdict(trusted.source_event),
            "b2_reference": asdict(trusted.source_b2),
        }
        and projection
        == asdict(trusted.projection)
        | {
            "representation": "projection",
            "stratum": "B2",
        }
        and producer
        == {
            "commit": trusted.producer_commit,
            "acquisition_id": trusted.producer_acquisition_id,
            "event": asdict(trusted.producer_event),
            "b2_reference": asdict(trusted.producer_b2),
            "source_receipt": asdict(trusted.producer_receipt),
            "reconstructed_event": trusted.producer_event_reconstructed,
        }
        and trusted.source_acquisition_id != trusted.producer_acquisition_id
        and profile["source_v1"] == asdict(trusted.source_v1)
        and profile["v2_lineage"] == asdict(trusted.v2_lineage)
        and profile["raw_admission"] == asdict(trusted.source_admission)
        and profile["projection_rights"] == asdict(trusted.projection_rights),
        "profile identity or reference differs",
    )
    _require(
        profile["source_rights_context"]["authorization"]
        == asdict(trusted.source_authorization)
        and profile["source_rights_context"]["source_contract"]
        == asdict(trusted.source_contract),
        "raw source rights references differ",
    )
    _require(
        admission.get("acquisition_id") == trusted.source_acquisition_id
        and admission.get("content_id") == trusted.source.sha256
        and admission.get("state") == "accepted"
        and admission.get("reviewer_status") == "unreviewed"
        and any(
            item.get("check_id") == "official-mbs-xml"
            and item.get("passed") is True
            for item in admission.get("validation_results", [])
        ),
        "existing raw source admission differs",
    )
    artifacts, decisions = v1["artifacts"], v1["promotion_decisions"]
    _require(
        len(artifacts) == len(decisions) == 1, "v1 source denominator differs"
    )
    artifact, decision = artifacts[0], decisions[0]
    rights = artifact["rights_decision"]
    _require(
        artifact["artifact_id"] == source_id
        and artifact["layer"] == "bronze_b2"
        and artifact["sha256"] == trusted.source.sha256
        and artifact["lineage"]
        == {
            "input_artifact_ids": [
                f"b1-acquisition:{trusted.source_acquisition_id}"
            ],
            "input_sha256": [trusted.source.sha256],
        }
        and artifact["promotion_status"] == "approved_within_scope"
        and rights["status"] == "approved"
        and rights["scope"]
        == f"{trusted.source.dataset}@{trusted.source.revision}:{trusted.source.path} sha256:{trusted.source.sha256}"
        and rights["reason_codes"]
        == ["existing_exact_source_release_authorization"]
        and decision["subject_artifact_id"] == source_id
        and (decision["from_layer"], decision["to_layer"])
        == ("bronze_b1", "bronze_b2")
        and decision["input_sha256"] == artifact["lineage"]["input_sha256"]
        and decision["rights_decision"] == rights
        and decision["status"] == "approved"
        and set(decision["required_gate_ids"])
        == {
            "existing_raw_b2_acceptance",
            "existing_exact_source_rights",
            "source_b1_b2_lineage",
        }
        and set(decision["required_gate_ids"])
        <= set(decision["passed_gate_ids"]),
        "v1 raw-source promotion semantics differ",
    )
    records = [
        r
        for r in v2["records"]
        if r["output_dataset"] == trusted.projection.path
    ]
    expected_fields = {
        (f"/MBS_XML/Data/{native}", output, "au-mbs-bronze:" + transform)
        for native in MBS_AUGUST_2026_FIELDS
        for output, transform in (
            ("fields[].name", "xml-child-local-name"),
            ("fields[].value", "xml-child-text-or-null"),
        )
    }
    expected_fields.update(
        (
            f"/MBS_XML/Data/{native}",
            "source_record_id",
            "au-mbs-bronze:source-record-identity",
        )
        for native in ("ItemNum", "SubItemNum", "ItemStartDate")
    )
    expected_fields.update({
        (
            "/MBS_XML/Data[position()]",
            "source_record_id",
            "au-mbs-bronze:source-record-identity",
        ),
        (
            "/MBS_XML/Data[position()]",
            "source_ordinal",
            "au-mbs-bronze:source-record-ordinal",
        ),
    })
    _require(
        len(expected_fields) == SOURCE_FIELDS
        and {
            (r["source_field"], r["output_field"], r["transformation_id"])
            for r in records
        }
        == expected_fields
        and len(records) == SOURCE_FIELDS
        and len({r["record_id"] for r in records}) == SOURCE_FIELDS
        and all(
            r["source_dataset"] == trusted.source.path
            and r["input_sha256"] == trusted.source.sha256
            and r["output_sha256"] == trusted.projection.sha256
            and r["code_version"] == f"git:{trusted.producer_commit}"
            and r["rights_decision_id"] == trusted.projection_rights.sha256
            and r["record_id"]
            == _digest({k: v for k, v in r.items() if k != "record_id"})
            for r in records
        ),
        "v2 projection field-lineage differs",
    )


def verify_v3_registration_receipt(
    receipt_bytes: bytes,
    plan_bytes: bytes,
    metadata: dict[str, Any],
    evidence: ProjectionEvidence,
    receipt_schema_bytes: bytes,
    v3_schema_bytes: bytes,
    *,
    trusted: ProjectionRoleTrust,
) -> None:
    """Verify a durable metadata receipt and its reconstructed v3 plan.

    Both expected plan and receipt digests must come from a separately trusted
    inventory. Reconstructing registration metadata is not payload replay.
    """
    if type(metadata) is not dict:
        raise TypeError("replay metadata is not an object")
    try:
        metadata_bytes = _canonical(metadata)
    except (ValueError, TypeError, RecursionError) as error:
        raise ValueError("invalid replay metadata") from error
    _require(
        len(metadata_bytes) <= MAX_METADATA_BYTES,
        "replay metadata byte limit exceeded",
    )
    receipt = _bound(receipt_bytes, trusted.v3_receipt_sha256)
    plan = _bound(plan_bytes, trusted.v3_plan_sha256)
    prior = _bound(evidence.prior_replay, trusted.prior_replay.sha256)
    _bound(evidence.v2_lineage, trusted.v2_lineage.sha256)
    _check_producer_inputs(evidence, trusted)
    _check_projection_rights(evidence, trusted)
    _check_reconstruction(evidence, trusted)
    prior_matches = [
        row
        for row in prior["objects"]
        if row["path"] == trusted.projection.path
    ]
    _require(
        len(prior_matches) == 1
        and all(
            prior_matches[0][key] == value
            for key, value in asdict(trusted.projection).items()
        )
        and prior_matches[0]["plan"]["sha256"] == trusted.v3_plan_sha256
        and prior_matches[0]["registration_sha256"]
        == trusted.v3_registration_sha256
        and prior_matches[0]["source"]["acquisition_id"]
        == trusted.producer_acquisition_id
        and prior_matches[0]["source"]["event"]
        == asdict(trusted.producer_event)
        and prior_matches[0]["source"]["b2"] == asdict(trusted.producer_b2)
        and prior_matches[0]["source"]["reconstructed_now"]
        is trusted.producer_event_reconstructed
        and prior["registration_replay"]
        == "passed_twice_in_memory_from_retained_metadata"
        and prior["historical_projection_reproduction_performed_by_this_replay"]
        is False,
        "prior replay receipt differs",
    )
    _validate(receipt, _schema(receipt_schema_bytes, RECEIPT_SCHEMA_SHA256))
    _validate(plan, _schema(v3_schema_bytes, V3_SCHEMA_SHA256))
    _require(
        receipt["projection"] == asdict(trusted.projection)
        and receipt["producer_acquisition_id"]
        == trusted.producer_acquisition_id
        and receipt["source_sha256"] == trusted.source.sha256
        and receipt["source_event"] == asdict(trusted.producer_event)
        and receipt["source_b2"] == asdict(trusted.producer_b2)
        and receipt["source_receipt"] == asdict(trusted.producer_receipt)
        and receipt["projection_rights"] == asdict(trusted.projection_rights)
        and receipt["v2_lineage"] == asdict(trusted.v2_lineage)
        and receipt["prior_replay"] == asdict(trusted.prior_replay)
        and receipt["reconstructed_plan_sha256"] == trusted.v3_plan_sha256
        and receipt["registration_sha256"] == trusted.v3_registration_sha256
        and receipt["replay_schema_sha256"] == V3_SCHEMA_SHA256
        and receipt["reconstruction"]
        == {
            "recipe": "mbs-august-v3-metadata-registration-v1",
            "python": "3.15.1",
            "lineage_report": asdict(trusted.lineage_report),
            "plan_builder": asdict(trusted.plan_builder),
            "v3_builder": asdict(trusted.v3_builder),
            "lineage_builder": asdict(trusted.lineage_builder),
        }
        and receipt["metadata_sha256"] == _digest(metadata)
        and metadata["projection"] == asdict(trusted.projection)
        and metadata["source_sha256"] == trusted.source.sha256
        and metadata["acquisition_id"] == trusted.producer_acquisition_id
        and metadata["source_event"] == asdict(trusted.producer_event)
        and metadata["source_b2"] == asdict(trusted.producer_b2)
        and metadata["source_receipt"] == asdict(trusted.producer_receipt)
        and metadata["field_lineage_sha256"] == trusted.v2_lineage.sha256
        and metadata["producer_commit"] == trusted.producer_commit
        and metadata["rights_evidence"] == asdict(trusted.projection_rights),
        "v3 receipt identity or provenance differs",
    )
    snapshots, replay_plan = plan["snapshots"], plan["replay_plan"]
    _require(
        len(snapshots) == len(replay_plan["steps"]) == 1,
        "v3 plan denominator differs",
    )
    snapshot, step = snapshots[0], replay_plan["steps"][0]
    subject = trusted.projection
    identity = {
        "dataset": subject.dataset,
        "revision": subject.revision,
        "path": subject.path,
    }
    logical = _digest(identity)
    partition = _digest(["au-mbs", "schedule-release:2026-08-01", logical])
    snap_id = _digest([partition, subject.sha256, _digest(metadata)])
    registration = {
        "snapshot_id": snap_id,
        "partition_id": partition,
        "idempotency_key": _digest([partition, snap_id]),
        "projection": asdict(subject),
        "source_sha256": trusted.source.sha256,
        "metadata_sha256": _digest(metadata),
    }
    _require(
        snapshot["source_id"] == "au-mbs"
        and snapshot["source_version_id"] == "2026-08-01"
        and snapshot["archive_period"] == "schedule-release:2026-08-01"
        and snapshot["observation_status"] == "acquired"
        and snapshot["correction_sequence"] == 0
        and snapshot["supersedes_snapshot_id"] is None
        and snapshot["late_arriving"] is False
        and snapshot["replay_eligible"] is True
        and snapshot["rights_state"]
        == "maintainer_attested_exact_scope_not_independently_reviewed"
        and snapshot["source_url"]
        == f"https://huggingface.co/datasets/{subject.dataset}/resolve/{subject.revision}/{subject.path}"
        and snapshot["logical_asset_id"] == logical
        and snapshot["partition_id"] == partition
        and snapshot["partition_value"]
        == f"{subject.dataset}@{subject.revision}:{subject.path}"
        and snapshot["snapshot_id"] == snap_id
        and snapshot["payload_sha256"] == subject.sha256
        and snapshot["metadata_sha256"] == _digest(metadata)
        and snapshot["idempotency_key"] == registration["idempotency_key"]
        and step["snapshot_id"] == snap_id
        and step["partition_id"] == partition
        and step["expected_payload_sha256"] == subject.sha256
        and step["expected_byte_count"] == subject.byte_count
        and step["action"]
        == "rebuild_projection_snapshot_registration_from_retained_metadata"
        and step["source_payload_values"] == "not_read"
        and step["registration_semantics"] == "append_only_idempotent"
        and step["candidate_only"] is True
        and step["hosted_replay_status"] == "not_requested_local_metadata_only"
        and step["v4_admission_performed"] is False
        and step["m112_consumer_canary_performed"] is False
        and replay_plan["eligible_snapshot_count"] == 1
        and replay_plan["deterministic"] is True
        and replay_plan["plan_sha256"]
        == _digest({k: v for k, v in replay_plan.items() if k != "plan_sha256"})
        and _digest(registration) == trusted.v3_registration_sha256,
        "v3 metadata replay semantics differ",
    )


def verify_v4_projection_role_binding(
    contract_bytes: bytes,
    receipts: tuple[ReceiptPayload, ...],
    profile_bytes: bytes,
    replay_receipt_bytes: bytes,
    plan_bytes: bytes,
    metadata: dict[str, Any],
    evidence: ProjectionEvidence,
    schemas: ProjectionSchemas,
    *,
    trusted: ProjectionRoleTrust,
) -> ReceiptClosure:
    """Close and semantically bind role bytes, without granting admission.

    The caller independently authenticates the trust configuration and all
    rights and privacy claims. A successful byte closure does not establish
    output privacy, authorize a consumer, or admit a real object.
    """
    verify_v1_projection_profile(
        profile_bytes,
        evidence,
        schemas.v1_profile,
        schemas.v1,
        schemas.v2,
        trusted=trusted,
    )
    verify_v3_registration_receipt(
        replay_receipt_bytes,
        plan_bytes,
        metadata,
        evidence,
        schemas.v3_receipt,
        schemas.v3,
        trusted=trusted,
    )
    closure = verify_receipt_closure(
        contract_bytes, receipts, schema=schemas.v4
    )
    document = _document(contract_bytes)
    source, location = document["source"], document["location"]
    actual = {
        "dataset": location["dataset"],
        "revision": location["revision"],
        "path": location["path"],
        "sha256": location["sha256"],
        "byte_count": location["bytes"],
    }
    roles = {item.role: item.sha256 for item in closure.roles}
    expected_inputs = {
        trusted.profile_sha256,
        trusted.source_admission.sha256,
        trusted.source_event.sha256,
        trusted.source_b2.sha256,
        trusted.source_authorization.sha256,
        trusted.source_contract.sha256,
        trusted.producer_event.sha256,
        trusted.producer_b2.sha256,
        trusted.producer_receipt.sha256,
        trusted.projection_rights.sha256,
        trusted.prior_replay.sha256,
        trusted.lineage_report.sha256,
        trusted.plan_builder.sha256,
        trusted.v3_builder.sha256,
        trusted.lineage_builder.sha256,
    }
    input_hashes = {
        item.sha256
        for item in closure.roles
        if item.role.startswith("/lineage/inputs/")
    }
    _require(
        actual == asdict(trusted.projection)
        and source["source_id"] == "au-mbs"
        and source["acquisition_id"] == trusted.producer_acquisition_id
        and source["layer"] == "bronze"
        and source["bronze_stratum"] == "B2"
        and source["representation"] == "projection"
        and document["lineage"]["promotion_receipt"] is None
        and roles.get("/lineage/v1_conformance") == trusted.source_v1.sha256
        and roles.get("/lineage/v2_field_lineage") == trusted.v2_lineage.sha256
        and roles.get("/lineage/v3_replay") == trusted.v3_receipt_sha256
        and expected_inputs <= input_hashes,
        "v4 projection subject or role binding differs",
    )
    return closure
