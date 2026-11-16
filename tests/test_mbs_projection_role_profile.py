"""Offline exact-identity tests for MBS projection role profiles."""

from __future__ import annotations

import copy
import hashlib
import json
import socket
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import scripts.qualify_mbs_august_projection_field_lineage as lineage
import scripts.qualify_mbs_frozen_projection_roles as previous
import scripts.qualify_mbs_frozen_projection_v1_v3 as qualification
from test_federation_receipt_closure import (
    PAYLOAD,
    SCHEMA,
    URL,
)
from test_federation_receipt_closure import (
    fixture as federation_fixture,
)

from global_medicines_atlas.federation_receipt_closure import (
    ReceiptPayload,
)
from global_medicines_atlas.mbs_projection_role_profile import (
    MetadataReference,
    ProjectionEvidence,
    ProjectionRoleTrust,
    ProjectionSchemas,
    verify_v1_projection_profile,
    verify_v3_registration_receipt,
    verify_v4_projection_role_binding,
)

ROOT = qualification.ROOT


def _digest(value: object) -> str:
    raw = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(raw).hexdigest()


@pytest.fixture(scope="module")
def evidence() -> tuple[dict[str, bytes], list[dict[str, Any]]]:
    """Rebuild only metadata, with no network or payload file access."""
    original_open = Path.open
    original_read_bytes = Path.read_bytes
    blocked_suffixes = {".parquet", ".xml", ".zip", ".xlsx", ".csv"}

    def safe_open(path: Path, *args: Any, **kwargs: Any) -> Any:
        if path.suffix.lower() in blocked_suffixes:
            pytest.fail("a payload file must not be opened")
        return original_open(path, *args, **kwargs)

    def safe_read_bytes(path: Path) -> bytes:
        if path.suffix.lower() in blocked_suffixes:
            pytest.fail("payload bytes must not be read")
        return original_read_bytes(path)

    def no_network(*_args: object, **_kwargs: object) -> None:
        pytest.fail("metadata qualification must not use the network")

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(socket.socket, "connect", no_network)
        patch.setattr(Path, "open", safe_open)
        patch.setattr(Path, "read_bytes", safe_read_bytes)
        # CI checkouts are shallow. Local --check verifies historical Git blobs.
        patch.setattr(previous, "check_code", lambda *_args: None)
        return qualification.assemble()


def _profile_check(
    outputs: dict[str, bytes],
    packet: dict[str, Any],
    *,
    trust: ProjectionRoleTrust | None = None,
    profile_bytes: bytes | None = None,
    v1_bytes: bytes | None = None,
    v2_bytes: bytes | None = None,
    admission_bytes: bytes | None = None,
) -> None:
    role_evidence = replace(
        packet["evidence"],
        source_v1=v1_bytes or packet["evidence"].source_v1,
        v2_lineage=v2_bytes or packet["evidence"].v2_lineage,
        source_admission=admission_bytes or packet["evidence"].source_admission,
    )
    verify_v1_projection_profile(
        profile_bytes or outputs[packet["profile"]["path"]],
        role_evidence,
        (ROOT / qualification.PROFILE_SCHEMA).read_bytes(),
        (ROOT / previous.V1_SCHEMA).read_bytes(),
        (ROOT / lineage.SCHEMA).read_bytes(),
        trusted=trust or packet["trust"],
    )


def _replay_check(
    outputs: dict[str, bytes],
    packet: dict[str, Any],
    *,
    trust: ProjectionRoleTrust | None = None,
    receipt_bytes: bytes | None = None,
    plan_bytes: bytes | None = None,
    metadata: dict[str, Any] | None = None,
    role_evidence: ProjectionEvidence | None = None,
) -> None:
    verify_v3_registration_receipt(
        receipt_bytes or outputs[packet["v3_receipt"]["path"]],
        plan_bytes or packet["plan_bytes"],
        packet["metadata"] if metadata is None else metadata,
        role_evidence or packet["evidence"],
        (ROOT / qualification.RECEIPT_SCHEMA).read_bytes(),
        (ROOT / previous.V3_SCHEMA).read_bytes(),
        trusted=trust or packet["trust"],
    )


