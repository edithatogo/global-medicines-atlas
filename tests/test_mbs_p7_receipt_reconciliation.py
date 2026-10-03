"""P7 receipt reconstruction stays metadata-only and fail closed."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from global_medicines_atlas.mbs_p7_receipt_reconciliation import (
    EXPECTED_RECEIPT_SHA256,
    dump_reconciliation,
    reconcile_p7_storage_receipt,
    write_reconciliation,
)

ROOT = Path(__file__).resolve().parents[1]


def _copy_qualification_inputs(root: Path) -> None:
    """Copy only the two small committed metadata qualification records."""

    for relative in (
        "quality/qualifications/mbs-workbook-storage-20260830.json",
        "quality/qualifications/australian-mbs-public-huggingface-20260829.json",
    ):
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / relative).read_bytes())


def _read_json(path: Path) -> dict[str, Any]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast("dict[str, Any]", value)


def test_reconstructs_exact_historical_archive_receipt_without_promotion() -> (
    None
):
    """The stored receipt digest is reproducible, but not source-origin proof."""

    result = reconcile_p7_storage_receipt(ROOT)

    assert result.reconstructed_receipt_sha256 == EXPECTED_RECEIPT_SHA256
    assert result.exact_receipt_match is True
    assert result.receipt_scope == "archive_storage_qualification_only"
    assert result.direct_bronze_qualification is False
    assert result.source_origin_acquisition_evidenced is False
    assert result.admission_lifecycle_evidenced is False
    assert result.source_date_semantics_qualified is False
    assert result.m112_federation_accepted is False
    assert result.payload_bytes_read_locally is False


def test_receipt_reconstruction_rejects_changed_digest(tmp_path: Path) -> None:
    """A changed hosted digest cannot be accepted as exact receipt evidence."""

    _copy_qualification_inputs(tmp_path)
    path = (
        tmp_path / "quality/qualifications/mbs-workbook-storage-20260830.json"
    )
    storage = _read_json(path)
    details = storage["storage_qualification"]
    assert isinstance(details, dict)
    details["source_receipt_sha256"] = "0" * 64
    path.write_text(json.dumps(storage), encoding="utf-8")

    with pytest.raises(ValueError, match="receipt evidence changed"):
        reconcile_p7_storage_receipt(tmp_path)


def test_receipt_reconstruction_rejects_missing_archive_restore(
    tmp_path: Path,
) -> None:
    """A receipt does not pass when its exact archive restore is unproven."""

    _copy_qualification_inputs(tmp_path)
    path = tmp_path / (
        "quality/qualifications/australian-mbs-public-huggingface-20260829.json"
    )
    archive = _read_json(path)
    archive["anonymous_clean_room_restore"] = False
    path.write_text(json.dumps(archive), encoding="utf-8")

    with pytest.raises(ValueError, match="archive identity or restore"):
        reconcile_p7_storage_receipt(tmp_path)


def test_report_projection_is_stable_and_written_as_metadata(
    tmp_path: Path,
) -> None:
    """The report projection contains no workbook values or bytes."""

    _copy_qualification_inputs(tmp_path)
    result = write_reconciliation(tmp_path)
    output = tmp_path / (
        "quality/qualifications/"
        "mbs-p7-storage-receipt-reconciliation-20261003.json"
    )
    text = output.read_text(encoding="utf-8")

    assert text == dump_reconciliation(result)
    assert "ItemNum" not in text
    assert '"payload_bytes_read_locally": false' in text
