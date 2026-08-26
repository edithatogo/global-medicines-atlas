"""Tests for official Open Medic token-page acquisition."""

from __future__ import annotations

import json
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import pytest
from scripts import qualify_open_medic_bronze as qualification_script

from global_medicines_atlas.iceberg_ready import plan_iceberg_partitions
from global_medicines_atlas.open_medic_acquisition import (
    inspect_open_medic_archive,
    open_medic_source_record_batch,
    resolve_open_medic_release,
)

PAGE_URL = (
    "https://open-data-assurance-maladie.ameli.fr/medicaments/"
    "download.php?Dir_Rep=Open_MEDIC_Base_Complete&Annee=2025"
)
QUALIFICATION = (
    Path(__file__).resolve().parents[1]
    / "quality/qualifications/open-medic-parser-qualification-20260821.json"
)
ZIP_TIMESTAMP = (2026, 1, 1, 0, 0, 0)


def _write_member(archive: ZipFile, name: str, payload: str | bytes) -> None:
    member = ZipInfo(name, date_time=ZIP_TIMESTAMP)
    member.compress_type = ZIP_DEFLATED
    archive.writestr(member, payload)


def _page(href: str) -> bytes:
    return f'<html><a href="{href}">release</a></html>'.encode()


def _archive(name: str = "OPEN_MEDIC_2025.CSV") -> bytes:
    stream = BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        _write_member(archive, name, "ATC;BOITES\nA01;1\n")
    return stream.getvalue()


def _source_archive(
    *,
    name: str = "OPEN_MEDIC_2025.CSV",
    header: str = "ATC1;ATC2;ATC3;ATC4;ATC5;CIP13;TOP_GEN;GEN_NUM;AGE;sexe;BEN_REG;PSP_SPE;BOITES;REM;BSE",
    row: str = "A;A01;A01A;A01AA;A01AA01;3400932387656;0;0;99;9;99;99;41;135,06;150,47",
) -> bytes:
    stream = BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        _write_member(
            archive,
            name,
            (header + "\r\n" + row + "\r\n").encode("iso-8859-1"),
        )
    return stream.getvalue()


def test_resolves_exact_official_token_link() -> None:
    release = resolve_open_medic_release(
        _page(
            "./download_file.php?token=abc123&file="
            "Open_MEDIC_Base_Complete/OPEN_MEDIC_2025.zip"
        ),
        page_url=PAGE_URL,
        year=2025,
    )
    assert release.filename == "OPEN_MEDIC_2025.zip"
    assert release.archive_url.host == "open-data-assurance-maladie.ameli.fr"


@pytest.mark.parametrize(
    "href",
    [
        "https://example.test/OPEN_MEDIC_2025.zip",
        "./download_file.php?token=abc123&file=other.zip",
        "./download_file.php?file=Open_MEDIC_Base_Complete/OPEN_MEDIC_2025.zip",
    ],
)
def test_resolver_rejects_substitution_or_incomplete_links(href: str) -> None:
    with pytest.raises(ValueError, match="one exact official"):
        resolve_open_medic_release(_page(href), page_url=PAGE_URL, year=2025)


def test_resolver_rejects_unreviewed_year_and_ignores_irrelevant_tags() -> None:
    with pytest.raises(ValueError, match="outside the reviewed series"):
        resolve_open_medic_release(b"", page_url=PAGE_URL, year=2013)
    with pytest.raises(ValueError, match="one exact official"):
        resolve_open_medic_release(
            b"<div href='ignored'></div><a>missing href</a>",
            page_url=PAGE_URL,
            year=2025,
        )


def test_archive_integrity_and_year_are_required() -> None:
    assert inspect_open_medic_archive(_archive(), year=2025) == (
        "OPEN_MEDIC_2025.CSV",
    )
    with pytest.raises(ValueError, match="release year"):
        inspect_open_medic_archive(_archive("OPEN_MEDIC.CSV"), year=2025)
    with pytest.raises(ValueError, match="not a ZIP"):
        inspect_open_medic_archive(b"not a zip", year=2025)


def test_download_limit_receipt_is_not_admitted_as_archive() -> None:
    with pytest.raises(ValueError, match="download limit refusal"):
        inspect_open_medic_archive(
            b"Telechargement refuse: Limite de telechargements atteinte",
            year=2025,
        )


