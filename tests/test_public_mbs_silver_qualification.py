"""Hosted-only public MBS candidate qualifier controls."""

from __future__ import annotations

import hashlib
import json
from functools import partial
from typing import Any, cast

import httpx
import pytest
from scripts import qualify_public_mbs_silver as command


class _Response:
    def __init__(self, payload: bytes, *, fail_status: bool = False) -> None:
        self.payload = payload
        self.fail_status = fail_status

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def raise_for_status(self) -> None:
        if self.fail_status:
            raise ValueError("unexpected HTTP redirect")

    def iter_bytes(self):
        yield self.payload


class _Client:
    def __init__(
        self,
        payload: bytes,
        official_payload: bytes | None = None,
        *,
        official_redirect: bool = False,
        **kwargs: object,
    ) -> None:
        assert kwargs["follow_redirects"] is True
        assert kwargs["trust_env"] is False
        assert isinstance(kwargs["timeout"], httpx.Timeout)
        assert kwargs["timeout"].read == 60
        assert kwargs["max_redirects"] == 3
        assert kwargs["transport"] is not None
        self.payload = payload
        self.official_payload = official_payload or payload
        self.official_redirect = official_redirect

    def __enter__(self) -> _Client:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def stream(self, method: str, url: str, **kwargs: object) -> _Response:
        assert method == "GET"
        if url == command.SOURCE_URI:
            assert not kwargs
            return _Response(self.payload)
        assert url == command.OFFICIAL_MBS_V3_URI
        assert kwargs == {"follow_redirects": False}
        return _Response(
            self.official_payload, fail_status=self.official_redirect
        )


def _client_factory(
    payload: bytes,
    official_payload: bytes | None = None,
    *,
    official_redirect: bool = False,
) -> Any:
    return cast(
        "Any",
        partial(
            _Client,
            payload,
            official_payload,
            official_redirect=official_redirect,
        ),
    )


