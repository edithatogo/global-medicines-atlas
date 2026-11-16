"""Reconciliation tests for MBS Bronze projection replay."""

from __future__ import annotations

import copy
import hashlib
import json
import socket
from dataclasses import replace
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pyarrow.parquet as pq
import pytest
import scripts.check_mbs_august_projection_consumers as consumer_preflight
import scripts.check_mbs_august_semantics_consumers as bounded_checks
import scripts.prepare_mbs_august_projection_admission as admission_prep
import scripts.qualify_mbs_august_projection_field_lineage as field_lineage
import scripts.qualify_mbs_august_projection_replay as projection_replay
import scripts.reconcile_mbs_august_projection_sources as source_reconstruction
from pydantic import AnyUrl
from scripts.reconcile_m112_mbs_bronze_projection_lineage import (
    rebuild_projection_bytes,
)

from global_medicines_atlas.bronze_raw_evidence import RawEvidenceManifest
from global_medicines_atlas.federation_consumer import ConsumerBinding
from global_medicines_atlas.receipts import (
    AcquisitionMethod,
    AcquisitionStatus,
    EvidenceClass,
    PayloadEvidence,
    RetrievalEvidence,
    RightsState,
    SourceIdentity,
    SourceReceipt,
    TransformationEvidence,
)

FIXTURE = Path(__file__).parent / "fixtures" / "adapters" / "au_mbs.xml"
FIXTURE_RECORD_COUNT = 2


