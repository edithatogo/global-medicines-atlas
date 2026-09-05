"""Governed PBS v3 archive and source-record contracts."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import cast
from zipfile import ZIP_DEFLATED, ZipFile

import pyarrow.parquet as pq
import pytest
from scripts import inspect_pbs_v3 as pbs_inspector
from scripts import qualify_pbs_v3_archive as pbs_qualifier
from scripts.qualify_pbs_v3_archive import qualify

from global_medicines_atlas.adapters.au_pbs import (
    PBS_V3_NAMESPACE,
    PBS_V3_SOURCE_SCHEMA,
    PBS_XML_POLICY,
    inspect_pbs_v3_tags,
    parse_pbs_v3_archive,
    pbs_v3_source_parquet,
)
from global_medicines_atlas.archive_safety import ArchiveSafetyError

RETRIEVED_AT = datetime(2026, 8, 30, 3, 0, tzinfo=UTC)
HTTP_METADATA: dict[str, object] = {
    "http_code": 200,
    "url_effective": "https://www.pbs.gov.au/example.zip",
    "content_type": "application/zip",
}


@pytest.mark.parametrize("option", ["--max-items", "--max_items"])
def test_pbs_cli_preserves_bounded_donor_item_views(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    option: str,
) -> None:
    path = tmp_path / "source.zip"
    xml = _xml().replace(
        b"</pbs:schedule>",
        b'<pbs:pharmaceutical-item xml:id="5678B"><pbs:block-container>'
        b"<dbk:para>Second item</dbk:para></pbs:block-container>"
        b"</pbs:pharmaceutical-item></pbs:schedule>",
    )
    path.write_bytes(_zip([("sch-test.xml", xml)]))
    monkeypatch.setattr(
        "sys.argv",
        ["inspect_pbs_v3", str(path), option, "1", "--first-item-xml"],
    )

    assert pbs_inspector.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["record_count"] == 2
    assert len(result["items"]) == 1
    assert result["items"][0]["item_code"] == "1234A"
    assert result["items"][0]["amt_references"] == [
        ["123456", "http://snomed.info/id/123456"]
    ]
    assert result["items"][0]["atc_codes"] == ["A01AA01"]
    assert "pharmaceutical-item" in result["first_item_xml_projection"]
    assert "5678B" not in result["first_item_xml_projection"]


@pytest.mark.parametrize("limit", ["0", "-1", "1001"])
def test_pbs_cli_rejects_unbounded_item_sample(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    limit: str,
) -> None:
    monkeypatch.setattr(
        "sys.argv", ["inspect_pbs_v3", "absent.zip", "--max-items", limit]
    )
    with pytest.raises(SystemExit) as error:
        pbs_inspector.main()
    assert error.value.code == 2
    assert "between 1 and 1000" in capsys.readouterr().err


def test_pbs_cli_default_omits_xml_projection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "source.zip"
    path.write_bytes(_zip([("sch-test.xml", _xml())]))
    monkeypatch.setattr("sys.argv", ["inspect_pbs_v3", str(path)])
    assert pbs_inspector.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["first_item_xml_projection"] is None
    assert len(result["items"]) == 1


def test_pbs_cli_rejects_oversize_xml_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "source.zip"
    path.write_bytes(_zip([("sch-test.xml", _xml())]))
    monkeypatch.setattr(pbs_inspector, "MAX_XML_OUTPUT_BYTES", 1)
    monkeypatch.setattr(
        "sys.argv", ["inspect_pbs_v3", str(path), "--first-item-xml"]
    )
    with pytest.raises(SystemExit) as error:
        pbs_inspector.main()
    assert error.value.code == 2
    assert "exceeds 1 MiB" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("constant", "message"),
    [
        ("MAX_ARCHIVE_BYTES", "archive byte limit"),
        ("MAX_OUTPUT_BYTES", "JSON exceeds 4 MiB"),
    ],
)
def test_pbs_cli_bounds_input_and_complete_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    constant: str,
    message: str,
) -> None:
    path = tmp_path / "source.zip"
    path.write_bytes(_zip([("sch-test.xml", _xml())]))
    monkeypatch.setattr(pbs_inspector, constant, 1)
    monkeypatch.setattr("sys.argv", ["inspect_pbs_v3", str(path)])
    with pytest.raises(SystemExit) as error:
        pbs_inspector.main()
    assert error.value.code == 2
    captured = capsys.readouterr()
    assert message in captured.err
    assert not captured.out


@pytest.mark.parametrize("limit", ["0", "4097"])
def test_pbs_cli_bounds_tag_sample(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    limit: str,
) -> None:
    monkeypatch.setattr(
        "sys.argv", ["inspect_pbs_v3", "absent.zip", "--max-tags", limit]
    )
    with pytest.raises(SystemExit) as error:
        pbs_inspector.main()
    assert error.value.code == 2
    assert "between 1 and 4096" in capsys.readouterr().err


def _xml(*, namespace: str = PBS_V3_NAMESPACE) -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<pbs:schedule xmlns:pbs="{namespace}"
 xmlns:dbk="http://docbook.org/ns/docbook"
 xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
 effective-date="2026-07-01">
 <pbs:pharmaceutical-item xml:id="1234A">
  <pbs:block-container><dbk:para>Exampleline 10 mg tablet</dbk:para></pbs:block-container>
  <pbs:drug-references-list><pbs:mp-reference><pbs:code
   rdf:resource="http://snomed.info/id/123456">123456</pbs:code></pbs:mp-reference></pbs:drug-references-list>
  <pbs:classification><pbs:code type="ATC">A01AA01</pbs:code></pbs:classification>
  <pbs:restrictions><pbs:restriction effective-date="2026-07-15">Authority required</pbs:restriction></pbs:restrictions>
 </pbs:pharmaceutical-item>
</pbs:schedule>""".encode()


