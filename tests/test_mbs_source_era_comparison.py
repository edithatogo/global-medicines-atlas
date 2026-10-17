"""Aggregate-only regression tests for adjacent MBS release comparison."""

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError
from scripts import compare_mbs_source_eras as command


def _payload(*records: str) -> bytes:
    body = "".join(f"<Data>{record}</Data>" for record in records)
    return f"<MBS_XML>{body}</MBS_XML>".encode()


def _record(item: str, amount: str, *, subitem: str = "1") -> str:
    return (
        f"<ItemNum>{item}</ItemNum><SubItemNum>{subitem}</SubItemNum>"
        "<ItemStartDate>01.07.2026</ItemStartDate>"
        f"<Benefit75>{amount}</Benefit75>"
    )


def _pin(monkeypatch: pytest.MonkeyPatch, july: bytes, august: bytes) -> None:
    july_era = dict(command.JULY)
    july_era.update(
        sha256=hashlib.sha256(july).hexdigest(), byte_count=len(july)
    )
    august_era = dict(command.AUGUST)
    august_era.update(
        sha256=hashlib.sha256(august).hexdigest(), byte_count=len(august)
    )
    monkeypatch.setattr(command, "JULY", july_era)
    monkeypatch.setattr(command, "AUGUST", august_era)


def test_comparison_emits_aggregate_counts_without_source_values_or_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    july = _payload(_record("10001", "10.00"), _record("10002", "20.00"))
    august = _payload(_record("10001", "11.00"), _record("10003", "30.00"))
    _pin(monkeypatch, july, august)

    report = command.compare_releases(
        july_payload=july,
        august_payload=august,
        july_official_payload=july,
        august_official_payload=august,
        compared_at=datetime(2026, 10, 17, tzinfo=UTC),
        exact_commit="a" * 40,
    )

    assert report["status"] == "aggregate_comparison_complete"
    assert [release["record_count"] for release in report["releases"]] == [2, 2]
    comparison = report["comparison"]
    assert comparison["matched_record_count"] == 1
    assert comparison["added_record_count"] == 1
    assert comparison["removed_record_count"] == 1
    assert comparison["changed_record_count"] == 1
    assert comparison["changed_field_counts"] == [
        {"native_field": "Benefit75", "count": 1}
    ]
    assert report["source_values_retained"] is False
    assert report["source_identifiers_emitted"] is False
    july_rights, august_rights = [
        release["rights_reference"] for release in report["releases"]
    ]
    assert (
        "australian-mbs-harvest-publication-authorization.json" in july_rights
    )
    assert august_rights.endswith("issues/339#issuecomment-5467052330")
    assert july_rights != august_rights
    assert report["semantics_accepted"] is False
    assert report["m109_accepted"] is False
    rendered = json.dumps(report)
    for source_value in ("10001", "10002", "10003", "10.00", "11.00"):
        assert source_value not in rendered


def test_comparison_rejects_archive_or_official_identity_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    july = _payload(_record("10001", "10.00"))
    august = _payload(_record("10001", "10.00"))
    _pin(monkeypatch, july, august)

    with pytest.raises(ValueError, match="2026-07-01 archive bytes"):
        command.compare_releases(
            july_payload=july + b" ",
            august_payload=august,
            july_official_payload=july,
            august_official_payload=august,
            compared_at=datetime(2026, 10, 17, tzinfo=UTC),
            exact_commit="a" * 40,
        )


def test_comparison_rejects_ambiguous_item_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    july = _payload(_record("10001", "10.00"), _record("10001", "12.00"))
    august = _payload(_record("10001", "11.00"))
    _pin(monkeypatch, july, august)

    with pytest.raises(
        ValueError, match="ambiguous repeated MBS item identity"
    ):
        command.compare_releases(
            july_payload=july,
            august_payload=august,
            july_official_payload=july,
            august_official_payload=august,
            compared_at=datetime(2026, 10, 17, tzinfo=UTC),
            exact_commit="a" * 40,
        )


