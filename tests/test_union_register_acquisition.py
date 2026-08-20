"""Contracts for fail-closed EU Union Register acquisition."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pyarrow.parquet as pq
import pytest
from pydantic import ValidationError

from global_medicines_atlas.union_register_acquisition import (
    UnionRegisterAuthorization,
    exercise_union_register,
    union_register_source_record_batch,
)

ROOT = Path(__file__).resolve().parents[1]
AUTHORIZATION = (
    ROOT / "quality/qualifications/union-register-live-authorization.json"
)


def _authorization() -> dict[str, object]:
    return json.loads(AUTHORIZATION.read_text(encoding="utf-8"))


def _approve(tmp_path: Path) -> Path:
    value = _authorization()
    value.update(
        acquisition_authorized=True,
        internal_retention_authorized=True,
        maintainer_licence_approved=True,
        decision_basis="Maintainer-approved test-only internal exercise.",
    )
    path = tmp_path / "authorization.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_committed_authorization_is_exact_and_blocked() -> None:
    authorization = UnionRegisterAuthorization.model_validate_json(
        AUTHORIZATION.read_bytes()
    )

    assert authorization.acquisition_authorized is False
    assert authorization.internal_retention_authorized is False
    assert authorization.maintainer_licence_approved is False
    assert authorization.public_release_authorized is False
    assert authorization.external_publication_authorized is False


def test_blocked_runner_never_calls_transport_or_creates_output(
    tmp_path: Path,
) -> None:
    called = False

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(500)

    output = tmp_path / "output"
    with pytest.raises(PermissionError, match="maintainer licence approval"):
        exercise_union_register(
            repository_root=ROOT,
            output_dir=output,
            authorization_path=AUTHORIZATION,
            transport=httpx.MockTransport(handler),
        )

    assert called is False
    assert output.exists() is False


@pytest.mark.parametrize(
    "updates",
    [
        {"public_release_authorized": True},
        {"external_publication_authorized": True},
        {"dataset_url": "https://example.invalid/products.json"},
        {"licence_url": "https://example.invalid/licence"},
        {"acquisition_authorized": True},
        {"coverage_complete": True},
    ],
)
def test_authorization_fails_closed_on_scope_drift(
    updates: dict[str, object],
) -> None:
    value = _authorization() | updates
    with pytest.raises(ValidationError):
        UnionRegisterAuthorization.model_validate(value)


@pytest.mark.parametrize(
    ("source_id", "media_hint", "document", "message"),
    [
        ("different", "json", {"data": []}, None),
        ("eu-union-register", "json", [], "only a data array"),
        ("eu-union-register", "json", {"data": [], "extra": 1}, "only"),
        ("eu-union-register", "json", {"data": []}, "non-empty"),
        ("eu-union-register", "json", {"data": ["row"]}, "objects"),
        ("eu-union-register", "json", {"data": [{}]}, "requires a URI"),
        (
            "eu-union-register",
            "json",
            {"data": [{"URI": "same"}, {"URI": "same"}]},
            "must be unique",
        ),
    ],
)
def test_source_record_projection_fails_closed_on_schema_drift(
    source_id: str,
    media_hint: str,
    document: object,
    message: str | None,
) -> None:
    payload = json.dumps(document).encode()
    if message is None:
        assert (
            union_register_source_record_batch(source_id, payload, media_hint)
            is None
        )
        return
    with pytest.raises((TypeError, ValueError), match=message):
        union_register_source_record_batch(source_id, payload, media_hint)


def test_runner_lands_projects_recovers_and_archives_representative_corpus(
    tmp_path: Path,
) -> None:
    payload = json.dumps({
        "data": [
            {
                "URI": "https://example.test/1",
                "Type": "Human",
                "Name": [{"LanguageCode": "EN", "Text": "Medicine A"}],
                "Status": "Authorised",
                "EUNumber": "EU/1/00/001",
                "ATC": ["A01AA"],
                "AuthorisationDate": "2026-01-02",
            },
            {
                "URI": "https://example.test/2",
                "Type": "Orphan designation",
                "Name": [{"LanguageCode": "EN", "Text": "Medicine B"}],
                "Status": "Refused",
                "EUNumber": None,
                "ATC": [],
                "AuthorisationDate": None,
            },
        ]
    }).encode()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=payload, headers={"content-type": "application/json"}
        )

    output = tmp_path / "output"
    manifest = exercise_union_register(
        repository_root=ROOT,
        output_dir=output,
        authorization_path=_approve(tmp_path),
        transport=httpx.MockTransport(handler),
        observed_at=datetime(2026, 8, 21, tzinfo=UTC),
    )

    assert manifest.source_record_rows == 2
    assert manifest.recovered_count == 1
    assert manifest.recovered_source_record_projection_count == 1
    assert manifest.external_publication_performed is False
    assert (output / "union-register-live.private.tar").is_file()
    original = next(
        (output / "runs/corpus/bronze/parquet").rglob("source_records.parquet")
    )
    recovered = next(
        (output / "runs/corpus/clean-room/parquet").rglob(
            "source_records.parquet"
        )
    )
    assert original.read_bytes() == recovered.read_bytes()
    table = pq.read_table(original)
    assert table.column("EUNumber").to_pylist() == ["EU/1/00/001", None]
    assert table.column("ATC").to_pylist() == [["A01AA"], []]
    assert (
        (output / "SHA256SUMS").read_text().startswith(manifest.archive_sha256)
    )
