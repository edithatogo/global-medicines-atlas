"""Governed PBS v3 archive and source-record contracts."""

from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pyarrow.parquet as pq
import pytest

from global_medicines_atlas.adapters.au_pbs import (
    PBS_V3_NAMESPACE,
    inspect_pbs_v3_tags,
    parse_pbs_v3_archive,
    pbs_v3_source_parquet,
)
from global_medicines_atlas.archive_safety import ArchiveSafetyError


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


def test_parse_pbs_v3_archive_rejects_decompression_bomb() -> None:
    with pytest.raises(ArchiveSafetyError, match="decompression ratio"):
        parse_pbs_v3_archive(_zip([("sch-a.xml", b"0" * 100_000)]))
