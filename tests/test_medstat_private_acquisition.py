"""Contracts for the hosted-only Medstat private retention path."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest

import global_medicines_atlas.medstat_private_acquisition as acquisition
from global_medicines_atlas.medstat_private_acquisition import (
    CHECKSUM,
    MANIFEST,
    PRIVATE_ARCHIVE,
    PRIVATE_DATASET,
    MedstatQuery,
    exercise_medstat_private_acquisition,
    require_authorized_medstat_query,
    require_medstat_authorization,
)
from global_medicines_atlas.reuse_gate import evaluate_reuse_gate
from global_medicines_atlas.source_catalog import load_source_catalog

ROOT = Path(__file__).resolve().parents[1]
AUTHORIZATION = (
    ROOT
    / "quality/qualifications/nordic-utilisation-acquisition-authorization.json"
)


def workbook_payload() -> bytes:
    """Return a minimal structurally valid OOXML workbook fixture."""
    buffer = BytesIO()
    with ZipFile(buffer, "w") as workbook:
        workbook.writestr("[Content_Types].xml", "<Types />")
        workbook.writestr("_rels/.rels", "<Relationships />")
        workbook.writestr("xl/workbook.xml", "<workbook />")
        workbook.writestr("xl/worksheets/sheet1.xml", "<worksheet />")
    return buffer.getvalue()


def reuse_decision():
    return evaluate_reuse_gate(
        acquisition.SOURCE_ID,
        repository_root=ROOT,
        catalog=load_source_catalog(),
        github_index={},
        huggingface_index={},
    )


def test_query_binds_the_single_approved_aggregate_scope() -> None:
    query = MedstatQuery()
    assert query.source_parameters() == {
        "year": ["2025"],
        "region": ["0"],
        "gender": ["A"],
        "ageGroup": ["A"],
        "searchVariable": ["turnover"],
        "atcCode": ["X"],
        "sector": ["2"],
    }
    assert query.export_url().startswith(
        "https://medstat.dk/da/viewDataTables/medicineAndMedicalGroups/"
        "exportToExcel/"
    )
    with pytest.raises(PermissionError, match="approved"):
        require_authorized_medstat_query(MedstatQuery(years=(2024,)))


def test_authorization_rejects_pending_or_public_scope(tmp_path: Path) -> None:
    document = json.loads(AUTHORIZATION.read_text(encoding="utf-8"))
    denmark = document["sources"][0]
    denmark.update(
        decision_status="pending",
        decision_date=None,
        acquisition_authorized=False,
        internal_retention_authorized=False,
    )
    pending = tmp_path / "pending.json"
    pending.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(PermissionError, match="pending"):
        require_medstat_authorization(pending)
    denmark.update(
        decision_status="approved_internal",
        decision_date="2026-09-13",
        acquisition_authorized=True,
        internal_retention_authorized=True,
        public_release_authorized=True,
    )
    public = tmp_path / "public.json"
    public.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="publication must remain"):
        require_medstat_authorization(public)


def test_private_acquisition_lands_recovers_and_archives(
    tmp_path: Path,
) -> None:
    result = exercise_medstat_private_acquisition(
        payload=workbook_payload(),
        output_dir=tmp_path / "output",
        authorization_path=AUTHORIZATION,
        observed_at=datetime(2026, 9, 13, tzinfo=UTC),
        reuse_decision=reuse_decision(),
    )
    assert result.private_dataset == PRIVATE_DATASET
    assert result.public_release_authorized is False
    assert result.external_publication_authorized is False
    assert result.clean_room_recovered_payload_count == 1
    assert (tmp_path / "output" / PRIVATE_ARCHIVE).is_file()
    assert (tmp_path / "output" / MANIFEST).is_file()
    assert (tmp_path / "output" / CHECKSUM).is_file()


def test_private_acquisition_rejects_empty_payload_and_unsafe_output(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="empty"):
        exercise_medstat_private_acquisition(
            payload=b"",
            output_dir=tmp_path / "empty",
            authorization_path=AUTHORIZATION,
            reuse_decision=reuse_decision(),
        )
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "prior.txt").write_text("prior", encoding="utf-8")
    with pytest.raises(FileExistsError, match="empty"):
        exercise_medstat_private_acquisition(
            payload=b"payload",
            output_dir=occupied,
            authorization_path=AUTHORIZATION,
            reuse_decision=reuse_decision(),
        )


def test_private_acquisition_rejects_naive_time_and_admission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        exercise_medstat_private_acquisition(
            payload=workbook_payload(),
            output_dir=tmp_path / "naive",
            authorization_path=AUTHORIZATION,
            observed_at=datetime.fromisoformat("2026-09-13T00:00:00"),
            reuse_decision=reuse_decision(),
        )

    def rejected_landing(*_: object, **__: object) -> object:
        return object()

    monkeypatch.setattr(
        acquisition,
        "land_bronze_payload",
        rejected_landing,
    )
    with pytest.raises(TypeError, match="not admitted"):
        exercise_medstat_private_acquisition(
            payload=workbook_payload(),
            output_dir=tmp_path / "rejected",
            authorization_path=AUTHORIZATION,
            observed_at=datetime(2026, 9, 13, tzinfo=UTC),
            reuse_decision=reuse_decision(),
        )


def test_private_acquisition_rejects_non_workbook_and_missing_reuse_gate(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="OOXML"):
        exercise_medstat_private_acquisition(
            payload=b"synthetic Medstat Excel export",
            output_dir=tmp_path / "opaque",
            authorization_path=AUTHORIZATION,
            observed_at=datetime(2026, 9, 13, tzinfo=UTC),
            reuse_decision=reuse_decision(),
        )
    arbitrary_zip = BytesIO()
    with ZipFile(arbitrary_zip, "w") as archive:
        archive.writestr("response.html", "<html>not a workbook</html>")
    with pytest.raises(ValueError, match="required OOXML"):
        exercise_medstat_private_acquisition(
            payload=arbitrary_zip.getvalue(),
            output_dir=tmp_path / "arbitrary-zip",
            authorization_path=AUTHORIZATION,
            observed_at=datetime(2026, 9, 13, tzinfo=UTC),
            reuse_decision=reuse_decision(),
        )
    with pytest.raises(PermissionError, match="approved"):
        exercise_medstat_private_acquisition(
            payload=workbook_payload(),
            output_dir=tmp_path / "custom-query",
            authorization_path=AUTHORIZATION,
            observed_at=datetime(2026, 9, 13, tzinfo=UTC),
            query=MedstatQuery(years=(2024,)),
            reuse_decision=reuse_decision(),
        )
    with pytest.raises(ValueError, match="reuse gate required"):
        exercise_medstat_private_acquisition(
            payload=workbook_payload(),
            output_dir=tmp_path / "missing-reuse",
            authorization_path=AUTHORIZATION,
            observed_at=datetime(2026, 9, 13, tzinfo=UTC),
        )