def test_source_record_projection_preserves_native_strings_and_decimal_comma() -> (
    None
):
    batch = open_medic_source_record_batch(
        "fr-open-medic", _source_archive(), "zip"
    )
    assert batch is not None
    assert batch.parser_identity == "fr-open-medic-csv-iso8859-1-v1"
    assert batch.record_id_column == "source_row_number"
    assert batch.table.to_pylist() == [
        {
            "ATC1": "A",
            "ATC2": "A01",
            "ATC3": "A01A",
            "ATC4": "A01AA",
            "ATC5": "A01AA01",
            "CIP13": "3400932387656",
            "TOP_GEN": "0",
            "GEN_NUM": "0",
            "AGE": "99",
            "sexe": "9",
            "BEN_REG": "99",
            "PSP_SPE": "99",
            "BOITES": "41",
            "REM": "135,06",
            "BSE": "150,47",
            "source_release_year": 2025,
            "source_row_number": 1,
        }
    ]
    assert batch.partition_policy is not None
    assert (
        plan_iceberg_partitions(
            (
                ("source_release_year", "long"),
                ("gma_acquired_at", "timestamptz"),
            ),
            row_count=1_000_000,
            policy=batch.partition_policy,
        )[0].source_field
        == "gma_acquired_at"
    )


def test_source_record_projection_supports_reviewed_label_columns() -> None:
    header = (
        "ATC1;l_ATC1;ATC2;L_ATC2;ATC3;L_ATC3;ATC4;L_ATC4;"
        "ATC5;L_ATC5;CIP13;l_cip13;TOP_GEN;GEN_NUM;age;sexe;BEN_REG;"
        "PSP_SPE;BOITES;REM;BSE"
    )
    row = (
        "A;Système digestif;A01;STOMATOLOGIQUES;A01A;PREPARATIONS;"
        "A01AA;ANTICARIES;A01AA01;SODIUM FLUORURE;3400932387656;"
        "FLUOGEL;0;0;99;9;99;99;41;135,06;150,47"
    )
    batch = open_medic_source_record_batch(
        "fr-open-medic", _source_archive(header=header, row=row), "zip"
    )
    assert batch is not None
    assert batch.table.column("l_ATC1").to_pylist() == ["Système digestif"]
    assert batch.table.column("REM").to_pylist() == ["135,06"]


@pytest.mark.parametrize(
    ("source_id", "media_hint"),
    [("other", "zip"), ("fr-open-medic", "csv")],
)
def test_source_record_projection_declines_unrelated_payloads(
    source_id: str, media_hint: str
) -> None:
    assert (
        open_medic_source_record_batch(source_id, _source_archive(), media_hint)
        is None
    )