def test_four_profiles_and_receipts_reproduce_without_payloads(
    evidence: tuple[dict[str, bytes], list[dict[str, Any]]],
) -> None:
    outputs, packets = evidence
    assert len(packets) == 4
    assert all(
        (ROOT / path).read_bytes() == raw for path, raw in outputs.items()
    )
    assert len({p["projection"]["path"] for p in packets}) == 4
    source_v1 = json.loads(outputs[qualification.SOURCE_V1])
    assert previous.semantic_errors(source_v1) == []
    decision = source_v1["promotion_decisions"][0]
    assert (decision["from_layer"], decision["to_layer"]) == (
        "bronze_b1",
        "bronze_b2",
    )
    assert decision["status"] == "approved"
    for packet in packets:
        _profile_check(outputs, packet)
        _replay_check(outputs, packet)
        assert "SYNTHETIC_MARKER" not in repr(
            replace(packet["evidence"], producer_receipt=b"SYNTHETIC_MARKER")
        )
        assert (
            packet["source_acquisition_id"] != packet["producer_acquisition_id"]
        )
        assert (
            packet["privacy"]["output_privacy"]
            == "unknown_output_values_not_screened"
        )
    report = json.loads(outputs[qualification.REPORT])
    assert report["raw_source_reviewer_status"] == "unreviewed"
    assert (
        report["pbs_bronze"]["output_privacy"]
        == "unknown_output_values_not_screened"
    )
    assert not any(report["boundaries"].values())


def test_rejects_different_projection_or_untrusted_profile(
    evidence: tuple[dict[str, bytes], list[dict[str, Any]]],
) -> None:
    outputs, packets = evidence
    first, second = packets[:2]
    with pytest.raises(ValueError, match="metadata content digest differs"):
        _profile_check(
            outputs, first, profile_bytes=outputs[second["profile"]["path"]]
        )
    altered = replace(first["trust"].projection, sha256="0" * 64)
    with pytest.raises(
        ValueError, match="existing projection rights evidence differs"
    ):
        _profile_check(
            outputs, first, trust=replace(first["trust"], projection=altered)
        )
    chronology = replace(
        first["trust"],
        producer_event_reconstructed=not first[
            "trust"
        ].producer_event_reconstructed,
    )
    with pytest.raises(
        ValueError, match="profile identity or reference differs"
    ):
        _profile_check(outputs, first, trust=chronology)


def test_v1_rejects_mismatched_target_even_if_rehashed(
    evidence: tuple[dict[str, bytes], list[dict[str, Any]]],
) -> None:
    outputs, packets = evidence
    packet = packets[0]
    source = json.loads(outputs[qualification.SOURCE_V1])
    source["promotion_decisions"][0]["to_layer"] = "silver"
    raw = previous.serialized(source)
    profile = json.loads(outputs[packet["profile"]["path"]])
    profile["source_v1"]["sha256"] = previous.sha(raw)
    profile_bytes = previous.serialized(profile)
    trust = replace(
        packet["trust"],
        source_v1=MetadataReference(
            path=qualification.SOURCE_V1, sha256=previous.sha(raw)
        ),
        profile_sha256=previous.sha(profile_bytes),
    )
    with pytest.raises(
        ValueError, match="v1 raw-source promotion semantics differ"
    ):
        _profile_check(
            outputs,
            packet,
            trust=trust,
            profile_bytes=profile_bytes,
            v1_bytes=raw,
        )


def test_v2_rejects_missing_native_field_even_if_rehashed(
    evidence: tuple[dict[str, bytes], list[dict[str, Any]]],
) -> None:
    outputs, packets = evidence
    packet = packets[0]
    v2 = json.loads((ROOT / lineage.OUTPUT).read_bytes())
    record = next(
        r
        for r in v2["records"]
        if r["output_dataset"] == packet["projection"]["path"]
    )
    record["source_field"] = "/MBS_XML/Data/Unexpected"
    record["record_id"] = _digest({
        k: v for k, v in record.items() if k != "record_id"
    })
    v2_bytes = previous.serialized(v2)
    profile = json.loads(outputs[packet["profile"]["path"]])
    profile["v2_lineage"]["sha256"] = previous.sha(v2_bytes)
    profile_bytes = previous.serialized(profile)
    trust = replace(
        packet["trust"],
        v2_lineage=MetadataReference(
            path=lineage.OUTPUT, sha256=previous.sha(v2_bytes)
        ),
        profile_sha256=previous.sha(profile_bytes),
    )
    with pytest.raises(ValueError, match="v2 projection field-lineage differs"):
        _profile_check(
            outputs,
            packet,
            trust=trust,
            profile_bytes=profile_bytes,
            v2_bytes=v2_bytes,
        )


