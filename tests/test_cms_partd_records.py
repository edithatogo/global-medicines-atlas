"""Source-faithful CMS Part D record projection contracts."""

from __future__ import annotations

import json
import sys
import zipfile
from io import BytesIO
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from global_medicines_atlas import cms_partd_records as records
from global_medicines_atlas.cms_partd_records import (
    project_cms_partd_payload,
    projection_cli,
)

WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github/workflows/cms-partd-record-projection.yml"
)


def _zip(members: dict[str, bytes]) -> bytes:
    output = BytesIO()
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)
    return output.getvalue()


def test_nested_formulary_tables_are_separate_and_source_faithful(
    tmp_path: Path,
) -> None:
    payload = tmp_path / "SPUF.zip"
    payload.write_bytes(
        _zip({
            "basic_drugs.zip": _zip({
                "formulary.txt": b"PLAN_ID\tNDC\tTIER\r\n001\t00001\t01\r\n"
            }),
            "pricing.zip": _zip({
                "pricing.csv": b"PLAN_ID,NDC,PRICE\n001,00001,10.00\n"
            }),
            "documentation.txt": b"not a projected outer table",
        })
    )
    projections = project_cms_partd_payload(
        payload, family="formulary", identity="a" * 64, output=tmp_path / "out"
    )
    assert len(projections) == 2
    tables = {
        item.inner_member_path: pq.read_table(  # pyright: ignore[reportUnknownMemberType]
            item.parquet_path
        )
        for item in projections
    }
    formulary = tables["formulary.txt"]
    assert formulary.column_names == [
        "PLAN_ID",
        "NDC",
        "TIER",
        "gma_payload_identity",
        "gma_outer_member_path",
        "gma_inner_member_path",
        "gma_source_row_number",
    ]
    assert formulary["PLAN_ID"].to_pylist() == ["001"]
    assert formulary["NDC"].to_pylist() == ["00001"]
    assert formulary["gma_source_row_number"].to_pylist() == [1]
    assert tables["pricing.csv"]["PRICE"].to_pylist() == ["10.00"]


def test_deflate64_member_uses_bounded_7zip_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive_path = tmp_path / "archive.zip"
    archive_path.write_bytes(_zip({"member.zip": b"abc"}))
    archive = zipfile.ZipFile(archive_path)
    info = archive.getinfo("member.zip")
    monkeypatch.setattr(  # pyright: ignore[reportUnknownArgumentType]
        archive,
        "open",
        lambda _info: (_ for _ in ()).throw(NotImplementedError()),  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    )
    monkeypatch.setattr(  # pyright: ignore[reportUnknownArgumentType]
        records.shutil,
        "which",
        lambda _name: "/usr/bin/7z",  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    )

    class Process:
        stdout = BytesIO(b"abc")
        returncode = 0

        def communicate(self) -> tuple[bytes, bytes]:
            return b"", b""

        def kill(self) -> None:
            raise AssertionError("bounded fallback unexpectedly killed")

    monkeypatch.setattr(  # pyright: ignore[reportUnknownArgumentType]
        records.subprocess,
        "Popen",
        lambda *_args, **_kwargs: Process(),  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    )
    with records._open_member(  # pyright: ignore[reportPrivateUsage]
        archive, info, archive_path=archive_path
    ) as member:
        assert member.read() == b"abc"
    archive.close()


def test_spending_payload_preserves_leading_zeroes_and_empty_strings(
    tmp_path: Path,
) -> None:
    payload = tmp_path / "spending.csv"
    payload.write_bytes(b"Brnd_Name,Tot_Clms,Flag\nMedicine,0007,\n")
    (projection,) = project_cms_partd_payload(
        payload, family="spending", identity="b" * 64, output=tmp_path / "out"
    )
    table = pq.read_table(  # pyright: ignore[reportUnknownMemberType]
        projection.parquet_path
    )
    assert table["Tot_Clms"].to_pylist() == ["0007"]
    assert table["Flag"].to_pylist() == [""]


def test_spending_data_api_json_preserves_strings_and_nulls(
    tmp_path: Path,
) -> None:
    payload = tmp_path / "data"
    payload.write_text(
        '[{"Brnd_Name":"Medicine","Tot_Clms":"0007","Flag":null}]',
        encoding="utf-8",
    )
    (projection,) = project_cms_partd_payload(
        payload, family="spending", identity="e" * 64, output=tmp_path / "out"
    )
    table = pq.read_table(  # pyright: ignore[reportUnknownMemberType]
        projection.parquet_path
    )
    assert table["Tot_Clms"].to_pylist() == ["0007"]
    assert table["Flag"].to_pylist() == [None]


@pytest.mark.parametrize(
    "payload",
    [b"[]", b"{}", b"[1]", b'[{"A":"x","B":1}]'],
)
def test_spending_data_api_json_fails_closed_on_drift(
    tmp_path: Path, payload: bytes
) -> None:
    source = tmp_path / "data"
    source.write_bytes(payload)
    with pytest.raises(ValueError, match="CMS Part D spending JSON"):
        project_cms_partd_payload(
            source,
            family="spending",
            identity="f" * 64,
            output=tmp_path / "out",
        )


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b"A,A\n1,2\n", "headers"),
        (b"A,B\n1\n", "row width"),
        (b"A,B\n", "no source records"),
    ],
)
def test_projection_fails_closed_on_schema_drift(
    tmp_path: Path, payload: bytes, message: str
) -> None:
    source = tmp_path / "source.csv"
    source.write_bytes(payload)
    with pytest.raises(ValueError, match=message):
        project_cms_partd_payload(
            source,
            family="spending",
            identity="c" * 64,
            output=tmp_path / "out",
        )


def test_projection_cli_writes_receipt_without_uploading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.csv"
    source.write_bytes(b"A,B\n1,2\n")
    manifest = tmp_path / "manifest.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "project_cms_partd_records.py",
            "--payload",
            str(source),
            "--family",
            "spending",
            "--identity",
            "d" * 64,
            "--output",
            str(tmp_path / "out"),
            "--manifest",
            str(manifest),
        ],
    )
    projection_cli()
    receipt = json.loads(manifest.read_text(encoding="utf-8"))
    assert receipt["source_record_count"] == 1
    assert receipt["cross_plan_year_schema_equivalence_claimed"] is False


def test_projection_workflow_is_hosted_public_and_resumable() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "RAW_REVISION: abcff8ebd1f624c4bbb0a87d903b184388c98254" in workflow
    assert "max-parallel: 8" in workflow
    assert "resolve/${RAW_REVISION}" in workflow
    assert "token=False" in workflow
    assert "Remove runner source bytes" in workflow
    assert "runner_source_bytes_retained': False" in workflow
    assert "upload_folder" in workflow