@pytest.mark.parametrize(
    ("header", "message"),
    [
        (
            "ATC1;ATC2;ATC3;ATC4;ATC5;CIP13;TOP_GEN;GEN_NUM;AGE;sexe;BEN_REG;PSP_SPE;BOITES;REM",
            "missing required",
        ),
        (
            "ATC1;ATC2;ATC3;ATC4;ATC5;CIP13;TOP_GEN;GEN_NUM;AGE;sexe;BEN_REG;PSP_SPE;BOITES;REM;BSE;NEW_FIELD",
            "unreviewed",
        ),
    ],
)
def test_source_record_projection_rejects_schema_drift(
    header: str, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        open_medic_source_record_batch(
            "fr-open-medic", _source_archive(header=header), "zip"
        )


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b"not a zip", "not a ZIP"),
        (
            _source_archive(name="open_medic_2025.csv"),
            "member name is not canonical",
        ),
        (
            _source_archive(name="OPEN_MEDIC_2013.CSV"),
            "outside reviewed scope",
        ),
        (_source_archive(row=""), "must contain source records"),
    ],
)
def test_source_record_projection_rejects_invalid_archive_scope(
    payload: bytes, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        open_medic_source_record_batch("fr-open-medic", payload, "zip")


def test_source_record_projection_rejects_multiple_csv_members() -> None:
    stream = BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        _write_member(archive, "OPEN_MEDIC_2024.CSV", "ATC1\n")
        _write_member(archive, "OPEN_MEDIC_2025.CSV", "ATC1\n")
    with pytest.raises(ValueError, match="one annual CSV"):
        open_medic_source_record_batch(
            "fr-open-medic", stream.getvalue(), "zip"
        )


def test_live_parser_qualification_is_bounded_and_content_bound() -> None:
    receipt = json.loads(QUALIFICATION.read_text(encoding="utf-8"))
    assert receipt["source_id"] == "fr-open-medic"
    assert receipt["immutable_revision"] == (
        "d19f7a66e35c58c557615bffa456856b485b7edc"
    )
    assert receipt["parser_identity"] == ("fr-open-medic-csv-iso8859-1-v1")
    assert [item["year"] for item in receipt["exercises"]] == [2014, 2025]
    assert [item["source_record_count"] for item in receipt["exercises"]] == [
        1833185,
        1873062,
    ]
    assert all(
        len(item["payload_sha256"]) == 64
        and item["payload_byte_count"] > 0
        and item["result"] == "passed"
        for item in receipt["exercises"]
    )
    assert receipt["source_bytes_committed"] is False
    assert receipt["external_publication_performed"] is False
    assert "all 12 annual releases remain pending" in receipt["limitations"][2]


def _public_revision(tmp_path: Path) -> tuple[Path, Path]:
    revision = tmp_path / "public-revision"
    source = revision / "data/fr-open-medic"
    files: list[dict[str, object]] = []
    for year in range(2014, 2026):
        payload = _source_archive(name=f"OPEN_MEDIC_{year}.CSV")
        payload_path = source / f"OPEN_MEDIC_{year}.zip"
        payload_path.parent.mkdir(parents=True, exist_ok=True)
        payload_path.write_bytes(payload)
        source_receipt = {
            "schema_id": "global-medicines-atlas.open-medic-acquisition",
            "schema_version": 1,
            "source_id": "fr-open-medic",
            "year": year,
            "resource_url": (
                "https://open-data-assurance-maladie.ameli.fr/medicaments/"
                "download.php?Dir_Rep=Open_MEDIC_Base_Complete&Annee="
                f"{year}"
            ),
            "sha256": sha256(payload).hexdigest(),
            "byte_count": len(payload),
            "rights": "Etalab-2.0",
            "admission_state": "accepted",
        }
        receipt_path = source / f"OPEN_MEDIC_{year}.receipt.json"
        receipt_path.write_text(
            json.dumps(source_receipt, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        files.extend(
            {
                "source_id": "fr-open-medic",
                "path": str(path.relative_to(revision)),
                "sha256": sha256(path.read_bytes()).hexdigest(),
                "byte_count": path.stat().st_size,
                "rights": "Etalab-2.0",
            }
            for path in (receipt_path, payload_path)
        )
    manifest = {
        "schema_id": "global-medicines-atlas.international-public-archive",
        "schema_version": 1,
        "archived_source_count": 1,
        "files": files,
        "pending_sources": {},
        "coverage_complete": False,
        "clinical_inference_permitted": False,
    }
    manifest_path = revision / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8"
    )
    publication = tmp_path / "publication.json"
    publication.write_text(
        json.dumps({
            "dataset": qualification_script.DATASET,
            "immutable_revision": qualification_script.REVISION,
            "manifest_sha256": sha256(manifest_path.read_bytes()).hexdigest(),
            "file_count": 24,
            "rights_families": ["Etalab-2.0"],
            "repository_private": False,
            "repository_gated": False,
        }),
        encoding="utf-8",
    )
    return revision, publication


@pytest.mark.timeout(120)
def test_all_release_runner_lands_recovers_and_verifies_public_revision(
    tmp_path: Path,
) -> None:
    revision, publication = _public_revision(tmp_path)
    result = qualification_script.qualify(
        revision,
        tmp_path / "qualification",
        publication_receipt_path=publication,
    )

    assert result["release_count"] == 12
    assert result["accepted_admission_count"] == 12
    assert result["source_record_count"] == 12
    assert result["source_record_projection_count"] == 12
    assert result["recovered_acquisition_count"] == 12
    assert result["recovered_source_record_projection_count"] == 12
    assert result["source_record_parquet_pairs_byte_identical"] == 12
    assert result["public_manifest_files_verified"] == 24
    assert result["existing_public_archive_verified"] is True
    assert result["source_live_qualified"] is True
    assert result["prompt_complete"] is False
    assert result["prompt_audit_qualified_source_ids"] == ["fr-open-medic"]
    assert result["reuse_disposition"] == "link"
    assert result["reuse_revision"] == qualification_script.REVISION
    assert result["source_bytes_committed"] is False
    assert result["external_publication_performed"] is False


def test_all_release_runner_rejects_public_manifest_digest_drift(
    tmp_path: Path,
) -> None:
    revision, publication = _public_revision(tmp_path)
    manifest_path = revision / "manifest.json"
    manifest_path.write_bytes(manifest_path.read_bytes() + b" ")

    with pytest.raises(ValueError, match="public manifest digest"):
        qualification_script.qualify(
            revision,
            tmp_path / "qualification",
            publication_receipt_path=publication,
        )