def _receipt(payload: bytes) -> SourceReceipt:
    evidence = PayloadEvidence.from_bytes(payload)
    return SourceReceipt(
        receipt_id="fixture:m112-mbs-bronze-projection",
        source=SourceIdentity(
            catalog_id="au-mbs",
            source_id="au-mbs",
            jurisdiction="AUS",
            authority="Australian Government Department of Health",
            dataset_title="Synthetic MBS source fixture",
            catalog_version="fixture-v1",
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl("https://fixtures.invalid/au-mbs"),
            retrieved_at=datetime(2026, 8, 29, tzinfo=UTC),
            acquisition_method=AcquisitionMethod.LOCAL_FIXTURE,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=evidence,
        rights_state=RightsState.UNKNOWN,
        evidence_class=EvidenceClass.SYNTHETIC,
        transformation=TransformationEvidence(
            transformation_id="au-mbs-source-fixture",
            transformation_sha256="a" * 64,
            output_sha256=evidence.sha256,
            output_byte_count=evidence.byte_count,
        ),
    )


def test_projection_replay_is_deterministic_and_keeps_p7_selection() -> None:
    payload = FIXTURE.read_bytes()
    receipt = _receipt(payload)

    first = rebuild_projection_bytes(
        payload, receipt, expected_record_count=FIXTURE_RECORD_COUNT
    )
    second = rebuild_projection_bytes(
        payload, receipt, expected_record_count=FIXTURE_RECORD_COUNT
    )

    assert set(first) == {"source.parquet", "p7.parquet"}
    assert first == second
    assert (
        hashlib.sha256(first["source.parquet"]).hexdigest()
        == hashlib.sha256(second["source.parquet"]).hexdigest()
    )
    assert (
        pq.read_table(BytesIO(first["source.parquet"])).num_rows  # pyright: ignore[reportUnknownMemberType]
        == FIXTURE_RECORD_COUNT
    )
    assert (
        pq.read_table(BytesIO(first["p7.parquet"])).num_rows  # pyright: ignore[reportUnknownMemberType]
        == FIXTURE_RECORD_COUNT
    )
    p7_schema = pq.read_schema(BytesIO(first["p7.parquet"]))  # pyright: ignore[reportUnknownMemberType]
    assert p7_schema.metadata is not None
    assert p7_schema.metadata[b"selection"] == b"Group=P7"


def test_august_field_lineage_binds_all_eight_exact_outputs() -> None:
    vocabulary, report = field_lineage.build()
    assert len(vocabulary["records"]) == 680
    assert len(report["objects"]) == 8
    assert sum(row["frozen_member"] for row in report["objects"]) == 4
    assert all(row["field_lineage_records"] == 85 for row in report["objects"])
    assert len({row["record_id"] for row in vocabulary["records"]}) == 680
    assert (
        report["v2_lineage"]["sha256"]
        == hashlib.sha256(
            (field_lineage.ROOT / field_lineage.OUTPUT).read_bytes()
        ).hexdigest()
    )
    assert all(
        row["field_semantics_accepted"] is False for row in report["objects"]
    )
    assert all(
        row["v4_admission"] == "not_performed" for row in report["objects"]
    )
    assert (
        sum(
            row["reproduction"]
            == "footer_adjusted_reproduction_not_historical_writer"
            for row in report["objects"]
        )
        == 4
    )
    assert not any(report["boundaries"].values())


@pytest.fixture(scope="module")
def august_projection_evidence() -> dict[str, dict[str, object]]:
    return {
        name: field_lineage.bounded.read_bound_metadata(
            field_lineage.ROOT, path, digest
        )
        for name, (path, digest) in field_lineage.INPUTS.items()
    }


@pytest.mark.parametrize(
    "mutation", ["privacy", "rights", "digest", "replay", "profile", "receipt"]
)
def test_august_lineage_rejects_mismatched_evidence(
    august_projection_evidence: dict[str, dict[str, object]], mutation: str
) -> None:
    evidence = copy.deepcopy(august_projection_evidence)
    if mutation == "privacy":
        evidence["readiness"]["mbs_objects"][0]["privacy"] = "unknown"
    elif mutation == "rights":
        evidence["frozen_rights"]["authorized_objects"][0]["sha256"] = "0" * 64
    elif mutation == "digest":
        evidence["digest_receipt"]["objects"][0]["sha256"] = "0" * 64
    elif mutation == "replay":
        evidence["outside_replay"]["objects"][0][
            "exact_digest_after_footer_substitution"
        ] = False
    elif mutation == "profile":
        evidence["profile"]["field_presence_diagnostics"][0][
            "presence_state_mismatches"
        ] = 1
    else:
        evidence["receipt_f9f9"]["sensitivity"]["personal_data"] = "unknown"
    with pytest.raises(ValueError, match="differs"):
        field_lineage.reconcile(evidence)


def test_v2_output_and_report_reproduce_without_payload_reads() -> None:
    vocabulary, report = field_lineage.build()
    assert (
        json.loads((field_lineage.ROOT / field_lineage.OUTPUT).read_text())
        == vocabulary
    )
    assert (
        json.loads((field_lineage.ROOT / field_lineage.REPORT).read_text())
        == report
    )
    for row in report["objects"]:
        assert row["selection"] == (
            "Group=P7"
            if row["path"].endswith("/p7.parquet")
            else "all_source_records"
        )
        assert row["reproduction"] == (
            "exact_bytes_reproduced_in_memory_at_prior_revision"
            if row["frozen_member"]
            else "footer_adjusted_reproduction_not_historical_writer"
        )


def test_synthetic_projection_preserves_native_fields_and_filters_p7() -> None:
    payload = FIXTURE.read_bytes().replace(
        b"<Group>P7</Group>", b"<Group>G1</Group>", 1
    )
    outputs = rebuild_projection_bytes(
        payload, _receipt(payload), expected_record_count=2
    )
    all_rows = pq.read_table(BytesIO(outputs["source.parquet"])).to_pylist()  # pyright: ignore[reportUnknownMemberType]
    p7_rows = pq.read_table(BytesIO(outputs["p7.parquet"])).to_pylist()  # pyright: ignore[reportUnknownMemberType]
    assert len(all_rows) == 2
    assert len(p7_rows) == 1
    assert p7_rows[0]["source_ordinal"] == 1
    assert p7_rows[0]["source_record_id"] == "au-mbs:124::2025-07-01:1"
    assert {f["name"]: f["value"] for f in p7_rows[0]["fields"]}[
        "Group"
    ] == "P7"
    assert {f["name"]: f["value"] for f in p7_rows[0]["fields"]}[
        "SubItemNum"
    ] is None
    assert all_rows[1] == p7_rows[0]


def test_reconstructed_source_metadata_preserves_original_acquisition() -> None:
    outputs = source_reconstruction.build()
    report = json.loads(outputs[source_reconstruction.REPORT])
    assert len(report["records"]) == 2
    assert (
        report["boundaries"]["b2_reference_existed_at_original_retrieval"]
        == "not_established"
    )
    for row in report["records"]:
        event = outputs[row["reconstructed_event"]["path"]]
        b2 = RawEvidenceManifest.model_validate_json(
            outputs[row["later_b2_reference"]["path"]]
        )
        assert (
            hashlib.sha256(event).hexdigest()
            == row["reconstructed_event"]["sha256"]
        )
        assert b2.rows[0].acquisition_id == row["acquisition_id"]
        assert b2.rows[0].content_id == field_lineage.SOURCE_SHA
        assert field_lineage.FROZEN_REVISION in str(
            b2.rows[0].external_reference
        )
        assert len(row["projection_paths"]) == 2


def test_reconstructed_event_rejects_changed_source_identity() -> None:
    name = "99fa"
    receipt_path, _ = field_lineage.INPUTS[f"receipt_{name}"]
    receipt = SourceReceipt.model_validate_json(
        (field_lineage.ROOT / receipt_path).read_bytes()
    )
    with pytest.raises(ValueError, match="identity or classification"):
        source_reconstruction._event(receipt, "0" * 64)  # pyright: ignore[reportPrivateUsage]


def test_projection_metadata_replays_keep_each_output_identity() -> None:
    outputs = projection_replay.build()
    report = json.loads(outputs[projection_replay.REPORT])
    assert len(report["objects"]) == 8
    assert (
        len({
            (r["dataset"], r["revision"], r["path"]) for r in report["objects"]
        })
        == 8
    )
    assert (
        sum(
            r["independent_replica_required_before_admission"]
            for r in report["objects"]
        )
        == 2
    )
    assert sum(r["source"]["reconstructed_now"] for r in report["objects"]) == 4
    assert (
        report["historical_projection_reproduction_performed_by_this_replay"]
        is False
    )
    assert not any(report["boundaries"].values())
    _, fields = field_lineage.build()
    by_path = {row["path"]: row for row in fields["objects"]}
    sources = projection_replay._sources(projection_replay.ROOT)  # pyright: ignore[reportPrivateUsage]
    for row in report["objects"]:
        packet = projection_replay._plan(  # pyright: ignore[reportPrivateUsage]
            projection_replay.ROOT,
            by_path[row["path"]],
            sources[row["producer"]],
            fields["v2_lineage"]["sha256"],
        )
        plan = packet["plan"]
        assert plan["snapshots"][0]["payload_sha256"] == row["sha256"]
        assert (
            plan["replay_plan"]["steps"][0]["expected_byte_count"]
            == row["byte_count"]
        )
        assert (
            hashlib.sha256(
                (json.dumps(plan, indent=2, sort_keys=True) + "\n").encode()
            ).hexdigest()
            == row["plan"]["sha256"]
        )
        assert row["plan"]["generated_and_validated_in_memory"] is True


def test_projection_registration_rejects_changed_output_metadata() -> None:
    _, report = field_lineage.build()
    row = report["objects"][0]
    source = projection_replay._sources(projection_replay.ROOT)["6bc9"]  # pyright: ignore[reportPrivateUsage]
    packet = projection_replay._plan(  # pyright: ignore[reportPrivateUsage]
        projection_replay.ROOT, row, source, report["v2_lineage"]["sha256"]
    )
    packet["metadata"]["projection"]["byte_count"] += 1
    with pytest.raises(ValueError, match="registration identity"):
        projection_replay._register(packet["plan"], packet["metadata"])  # pyright: ignore[reportPrivateUsage]


def test_all_august_consumer_probes_refuse_unadmitted_reads() -> None:
    report = consumer_preflight.build()
    assert len(report["objects"]) == 8
    assert all(
        row["synthetic_v4_shape_and_consumer_identity"] == "passed"
        and row["reader_refuses_without_admission"] == "passed"
        and row["actual_v4_admission"] == "not_performed"
        and row["actual_payload_consumer_canary"] == "not_performed"
        for row in report["objects"]
    )
    assert (
        sum(
            row["independent_replica_required_before_admission"]
            for row in report["objects"]
        )
        == 2
    )
    assert not any(report["boundaries"].values())


def test_consumer_probe_rejects_an_identity_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bind = consumer_preflight.bind_consumer_contract

    def wrong_digest(
        raw: bytes, *, consumer_repository: str, consumer_commit: str
    ) -> ConsumerBinding:
        return replace(
            bind(
                raw,
                consumer_repository=consumer_repository,
                consumer_commit=consumer_commit,
            ),
            object_sha256="0" * 64,
        )

    monkeypatch.setattr(
        consumer_preflight, "bind_consumer_contract", wrong_digest
    )
    with pytest.raises(ValueError, match="consumer identity binding differs"):
        consumer_preflight.build()


def test_august_admission_preparation_binds_eight_without_admitting() -> None:
    report = admission_prep.build()
    assert report == json.loads(
        (admission_prep.ROOT / admission_prep.OUTPUT).read_bytes()
    )
    objects = report["objects"]
    assert len(objects) == 8
    assert sum(row["frozen_member"] for row in objects) == 4
    assert (
        sum(
            row["independent_replica_required_before_admission"]
            for row in objects
        )
        == 2
    )
    assert all(row["admission_ready"] is False for row in objects)
    assert all(row["actual_admission"] == "not_performed" for row in objects)
    assert all(
        row["privacy"]["status"] == "source_profile_assessed_non_sensitive"
        for row in objects
    )
    assert all(row["lineage"]["field_records"] == 85 for row in objects)
    assert all(
        row["lineage"]["replay_scope"] == "registration_metadata_only"
        for row in objects
    )
    assert all(
        row["consumer"]["actual_payload_canary"] == "not_performed"
        for row in objects
    )
    assert not any(report["boundaries"].values())


@pytest.mark.parametrize(
    "mutation",
    [
        "digest",
        "revision",
        "privacy",
        "membership",
        "replica",
        "field",
        "disposition",
        "disposition_revision",
        "source_chronology",
        "rights_revision",
    ],
)
def test_august_admission_preparation_rejects_inconsistent_evidence(
    mutation: str,
) -> None:
    evidence = copy.deepcopy(admission_prep.load())
    if mutation == "digest":
        evidence["digest"]["objects"][0]["sha256"] = "0" * 64
    elif mutation == "revision":
        evidence["replay"]["objects"][0]["revision"] = "0" * 40
    elif mutation == "privacy":
        evidence["privacy"]["objects"][0]["privacy"] = "unassessed"
    elif mutation == "membership":
        evidence["lineage"]["objects"][0]["frozen_member"] = False
    elif mutation == "replica":
        evidence["consumer"]["objects"][-1][
            "independent_replica_required_before_admission"
        ] = False
    elif mutation == "field":
        evidence["v2"]["records"][0]["output_sha256"] = "0" * 64
    elif mutation == "disposition_revision":
        evidence["disposition"]["evidence"]["revision"] = "0" * 40
    elif mutation == "source_chronology":
        evidence["replay"]["objects"][0]["source"]["reconstructed_now"] = True
    elif mutation == "rights_revision":
        row = next(
            row
            for row in evidence["lineage"]["objects"]
            if not row["frozen_member"]
        )
        rights = evidence["referenced"][row["rights_evidence"]["path"]]
        rights["authorized_objects"][0]["revision"] = "0" * 40
    else:
        evidence["disposition"]["objects"].pop()
    with pytest.raises(ValueError, match="differs"):
        admission_prep.reconcile(evidence)


def test_august_admission_preparation_does_not_use_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("admission preparation attempted network access")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    assert len(admission_prep.build()["objects"]) == 8


def test_august_bounded_semantics_and_consumer_checks() -> None:
    report = bounded_checks.build()
    assert report == json.loads(
        (bounded_checks.ROOT / bounded_checks.OUTPUT).read_bytes()
    )
    assert report["semantics"]["native_fields"] == 40
    assert len(report["semantics"]["checked_native_fields"]) == 40
    assert (
        report["semantics"]["aggregate_date_conversion_accounting"] == "matched"
    )
    assert report["semantics"]["changed_date_fields"] == 6
    assert report["semantics"]["field_semantics_accepted"] is False
    assert report["semantics"]["unresolved_conflicts"] == [
        "EMSNCap",
        "ItemChange",
    ]
    assert len(report["consumers"]["objects"]) == 8
    assert all(
        row["prior_silver_admissions_rejected"]
        and row["rekeyed_silver_identity_rejected"]
        for row in report["consumers"]["objects"]
    )
    assert not any(report["boundaries"].values())


@pytest.mark.parametrize(
    "mutation",
    [
        "state",
        "date",
        "field",
        "history",
        "admission",
        "semantics",
        "transformation",
        "nondate_conversion",
        "quality_total",
    ],
)
def test_august_bounded_semantics_rejects_inconsistent_metadata(
    mutation: str,
) -> None:
    evidence = copy.deepcopy(bounded_checks.load())
    if mutation == "state":
        evidence["dmy"]["field_presence_diagnostics"][0]["source_null"] += 1
    elif mutation == "date":
        evidence["dmy"]["qualification"]["date_format"] = "iso"
    elif mutation == "field":
        evidence["baseline"]["field_presence_diagnostics"][0][
            "native_field"
        ] = "invented"
    elif mutation == "history":
        evidence["history"]["unresolved_history"][
            "release_semantics_qualified"
        ] = True
    elif mutation == "admission":
        evidence["prior_admission"]["objects"].pop()
    elif mutation == "transformation":
        evidence["projection"]["v2"]["records"][0]["transformation_id"] = (
            "invented"
        )
    elif mutation == "nondate_conversion":
        row = next(
            row
            for row in evidence["dmy"]["field_presence_diagnostics"]
            if row["native_field"] == "AnaesChange"
        )
        row["conversion_status_counts"] = {"converted": row["rows"]}
    elif mutation == "quality_total":
        evidence["dmy"]["qualification"]["quality"][0]["count"] += 1
    else:
        evidence["projection"]["lineage"]["objects"][0][
            "field_semantics_accepted"
        ] = True
    with pytest.raises(ValueError, match="differ"):
        bounded_checks.reconcile(evidence)


def test_august_bounded_checks_do_not_use_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("bounded checks attempted network access")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    assert len(bounded_checks.build()["consumers"]["objects"]) == 8