def _production_xml() -> bytes:
    schedule = _xml().decode().split("?>", 1)[1]
    item = schedule.split(" <pbs:pharmaceutical-item", 1)[1].split(
        "</pbs:pharmaceutical-item>", 1
    )[0]
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<pbs:root xmlns:pbs="{PBS_V3_NAMESPACE}"
 xmlns:dbk="http://docbook.org/ns/docbook"
 xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
 xmlns:dct="http://purl.org/dc/terms/" version="3.1">
 <pbs:info><dct:valid>2026-04-01</dct:valid></pbs:info>
 <pbs:schedule />
 <pbs:pharmaceutical-items-list>
  <pbs:pharmaceutical-item{item}</pbs:pharmaceutical-item>
 </pbs:pharmaceutical-items-list>
</pbs:root>""".encode()


def _zip(entries: list[tuple[str, bytes]]) -> bytes:
    stream = BytesIO()
    with ZipFile(stream, "w", compression=ZIP_DEFLATED) as archive:
        for name, payload in entries:
            archive.writestr(name, payload)
    return stream.getvalue()


def test_parse_pbs_v3_archive_preserves_identity_and_namespace() -> None:
    archive = _zip([("release/sch-2026-07.xml", _xml())])

    result = parse_pbs_v3_archive(archive)

    assert result.archive_sha256
    assert result.member.path == "release/sch-2026-07.xml"
    assert result.member.sha256
    assert result.namespace_uri == PBS_V3_NAMESPACE
    assert result.effective_date == "2026-07-01"
    assert result.records[0].item_code == "1234A"
    assert result.records[0].product_name == "Exampleline 10 mg tablet"
    assert result.records[0].amt_references == (
        ("123456", "http://snomed.info/id/123456"),
    )
    assert result.records[0].atc_codes == ("A01AA01",)
    assert result.records[0].restrictions == ("Authority required",)
    assert result.records[0].restriction_effective_dates == ("2026-07-15",)


def test_parse_pbs_v3_archive_accepts_official_root_shape() -> None:
    result = parse_pbs_v3_archive(
        _zip([("release/sch-2026-04-01-r1.xml", _production_xml())])
    )

    assert result.effective_date == "2026-04-01"
    assert result.records[0].item_code == "1234A"


def test_hosted_qualification_binds_raw_member_and_projection(
    tmp_path: Path,
) -> None:
    archive_path = tmp_path / "source.zip"
    archive_path.write_bytes(
        _zip([("release/sch-2026-04-01-r1.xml", _production_xml())])
    )

    manifest = qualify(
        archive_path,
        tmp_path / "stage",
        source_url="https://www.pbs.gov.au/example.zip",
        dataset="edithatogo/australian-pbs-source-archive",
        retrieved_at=RETRIEVED_AT,
        http_metadata=HTTP_METADATA,
    )

    assert manifest["source_effective_date"] == "2026-04-01"
    assert manifest["record_count"] == 1
    assert manifest["raw_bytes_are_source_of_truth"] is True
    assert manifest["parquet_is_rebuildable_projection"] is True
    assert (tmp_path / "stage/raw/2026-04-01/2026-04-01-XML-V3.zip").exists()
    assert (tmp_path / "stage/bronze/2026-04-01/pbs-v3-source.parquet").exists()
    assert (tmp_path / "stage/bronze/2026-04-01/sch-2026-04-01-r1.xml").exists()
    admission = cast("dict[str, object]", manifest["admission"])
    assert admission["state"] == "accepted"
    assert (tmp_path / "stage/bronze/2026-04-01/source-receipt.json").exists()
    assert (tmp_path / "stage/bronze/2026-04-01/admission.json").exists()
    receipt = json.loads(
        (tmp_path / "stage/bronze/2026-04-01/source-receipt.json").read_text()
    )
    parquet = pq.read_table(  # pyright: ignore[reportUnknownMemberType]
        tmp_path / "stage/bronze/2026-04-01/pbs-v3-source.parquet"
    )
    assert (
        parquet.schema.metadata[b"source_id"]
        == str(manifest["source_id"]).encode()
    )
    assert (
        parquet.schema.metadata[b"source_id"]
        == receipt["source"]["source_id"].encode()
    )
    assert (
        receipt["transformation"]["transformation_id"]
        == "au-pbs-v3-source-parquet-v2"
    )
    script = Path(pbs_qualifier.__file__)
    adapter = (
        script.parent.parent / "src/global_medicines_atlas/adapters/au_pbs.py"
    )
    expected = hashlib.sha256(
        script.read_bytes() + b"\x00" + adapter.read_bytes()
    ).hexdigest()
    assert receipt["transformation"]["transformation_sha256"] == expected


def test_hosted_qualification_rejects_non_calendar_effective_date(
    tmp_path: Path,
) -> None:
    archive_path = tmp_path / "source.zip"
    archive_path.write_bytes(
        _zip([
            ("sch-invalid.xml", _xml().replace(b"2026-07-01", b"2026-99-99"))
        ])
    )

    with pytest.raises(ValueError, match="ISO calendar date"):
        qualify(
            archive_path,
            tmp_path / "stage",
            source_url="https://www.pbs.gov.au/example.zip",
            dataset="edithatogo/australian-pbs-source-archive",
            retrieved_at=RETRIEVED_AT,
            http_metadata=HTTP_METADATA,
        )


def test_hosted_qualification_rejects_missing_effective_date(
    tmp_path: Path,
) -> None:
    archive_path = tmp_path / "source.zip"
    archive_path.write_bytes(
        _zip([
            (
                "sch-missing-date.xml",
                _xml().replace(b' effective-date="2026-07-01"', b""),
            )
        ])
    )

    with pytest.raises(ValueError, match="ISO calendar date"):
        qualify(
            archive_path,
            tmp_path / "stage",
            source_url="https://www.pbs.gov.au/example.zip",
            dataset="edithatogo/australian-pbs-source-archive",
            retrieved_at=RETRIEVED_AT,
            http_metadata=HTTP_METADATA,
        )


def test_hosted_qualification_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    archive_path = tmp_path / "source.zip"
    archive_path.write_bytes(
        _zip([("sch-2026-04-01-r1.xml", _production_xml())])
    )
    metadata_path = tmp_path / "http.json"
    metadata_path.write_text(json.dumps(HTTP_METADATA))
    monkeypatch.setattr(
        "sys.argv",
        [
            "qualify_pbs_v3_archive.py",
            "--archive",
            str(archive_path),
            "--output",
            str(tmp_path / "stage-command"),
            "--source-url",
            "https://www.pbs.gov.au/example.zip",
            "--dataset",
            "edithatogo/australian-pbs-source-archive",
            "--retrieved-at",
            RETRIEVED_AT.isoformat(),
            "--http-metadata",
            str(metadata_path),
        ],
    )

    assert pbs_qualifier.main() == 0
    assert json.loads(capsys.readouterr().out)["record_count"] == 1


def test_tag_inspector_is_bounded_and_source_native() -> None:
    result = parse_pbs_v3_archive(_zip([("sch-a.xml", _xml())]))

    tags = inspect_pbs_v3_tags(result.xml_payload, max_tags=4)

    assert len(tags) == 4
    assert tags[0] == f"{{{PBS_V3_NAMESPACE}}}schedule"

    with pytest.raises(ValueError, match="positive"):
        inspect_pbs_v3_tags(result.xml_payload, max_tags=0)


def test_source_parquet_is_deterministic_and_source_faithful() -> None:
    result = parse_pbs_v3_archive(_zip([("sch-a.xml", _xml())]))

    first = pbs_v3_source_parquet(result.records)
    second = pbs_v3_source_parquet(result.records)
    row = pq.read_table(  # pyright: ignore[reportUnknownMemberType]
        BytesIO(first)
    ).to_pylist()[0]

    assert first == second
    assert row["item_code"] == "1234A"
    assert row["amt_codes"] == ["123456"]
    assert row["atc_codes"] == ["A01AA01"]
    assert row["projected_item_sha256"] == (
        result.records[0].projected_item_sha256
    )


def test_source_schema_keeps_funding_and_nonfunding_dimensions_separate() -> (
    None
):
    metadata = {
        key.decode(): value.decode()
        for key, value in PBS_V3_SOURCE_SCHEMA.metadata.items()
    }

    assert metadata["schema_version"] == "2.0"
    assert "dimension" not in metadata
    assert metadata["dimension_funding"] == "source_structure"
    assert metadata["dimension_formulary"] == "source_structure"
    assert metadata["mapping_status"] == "source_native"
    assert metadata["absence_interpretation"] == "unknown"
    assert metadata["qualification"] == "candidate"
    assert metadata["dimension_regulatory"] == "not_asserted"
    assert metadata["dimension_terminology"] == "reference_only"
    assert metadata["dimension_classification"] == "reference_only"


def test_source_parquet_preserves_missing_amt_resource_as_null() -> None:
    payload = _xml().replace(
        b' rdf:resource="http://snomed.info/id/123456"', b""
    )
    result = parse_pbs_v3_archive(_zip([("sch-a.xml", payload)]))

    row = pq.read_table(  # pyright: ignore[reportUnknownMemberType]
        BytesIO(pbs_v3_source_parquet(result.records))
    ).to_pylist()[0]

    assert row["amt_resources"] == [None]


@pytest.mark.parametrize(
    ("entries", "message"),
    [
        ([("../sch-a.xml", _xml())], "unsafe member path"),
        (
            [("sch-a.xml", _xml()), ("SCH-A.XML", _xml())],
            "duplicate archive member",
        ),
        ([("notes.txt", b"none")], "exactly one schedule XML"),
        (
            [("sch-a.xml", _xml()), ("nested/sch-b.xml", _xml())],
            "exactly one schedule XML",
        ),
    ],
)
def test_parse_pbs_v3_archive_rejects_unsafe_or_ambiguous_members(
    entries: list[tuple[str, bytes]], message: str
) -> None:
    with pytest.raises((ArchiveSafetyError, ValueError), match=message):
        parse_pbs_v3_archive(_zip(entries))


def test_parse_pbs_v3_archive_rejects_malformed_xml() -> None:
    with pytest.raises(ValueError, match="valid PBS XML"):
        parse_pbs_v3_archive(_zip([("sch-a.xml", b"<broken>")]))


def test_parse_pbs_v3_archive_rejects_namespace_drift() -> None:
    archive = _zip([("sch-a.xml", _xml(namespace="https://example.invalid"))])
    with pytest.raises(ValueError, match="namespace drift"):
        parse_pbs_v3_archive(archive)


def test_parse_pbs_v3_archive_rejects_root_drift() -> None:
    payload = _xml().replace(b"pbs:schedule", b"pbs:document")
    with pytest.raises(ValueError, match="root drift"):
        parse_pbs_v3_archive(_zip([("sch-a.xml", payload)]))


def test_parse_pbs_v3_archive_rejects_missing_namespace() -> None:
    with pytest.raises(ValueError, match="namespace drift: missing"):
        parse_pbs_v3_archive(_zip([("sch-a.xml", b"<schedule />")]))


def test_parse_pbs_v3_archive_rejects_missing_item_identity() -> None:
    payload = _xml().replace(b' xml:id="1234A"', b"")
    with pytest.raises(ValueError, match="xml:id"):
        parse_pbs_v3_archive(_zip([("sch-a.xml", payload)]))


def test_parse_pbs_v3_archive_rejects_empty_schedule() -> None:
    payload = f'<pbs:schedule xmlns:pbs="{PBS_V3_NAMESPACE}" />'.encode()
    with pytest.raises(ValueError, match="no pharmaceutical items"):
        parse_pbs_v3_archive(_zip([("sch-a.xml", payload)]))


def test_parse_pbs_v3_archive_rejects_duplicate_item_identity() -> None:
    item = (
        _xml()
        .split(b"<pbs:pharmaceutical-item", 1)[1]
        .split(b"</pbs:pharmaceutical-item>", 1)[0]
    )
    payload = _xml().replace(
        b"</pbs:schedule>",
        b"<pbs:pharmaceutical-item"
        + item
        + b"</pbs:pharmaceutical-item></pbs:schedule>",
    )
    with pytest.raises(ValueError, match="duplicate item identity"):
        parse_pbs_v3_archive(_zip([("sch-a.xml", payload)]))


def test_pbs_policy_accepts_representative_large_element_count() -> None:
    metadata = b"".join(
        f'<pbs:metadata id="{index}"/>'.encode() for index in range(100_001)
    )
    payload = _xml().replace(
        b"<pbs:pharmaceutical-item",
        metadata + b"<pbs:pharmaceutical-item",
    )

    result = parse_pbs_v3_archive(_zip([("sch-large.xml", payload)]))

    assert len(result.records) == 1
    assert inspect_pbs_v3_tags(result.xml_payload, max_tags=2) == (
        f"{{{PBS_V3_NAMESPACE}}}schedule",
        f"{{{PBS_V3_NAMESPACE}}}metadata",
    )


def test_pbs_policy_retains_finite_official_schedule_envelope() -> None:
    assert PBS_XML_POLICY.max_xml_elements == 50_000_000
    assert PBS_XML_POLICY.max_bytes == 512 * 1024 * 1024
    assert PBS_XML_POLICY.max_xml_text_bytes == 384 * 1024 * 1024


@pytest.mark.parametrize("source_id", ["au-pbs", "au-pbs-historical-xml"])
def test_source_identity_parameterization_preserves_native_values(
    source_id: str,
) -> None:
    records = parse_pbs_v3_archive(_zip([("sch-a.xml", _xml())])).records
    default = pq.read_table(BytesIO(pbs_v3_source_parquet(records)))  # pyright: ignore[reportUnknownMemberType]
    selected = pq.read_table(  # pyright: ignore[reportUnknownMemberType]
        BytesIO(pbs_v3_source_parquet(records, source_id=source_id))
    )
    assert default.schema.metadata[b"source_id"] == b"au-pbs"
    assert selected.schema.metadata[b"source_id"] == source_id.encode()
    assert selected.to_pylist() == default.to_pylist()
    assert selected.schema.metadata[b"dimension_regulatory"] == b"not_asserted"


def test_source_identity_rejects_unrelated_domain():
    with pytest.raises(ValueError, match="source identity"):
        pbs_v3_source_parquet((), source_id="au-mbs")


@pytest.mark.parametrize("changed", ["script", "adapter"])
def test_qualification_digest_changes_with_either_implementation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, changed: str
) -> None:
    script = Path(pbs_qualifier.__file__).resolve()
    adapter = (
        script.parent.parent / "src/global_medicines_atlas/adapters/au_pbs.py"
    )
    baseline = hashlib.sha256(
        script.read_bytes() + b"\x00" + adapter.read_bytes()
    ).hexdigest()
    original = Path.read_bytes
    changed_path = script if changed == "script" else adapter

    def read(path: Path) -> bytes:
        value = original(path)
        return (
            value + b"\n# synthetic implementation change\n"
            if path.resolve() == changed_path
            else value
        )

    monkeypatch.setattr(Path, "read_bytes", read)
    archive = tmp_path / "input.zip"
    archive.write_bytes(_zip([("sch-a.xml", _production_xml())]))
    qualify(
        archive,
        tmp_path / "stage",
        source_url="https://www.pbs.gov.au/example.zip",
        dataset="edithatogo/australian-pbs-source-archive",
        retrieved_at=RETRIEVED_AT,
        http_metadata=HTTP_METADATA,
    )
    receipt = json.loads(
        (tmp_path / "stage/bronze/2026-04-01/source-receipt.json").read_text()
    )
    assert receipt["transformation"]["transformation_sha256"] != baseline


def test_parse_pbs_v3_archive_rejects_decompression_bomb() -> None:
    with pytest.raises(ArchiveSafetyError, match="decompression ratio"):
        parse_pbs_v3_archive(_zip([("sch-a.xml", b"0" * 100_000)]))
