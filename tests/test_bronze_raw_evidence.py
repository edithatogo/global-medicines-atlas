"""Executable contracts for the B2 raw-evidence boundary."""

# pyright: reportUnknownMemberType=false

from __future__ import annotations

import io
import json
import tarfile
import zipfile
from hashlib import sha256
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from jsonschema import Draft202012Validator
from tests.test_source_receipts import source_receipt

from global_medicines_atlas import us_source_records
from global_medicines_atlas.archive_safety import ArchiveSafetyError
from global_medicines_atlas.bronze_landing import (
    BronzeLanding,
    SourceRecordBatch,
    land_bronze_payload,
)
from global_medicines_atlas.bronze_raw_evidence import (
    RawEvidenceState,
    build_archive_member_manifest,
    build_document_manifest,
    build_raw_evidence_record,
    read_raw_evidence_manifest,
    write_raw_evidence_manifest,
)
from global_medicines_atlas.receipts import (
    PayloadEvidence,
    SourceReceipt,
    require_temporal,
)
from global_medicines_atlas.reuse_gate import acquire_new_decision


def _receipt(payload: bytes) -> SourceReceipt:
    receipt = source_receipt()
    evidence = PayloadEvidence.from_bytes(payload)
    return receipt.model_copy(
        update={
            "payload": evidence,
            "reuse": acquire_new_decision(receipt.source.source_id),
        }
    )


@pytest.mark.unit
def test_raw_evidence_record_is_content_addressed_and_explicitly_b2() -> None:
    payload = b'{"native":true}\x00\xff'
    receipt = _receipt(payload)
    record = build_raw_evidence_record(
        receipt,
        raw_locator="file:///tmp/bronze/payloads/by_content/x/payload.bin",
        state=RawEvidenceState.RETAINED,
    )

    assert record.stratum == "B2"
    assert record.state is RawEvidenceState.RETAINED
    assert record.content_id == sha256(payload).hexdigest()
    assert record.payload_sha256 == record.content_id
    assert record.byte_count == len(payload)
    assert record.payload_contents_in_metadata is False


@pytest.mark.unit
def test_raw_evidence_state_validation_is_fail_closed() -> None:
    receipt = _receipt(b"state")
    with pytest.raises(ValueError, match="locator"):
        build_raw_evidence_record(
            receipt,
            raw_locator=" ",
            state=RawEvidenceState.RETAINED,
        )
    with pytest.raises(ValueError, match="retained bytes"):
        build_raw_evidence_record(
            receipt,
            raw_locator="https://example.invalid/payload",
            state=RawEvidenceState.RETAINED,
            retain_bytes=False,
        )
    with pytest.raises(ValueError, match="retain bytes"):
        build_raw_evidence_record(
            receipt,
            raw_locator="https://example.invalid/payload",
            state=RawEvidenceState.EXTERNAL_REFERENCE_ONLY,
        )


@pytest.mark.unit
def test_raw_evidence_manifest_rejects_tampering_and_conflicting_rewrites(
    tmp_path: Path,
) -> None:
    record = build_raw_evidence_record(
        _receipt(b"manifest"),
        raw_locator="file:///tmp/manifest.bin",
        state=RawEvidenceState.RETAINED,
    )
    path = tmp_path / "manifest.json"
    write_raw_evidence_manifest(path, (record,))
    with pytest.raises(ValueError, match="cannot be rewritten"):
        write_raw_evidence_manifest(
            path,
            (
                record.model_copy(
                    update={"media_type": "application/octet-stream"}
                ),
            ),
        )
    tampered = json.loads(path.read_text())
    tampered["manifest_sha256"] = "0" * 64
    path.write_text(json.dumps(tampered))
    with pytest.raises(ValueError, match="digest"):
        read_raw_evidence_manifest(path)


