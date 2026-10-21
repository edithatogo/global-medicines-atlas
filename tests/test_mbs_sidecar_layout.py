"""Sidecar format metadata is exhaustive, bounded and withholds native values."""

import hashlib
import json
from pathlib import Path

import pytest

from global_medicines_atlas import mbs_sidecar_layout as module
from global_medicines_atlas.mbs_sidecar_inventory import BoundSidecar
from global_medicines_atlas.mbs_sidecar_layout import profile_sidecar


def source(payload, source_format):
    return BoundSidecar(
        "synthetic/sidecar",
        "1" * 40,
        "raw/synthetic",
        hashlib.sha256(payload).hexdigest(),
        len(payload),
        source_format,
        "2" * 64,
        (),
    )


def test_csv_keeps_first_row_multiline_empty_cells_and_no_header_claim():
    payload = b'\xef\xbb\xbfA,B\r\n"SYNTHETIC\r\nMULTILINE",\r\n'
    report = profile_sidecar(payload, source(payload, "csv"))
    assert report["layout"]["records"] == 2
    assert report["layout"]["native_fields"] == 4
    assert report["layout"]["empty_fields"] == 1
    assert report["layout"]["header_semantics"] == "unqualified"
    assert "SYNTHETIC" not in json.dumps(report)


def test_xml_accounts_for_all_attributes_text_tail_and_null_states():
    payload = b'<r a=""><c>SYNTHETIC</c>tail<c/></r>'
    report = profile_sidecar(payload, source(payload, "xml"))
    assert report["layout"]["elements"] == 3
    assert report["layout"]["native_fields"] == 7
    assert report["layout"]["null_fields"] == 4
    assert "SYNTHETIC" not in json.dumps(report)


def test_text_counts_every_line_and_byte_without_assuming_delimiters():
    payload = b"SYNTHETIC,VALUE\r\n01,2\n\r03,4"
    report = profile_sidecar(payload, source(payload, "text"))
    assert report["layout"]["native_records"] == 4
    assert report["layout"]["native_line_bytes"] == len(payload)
    assert report["layout"]["column_semantics"] == "unqualified"
    assert "SYNTHETIC" not in json.dumps(report)


def test_source_identity_checked_before_parsing():
    payload = b"A,B\n"
    with pytest.raises(ValueError, match="identity"):
        profile_sidecar(payload + b"changed", source(payload, "csv"))


@pytest.mark.parametrize(
    ("limit", "payload", "kind"),
    [
        ("MAX_RECORDS", b"A,B\n1,2\n", "csv"),
        ("MAX_COLUMNS", b"A,B\n", "csv"),
        ("MAX_RECORDS", b"one\ntwo\n", "text"),
        ("MAX_PATHS", b"<r/>", "xml"),
        ("MAX_REPORT_BYTES", b"A\n", "csv"),
    ],
)
def test_limits_reject_whole_report_instead_of_truncating(
    monkeypatch, limit, payload, kind
):
    monkeypatch.setattr(module, limit, 1)
    with pytest.raises(ValueError, match="bound"):
        profile_sidecar(payload, source(payload, kind))


def test_xml_entities_are_rejected_before_inventory():
    payload = b'<!DOCTYPE r [<!ENTITY v "SYNTHETIC">]><r>&v;</r>'
    with pytest.raises(ValueError, match=r"DTD|entity"):
        profile_sidecar(payload, source(payload, "xml"))


def test_unknown_format_is_not_guessed():
    payload = b"A,B\n"
    with pytest.raises(ValueError, match="unsupported"):
        profile_sidecar(payload, source(payload, "unknown"))


def test_non_utf8_text_retains_bytes_without_replacement_or_decoding_claim():
    payload = b"\xff\r\n"
    report = profile_sidecar(payload, source(payload, "text"))
    assert report["layout"]["utf8_valid"] is False
    assert report["layout"]["native_line_bytes"] == len(payload)


def test_native_inventory_is_deterministic_and_values_affect_digest():
    one, two = b"A,B\n1,2\n", b"A,B\n1,3\n"
    first = profile_sidecar(one, source(one, "csv"))
    assert first == profile_sidecar(one, source(one, "csv"))
    assert (
        first["layout"]["native_fields_sha256"]
        != profile_sidecar(two, source(two, "csv"))["layout"][
            "native_fields_sha256"
        ]
    )


def test_actual_retained_inventory_keeps_headers_and_column_meanings_unqualified():
    path = (
        Path(__file__).resolve().parents[1]
        / "quality/qualifications/mbs-bsd-rvg-native-layout-20261022-39675543570.json"
    )
    report = json.loads(path.read_bytes())
    assert report["status"] == "passed"
    assert (
        report["workflow_commit"] == "939aa2437076cd20bd11c46d57da09c5c9602cbf"
    )
    csv = next(
        row for row in report["objects"] if row["source_path"].endswith(".csv")
    )
    xml = next(
        row for row in report["objects"] if row["source_path"].endswith(".xml")
    )
    text = next(
        row for row in report["objects"] if row["source_path"].endswith(".TXT")
    )
    assert csv["layout"]["records"] == 4655
    assert csv["layout"]["native_fields"] == 9310
    assert csv["layout"]["first_record_retained"] is True
    assert csv["layout"]["header_semantics"] == "unqualified"
    assert sum(xml["layout"]["schema_path_counts"].values()) == 27926
    assert text["layout"]["native_records"] == 482
    assert text["layout"]["column_semantics"] == "unqualified"
    assert report["typed_output_qualified"] is False