def test_v3_rejects_semantic_substitution_even_if_rehashed(
    evidence: tuple[dict[str, bytes], list[dict[str, Any]]],
) -> None:
    outputs, packets = evidence
    packet = packets[0]
    plan = json.loads(packet["plan_bytes"])
    plan["replay_plan"]["steps"][0]["action"] = "some_other_action"
    plan["replay_plan"]["plan_sha256"] = _digest({
        k: v for k, v in plan["replay_plan"].items() if k != "plan_sha256"
    })
    plan_bytes = previous.serialized(plan)
    receipt = json.loads(outputs[packet["v3_receipt"]["path"]])
    receipt["reconstructed_plan_sha256"] = previous.sha(plan_bytes)
    prior = json.loads(packet["evidence"].prior_replay)
    prior_row = next(
        row
        for row in prior["objects"]
        if row["path"] == packet["projection"]["path"]
    )
    prior_row["plan"]["sha256"] = previous.sha(plan_bytes)
    prior_bytes = previous.serialized(prior)
    receipt["prior_replay"]["sha256"] = previous.sha(prior_bytes)
    receipt_bytes = previous.serialized(receipt)
    trust = replace(
        packet["trust"],
        v3_plan_sha256=previous.sha(plan_bytes),
        v3_receipt_sha256=previous.sha(receipt_bytes),
        prior_replay=replace(
            packet["trust"].prior_replay, sha256=previous.sha(prior_bytes)
        ),
    )
    with pytest.raises(ValueError, match="v3 metadata replay semantics differ"):
        _replay_check(
            outputs,
            packet,
            trust=trust,
            receipt_bytes=receipt_bytes,
            plan_bytes=plan_bytes,
            role_evidence=replace(packet["evidence"], prior_replay=prior_bytes),
        )


def test_v3_rejects_different_source_acquisition(
    evidence: tuple[dict[str, bytes], list[dict[str, Any]]],
) -> None:
    outputs, packets = evidence
    packet = packets[0]
    receipt = json.loads(outputs[packet["v3_receipt"]["path"]])
    receipt["producer_acquisition_id"] = "0" * 64
    raw = previous.serialized(receipt)
    with pytest.raises(
        ValueError, match="v3 receipt identity or provenance differs"
    ):
        _replay_check(
            outputs,
            packet,
            trust=replace(packet["trust"], v3_receipt_sha256=previous.sha(raw)),
            receipt_bytes=raw,
        )


def test_profile_rejects_rehashed_producer_event_with_wrong_content(
    evidence: tuple[dict[str, bytes], list[dict[str, Any]]],
) -> None:
    outputs, packets = evidence
    packet = packets[0]
    event = json.loads(packet["evidence"].producer_event)
    event["content_id"] = "0" * 64
    event_bytes = previous.serialized(event)
    profile = json.loads(outputs[packet["profile"]["path"]])
    profile["producer"]["event"]["sha256"] = previous.sha(event_bytes)
    profile_bytes = previous.serialized(profile)
    trust = replace(
        packet["trust"],
        producer_event=replace(
            packet["trust"].producer_event, sha256=previous.sha(event_bytes)
        ),
        profile_sha256=previous.sha(profile_bytes),
    )
    changed_packet = dict(packet)
    changed_packet["evidence"] = replace(
        packet["evidence"], producer_event=event_bytes
    )
    with pytest.raises(ValueError, match="B1/B2 source metadata differs"):
        _profile_check(
            outputs, changed_packet, trust=trust, profile_bytes=profile_bytes
        )


def test_profile_rejects_expanded_projection_rights_even_if_rehashed(
    evidence: tuple[dict[str, bytes], list[dict[str, Any]]],
) -> None:
    outputs, packets = evidence
    packet = packets[0]
    rights = json.loads(packet["evidence"].projection_rights)
    rights["boundaries"]["v4_admission_or_promotion_authorized"] = True
    rights_bytes = previous.serialized(rights)
    profile = json.loads(outputs[packet["profile"]["path"]])
    profile["projection_rights"]["sha256"] = previous.sha(rights_bytes)
    profile_bytes = previous.serialized(profile)
    trust = replace(
        packet["trust"],
        projection_rights=replace(
            packet["trust"].projection_rights, sha256=previous.sha(rights_bytes)
        ),
        profile_sha256=previous.sha(profile_bytes),
    )
    changed_packet = dict(packet)
    changed_packet["evidence"] = replace(
        packet["evidence"], projection_rights=rights_bytes
    )
    with pytest.raises(
        ValueError, match="existing projection rights evidence differs"
    ):
        _profile_check(
            outputs, changed_packet, trust=trust, profile_bytes=profile_bytes
        )


