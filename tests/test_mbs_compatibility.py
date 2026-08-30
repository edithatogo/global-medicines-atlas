"""Historical monthly scraper contracts and no-data failure regression."""

from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from global_medicines_atlas.mbs_compatibility import (
    ProbeRehearsal,
    historical_targets,
    month_range,
    rehearse_probes,
)
from global_medicines_atlas.receipts import EvidenceClass, FailureReceipt
from global_medicines_atlas.reuse_gate import acquire_new_decision

NOW = datetime(2026, 8, 30, tzinfo=UTC)


def test_rehearsal_cannot_accept_a_success_claim() -> None:
    locked = {field.name: field.init for field in fields(ProbeRehearsal)}
    assert locked["data_acquired"] is False
    assert locked["qualification_status"] is False


def test_month_range_is_inclusive_across_years() -> None:
    assert month_range(202312, 202402) == (202312, 202401, 202402)


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (202400, 202402),
        (202413, 202501),
        (202402, 202401),
        (190001, 202601),
        (True, 202401),
    ],
)
def test_invalid_or_unbounded_month_ranges(start: int, end: int) -> None:
    with pytest.raises((ValueError, TypeError), match=r"month|range"):
        month_range(start, end)


def test_historical_urls_and_filenames_preserve_donor_order() -> None:
    targets = historical_targets(("104", "205"), 202401, 202402)
    assert len(targets) == 6
    assert targets[0].filename == "item_104_202401.html"
    assert targets[1].filename == "item_205_202401.html"
    assert targets[-1].filename == "participants_202402.html"
    assert targets[0].url.endswith("/Content/item104-202401")
    assert targets[-1].url.endswith("/Content/participants-202402")


@pytest.mark.parametrize(
    "items", [("../1",), ("\u0661",), ("",), ("1", "1"), ("1234567",)]
)
def test_item_identity_cannot_inject_path(items: tuple[str, ...]) -> None:
    with pytest.raises(ValueError, match="item"):
        historical_targets(items, 202401, 202401)


def test_six_404s_are_failed_data_not_success(tmp_path: Path) -> None:
    targets = historical_targets(("104", "205"), 202401, 202402)
    delays: list[float] = []
    results = rehearse_probes(
        targets,
        tmp_path,
        transport=httpx.MockTransport(lambda _: httpx.Response(404)),
        reuse_decision=acquire_new_decision("au-mbs"),
        clock=lambda: NOW,
        sleep=delays.append,
    )
    assert not results.data_acquired
    assert results.failed_count == 6
    assert len(results.attempts) == 6
    assert len({attempt.receipt_id for attempt in results.attempts}) == 6
    assert all(
        attempt.evidence_class is EvidenceClass.SYNTHETIC
        for attempt in results.attempts
    )
    assert all(
        isinstance(attempt, FailureReceipt) for attempt in results.attempts
    )
    assert all(
        attempt.failure_message == "HTTP status 404"
        for attempt in results.attempts
        if isinstance(attempt, FailureReceipt)
    )
    assert len(delays) == 5
    assert all(delay >= 0.1 for delay in delays)
    assert not list(tmp_path.rglob("*.html"))


def test_timeout_retries_are_bounded_and_receipted(tmp_path: Path) -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("fixture timeout", request=request)

    result = rehearse_probes(
        historical_targets((), 202401, 202401),
        tmp_path,
        transport=httpx.MockTransport(timeout),
        reuse_decision=acquire_new_decision("au-mbs"),
        clock=lambda: NOW,
        sleep=lambda _: None,
    )
    assert len(result.attempts) == 3
    assert len({attempt.receipt_id for attempt in result.attempts}) == 3
    assert result.failed_count == 1
    assert result.empty_count == 0
    assert not result.data_acquired


def test_empty_response_is_not_acquisition(tmp_path: Path) -> None:
    result = rehearse_probes(
        historical_targets((), 202401, 202401),
        tmp_path,
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200, content=b"", headers={"content-type": "text/html"}
            )
        ),
        reuse_decision=acquire_new_decision("au-mbs"),
        clock=lambda: NOW,
        sleep=lambda _: None,
    )
    assert not result.data_acquired
    assert result.failed_count == 1
    assert result.empty_count == 1


def test_target_count_is_bounded() -> None:
    with pytest.raises(ValueError, match="request count"):
        historical_targets(tuple(str(i) for i in range(10)), 190001, 199912)


def test_rehearsal_rejects_network_transport(tmp_path: Path) -> None:
    with pytest.raises(TypeError, match="MockTransport"):
        rehearse_probes(
            historical_targets((), 202401, 202401),
            tmp_path,
            transport=httpx.HTTPTransport(),
            reuse_decision=acquire_new_decision("au-mbs"),
            clock=lambda: NOW,
            sleep=lambda _: None,
        )


@pytest.mark.parametrize("count", [0, 2])
def test_rehearsal_rejects_empty_or_duplicate_targets(
    tmp_path: Path, count: int
) -> None:
    targets = historical_targets((), 202401, 202401) * count
    with pytest.raises(ValueError, match="nonempty, unique and bounded"):
        rehearse_probes(
            targets,
            tmp_path,
            transport=httpx.MockTransport(lambda _: httpx.Response(404)),
            reuse_decision=acquire_new_decision("au-mbs"),
            clock=lambda: NOW,
            sleep=lambda _: None,
        )


def test_successful_download_is_not_yet_qualified_data(tmp_path: Path) -> None:
    result = rehearse_probes(
        historical_targets((), 202401, 202401),
        tmp_path,
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                content=b"<html>maintenance</html>",
                headers={"content-type": "text/html"},
            )
        ),
        reuse_decision=acquire_new_decision("au-mbs"),
        clock=lambda: NOW,
        sleep=lambda _: None,
    )
    assert not result.data_acquired
    assert result.downloaded_count == 1
    assert result.qualification_status == "table_admission_pending"
