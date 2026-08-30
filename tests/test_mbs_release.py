"""Hosted current-release acquisition preserves raw bytes and honest admission."""

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from global_medicines_atlas.adapters.au_mbs import parse_mbs_source_xml
from global_medicines_atlas.mbs_release import (
    MbsReleaseContract,
    mbs_source_parquet,
    require_mbs_hosted_authority,
    stage_mbs_release,
)
from global_medicines_atlas.receipts import EvidenceClass, SourceReceipt
from global_medicines_atlas.reuse_gate import acquire_new_decision

NOW = datetime(2026, 8, 30, tzinfo=UTC)
CONTRACT = Path("quality/qualifications/mbs-current-release-contract.json")
PAYLOAD = (
    b"<MBS_XML><Data><ItemNum>00104</ItemNum><Group>P7</Group></Data></MBS_XML>"
)


def test_local_live_acquisition_is_closed(tmp_path: Path) -> None:
    contract = MbsReleaseContract.model_validate_json(CONTRACT.read_bytes())
    with pytest.raises(ValueError, match="GitHub Actions"):
        stage_mbs_release(
            contract,
            tmp_path,
            clock=lambda: NOW,
            reuse_decision=acquire_new_decision("au-mbs"),
        )


def test_non_mock_local_transport_is_rejected(tmp_path: Path) -> None:
    contract = MbsReleaseContract.model_validate_json(CONTRACT.read_bytes())
    with (
        httpx.HTTPTransport() as transport,
        pytest.raises(TypeError, match="MockTransport"),
    ):
        stage_mbs_release(
            contract,
            tmp_path,
            reuse_decision=acquire_new_decision("au-mbs"),
            transport=transport,
        )


@pytest.mark.parametrize("payload", [PAYLOAD, b"<html>Maintenance</html>", b""])
def test_mock_stage_preserves_raw_and_separates_admission(
    tmp_path: Path, payload: bytes
) -> None:
    contract = MbsReleaseContract.model_validate_json(CONTRACT.read_bytes())
    stage = stage_mbs_release(
        contract,
        tmp_path,
        reuse_decision=acquire_new_decision("au-mbs"),
        clock=lambda: NOW,
        sleep=lambda _: None,
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200, content=payload, headers={"content-type": "text/xml"}
            )
        ),
    )
    assert stage.manifest.data_acquired is False
    assert stage.manifest.evidence_class == "synthetic"
    assert stage.manifest.admission_state == (
        "accepted" if payload == PAYLOAD else "quarantined"
    )
    raw = [item for item in stage.manifest.objects if item.role == "raw"]
    assert len(raw) == 1
    assert (stage.path / raw[0].path).read_bytes() == payload


def test_retry_budget_retains_failures_without_claiming_data(
    tmp_path: Path,
) -> None:
    def timeout(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("fixture timeout")

    delays: list[float] = []
    stage = stage_mbs_release(
        MbsReleaseContract.model_validate_json(CONTRACT.read_bytes()),
        tmp_path,
        reuse_decision=acquire_new_decision("au-mbs"),
        clock=lambda: NOW,
        sleep=delays.append,
        transport=httpx.MockTransport(timeout),
    )
    assert delays == [2, 2]
    assert stage.manifest.admission_state == "unavailable"
    assert len(stage.manifest.objects) == 3
    assert all(item.role == "attempt" for item in stage.manifest.objects)


def test_unknown_release_surface_and_unapproved_hosted_run_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = MbsReleaseContract.model_validate_json(CONTRACT.read_bytes())
    wrong = contract.model_dump(mode="json")
    wrong["source_url"] = "https://example.org/data.xml"
    with pytest.raises(ValueError, match="exact official"):
        MbsReleaseContract.model_validate(wrong)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", "edithatogo/global-medicines-atlas")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    with pytest.raises(ValueError, match="not authorized"):
        require_mbs_hosted_authority(
            contract.model_copy(update={"publication_authorized": False})
        )


def test_live_policy_with_stubbed_acquisition_and_deterministic_parquet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    contract = MbsReleaseContract.model_validate_json(CONTRACT.read_bytes())
    fixture = stage_mbs_release(
        contract,
        tmp_path / "fixture",
        reuse_decision=acquire_new_decision("au-mbs"),
        clock=lambda: NOW,
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200, content=PAYLOAD, headers={"content-type": "text/xml"}
            )
        ),
    )
    receipt_object = next(
        item
        for item in fixture.manifest.objects
        if item.role == "source_receipt"
    )
    receipt = SourceReceipt.model_validate_json(
        (fixture.path / receipt_object.path).read_bytes()
    )
    batch = parse_mbs_source_xml(PAYLOAD, receipt)
    assert mbs_source_parquet(batch) == mbs_source_parquet(batch)
    for name, value in {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": "edithatogo/global-medicines-atlas",
        "GITHUB_REF": "refs/heads/main",
    }.items():
        monkeypatch.setenv(name, value)

    def acquire(
        _source_id: str,
        destination: Path,
        *,
        repository_root: Path,
        **_kwargs: object,
    ) -> SourceReceipt:
        (repository_root / destination).write_bytes(PAYLOAD)
        return receipt.model_copy(update={"evidence_class": EvidenceClass.LIVE})

    monkeypatch.setattr(
        "global_medicines_atlas.mbs_release.acquire_source", acquire
    )
    live = stage_mbs_release(
        contract.model_copy(update={"publication_authorized": True}),
        tmp_path / "live",
        reuse_decision=acquire_new_decision("au-mbs"),
        clock=lambda: NOW,
    )
    assert live.manifest.record_count == live.manifest.p7_record_count == 1
    assert live.manifest.data_acquired is False
    assert any(item.role == "source_health" for item in live.manifest.objects)
    assert not (live.path / "source.xml").exists()
    saved = next(
        item for item in live.manifest.objects if item.role == "source_receipt"
    )
    source = SourceReceipt.model_validate_json(
        (live.path / saved.path).read_bytes()
    )
    assert source.rights_state.value == "permitted"
    assert source.temporal is not None
    assert source.temporal.source_version == "2026-08-01"