def test_profile_rejects_changed_raw_source_rights_even_if_rehashed(
    evidence: tuple[dict[str, bytes], list[dict[str, Any]]],
) -> None:
    outputs, packets = evidence
    packet = packets[0]
    contract = json.loads(packet["evidence"].source_contract)
    contract["rights"]["subject_sha256"] = "0" * 64
    contract_bytes = previous.serialized(contract)
    profile = json.loads(outputs[packet["profile"]["path"]])
    profile["source_rights_context"]["source_contract"]["sha256"] = (
        previous.sha(contract_bytes)
    )
    profile_bytes = previous.serialized(profile)
    trust = replace(
        packet["trust"],
        source_contract=replace(
            packet["trust"].source_contract, sha256=previous.sha(contract_bytes)
        ),
        profile_sha256=previous.sha(profile_bytes),
    )
    changed_packet = dict(packet)
    changed_packet["evidence"] = replace(
        packet["evidence"], source_contract=contract_bytes
    )
    with pytest.raises(
        ValueError, match="existing raw source rights evidence differs"
    ):
        _profile_check(
            outputs, changed_packet, trust=trust, profile_bytes=profile_bytes
        )


def test_reconstruction_rejects_changed_builder_code(
    evidence: tuple[dict[str, bytes], list[dict[str, Any]]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outputs, packets = evidence
    receipt = json.loads(outputs[packets[0]["v3_receipt"]["path"]])
    original = Path.read_bytes

    def changed(path: Path) -> bytes:
        if path == ROOT / qualification.PLAN_BUILDER[0]:
            return b"synthetic changed builder"
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", changed)
    with pytest.raises(ValueError, match="v3 builder code differs"):
        qualification.reconstruct_plan(ROOT, receipt)


def test_metadata_receipts_can_be_byte_closed_in_synthetic_v4(
    evidence: tuple[dict[str, bytes], list[dict[str, Any]]],
) -> None:
    outputs, packets = evidence
    packet = packets[0]
    _profile_check(outputs, packet)
    _replay_check(outputs, packet)
    document = federation_fixture()
    document["source"].update(
        layer="bronze",
        bronze_stratum="B2",
        representation="projection",
        source_id="au-mbs",
        acquisition_id=packet["producer_acquisition_id"],
    )
    subject = packet["projection"]
    document["location"].update(
        dataset=subject["dataset"],
        revision=subject["revision"],
        path=subject["path"],
        sha256=subject["sha256"],
        bytes=subject["byte_count"],
    )
    document["verification"].update(
        dataset=subject["dataset"],
        revision=subject["revision"],
        path=subject["path"],
        sha256=subject["sha256"],
        bytes=subject["byte_count"],
    )
    document["rights"].update(
        dataset=subject["dataset"],
        path=subject["path"],
        subject_sha256=subject["sha256"],
    )
    role_evidence = packet["evidence"]
    role_bytes = {
        "profile": outputs[packet["profile"]["path"]],
        "v1": outputs[qualification.SOURCE_V1],
        "v2": (ROOT / lineage.OUTPUT).read_bytes(),
        "v3": outputs[packet["v3_receipt"]["path"]],
        "raw_admission": role_evidence.source_admission,
        "raw_event": role_evidence.source_event,
        "raw_b2": role_evidence.source_b2,
        "raw_authorization": role_evidence.source_authorization,
        "raw_contract": role_evidence.source_contract,
        "producer_event": role_evidence.producer_event,
        "producer_b2": role_evidence.producer_b2,
        "producer_receipt": role_evidence.producer_receipt,
        "rights": role_evidence.projection_rights,
        "prior_replay": role_evidence.prior_replay,
        "lineage_report": role_evidence.lineage_report,
        "plan_builder": role_evidence.plan_builder,
        "v3_builder": role_evidence.v3_builder,
        "lineage_builder": role_evidence.lineage_builder,
    }
    refs = {
        name: {
            "url": f"https://example.org/{name}.json",
            "sha256": previous.sha(raw),
        }
        for name, raw in role_bytes.items()
    }
    document["lineage"].update(
        inputs=[
            refs[name]
            for name in (
                "profile",
                "raw_admission",
                "raw_event",
                "raw_b2",
                "raw_authorization",
                "raw_contract",
                "producer_event",
                "producer_b2",
                "producer_receipt",
                "rights",
                "prior_replay",
                "lineage_report",
                "plan_builder",
                "v3_builder",
                "lineage_builder",
            )
        ],
        v1_conformance=refs["v1"],
        v2_field_lineage=refs["v2"],
        v3_replay=refs["v3"],
        promotion_receipt=None,
    )
    receipt_payloads = [ReceiptPayload(url=URL, payload=PAYLOAD)]
    receipt_payloads.extend(
        ReceiptPayload(url=refs[name]["url"], payload=raw)
        for name, raw in role_bytes.items()
    )
    schemas = ProjectionSchemas(
        v1_profile=(ROOT / qualification.PROFILE_SCHEMA).read_bytes(),
        v1=(ROOT / previous.V1_SCHEMA).read_bytes(),
        v2=(ROOT / lineage.SCHEMA).read_bytes(),
        v3_receipt=(ROOT / qualification.RECEIPT_SCHEMA).read_bytes(),
        v3=(ROOT / previous.V3_SCHEMA).read_bytes(),
        v4=SCHEMA,
    )
    closed = verify_v4_projection_role_binding(
        json.dumps(document).encode(),
        tuple(receipt_payloads),
        role_bytes["profile"],
        role_bytes["v3"],
        packet["plan_bytes"],
        packet["metadata"],
        role_evidence,
        schemas,
        trusted=packet["trust"],
    )
    assert closed.scope == "receipt_bytes_only"
    assert {
        "/lineage/inputs/0",
        "/lineage/v1_conformance",
        "/lineage/v2_field_lineage",
        "/lineage/v3_replay",
    } <= {item.role for item in closed.roles}
    missing_profile = copy.deepcopy(document)
    missing_profile["lineage"]["inputs"] = [
        item
        for item in missing_profile["lineage"]["inputs"]
        if item["url"] != refs["profile"]["url"]
    ]
    without_profile = tuple(
        item for item in receipt_payloads if item.url != refs["profile"]["url"]
    )
    with pytest.raises(
        ValueError, match="v4 projection subject or role binding differs"
    ):
        verify_v4_projection_role_binding(
            json.dumps(missing_profile).encode(),
            without_profile,
            role_bytes["profile"],
            role_bytes["v3"],
            packet["plan_bytes"],
            packet["metadata"],
            role_evidence,
            schemas,
            trusted=packet["trust"],
        )
    document["location"]["sha256"] = "0" * 64
    document["verification"]["sha256"] = "0" * 64
    document["rights"]["subject_sha256"] = "0" * 64
    with pytest.raises(
        ValueError, match="v4 projection subject or role binding differs"
    ):
        verify_v4_projection_role_binding(
            json.dumps(document).encode(),
            tuple(receipt_payloads),
            role_bytes["profile"],
            role_bytes["v3"],
            packet["plan_bytes"],
            packet["metadata"],
            role_evidence,
            schemas,
            trusted=packet["trust"],
        )


def test_rejects_duplicate_keys_and_unpinned_schema(
    evidence: tuple[dict[str, bytes], list[dict[str, Any]]],
) -> None:
    outputs, packets = evidence
    packet = packets[0]
    duplicate = b'{"schema_id":"a","schema_id":"b"}'
    trust = replace(packet["trust"], profile_sha256=previous.sha(duplicate))
    with pytest.raises(ValueError, match="invalid metadata JSON"):
        _profile_check(outputs, packet, trust=trust, profile_bytes=duplicate)
    with pytest.raises(ValueError, match="schema digest differs"):
        verify_v3_registration_receipt(
            outputs[packet["v3_receipt"]["path"]],
            packet["plan_bytes"],
            packet["metadata"],
            packet["evidence"],
            b"{}",
            (ROOT / previous.V3_SCHEMA).read_bytes(),
            trusted=packet["trust"],
        )
