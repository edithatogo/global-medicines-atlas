"""Tests for the bounded, hosted-only NIPH report acquisition contract."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from pydantic import AnyHttpUrl

import global_medicines_atlas.norpd_private_acquisition as norpd_module
from global_medicines_atlas.nordic_utilisation_acquisition import (
    NordicAuthorization,
)
from global_medicines_atlas.norpd_private_acquisition import (
    PRIVATE_ARCHIVE,
    REPORT_URL,
    exercise_norpd_private_acquisition,
    require_norpd_authorization,
    validate_norpd_report,
)
from global_medicines_atlas.receipts import HttpRetrievalEvidence
from global_medicines_atlas.reuse_gate import (
    DiscoverySurface,
    DiscoverySurfaceState,
    ReuseDiscoverySnapshot,
    acquire_new_decision,
)

ROOT = Path(__file__).resolve().parents[1]
AUTHORIZATION = (
    ROOT
    / "quality/qualifications/nordic-utilisation-acquisition-authorization.json"
)
_NOW = datetime(2026, 10, 1, 12, tzinfo=UTC)
_PDF = b"%PDF-1.7\n% test-only anonymous aggregate report fixture\n%%EOF\n"


def _reuse():
    snapshot = ReuseDiscoverySnapshot(
        source_id="no-norpd-utilisation",
        generated_at=_NOW,
        freshness_seconds=86_400,
        tool_version="test/v1",
        surfaces=tuple(
            DiscoverySurface(
                name=name,
                state=DiscoverySurfaceState.SUCCESS,
                query="no-norpd-utilisation",
            )
            for name in (
                "local_clones",
                "github",
                "hugging_face",
                "source_registry",
            )
        ),
    )
    return acquire_new_decision("no-norpd-utilisation", snapshot=snapshot)


def _http_evidence():
    return HttpRetrievalEvidence(
        original_uri=AnyHttpUrl(REPORT_URL),
        final_uri=AnyHttpUrl(REPORT_URL),
        http_method="GET",
        http_status=200,
        content_type="application/pdf",
        observed_byte_length=len(_PDF),
        acquisition_agent_version="test/v1",
    )


def test_norpd_internal_authorization_is_dated_and_narrow() -> None:
    require_norpd_authorization(AUTHORIZATION)


def test_norpd_authorization_rejects_publication_scope_widening() -> None:
    raw = NordicAuthorization.model_validate_json(
        AUTHORIZATION.read_text(encoding="utf-8")
    ).model_dump(mode="json")
    norway = raw["sources"][1]
    norway["public_release_authorized"] = True
    with pytest.raises(
        ValueError, match="publication must remain separately gated"
    ):
        NordicAuthorization.model_validate(raw)


def test_norpd_authorization_rejects_source_identity_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def wrong_source(_path: Path) -> Any:
        return SimpleNamespace(
            sources=(None, SimpleNamespace(source_id="different-source"))
        )

    monkeypatch.setattr(
        norpd_module,
        "load_nordic_authorization",
        cast("Any", wrong_source),
    )
    with pytest.raises(ValueError, match="source identity drifted"):
        require_norpd_authorization(AUTHORIZATION)


def test_norpd_authorization_rejects_wrong_decision_date(
    tmp_path: Path,
) -> None:
    raw = json.loads(AUTHORIZATION.read_text(encoding="utf-8"))
    raw["sources"][1]["decision_date"] = "2026-09-30"
    altered = tmp_path / "authorization.json"
    altered.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(PermissionError, match="bounded internal decision"):
        require_norpd_authorization(altered)


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b"", "not a PDF"),
        (b"<!doctype html>", "not a PDF"),
        (b"%PDF-1.7\ntruncated", "end marker"),
    ],
)
def test_norpd_rejects_non_pdf_response(payload: bytes, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        validate_norpd_report(payload)


def test_norpd_rejects_oversized_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(norpd_module, "MAX_REPORT_BYTES", len(_PDF) - 1)
    with pytest.raises(ValueError, match="100 MB bound"):
        validate_norpd_report(_PDF)


def test_norpd_report_acquisition_lands_and_restores_exact_pdf(
    tmp_path: Path,
) -> None:
    manifest = exercise_norpd_private_acquisition(
        payload=_PDF,
        output_dir=tmp_path / "out",
        authorization_path=AUTHORIZATION,
        reuse_decision=_reuse(),
        http_evidence=_http_evidence(),
        observed_at=_NOW,
    )
    assert str(manifest.report_url) == REPORT_URL
    assert manifest.report_period == "2014-2018"
    assert manifest.payload_byte_count == len(_PDF)
    assert manifest.public_release_authorized is False
    assert manifest.external_publication_authorized is False
    assert manifest.clean_room_recovered_payload_count == 1
    assert (tmp_path / "out" / PRIVATE_ARCHIVE).is_file()


def test_norpd_requires_pinned_reuse_discovery(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="reuse gate required"):
        exercise_norpd_private_acquisition(
            payload=_PDF,
            output_dir=tmp_path / "out",
            authorization_path=AUTHORIZATION,
            reuse_decision=None,
            http_evidence=_http_evidence(),
            observed_at=_NOW,
        )


def test_norpd_requires_empty_output_directory(tmp_path: Path) -> None:
    output = tmp_path / "out"
    output.mkdir()
    (output / "preserve.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError, match="must not already exist"):
        exercise_norpd_private_acquisition(
            payload=_PDF,
            output_dir=output,
            authorization_path=AUTHORIZATION,
            reuse_decision=_reuse(),
            http_evidence=_http_evidence(),
            observed_at=_NOW,
        )


def test_norpd_requires_timezone_aware_retrieval(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        exercise_norpd_private_acquisition(
            payload=_PDF,
            output_dir=tmp_path / "out",
            authorization_path=AUTHORIZATION,
            reuse_decision=_reuse(),
            http_evidence=_http_evidence(),
            observed_at=datetime.fromisoformat("2026-10-01T00:00:00"),
        )


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"observed_byte_length": len(_PDF) + 1}, "byte count"),
        ({"http_status": 503}, "status is not successful"),
        ({"content_type": "text/html"}, "media type is not PDF"),
    ],
)
def test_norpd_rejects_http_evidence_drift(
    tmp_path: Path, change: dict[str, object], message: str
) -> None:
    evidence = _http_evidence().model_copy(update=change)
    with pytest.raises(ValueError, match=message):
        exercise_norpd_private_acquisition(
            payload=_PDF,
            output_dir=tmp_path / "out",
            authorization_path=AUTHORIZATION,
            reuse_decision=_reuse(),
            http_evidence=evidence,
            observed_at=_NOW,
        )


def test_norpd_rejects_nonlanding_admission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def not_landed(*args: object, **kwargs: object) -> None:
        del args, kwargs

    monkeypatch.setattr(
        norpd_module, "land_bronze_payload", cast("Any", not_landed)
    )
    with pytest.raises(TypeError, match="not admitted to Bronze"):
        exercise_norpd_private_acquisition(
            payload=_PDF,
            output_dir=tmp_path / "out",
            authorization_path=AUTHORIZATION,
            reuse_decision=_reuse(),
            http_evidence=_http_evidence(),
            observed_at=_NOW,
        )


def test_norpd_rejects_incomplete_clean_room_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def incomplete_recovery(
        _root: Path, *, fail_closed_on_incomplete: bool
    ) -> Any:
        del fail_closed_on_incomplete
        return SimpleNamespace(landings=())

    monkeypatch.setattr(
        norpd_module,
        "reconstruct_bronze",
        cast("Any", incomplete_recovery),
    )
    with pytest.raises(ValueError, match="recovery count drifted"):
        exercise_norpd_private_acquisition(
            payload=_PDF,
            output_dir=tmp_path / "out",
            authorization_path=AUTHORIZATION,
            reuse_decision=_reuse(),
            http_evidence=_http_evidence(),
            observed_at=_NOW,
        )