def test_qualifies_only_digest_bound_public_bytes_in_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = b"<MBS_XML><Data><ItemNum>00123</ItemNum></Data></MBS_XML>"
    monkeypatch.setattr(command, "LEGACY_MBS_BYTES", len(payload))
    monkeypatch.setattr(
        command, "LEGACY_MBS_SHA256", hashlib.sha256(payload).hexdigest()
    )
    monkeypatch.setattr(
        command, "OFFICIAL_RELEASED_AT", command.date(2025, 6, 16)
    )
    monkeypatch.setattr(command.httpx, "Client", _client_factory(payload))

    result = command.qualify(exact_commit="a" * 40)

    qualification = cast("dict[str, object]", result["qualification"])
    assert qualification["source_record_count"] == 1
    tables = cast("list[dict[str, object]]", qualification["tables"])
    assert sum(cast("int", table["field_count"]) for table in tables) == 40
    assert qualification["promotion_status"] == "candidate_only"
    assert qualification["blockers"] == ["public_v4_identity_unverified"]
    assert (
        cast("dict[str, object]", result["official_release_check"])[
            "matched_pinned_archive"
        ]
        is True
    )
    assert result["publication_performed"] is False
    assert result["source_bytes_retained"] is False
    candidate_report = {
        "qualification": qualification,
        "quality_diagnostics": result["quality_diagnostics"],
        "official_release_check": result["official_release_check"],
    }
    expected_digest = hashlib.sha256(
        json.dumps(
            candidate_report, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    assert result["candidate_report_sha256"] == expected_digest
    assert cast("int", result["candidate_report_byte_count"]) > 0
    assert "payload" not in result
    diagnostics = cast("dict[str, object]", result["quality_diagnostics"])
    assert diagnostics["source_values_included"] is False


def test_quality_diagnostics_locate_field_and_row_without_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = (
        b"<MBS_XML><Data><ItemNum>00123</ItemNum>"
        b"<ItemStartDate>not-a-date</ItemStartDate>"
        b"<Benefit85>123456.78</Benefit85></Data>"
        b"<Data><ItemNum>00456</ItemNum>"
        b"<Benefit85>bad-amount</Benefit85></Data></MBS_XML>"
    )
    monkeypatch.setattr(command, "LEGACY_MBS_BYTES", len(payload))
    monkeypatch.setattr(
        command, "LEGACY_MBS_SHA256", hashlib.sha256(payload).hexdigest()
    )
    monkeypatch.setattr(
        command, "OFFICIAL_RELEASED_AT", command.date(2025, 6, 16)
    )
    monkeypatch.setattr(command.httpx, "Client", _client_factory(payload))

    result = command.qualify(exact_commit="a" * 40)

    assert cast("dict[str, object]", result["qualification"])["blockers"] == [
        "public_v4_identity_unverified",
        "quality_findings_present",
    ]
    diagnostics = cast("dict[str, object]", result["quality_diagnostics"])
    findings = cast(
        "list[dict[str, object]]",
        diagnostics["quality_finding_source_ordinals"],
    )
    invalid = [item for item in findings if item["status"] == "invalid"]
    assert invalid == [
        {
            "table": "benefits",
            "field": "Benefit85",
            "status": "invalid",
            "source_ordinals": [0, 1],
        },
        {
            "table": "services",
            "field": "ItemStartDate",
            "status": "invalid",
            "source_ordinals": [0],
        },
    ]
    amount_reasons = cast(
        "list[dict[str, object]]",
        diagnostics["invalid_amount_reason_source_ordinals"],
    )
    assert amount_reasons == [
        {
            "table": "benefits",
            "field": "Benefit85",
            "reason": "integer_width_exceeded",
            "source_ordinals": [0],
        },
        {
            "table": "benefits",
            "field": "Benefit85",
            "reason": "strict_numeric_grammar_mismatch",
            "source_ordinals": [1],
        },
    ]
    assert diagnostics["source_values_included"] is False
    assert "not-a-date" not in json.dumps(result)
    assert "123456.78" not in json.dumps(result)
    assert "bad-amount" not in json.dumps(result)
    assert (
        result["candidate_report_sha256"]
        == hashlib.sha256(
            json.dumps(
                {
                    "qualification": result["qualification"],
                    "quality_diagnostics": diagnostics,
                    "official_release_check": result["official_release_check"],
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
    )


@pytest.mark.parametrize(
    ("actual_bytes", "expected_bytes", "expected_sha", "message"),
    [
        (b"abc", 4, hashlib.sha256(b"abc").hexdigest(), "byte count"),
        (b"abc", 3, "0" * 64, "digest"),
    ],
)
def test_rejects_public_object_identity_drift(
    monkeypatch: pytest.MonkeyPatch,
    actual_bytes: bytes,
    expected_bytes: int,
    expected_sha: str,
    message: str,
) -> None:
    monkeypatch.setattr(command, "LEGACY_MBS_BYTES", expected_bytes)
    monkeypatch.setattr(command, "LEGACY_MBS_SHA256", expected_sha)
    monkeypatch.setattr(command.httpx, "Client", _client_factory(actual_bytes))

    with pytest.raises(ValueError, match=message):
        command.qualify(exact_commit="a" * 40)


def test_official_release_mismatch_keeps_era_blocker_and_hash_only_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = b"<MBS_XML><Data><ItemNum>00123</ItemNum></Data></MBS_XML>"
    official_payload = payload + b" "
    monkeypatch.setattr(command, "LEGACY_MBS_BYTES", len(payload))
    monkeypatch.setattr(
        command, "LEGACY_MBS_SHA256", hashlib.sha256(payload).hexdigest()
    )
    monkeypatch.setattr(
        command.httpx, "Client", _client_factory(payload, official_payload)
    )

    result = command.qualify(exact_commit="a" * 40)

    qualification = cast("dict[str, object]", result["qualification"])
    assert qualification["blockers"] == [
        "public_v4_identity_unverified",
        "real_source_era_unqualified",
    ]
    release_check = cast("dict[str, object]", result["official_release_check"])
    assert release_check["matched_pinned_archive"] is False
    assert (
        release_check["source_sha256"]
        == hashlib.sha256(official_payload).hexdigest()
    )
    assert release_check["source_byte_count"] == len(official_payload)
    assert "<MBS_XML>" not in json.dumps(result)


def test_official_release_redirect_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = b"<MBS_XML><Data><ItemNum>00123</ItemNum></Data></MBS_XML>"
    monkeypatch.setattr(command, "LEGACY_MBS_BYTES", len(payload))
    monkeypatch.setattr(
        command, "LEGACY_MBS_SHA256", hashlib.sha256(payload).hexdigest()
    )
    monkeypatch.setattr(
        command.httpx,
        "Client",
        _client_factory(payload, official_redirect=True),
    )

    with pytest.raises(ValueError, match="redirect"):
        command.qualify(exact_commit="a" * 40)


def test_invalid_amount_decimal_probe_is_value_free(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native_spellings = (
        " 12.5 ",
        "1e2",
        "1_000",
        "1,000",
    )
    records = b"".join(
        (
            f"<Data><ItemNum>{index + 1:05d}</ItemNum>"
            f"<Benefit85>{spelling}</Benefit85></Data>"
        ).encode()
        for index, spelling in enumerate(native_spellings)
    )
    payload = b"<MBS_XML>" + records + b"</MBS_XML>"
    monkeypatch.setattr(command, "LEGACY_MBS_BYTES", len(payload))
    monkeypatch.setattr(
        command, "LEGACY_MBS_SHA256", hashlib.sha256(payload).hexdigest()
    )
    monkeypatch.setattr(command.httpx, "Client", _client_factory(payload))

    result = command.qualify(exact_commit="a" * 40)

    diagnostics = cast("dict[str, object]", result["quality_diagnostics"])
    probes = cast(
        "list[dict[str, object]]",
        diagnostics["invalid_amount_decimal_probe_source_ordinals"],
    )
    assert probes == [
        {
            "table": "benefits",
            "probe": "decimal_constructor_rejected",
            "source_ordinals": [3],
        },
        {
            "table": "benefits",
            "probe": "exponent_notation",
            "source_ordinals": [1],
        },
        {
            "table": "benefits",
            "probe": "surrounding_whitespace",
            "source_ordinals": [0],
        },
        {
            "table": "benefits",
            "probe": "underscore_separator",
            "source_ordinals": [2],
        },
    ]
    serialized = json.dumps(result)
    assert all(spelling not in serialized for spelling in native_spellings)
    assert diagnostics["source_values_included"] is False


@pytest.mark.parametrize("commit", ["", "A" * 40, "a" * 39, "z" * 40])
def test_requires_exact_lowercase_commit(commit: str) -> None:
    with pytest.raises(ValueError, match="exact commit"):
        command.qualify(exact_commit=commit)


def test_workflow_is_exact_main_read_only_and_never_publishes() -> None:
    workflow = (
        command.ROOT
        / ".github/workflows/australian-mbs-silver-qualification.yml"
    ).read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert "REQUESTED_COMMIT" in workflow
    assert 'test "${GITHUB_SHA}" = "${REQUESTED_COMMIT}"' in workflow
    assert "permissions: {}" in workflow
    assert "contents: read" in workflow
    assert "issue" not in workflow.lower()
    assert "publish" not in workflow.lower()
    assert "source-retained" not in workflow.lower()
