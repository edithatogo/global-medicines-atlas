"""Source-profile-aware Bronze admission contracts."""

from __future__ import annotations

import gzip
from io import BytesIO
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from tests.test_source_receipts import source_receipt

from global_medicines_atlas.bronze_admission import (
    BronzeAdmissionState,
    evaluate_bronze_payload,
)
from global_medicines_atlas.bronze_profiles import (
    BronzeAdmissionProfile,
    JsonContainer,
    ProfileMismatchAction,
)
from global_medicines_atlas.receipts import (
    PayloadEvidence,
    temporal_identity_from_source,
)
from global_medicines_atlas.reuse_gate import acquire_new_decision


def _profile(**kwargs: object) -> BronzeAdmissionProfile:
    payload: dict[str, Any] = {"profile_id": "test", **kwargs}
    return BronzeAdmissionProfile.model_validate(payload)


def _evaluate(
    payload: bytes,
    tmp_path: Path,
    profile: BronzeAdmissionProfile | None = None,
):
    suffix = (
        ".json"
        if profile is None or not profile.expected_media
        else "." + profile.expected_media[0]
    )
    payload_path = tmp_path / ("fixture" + suffix)
    payload_path.write_bytes(payload)
    return evaluate_bronze_payload(
        payload_path,
        _receipt(payload),
        profile=profile,
    )


def _receipt(payload: bytes):
    receipt = source_receipt()
    evidence = PayloadEvidence.from_bytes(payload)
    return receipt.model_copy(
        update={
            "payload": evidence,
            "reuse": acquire_new_decision(receipt.source.source_id),
            "temporal": temporal_identity_from_source(
                retrieved_at=receipt.retrieval.retrieved_at,
                source_id=receipt.source.source_id,
                payload_sha256=evidence.sha256,
            ),
        }
    )


def test_generic_json_arrays_are_not_quarantined(tmp_path: Path) -> None:
    record = _evaluate(b'[{"id": 1}]', tmp_path)
    assert record.state is BronzeAdmissionState.ACCEPTED
    assert "profile_mismatch" not in record.reason_codes


def test_profile_can_require_array_and_quarantines_object(
    tmp_path: Path,
) -> None:
    profile = _profile(json_containers=(JsonContainer.ARRAY,))
    record = _evaluate(b'{"id": 1}', tmp_path, profile)
    assert record.state is BronzeAdmissionState.QUARANTINED
    assert "profile_mismatch" in record.reason_codes


def test_profile_accepts_json_lines_and_csv_contract(tmp_path: Path) -> None:
    jsonl = _evaluate(
        b'{"id": 1}\n{"id": 2}\n',
        tmp_path,
        _profile(json_containers=(JsonContainer.JSON_LINES,)),
    )
    assert jsonl.state is BronzeAdmissionState.ACCEPTED
    csv = _evaluate(
        b"code;name\nA;Aspirin\n",
        tmp_path,
        _profile(
            expected_media=("csv",),
            csv_delimiter=";",
            csv_required_headers=("code", "name"),
        ),
    )
    assert csv.state is BronzeAdmissionState.ACCEPTED


def test_profile_mismatch_can_warn_without_quarantine(tmp_path: Path) -> None:
    profile = _profile(
        json_containers=(JsonContainer.ARRAY,),
        mismatch_action=ProfileMismatchAction.WARN,
    )
    record = _evaluate(b'{"id": 1}', tmp_path, profile)
    assert record.state is BronzeAdmissionState.ACCEPTED
    assert "profile_warning" in record.reason_codes


def test_profile_rejects_xml_root_and_archive_member_shape(
    tmp_path: Path,
) -> None:
    profile = _profile(expected_media=("xml",), xml_root="medicines")
    record = _evaluate(b"<other />", tmp_path, profile)
    assert record.state is BronzeAdmissionState.QUARANTINED
    assert "profile_mismatch" in record.reason_codes


def test_archive_profile_limits_members_without_discarding_archive(
    tmp_path: Path,
) -> None:
    stream = BytesIO()
    with ZipFile(stream, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("medicines.json", b"[]")
        archive.writestr("notes.txt", b"notes")
    profile = _profile(
        expected_media=("zip",),
        archive_type="zip",
        archive_member_patterns=("*.json",),
        max_member_count=2,
    )
    record = _evaluate(stream.getvalue(), tmp_path, profile)
    assert record.state is BronzeAdmissionState.QUARANTINED
    assert "profile_mismatch" in record.reason_codes
    assert (tmp_path / "fixture.zip").read_bytes() == stream.getvalue()


def test_archive_profile_enforces_member_nesting(tmp_path: Path) -> None:
    stream = BytesIO()
    with ZipFile(stream, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("a/b/c/medicines.json", b"[]")
    record = _evaluate(
        stream.getvalue(),
        tmp_path,
        _profile(
            expected_media=("zip",),
            archive_type="zip",
            max_nesting=2,
        ),
    )
    assert record.state is BronzeAdmissionState.QUARANTINED
    assert "profile_mismatch" in record.reason_codes


def test_gzip_profile_enforces_expansion_ratio(tmp_path: Path) -> None:
    stream = BytesIO()
    with gzip.GzipFile(fileobj=stream, mode="wb") as archive:
        archive.write(b"0" * 20_000)
    record = _evaluate(
        stream.getvalue(),
        tmp_path,
        _profile(
            expected_media=("gzip",),
            archive_type="gzip",
            max_expansion_ratio=2,
        ),
    )
    assert record.state is BronzeAdmissionState.QUARANTINED
    assert "profile_mismatch" in record.reason_codes


def test_malformed_and_opaque_payloads_remain_quarantined_or_accepted_safely(
    tmp_path: Path,
) -> None:
    malformed = _evaluate(b"{not-json}", tmp_path)
    assert malformed.state is BronzeAdmissionState.QUARANTINED
    opaque = _evaluate(
        b"\x00\xff\x10", tmp_path, _profile(document_or_opaque=True)
    )
    assert opaque.state is BronzeAdmissionState.ACCEPTED


def test_profile_schema_is_versioned_and_bounded() -> None:
    assert BronzeAdmissionProfile(profile_id="x").schema_version == 1
    with pytest.raises(ValueError, match="greater than or equal to 1"):
        BronzeAdmissionProfile(profile_id="x", max_size_bytes=0)
