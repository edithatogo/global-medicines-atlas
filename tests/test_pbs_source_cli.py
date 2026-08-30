"""Donor PBS command behavior on digest-bound synthetic archive bytes."""

from __future__ import annotations

import hashlib
import json
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from typer.testing import CliRunner

from global_medicines_atlas import pbs_cli
from global_medicines_atlas.archive_safety import ArchivePolicy
from global_medicines_atlas.cli import app

XML = b"""<pbs:schedule xmlns:pbs="http://schema.pbs.gov.au/"
 xmlns:dbk="http://docbook.org/ns/docbook" effective-date="2026-04-01">
 <pbs:pharmaceutical-item xml:id="123A">
 <pbs:block-container><dbk:para>Example tablet</dbk:para></pbs:block-container>
 <pbs:drug-references-list><pbs:mp-reference><pbs:code>456</pbs:code>
 </pbs:mp-reference></pbs:drug-references-list>
 <pbs:code type="ATC">A01AA01</pbs:code>
 </pbs:pharmaceutical-item></pbs:schedule>"""


def _arguments(tmp_path: Path, xml: bytes = XML) -> list[str]:
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("sch-example.xml", xml)
    payload = stream.getvalue()
    path = tmp_path / "schedule.zip"
    path.write_bytes(payload)
    return [
        "--archive",
        str(path),
        "--sha256",
        hashlib.sha256(payload).hexdigest(),
    ]


def test_parse_donor_labels_and_limit_alias(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        ["source", "pbs", "parse", *_arguments(tmp_path), "--max_items", "1"],
    )
    assert result.exit_code == 0, result.output
    assert "PBS Item Code (xml:id): 123A" in result.output
    assert "Drug Name/Description: Example tablet" in result.output
    assert "AMT Codes Info: 456" in result.output
    assert "ATC Codes: A01AA01" in result.output


def test_parse_json_binds_source_and_reports_truncation(tmp_path: Path) -> None:
    item = (
        b" <pbs:pharmaceutical-item"
        + XML.split(b" <pbs:pharmaceutical-item", 1)[1].split(
            b"</pbs:schedule>"
        )[0]
    )
    xml = XML.replace(
        b"</pbs:schedule>", item.replace(b"123A", b"999B") + b"</pbs:schedule>"
    )
    args = _arguments(tmp_path, xml)
    result = CliRunner().invoke(
        app,
        [
            "source",
            "pbs",
            "parse",
            *args,
            "--max-items",
            "1",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0, result.output
    document = json.loads(result.stdout)
    assert document["archive_sha256"] == args[-1]
    assert document["total_items"] == 2
    assert document["truncated"] is True
    assert len(document["records"]) == 1
    assert document["records"][0]["amt_references"] == [["456", None]]
    assert document["publication_status"] == "not_published_by_this_command"


def test_inspect_preserves_first_item_structure(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app, ["source", "pbs", "inspect", *_arguments(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    document = json.loads(result.stdout)
    assert "pharmaceutical-item" in document["first_item_xml"]
    assert "123A" in document["first_item_xml"]
    assert document["xml_representation"] == "normalized_not_source_bytes"


@pytest.mark.parametrize("command", ["parse", "inspect"])
def test_digest_mismatch_fails_without_partial_output(
    tmp_path: Path, command: str
) -> None:
    args = _arguments(tmp_path)
    args[-1] = "0" * 64
    result = CliRunner().invoke(app, ["source", "pbs", command, *args])
    assert result.exit_code == 2
    assert not result.stdout
    assert "digest" in result.stderr


@pytest.mark.parametrize(
    "extra",
    [["--max-items", "0"], ["--max-items", "1001"], ["--format", "csv"]],
)
def test_parse_rejects_invalid_options(
    tmp_path: Path, extra: list[str]
) -> None:
    result = CliRunner().invoke(
        app, ["source", "pbs", "parse", *_arguments(tmp_path), *extra]
    )
    assert result.exit_code == 2


def test_invalid_schedule_is_not_success(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app, ["source", "pbs", "parse", *_arguments(tmp_path, b"<wrong />")]
    )
    assert result.exit_code == 2
    assert not result.stdout


def test_first_item_output_bound_fails_closed(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "source",
            "pbs",
            "inspect",
            *_arguments(tmp_path),
            "--max-output-bytes",
            "1",
        ],
    )
    assert result.exit_code == 2
    assert not result.stdout


@pytest.mark.parametrize("digest", ["bad", "G" * 64])
def test_invalid_digest(tmp_path: Path, digest: str) -> None:
    args = _arguments(tmp_path)
    args[-1] = digest
    result = CliRunner().invoke(app, ["source", "pbs", "parse", *args])
    assert result.exit_code == 2
    assert "lowercase SHA-256" in result.stderr


def test_read_bound(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    args = _arguments(tmp_path)
    monkeypatch.setattr(
        pbs_cli, "PBS_ARCHIVE_POLICY", ArchivePolicy(max_archive_bytes=1)
    )
    result = CliRunner().invoke(app, ["source", "pbs", "parse", *args])
    assert result.exit_code == 2
    assert "archive exceeds" in result.stderr


def test_read_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    args = _arguments(tmp_path)

    def fail_read(_path: Path, _digest: str) -> bytes:
        raise OSError("unavailable")

    monkeypatch.setattr(pbs_cli, "_read_archive", fail_read)
    result = CliRunner().invoke(app, ["source", "pbs", "parse", *args])
    assert result.exit_code == 2
    assert "unavailable" in result.stderr


def test_url_does_not_trigger_ungoverned_download() -> None:
    result = CliRunner().invoke(
        app,
        ["source", "pbs", "parse", "--url", "https://example.org/schedule.zip"],
    )
    assert result.exit_code == 2