@pytest.mark.unit
def test_b2_record_matches_committed_schema() -> None:
    schema = json.loads(
        Path("schemas/b2-raw-evidence-v1.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    record = build_raw_evidence_record(
        _receipt(b"schema"),
        raw_locator="file:///tmp/payload.bin",
        state=RawEvidenceState.RETAINED,
    )
    Draft202012Validator(schema).validate(record.model_dump(mode="json"))


@pytest.mark.unit
def test_external_reference_and_blocked_states_never_fabricate_payload() -> (
    None
):
    payload = b"restricted"
    receipt = _receipt(payload)
    external = build_raw_evidence_record(
        receipt,
        raw_locator="https://official.example/restricted.bin",
        state=RawEvidenceState.EXTERNAL_REFERENCE_ONLY,
        retain_bytes=False,
    )
    blocked = build_raw_evidence_record(
        receipt,
        raw_locator="blocked://rights-review/295",
        state=RawEvidenceState.BLOCKED,
        retain_bytes=False,
        blocked_reason="rights decision pending",
    )

    assert external.payload_sha256 is None
    assert external.byte_count is None
    assert blocked.payload_sha256 is None
    assert blocked.byte_count is None
    assert external.raw_object_locator is None
    assert blocked.raw_object_locator is None


@pytest.mark.unit
def test_archive_member_manifest_preserves_archive_as_raw_bytes() -> None:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("records.csv", b"id,name\n1,A\n")
        archive.writestr("opaque.bin", b"\x00\xff\x80")
    payload = output.getvalue()
    manifest = build_archive_member_manifest(payload, media_hint="zip")

    assert manifest.archive_sha256 == sha256(payload).hexdigest()
    assert [item.member_name for item in manifest.members] == [
        "opaque.bin",
        "records.csv",
    ]
    assert manifest.members[0].byte_count == 3
    assert manifest.members[0].text_decoding is None


@pytest.mark.unit
def test_archive_manifest_rejects_non_archive_and_tracks_tar_directories() -> (
    None
):
    with pytest.raises(ValueError, match="supported"):
        build_archive_member_manifest(b"plain bytes", media_hint="bin")
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        archive.addfile(tarfile.TarInfo("directory/"))
    manifest = build_archive_member_manifest(
        output.getvalue(), media_hint="tar"
    )
    assert manifest.members[0].is_directory is True
    assert manifest.members[0].byte_count == 0


@pytest.mark.unit
def test_archive_member_manifest_reuses_fail_closed_archive_limits() -> None:
    output = io.BytesIO()
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        archive.writestr("bomb.bin", b"0" * (1024 * 1024))

    with pytest.raises(ArchiveSafetyError, match="decompression ratio"):
        build_archive_member_manifest(output.getvalue(), media_hint="zip")


@pytest.mark.unit
def test_tar_member_manifest_and_document_manifest_are_nonsemantic() -> None:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        data = b"<root>\xff</root>"
        info = tarfile.TarInfo("document.xml")
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    payload = output.getvalue()

    archive_manifest = build_archive_member_manifest(payload, media_hint="tar")
    document_manifest = build_document_manifest(
        b"%PDF-1.7\n%\xff\xfe\n%%EOF\n", media_hint="pdf"
    )
    assert archive_manifest.members[0].member_name == "document.xml"
    assert document_manifest.extraction_state == "derived_not_raw"
    assert document_manifest.text_extraction_performed is False
    assert (
        document_manifest.payload_sha256
        == sha256(b"%PDF-1.7\n%\xff\xfe\n%%EOF\n").hexdigest()
    )


@pytest.mark.unit
def test_raw_evidence_manifest_regenerates_without_parquet_projection(
    tmp_path: Path,
) -> None:
    payload = b'{"records":[{"id":"A"}]}'
    receipt = _receipt(payload)
    landing = land_bronze_payload(
        payload,
        receipt,
        bronze_root=tmp_path / "bronze",
        media_hint="json",
    )
    assert isinstance(landing, BronzeLanding)
    manifest_path = tmp_path / "raw-evidence.json"
    write_raw_evidence_manifest(
        manifest_path,
        (
            build_raw_evidence_record(
                landing.receipt,
                raw_locator=landing.payload_path.as_uri(),
                state=RawEvidenceState.RETAINED,
            ),
        ),
    )
    parquet_digest = sha256(landing.parquet_path.read_bytes()).hexdigest()
    landing.parquet_path.unlink()
    loaded = read_raw_evidence_manifest(manifest_path)
    temporal = require_temporal(landing.receipt.temporal)
    assert loaded.rows[0].acquisition_id == temporal.acquisition_id
    assert loaded.rows[0].content_id == temporal.content_id
    assert (
        sha256(landing.payload_path.read_bytes()).hexdigest()
        == loaded.rows[0].content_id
    )
    assert not landing.parquet_path.exists()
    assert parquet_digest


@pytest.mark.unit
def test_b2_manifest_does_not_include_source_native_or_silver_columns(
    tmp_path: Path,
) -> None:
    payload = b"opaque\x00\xff"
    landing = land_bronze_payload(
        payload,
        _receipt(payload),
        bronze_root=tmp_path / "bronze",
        media_hint="bin",
    )
    assert isinstance(landing, BronzeLanding)
    table = pq.read_table(landing.parquet_path)
    assert "native_record" not in table.column_names
    assert "canonical_medicine" not in table.column_names
    assert "normalized_product" not in table.column_names


@pytest.mark.unit
def test_landing_exposes_b2_manifest_and_rejects_non_native_projection(
    tmp_path: Path,
) -> None:
    payload = b'{"records":[{"id":"A"}]}'
    landing = land_bronze_payload(
        payload,
        _receipt(payload),
        bronze_root=tmp_path / "bronze",
        media_hint="json",
    )
    assert isinstance(landing, BronzeLanding)
    assert landing.raw_evidence_manifest_path.is_file()
    assert (
        landing.raw_evidence_manifest.rows[0].state is RawEvidenceState.RETAINED
    )
    for batch in (
        SourceRecordBatch(
            table=pa.table({"id": ["A"]}),
            parser_identity="tests.invalid.v1",
            record_id_column="id",
            projection_kind="source_native",
            preserves_native_columns=False,
        ),
        SourceRecordBatch(
            table=pa.table({"id": ["A"], "canonical_medicine": ["x"]}),
            parser_identity="tests.invalid.v1",
            record_id_column="id",
        ),
    ):
        with pytest.raises(ValueError, match=r"Silver|harmonise"):
            land_bronze_payload(
                payload,
                _receipt(payload),
                bronze_root=tmp_path / "other",
                media_hint="json",
                source_records=batch,
            )


@pytest.mark.unit
def test_archive_record_decoder_rejects_opaque_or_replacement_text() -> None:
    with pytest.raises(ValueError, match="opaque"):
        us_source_records._decode_member(b"id\x00value")
    with pytest.raises(ValueError, match="replacement"):
        us_source_records._decode_member(b"id\n\xef\xbf\xbd")
