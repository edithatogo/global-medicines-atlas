"""Contract tests for bounded Socialstyrelsen aggregate acquisition."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from scripts import acquire_sweden_socialstyrelsen_private as sweden_runner

from global_medicines_atlas.reuse_gate import (
    ReuseDisposition,
    evaluate_reuse_gate,
)
from global_medicines_atlas.sweden_socialstyrelsen_acquisition import (
    API_ROOT,
    MANIFEST,
    PRIVATE_ARCHIVE,
    SwedenQuery,
    exercise_sweden_private_acquisition,
    require_sweden_authorization,
    validate_sweden_response,
)

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[1]
AUTHORIZATION = (
    ROOT
    / "quality/qualifications/nordic-utilisation-acquisition-authorization.json"
)


def _empty_recovery(*_args: object, **_kwargs: object) -> SimpleNamespace:
    return SimpleNamespace(landings=())


def _reject_bronze_admission(*_args: object, **_kwargs: object) -> None:
    return None


def test_approved_query_is_bounded_and_records_exact_dimensions() -> None:
    query = SwedenQuery()
    assert query.cell_count == 90
    assert query.maximum_cells == 90
    assert query.source_parameters()["year"] == ["2025"]
    assert query.source_parameters()["measure_ids"] == [1, 2, 3, 4, 9]
    assert query.source_parameters()["atc_codes"] == ["TOTALT"]
    assert len(query.source_urls()) == 5
    assert all(
        url.startswith(API_ROOT + "/resultat/matt/")
        for url in query.source_urls()
    )


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"year": ("2024",)}, "year must match"),
        ({"measure_ids": (1,)}, "preserve all five"),
        ({"atc_codes": ("A", "B")}, "ATC scope"),
        ({"regions": ("0", "1")}, "dimensions exceed"),
        ({"maximum_cells": 89}, "declared cell bound"),
    ],
)
def test_query_rejects_scope_widening(
    change: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        SwedenQuery.model_validate(change)


def test_authorization_is_dated_and_publication_stays_off() -> None:
    require_sweden_authorization(AUTHORIZATION)


def test_runner_refuses_local_execution_before_source_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    with pytest.raises(SystemExit, match="only in GitHub Actions"):
        sweden_runner.main()


def test_runner_rejects_non_allowlisted_source_url() -> None:
    with pytest.raises(ValueError, match="outside the approved allowlist"):
        sweden_runner.fetch_socialstyrelsen_response(
            "http://example.invalid/result"
        )


@pytest.mark.parametrize("payload", [b"", b"null", b'"scalar"', b"{"])
def test_response_must_be_bounded_json_result_document(payload: bytes) -> None:
    with pytest.raises((ValueError, TypeError)):
        validate_sweden_response(payload)


def test_response_over_source_size_limit_is_rejected() -> None:
    with pytest.raises(ValueError, match="25 MB bound"):
        validate_sweden_response(b" " * 25_000_001)


def test_stale_decision_date_cannot_authorize_payloads(tmp_path: Path) -> None:
    raw = json.loads(AUTHORIZATION.read_text(encoding="utf-8"))
    raw["sources"][2]["decision_date"] = "2026-09-28"
    stale = tmp_path / "authorization.json"
    stale.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(PermissionError, match="approval date is not current"):
        require_sweden_authorization(stale)


def test_hosted_acquisition_refuses_wrong_response_count_before_writing(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="response count"):
        exercise_sweden_private_acquisition(
            payloads=(b"{}",),
            output_dir=tmp_path / "output",
            authorization_path=AUTHORIZATION,
            reuse_decision=None,
        )
    assert not (tmp_path / "output").exists()
    assert MANIFEST.endswith("manifest.json")
    assert PRIVATE_ARCHIVE.endswith(".private.tar")


def test_acquisition_requires_empty_destination_and_aware_timestamp(
    tmp_path: Path,
) -> None:
    output = tmp_path / "output"
    output.mkdir()
    (output / "preserve.txt").write_text("existing", encoding="utf-8")
    payloads = tuple(b'{"Results":[]}' for _ in range(5))
    with pytest.raises(FileExistsError, match="must be empty"):
        exercise_sweden_private_acquisition(
            payloads=payloads,
            output_dir=output,
            authorization_path=AUTHORIZATION,
            reuse_decision=None,
        )
    (output / "preserve.txt").unlink()
    with pytest.raises(ValueError, match="timezone-aware"):
        exercise_sweden_private_acquisition(
            payloads=payloads,
            output_dir=output,
            authorization_path=AUTHORIZATION,
            reuse_decision=None,
            observed_at=datetime(2026, 9, 29, tzinfo=UTC).replace(tzinfo=None),
        )


def test_recovery_count_mismatch_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reuse = evaluate_reuse_gate(
        "se-socialstyrelsen-utilisation",
        repository_root=ROOT,
        requested=ReuseDisposition.ACQUIRE_NEW,
        github_index={},
        huggingface_index={},
        huggingface_revisions={},
    )
    monkeypatch.setattr(
        "global_medicines_atlas.sweden_socialstyrelsen_acquisition.reconstruct_bronze",
        _empty_recovery,
    )
    with pytest.raises(ValueError, match="recovery count"):
        exercise_sweden_private_acquisition(
            payloads=tuple(b'{"Results":[]}' for _ in range(5)),
            output_dir=tmp_path / "output",
            authorization_path=AUTHORIZATION,
            reuse_decision=reuse,
        )


def test_non_bronze_admission_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reuse = evaluate_reuse_gate(
        "se-socialstyrelsen-utilisation",
        repository_root=ROOT,
        requested=ReuseDisposition.ACQUIRE_NEW,
        github_index={},
        huggingface_index={},
        huggingface_revisions={},
    )
    monkeypatch.setattr(
        "global_medicines_atlas.sweden_socialstyrelsen_acquisition.land_bronze_payload",
        _reject_bronze_admission,
    )
    with pytest.raises(TypeError, match="not admitted to Bronze"):
        exercise_sweden_private_acquisition(
            payloads=tuple(b'{"Results":[]}' for _ in range(5)),
            output_dir=tmp_path / "output",
            authorization_path=AUTHORIZATION,
            reuse_decision=reuse,
        )


def test_synthetic_acquisition_lands_and_recovers_all_measure_responses(
    tmp_path: Path,
) -> None:
    reuse = evaluate_reuse_gate(
        "se-socialstyrelsen-utilisation",
        repository_root=ROOT,
        requested=ReuseDisposition.ACQUIRE_NEW,
        github_index={},
        huggingface_index={},
        huggingface_revisions={},
    )
    output = tmp_path / "output"
    manifest = exercise_sweden_private_acquisition(
        payloads=tuple(b'{"Results":[]}' for _ in range(5)),
        output_dir=output,
        authorization_path=AUTHORIZATION,
        reuse_decision=reuse,
    )
    assert manifest.clean_room_recovered_payload_count == 5
    assert len(manifest.payload_sha256) == 5
    assert manifest.public_release_authorized is False
    assert manifest.external_publication_authorized is False
    assert (output / PRIVATE_ARCHIVE).is_file()
    assert (output / MANIFEST).is_file()
    receipts = tuple(
        (
            output / "corpus/bronze/acquisitions/se-socialstyrelsen-utilisation"
        ).glob("*.json")
    )
    assert len(receipts) == 5
    for receipt_path in receipts:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        assert receipt["rights_state"] == "unknown"
        assert receipt["rights_policy"]["retain_evidence"] == "permitted"
        assert receipt["rights_policy"]["publish_bytes"] == "prohibited"
        assert receipt["rights_policy"]["transform"] == "unknown"
        assert receipt["rights_policy"]["maintainer_licence_approved"] is False
        assert (
            receipt["rights_policy"]["maintainer_publication_approved"] is False
        )
