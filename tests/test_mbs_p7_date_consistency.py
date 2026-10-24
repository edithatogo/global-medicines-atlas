"""Focused, value-free tests for the exact P7 date-profile inference."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from scripts import qualify_mbs_p7_date_consistency as cli

from global_medicines_atlas import mbs_p7_date_consistency as consistency
from global_medicines_atlas.receipts import SourceReceipt

_SHA = "2f1cbc2d2dcbb93be86f42c8dbbe9f5f9e8fb550cad38b6ee54d0e9bdd2e27b8"
_FIELDS = sorted(consistency._DATE_FIELDS)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("01.01.2020", "unique_calendar_date"),
        ("02.03.2020", "ambiguous_calendar_order"),
        ("13.02.2020", "unique_dmy_calendar_date"),
        ("02.13.2020", "unique_mdy_calendar_date"),
        ("31.02.2020", "invalid"),
        ("2020-01-01", "invalid"),
    ],
)
def test_date_status_calendar_profiles(value: str, expected: str) -> None:
    assert consistency._date_status(value) == expected


def _valid_profile() -> dict[str, Any]:
    profile: dict[str, Any] = {
        "schema_version": 1,
        "source_sha256": _SHA,
        "source_byte_count": 87727,
        "date_order_selected": False,
        "source_values_emitted": False,
        "by_field": {},
        "lexical_profile_by_field": {},
    }
    for index, field in enumerate(_FIELDS):
        profile["by_field"][field] = {
            "ambiguous_calendar_order": 319,
            "unique_dmy_calendar_date": 1 if index == 0 else 0,
        }
        profile["lexical_profile_by_field"][field] = {"dd_mm_yyyy_dotted": 320}
    return profile


def test_count_validation_rejects_malformed_maps_and_boolean_counts() -> None:
    assert consistency._validated_counts(None) is None
    assert consistency._validated_counts({"field": []}) is None
    assert consistency._validated_counts({1: {"ok": 1}}) is None
    assert consistency._validated_counts({"field": {1: 1}}) is None
    assert consistency._validated_counts({"field": {"ok": True}}) is None
    assert consistency._validated_counts({"field": {"ok": -1}}) is None
    assert consistency._validated_counts({"field": {"ok": 1}}) == {
        "field": {"ok": 1}
    }


def test_profile_rejects_wrong_receipt_digest() -> None:
    receipt = SimpleNamespace(payload=SimpleNamespace(sha256="wrong"))
    with pytest.raises(ValueError, match="pinned source"):
        consistency.profile_p7_date_consistency(
            b"synthetic", cast("SourceReceipt", receipt)
        )


def test_profile_aggregates_statuses_without_emitting_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Batch:
        def to_pylist(self) -> list[dict[str, Any]]:
            return [
                {
                    "mapping_field": _FIELDS[0],
                    "row_kind": "header",
                    "display_value": "not emitted",
                    "cell_type": "s",
                    "formula_state": "missing_field",
                    "present_properties": ["display_value"],
                },
                {
                    "mapping_field": "unrelated",
                    "row_kind": "cell",
                    "display_value": "not emitted",
                    "cell_type": "s",
                    "formula_state": "missing_field",
                    "present_properties": ["display_value"],
                },
                {
                    "mapping_field": _FIELDS[0],
                    "row_kind": "cell",
                    "display_value": "13.02.2020",
                    "cell_type": "s",
                    "formula_state": "missing_field",
                    "present_properties": ["display_value"],
                },
                {
                    "mapping_field": _FIELDS[0],
                    "row_kind": "cell",
                    "display_value": None,
                    "cell_type": "e",
                    "formula_state": "missing_field",
                    "present_properties": ["display_value"],
                },
                {
                    "mapping_field": _FIELDS[0],
                    "row_kind": "cell",
                    "display_value": None,
                    "cell_type": "s",
                    "formula_state": "formula",
                    "present_properties": ["display_value"],
                },
                {
                    "mapping_field": _FIELDS[0],
                    "row_kind": "cell",
                    "display_value": None,
                    "cell_type": "s",
                    "formula_state": "missing_field",
                    "present_properties": ["display_value"],
                },
                {
                    "mapping_field": _FIELDS[0],
                    "row_kind": "cell",
                    "display_value": None,
                    "cell_type": "s",
                    "formula_state": "missing_field",
                    "present_properties": [],
                },
                {
                    "mapping_field": _FIELDS[0],
                    "row_kind": "cell",
                    "display_value": "45292",
                    "cell_type": "n",
                    "formula_state": "missing_field",
                    "present_properties": ["display_value"],
                },
                {
                    "mapping_field": _FIELDS[0],
                    "row_kind": "cell",
                    "display_value": "bad date",
                    "cell_type": "s",
                    "formula_state": "missing_field",
                    "present_properties": ["display_value"],
                },
            ]

    def fake_batches(_payload: bytes, _receipt: SourceReceipt) -> list[Batch]:
        return [Batch()]

    monkeypatch.setattr(
        consistency, "iter_workbook_domain_batches", fake_batches
    )
    receipt = SimpleNamespace(
        payload=SimpleNamespace(sha256=_SHA, byte_count=87727)
    )
    result = consistency.profile_p7_date_consistency(
        b"synthetic", cast("SourceReceipt", receipt)
    )

    assert result["by_field"][_FIELDS[0]] == {
        "formula_unresolved": 1,
        "invalid": 1,
        "missing_value": 1,
        "null": 1,
        "source_error": 1,
        "unique_dmy_calendar_date": 1,
        "unsupported_serial_date": 1,
    }
    assert result["lexical_profile_by_field"][_FIELDS[0]] == {
        "dd_mm_yyyy_dotted": 1,
        "other_text_profile": 1,
    }
    assert "13.02.2020" not in str(result)
    assert result["profiled_cells_by_field"][_FIELDS[0]] == 7


@pytest.mark.parametrize(
    ("mutate", "digest"),
    [
        (lambda p: p.update(schema_version=2), _SHA),
        (lambda p: p.update(source_byte_count=1), _SHA),
        (lambda p: p.update(date_order_selected=True), _SHA),
        (lambda p: p.update(source_values_emitted=True), _SHA),
        (lambda p: p.update(source_sha256="other"), _SHA),
        (
            lambda p: p["by_field"].update(
                extra={"ambiguous_calendar_order": 320}
            ),
            _SHA,
        ),
        (lambda p: p["by_field"].update({_FIELDS[0]: {"bad": "count"}}), _SHA),
        (
            lambda p: p["lexical_profile_by_field"].update({_FIELDS[0]: []}),
            _SHA,
        ),
        (
            lambda p: p["lexical_profile_by_field"][_FIELDS[0]].update({
                "other_text_profile": 1
            }),
            _SHA,
        ),
        (
            lambda p: p["lexical_profile_by_field"][_FIELDS[0]].update({
                "dd_mm_yyyy_dotted": 319
            }),
            _SHA,
        ),
        (lambda p: p["by_field"][_FIELDS[0]].update({"invalid": 1}), _SHA),
        (
            lambda p: p["by_field"][_FIELDS[0]].update({
                "formula_unresolved": 1
            }),
            _SHA,
        ),
        (lambda p: p["by_field"][_FIELDS[0]].update({"source_error": 1}), _SHA),
        (
            lambda p: p["by_field"][_FIELDS[0]].update({
                "unsupported_serial_date": 1
            }),
            _SHA,
        ),
        (
            lambda p: p["by_field"][_FIELDS[0]].update({
                "unique_mdy_calendar_date": 1
            }),
            _SHA,
        ),
        (lambda p: p["by_field"][_FIELDS[0]].update({"null": 1}), _SHA),
        (lambda p: p["by_field"].pop(_FIELDS[0]), _SHA),
        (lambda p: p.update({}), "wrong-digest"),
    ],
)
def test_selector_abstains_on_invalid_or_incomplete_evidence(
    mutate: Any, digest: str
) -> None:
    profile = _valid_profile()
    mutate(profile)
    decision = consistency.decide_p7_date_consistency(
        profile, expected_source_sha256=digest
    )
    assert decision["selected_profile"] is None
    assert decision["selection_status"] == "unresolved"


def test_selector_abstains_without_populated_values_or_dmy_only() -> None:
    profile = _valid_profile()
    for field in _FIELDS:
        profile["by_field"][field] = {"null": 320}
        profile["lexical_profile_by_field"][field] = {}
    decision = consistency.decide_p7_date_consistency(
        profile, expected_source_sha256=_SHA
    )
    assert decision["selected_profile"] is None

    profile = _valid_profile()
    profile["by_field"][_FIELDS[0]] = {"ambiguous_calendar_order": 320}
    profile["lexical_profile_by_field"][_FIELDS[0]] = {"dd_mm_yyyy_dotted": 320}
    decision = consistency.decide_p7_date_consistency(
        profile, expected_source_sha256=_SHA
    )
    assert decision["selected_profile"] is None


def test_cli_rejects_non_main_context_before_acquisition(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "qualify_mbs_p7_date_consistency.py",
            "--output",
            str(tmp_path / "report.json"),
            "--exact-commit",
            "abc",
        ],
    )
    monkeypatch.setenv("GITHUB_ACTIONS", "false")
    monkeypatch.setenv("GITHUB_REPOSITORY", "edithatogo/global-medicines-atlas")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_SHA", "abc")

    with pytest.raises(ValueError, match="requires exact main"):
        cli.main()

    assert not (tmp_path / "report.json").exists()


def test_cli_success_path_is_mocked_and_writes_bounded_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    payload = b"synthetic"
    payload_sha = cli.hashlib.sha256(payload).hexdigest()
    monkeypatch.setattr(
        cli,
        "LEGACY_P7_SHA256",
        payload_sha,
    )
    monkeypatch.setattr(cli, "LEGACY_P7_BYTES", len(payload))

    class FakeClient:
        def __init__(self, **_kwargs: Any) -> None: ...

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

    monkeypatch.setattr(cli.httpx, "Client", FakeClient)
    monkeypatch.setattr(cli, "acquire_hosted_workbook", lambda _client: payload)
    receipt = object()
    monkeypatch.setattr(cli, "_receipt", lambda _payload, _retrieved: receipt)
    profile = {"source_values_emitted": False}
    monkeypatch.setattr(
        cli, "profile_p7_date_consistency", lambda _payload, _receipt: profile
    )
    decision = {"selection_status": "unresolved"}

    def fake_decision(
        _profile: dict[str, Any], *, expected_source_sha256: str
    ) -> dict[str, str]:
        assert expected_source_sha256 == payload_sha
        return decision

    monkeypatch.setattr(
        cli,
        "decide_p7_date_consistency",
        fake_decision,
    )
    output = tmp_path / "report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "qualify_mbs_p7_date_consistency.py",
            "--output",
            str(output),
            "--exact-commit",
            "abc123",
        ],
    )
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", "edithatogo/global-medicines-atlas")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_SHA", "abc123")
    monkeypatch.setenv("GITHUB_RUN_ID", "12345")

    cli.main()

    report = cli.json.loads(output.read_text(encoding="utf-8"))
    assert report["profile"] == profile
    assert report["decision"]["workflow_commit"] == "abc123"
    assert report["decision"]["workflow_run"].endswith("/12345")


def test_cli_rejects_changed_hosted_payload_identity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class FakeClient:
        def __init__(self, **_kwargs: Any) -> None: ...

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

    monkeypatch.setattr(cli.httpx, "Client", FakeClient)
    monkeypatch.setattr(
        cli, "acquire_hosted_workbook", lambda _client: b"wrong"
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "qualify_mbs_p7_date_consistency.py",
            "--output",
            str(tmp_path / "report.json"),
            "--exact-commit",
            "abc123",
        ],
    )
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", "edithatogo/global-medicines-atlas")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_SHA", "abc123")

    with pytest.raises(ValueError, match="identity changed"):
        cli.main()


def test_cli_receipt_binds_synthetic_payload() -> None:
    payload = b"synthetic receipt payload"
    receipt = cli._receipt(payload, cli.datetime.now(cli.UTC))
    assert receipt.payload.sha256 == cli.hashlib.sha256(payload).hexdigest()
    assert receipt.payload.byte_count == len(payload)
