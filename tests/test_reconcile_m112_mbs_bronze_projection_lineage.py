"""Reconciliation tests for MBS Bronze projection replay."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pyarrow.parquet as pq
import pytest
import scripts.qualify_mbs_august_projection_field_lineage as field_lineage
from pydantic import AnyUrl
from scripts.reconcile_m112_mbs_bronze_projection_lineage import (
    rebuild_projection_bytes,
)

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