def test_harvest_receipt_must_bind_exact_source_category_and_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = {
        "schema_id": "global-medicines-atlas.australian-harvest-receipt",
        "schema_version": 1,
        "source_id": "au-mbs",
        "category": "monthly_schedule_xml",
        "source_url": command.JULY["official_uri"],
        "final_url": command.JULY["official_uri"],
        "archive_path": command.JULY["archive_path"],
        "sha256": command.JULY["sha256"],
        "byte_count": command.JULY["byte_count"],
    }
    receipt_bytes = json.dumps(receipt).encode()
    monkeypatch.setitem(
        command.JULY,
        "harvest_receipt_sha256",
        hashlib.sha256(receipt_bytes).hexdigest(),
    )
    command._validate_harvest_receipt(command.JULY, receipt_bytes)

    monkeypatch.setitem(command.JULY, "harvest_receipt_sha256", "0" * 64)
    with pytest.raises(ValueError, match="pinned sidecar identity"):
        command._validate_harvest_receipt(command.JULY, receipt_bytes)

    receipt["source_url"] = command.AUGUST["official_uri"]
    wrong_source_bytes = json.dumps(receipt).encode()
    monkeypatch.setitem(
        command.JULY,
        "harvest_receipt_sha256",
        hashlib.sha256(wrong_source_bytes).hexdigest(),
    )
    with pytest.raises(ValueError, match="harvest receipt identity"):
        command._validate_harvest_receipt(command.JULY, wrong_source_bytes)


def test_harvest_receipt_must_be_a_json_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt_bytes = b"[]"
    monkeypatch.setitem(
        command.JULY,
        "harvest_receipt_sha256",
        hashlib.sha256(receipt_bytes).hexdigest(),
    )

    with pytest.raises(ValidationError, match="Input should be an object"):
        command._validate_harvest_receipt(command.JULY, receipt_bytes)


def test_incomplete_report_is_explicit_and_does_not_emit_exception_text() -> (
    None
):
    report = command._incomplete_report(
        exact_commit="a" * 40,
        compared_at=datetime(2026, 10, 17, tzinfo=UTC),
        error=ValueError("source value 10.00 for item 10001 differed"),
    )

    rendered = json.dumps(report)
    assert report["status"] == "incomplete"
    assert report["failure_class"] == "identity_or_structure_mismatch"
    assert report["source_values_retained"] is False
    assert report["m109_accepted"] is False
    assert "10.00" not in rendered
    assert "10001" not in rendered


@pytest.mark.parametrize(
    ("error", "failure_class", "sensitive_text"),
    [
        pytest.param(
            httpx.ConnectError("endpoint secret 10.00"),
            "source_endpoint_unavailable",
            "10.00",
            id="httpx-endpoint-error",
        ),
        pytest.param(
            OSError("dns lookup secret.internal for 10.00"),
            "source_endpoint_unavailable",
            "secret.internal",
            id="dns-os-error",
        ),
        pytest.param(
            command.DestinationPolicyError(
                "redirect-host-not-allowed", "blocked redirect secret.internal"
            ),
            "destination_policy_rejected",
            "secret.internal",
            id="destination-policy-error",
        ),
    ],
)
def test_cli_writes_incomplete_artifact_and_fails_on_transport_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    error: Exception,
    failure_class: str,
    sensitive_text: str,
) -> None:
    output = tmp_path / "comparison.json"

    def unavailable(*, exact_commit: str) -> dict[str, object]:
        assert len(exact_commit) == 40
        raise error

    monkeypatch.setattr(command, "compare", unavailable)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "compare_mbs_source_eras.py",
            "--exact-commit",
            "a" * 40,
            "--output",
            str(output),
        ],
    )

    assert command.main() == 1
    rendered = output.read_text(encoding="utf-8")
    report = json.loads(rendered)
    assert report["status"] == "incomplete"
    assert report["failure_class"] == failure_class
    assert sensitive_text not in rendered
