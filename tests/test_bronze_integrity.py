"""Bronze integrity inspection quarantines hostile bytes without mutating them."""

from __future__ import annotations

import gzip
import tarfile
import zipfile
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from tests.test_source_receipts import source_receipt

from global_medicines_atlas.archive_safety import (
    ArchivePolicy,
    ArchiveSafetyError,
    inspect_gzip,
)
from global_medicines_atlas.bronze_admission import (
    BronzeAdmissionState,
    evaluate_bronze_admission,
)
from global_medicines_atlas.bronze_integrity import (
    inspect_untrusted_payload,
    sniff_payload_kind,
)
from global_medicines_atlas.bronze_landing import land_bronze_payload
from global_medicines_atlas.receipts import (
    PayloadEvidence,
    SourceReceipt,
    temporal_identity_from_source,
)
from global_medicines_atlas.reuse_gate import acquire_new_decision

PAYLOAD = b'{"ok":true}'


def _landable(payload: bytes = PAYLOAD) -> SourceReceipt:
    receipt = source_receipt()
    evidence = PayloadEvidence.from_bytes(payload)
    retrieval = receipt.retrieval
    return receipt.model_copy(
        update={
            "payload": evidence,
            "reuse": acquire_new_decision(receipt.source.source_id),
            "temporal": temporal_identity_from_source(
                retrieved_at=retrieval.retrieved_at,
                source_id=receipt.source.source_id,
                payload_sha256=evidence.sha256,
                original_uri=str(retrieval.uri),
            ),
        }
    )


def _zip(entries: list[tuple[str, bytes]]) -> bytes:
    stream = BytesIO()
    with zipfile.ZipFile(
        stream, "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        for name, data in entries:
            archive.writestr(name, data)
    return stream.getvalue()


def _tar(
    entries: list[tuple[str, bytes]], *, compressed: bool = False
) -> bytes:
    stream = BytesIO()
    mode = "w:gz" if compressed else "w"
    with tarfile.open(fileobj=stream, mode=mode) as archive:
        for name, data in entries:
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            archive.addfile(info, BytesIO(data))
    return stream.getvalue()


@pytest.mark.unit
def test_checksum_and_truncation_quarantine_without_rewriting_bytes() -> None:
    payload = b"incomplete-json"
    inspection = inspect_untrusted_payload(
        payload,
        expected_sha256="a" * 64,
        declared_length=64,
    )
    assert inspection.blocking
    assert "checksum_mismatch" in inspection.reason_codes
    assert "truncated_download" in inspection.reason_codes
    assert inspection.content_id == sha256(payload).hexdigest()


@pytest.mark.unit
def test_hostile_filename_and_media_mismatch_are_quarantined() -> None:
    archive = _zip([("safe.txt", b"ok")])
    inspection = inspect_untrusted_payload(
        archive,
        declared_media="json",
        declared_filename="../etc/passwd",
    )
    assert "hostile_filename" in inspection.reason_codes
    assert "mime_extension_mismatch" in inspection.reason_codes


@pytest.mark.unit
def test_malicious_zip_and_tar_are_quarantined() -> None:
    zip_inspection = inspect_untrusted_payload(_zip([("../x", b"x")]))
    tar_inspection = inspect_untrusted_payload(_tar([("/abs/x", b"x")]))
    assert zip_inspection.reason_codes == ("malicious_or_corrupt_archive",)
    assert tar_inspection.reason_codes == ("malicious_or_corrupt_archive",)
    assert sniff_payload_kind(b"PK\x03\x04corrupt") == "zip"
    corrupt = inspect_untrusted_payload(b"PK\x03\x04corrupt")
    assert corrupt.blocking


@pytest.mark.unit
def test_schema_poisoning_and_malformed_documents() -> None:
    poison = inspect_untrusted_payload(
        b'{"acquisition_id":"spoofed","ok":true}'
    )
    xml = inspect_untrusted_payload(
        b'<!DOCTYPE x [<!ENTITY y "z">]><x>&y;</x>',
        declared_media="xml",
    )
    csv_payload = inspect_untrusted_payload(
        b"a,b\x00\n1,2", declared_media="csv"
    )
    assert "schema_poisoning" in poison.reason_codes
    assert "malformed_payload" in xml.reason_codes
    assert "malformed_payload" in csv_payload.reason_codes


@pytest.mark.unit
def test_replay_and_source_mutation_are_distinct() -> None:
    first = sha256(PAYLOAD).hexdigest()
    mutated = inspect_untrusted_payload(
        b'{"ok":false}',
        previous_content_id=first,
        previous_acquisition_id="a" * 64,
        acquisition_id="b" * 64,
    )
    replay = inspect_untrusted_payload(
        PAYLOAD,
        previous_content_id=first,
        previous_acquisition_id="a" * 64,
        acquisition_id="a" * 64,
    )
    assert "unexpected_source_mutation" in mutated.reason_codes
    assert "replayed_acquisition" in replay.reason_codes


@pytest.mark.unit
def test_safe_zip_lands_and_can_be_accepted(tmp_path: Path) -> None:
    payload = _zip([("data/a.txt", b"a")])
    landing = land_bronze_payload(
        payload,
        _landable(payload),
        bronze_root=tmp_path / "bronze",
        media_hint="zip",
    )
    record = evaluate_bronze_admission(landing)
    assert landing.payload_path.read_bytes() == payload
    assert record.state is BronzeAdmissionState.ACCEPTED


@pytest.mark.unit
def test_poisoned_json_is_landed_then_quarantined(tmp_path: Path) -> None:
    payload = b'{"content_id":"not-a-digest"}'
    landing = land_bronze_payload(
        payload,
        _landable(payload),
        bronze_root=tmp_path / "bronze",
        media_hint="json",
    )
    record = evaluate_bronze_admission(landing)
    assert landing.payload_path.read_bytes() == payload
    assert record.state is BronzeAdmissionState.QUARANTINED
    assert "schema_poisoning" in record.reason_codes


@pytest.mark.property
@given(st.binary(min_size=0, max_size=256))
def test_inspection_never_mutates_or_crashes(payload: bytes) -> None:
    inspection = inspect_untrusted_payload(payload)
    assert inspection.content_id == PayloadEvidence.from_bytes(payload).sha256
    assert inspection.sniffed_kind
    assert inspection.findings


@pytest.mark.edge
def test_gzip_bomb_is_rejected_before_expansion() -> None:
    buffer = BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb") as handle:
        handle.write(b"0" * 20_000)
    payload = buffer.getvalue()
    with pytest.raises(ArchiveSafetyError, match="decompression ratio"):
        inspect_gzip(payload, ArchivePolicy(max_decompression_ratio=2))
