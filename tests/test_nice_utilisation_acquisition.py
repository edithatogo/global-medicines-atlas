"""Tests for the historic NHS NICE-utilisation acquisition gate."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from scripts import acquire_nice_utilisation_private as acquisition_script

from global_medicines_atlas.nice_utilisation_acquisition import (
    NICE_UTILISATION_ARTIFACTS,
    NICEUtilisationAuthorization,
    inspect_nice_utilisation_payload,
)

AUTHORIZATION = (
    Path(__file__).resolve().parents[1]
    / "quality/qualifications/nice-utilisation-acquisition-authorization.json"
)


def _raw() -> dict[str, object]:
    return json.loads(AUTHORIZATION.read_text(encoding="utf-8"))


def test_inventory_locks_the_discontinued_four_release_series() -> None:
    authorization = NICEUtilisationAuthorization.model_validate(_raw())
    assert [item.label for item in authorization.releases] == [
        "2008",
        "2009",
        "2010-and-2011",
        "2012",
    ]
    assert authorization.releases[-1].corrected_after_publication is True
    authorization.require_payload_authority()
    assert authorization.acquisition_authorized is True
    assert authorization.internal_retention_authorized is True
    assert authorization.public_release_authorized is False
    assert authorization.external_publication_authorized is False


@pytest.mark.parametrize(
    ("update", "message"),
    [
        (
            {"internal_retention_authorized": False},
            "requires dated authority",
        ),
        ({"public_release_authorized": True}, "separately gated"),
        ({"series_url": "https://example.test/series"}, "official NHS hosts"),
    ],
)
def test_authorization_rejects_scope_widening(
    update: dict[str, object], message: str
) -> None:
    raw = _raw()
    raw.update(update)
    with pytest.raises(ValidationError, match=message):
        NICEUtilisationAuthorization.model_validate(raw)


def test_release_inventory_and_correction_cannot_drift() -> None:
    raw = _raw()
    raw["releases"] = list(raw["releases"])[:-1]  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="all four historic releases"):
        NICEUtilisationAuthorization.model_validate(raw)
    raw = _raw()
    releases = list(raw["releases"])  # type: ignore[arg-type]
    releases[-1] = {**releases[-1], "corrected_after_publication": False}
    raw["releases"] = releases
    with pytest.raises(
        ValidationError, match="correction must remain explicit"
    ):
        NICEUtilisationAuthorization.model_validate(raw)

    raw = _raw()
    releases = list(raw["releases"])  # type: ignore[arg-type]
    releases[0] = {**releases[0], "label": "2009"}
    raw["releases"] = releases
    with pytest.raises(
        ValidationError, match="historic release sequence drifted"
    ):
        NICEUtilisationAuthorization.model_validate(raw)


@pytest.mark.parametrize(
    ("update", "message"),
    [
        ({"publication_url": "https://example.test/release"}, "digital.nhs.uk"),
        ({"period_start": "2008-01-02"}, "period must be ordered"),
    ],
)
def test_release_rejects_host_and_period_drift(
    update: dict[str, object], message: str
) -> None:
    raw = _raw()
    releases = list(raw["releases"])  # type: ignore[arg-type]
    releases[0] = {**releases[0], **update}
    raw["releases"] = releases
    with pytest.raises(ValidationError, match=message):
        NICEUtilisationAuthorization.model_validate(raw)


def test_approved_internal_scope_requires_date_and_retention() -> None:
    raw = _raw()
    raw.update({
        "decision_status": "approved_internal",
        "decision_date": "2026-08-21",
        "acquisition_authorized": True,
        "internal_retention_authorized": True,
    })
    NICEUtilisationAuthorization.model_validate(raw).require_payload_authority()
    raw["decision_date"] = None
    with pytest.raises(ValidationError, match="requires dated authority"):
        NICEUtilisationAuthorization.model_validate(raw)


def test_exact_private_artifact_inventory_is_fail_closed() -> None:
    assert len(NICE_UTILISATION_ARTIFACTS) == 15
    assert {item.release_label for item in NICE_UTILISATION_ARTIFACTS} == {
        "2008",
        "2009",
        "2010-and-2011",
        "2012",
    }
    assert (
        sum(item.source_record_eligible for item in NICE_UTILISATION_ARTIFACTS)
        == 1
    )
    assert all(
        item.url.host == "files.digital.nhs.uk"
        for item in NICE_UTILISATION_ARTIFACTS
    )
    assert all(
        item.publication_authorized is False
        for item in NICE_UTILISATION_ARTIFACTS
    )


@pytest.mark.parametrize(
    ("filename", "payload", "expected_media"),
    [
        ("report.pdf", b"%PDF-1.7\nfixture", "pdf"),
        (
            "tables.xlsx",
            b"PK\x03\x04fixture-xl/workbook.xml-fixture",
            "xlsx",
        ),
        ("feedback.doc", b"\xd0\xcf\x11\xe0fixture", "doc"),
    ],
)
def test_payload_inspection_rejects_extension_magic_mismatch(
    filename: str, payload: bytes, expected_media: str
) -> None:
    assert inspect_nice_utilisation_payload(filename, payload) == expected_media
    with pytest.raises(ValueError, match="does not match"):
        inspect_nice_utilisation_payload(filename, b"not the declared format")


def test_private_runner_lands_and_clean_room_restores_exact_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = NICE_UTILISATION_ARTIFACTS[0]
    payload = b"%PDF-1.7\nprivate governed fixture"
    input_dir = tmp_path / "input"
    source_path = input_dir / artifact.release_label / artifact.filename
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(payload)
    monkeypatch.setattr(
        acquisition_script, "NICE_UTILISATION_ARTIFACTS", (artifact,)
    )

    result = acquisition_script.acquire(
        input_dir, tmp_path / "output", download=False
    )

    assert result["file_count"] == 1
    assert result["restore_verified"] is True
    assert result["restore_verified_payload_count"] == 1
    assert result["publication_authorized"] is False
    assert result["external_publication_authorized"] is False
    assert Path(str(result["archive_path"])).is_file()
    assert len(str(result["archive_sha256"])) == 64


def test_private_runner_downloads_only_missing_reviewed_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = NICE_UTILISATION_ARTIFACTS[0]
    payload = b"%PDF-1.7\ndownloaded fixture"
    requests: list[str] = []

    class Response:
        content = payload

        @staticmethod
        def raise_for_status() -> None:
            return None

    class Client:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> Client:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        @staticmethod
        def get(url: str) -> Response:
            requests.append(url)
            return Response()

    monkeypatch.setattr(
        acquisition_script, "NICE_UTILISATION_ARTIFACTS", (artifact,)
    )
    monkeypatch.setattr(acquisition_script.httpx, "Client", Client)

    acquisition_script._retrieve(tmp_path)
    acquisition_script._retrieve(tmp_path)

    assert requests == [str(artifact.url)]
    assert (
        tmp_path / artifact.release_label / artifact.filename
    ).read_bytes() == payload
