"""Bronze integrity inspection quarantines hostile bytes without mutating them."""

from __future__ import annotations

import gzip
import json
import tarfile
import zipfile
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from tests.test_source_receipts import source_receipt

from global_medicines_atlas import bronze_integrity
from global_medicines_atlas.archive_safety import (
    ArchivePolicy,
    ArchiveSafetyError,
    inspect_gzip,
    inspect_tar,
    inspect_zip,
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


def _gzip(payload: bytes) -> bytes:
    buffer = BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb") as handle:
        handle.write(payload)
    return buffer.getvalue()


@pytest.mark.unit
def test_gzip_and_document_branches_are_classified() -> None:
    gzip_payload = _gzip(b"hello")
    assert sniff_payload_kind(gzip_payload) == "gzip"
    gzip_ok = inspect_untrusted_payload(gzip_payload)
    assert gzip_ok.sniffed_kind == "gzip"
    assert not gzip_ok.blocking
    bomb = _gzip(b"0" * 20_000)
    assert inspect_untrusted_payload(bomb).blocking
    xml = inspect_untrusted_payload(b"<root>ok</root>")
    assert xml.sniffed_kind == "xml"
    assert not xml.blocking
    csv_ok = inspect_untrusted_payload(b"a,b\n1,2")
    assert csv_ok.sniffed_kind == "csv"
    assert not csv_ok.blocking
    safe_tar = inspect_untrusted_payload(_tar([("data/a.txt", b"a")]))
    assert safe_tar.sniffed_kind == "tar"
    assert not safe_tar.blocking
    empty_csv = bronze_integrity._Collector()
    bronze_integrity._check_csv(empty_csv, b"")
    assert empty_csv.reasons == ["malformed_payload"]


@pytest.mark.unit
def test_filename_poison_length_and_replay_edges() -> None:
    empty = inspect_untrusted_payload(PAYLOAD, declared_filename="")
    relative = inspect_untrusted_payload(PAYLOAD, declared_filename="..")
    reserved = inspect_untrusted_payload(PAYLOAD, declared_filename="CON.txt")
    assert "hostile_filename" in empty.reason_codes
    assert "hostile_filename" in relative.reason_codes
    assert "hostile_filename" in reserved.reason_codes
    nested: object = {"ok": True}
    for _ in range(10):
        nested = {"child": nested}
    deep = inspect_untrusted_payload(json.dumps(nested).encode())
    assert "schema_poisoning" in deep.reason_codes
    assert bronze_integrity._walk_poison_keys({1: "x"}) is None
    nested_poison = inspect_untrusted_payload(
        b'{"ok":{"content_id":"spoofed"}}'
    )
    listed = inspect_untrusted_payload(b'[{"acquisition_id":"x"}]')
    nested_list = inspect_untrusted_payload(b'{"items":[{"constructor":true}]}')
    assert "schema_poisoning" in nested_poison.reason_codes
    assert "schema_poisoning" in listed.reason_codes
    assert "schema_poisoning" in nested_list.reason_codes
    longer = inspect_untrusted_payload(PAYLOAD, declared_length=1)
    matched = inspect_untrusted_payload(PAYLOAD, declared_length=len(PAYLOAD))
    assert "content_length_mismatch" in longer.reason_codes
    assert not matched.blocking
    colliding = inspect_untrusted_payload(
        b'{"ok":false}',
        previous_content_id=sha256(PAYLOAD).hexdigest(),
        previous_acquisition_id="a" * 64,
        acquisition_id="a" * 64,
    )
    assert "replayed_acquisition" in colliding.reason_codes


@pytest.mark.unit
def test_inspect_helpers_are_reachable_from_unit_lane() -> None:
    archive = _zip([("data/a.txt", b"a")])
    assert inspect_zip(archive) == 1
    assert inspect_tar(_tar([("data/a.txt", b"a")])) == 1
    tiny = ArchivePolicy(max_archive_bytes=1)
    with pytest.raises(ArchiveSafetyError, match="archive byte limit"):
        inspect_zip(archive, tiny)
    with pytest.raises(ArchiveSafetyError, match="archive byte limit"):
        inspect_tar(_tar([("a.txt", b"a")]), tiny)
    with pytest.raises(ArchiveSafetyError, match="archive byte limit"):
        inspect_gzip(_gzip(b"hello"), tiny)
