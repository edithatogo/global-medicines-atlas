from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest

from global_medicines_atlas.countries import SourceDimension
from global_medicines_atlas.source_catalog import (
    AccessMode,
    MedicineDataSource,
    SourceReadiness,
)
from global_medicines_atlas.source_health import (
    ProbeState,
    SchemaDriftState,
    assess_schema_drift,
    compare_schema_fingerprints,
    drift_report_json,
    fingerprint_baseline,
    observations_json,
    probe_source,
    probe_sources,
    schema_fingerprint,
)

NOW = datetime(2026, 7, 29, tzinfo=UTC)


def source(
    *,
    source_id: str = "example",
    access_mode: AccessMode = AccessMode.API,
    readiness: SourceReadiness = SourceReadiness.CANDIDATE,
) -> MedicineDataSource:
    return MedicineDataSource(
        source_id=source_id,
        jurisdictions=("NZL",),
        authority="Example authority",
        title="Example source",
        dimension=SourceDimension.REGULATORY,
        access_mode=access_mode,
        landing_page="https://example.test/",
        api_url=(
            "https://example.test/api"
            if access_mode in {AccessMode.API, AccessMode.API_AND_DOWNLOAD}
            else None
        ),
        download_url=(
            "https://example.test/data.csv"
            if access_mode in {AccessMode.DOWNLOAD, AccessMode.API_AND_DOWNLOAD}
            else None
        ),
        update_cadence="weekly",
        rights_status="review pending",
        readiness=readiness,
        evidence_limit="health is not evidence of completeness",
    )


def test_probe_is_bounded_and_returns_schema_metadata_only() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["range"] == "bytes=0-127"
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json={"records": [{"name": "one", "active": True}]},
        )

    result = probe_source(
        source(),
        checked_at=NOW,
        transport=httpx.MockTransport(handler),
        max_bytes=128,
    )

    assert result.state is ProbeState.AVAILABLE
    assert result.schema_fingerprint is not None
    assert 0 < result.bytes_sampled <= 128
    assert "one" not in observations_json((result,))


@pytest.mark.parametrize(
    ("access_mode", "readiness", "expected"),
    [
        (
            AccessMode.LICENSED_FEED,
            SourceReadiness.BLOCKED,
            ProbeState.BLOCKED,
        ),
        (
            AccessMode.WEB_SEARCH,
            SourceReadiness.CANDIDATE,
            ProbeState.UNAVAILABLE,
        ),
    ],
)
def test_non_probeable_sources_are_explicit(
    access_mode: AccessMode,
    readiness: SourceReadiness,
    expected: ProbeState,
) -> None:
    result = probe_source(
        source(access_mode=access_mode, readiness=readiness),
        checked_at=NOW,
        transport=httpx.MockTransport(
            lambda _request: pytest.fail("network must not be called")
        ),
    )
    assert result.state is expected
    assert result.bytes_sampled == 0


def test_http_failure_is_unavailable_without_raising() -> None:
    result = probe_source(
        source(),
        checked_at=NOW,
        transport=httpx.MockTransport(lambda _request: httpx.Response(503)),
    )
    assert result.state is ProbeState.UNAVAILABLE
    assert result.status_code == 503
    assert result.schema_fingerprint is None


def test_redirect_is_not_followed() -> None:
    result = probe_source(
        source(),
        checked_at=NOW,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                302, headers={"location": "https://other.test/"}
            )
        ),
    )
    assert result.state is ProbeState.UNAVAILABLE
    assert result.status_code == 302


def test_schema_fingerprint_ignores_json_values_and_mapping_order() -> None:
    first = schema_fingerprint(
        b'{"name":"one","active":true}',
        content_type="application/json",
    )
    second = schema_fingerprint(
        b'{"active":false,"name":"two"}',
        content_type="application/json; charset=utf-8",
    )
    assert first == second


def test_schema_fingerprint_tracks_csv_header_changes() -> None:
    first = schema_fingerprint(b"id,name\n1,one\n", content_type="text/csv")
    second = schema_fingerprint(
        b"id,name,status\n1,one,active\n",
        content_type="text/csv",
    )
    assert first != second


@pytest.mark.parametrize(
    ("payload", "content_type"),
    [
        (b"", "text/csv"),
        (b"<root><item /></root>", "application/xml"),
        (b"\x00\x01", "application/octet-stream"),
        (b'[null, 1.5, "value"]', "application/json"),
    ],
)
def test_schema_fingerprint_supports_bounded_source_shapes(
    payload: bytes,
    content_type: str,
) -> None:
    assert len(schema_fingerprint(payload, content_type=content_type)) == 64


@pytest.mark.parametrize(
    "payload",
    [
        b"<!DOCTYPE root><root />",
        b"plain text without tags",
    ],
)
def test_unsafe_or_invalid_xml_is_rejected(payload: bytes) -> None:
    with pytest.raises(
        ValueError,
        match=r"declarations are not fingerprinted|contains no element tags",
    ):
        schema_fingerprint(payload, content_type="application/xml")


def test_truncated_response_is_available_without_schema_claim() -> None:
    result = probe_source(
        source(),
        checked_at=NOW,
        max_bytes=8,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                headers={"content-type": "application/json"},
                content=b'{"records":[{"id":1}]}',
            )
        ),
    )
    assert result.state is ProbeState.AVAILABLE
    assert result.bytes_sampled == 8
    assert result.schema_fingerprint is None
    assert "truncated" in result.detail


def test_download_endpoint_and_transport_failure_are_fail_honest() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/data.csv"
        raise httpx.ConnectError("offline", request=request)

    result = probe_source(
        source(access_mode=AccessMode.DOWNLOAD),
        checked_at=NOW,
        transport=httpx.MockTransport(handler),
    )
    assert result.state is ProbeState.UNAVAILABLE
    assert result.status_code is None


def test_catalog_blocked_api_is_not_probed() -> None:
    result = probe_source(
        source(readiness=SourceReadiness.BLOCKED),
        checked_at=NOW,
        transport=httpx.MockTransport(
            lambda _request: pytest.fail("network must not be called")
        ),
    )
    assert result.state is ProbeState.BLOCKED
    assert "catalog" in result.detail


def test_schema_drift_requires_two_comparable_fingerprints() -> None:
    observations = probe_sources(
        (source(source_id="b"), source(source_id="a")),
        checked_at=NOW,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                headers={"content-type": "application/json"},
                json={"id": 1},
            )
        ),
    )
    assert [item.source_id for item in observations] == ["a", "b"]
    assert compare_schema_fingerprints(
        observations,
        {"a": "0" * 64},
    ) == {"a": observations[0].schema_fingerprint}


def test_drift_assessment_distinguishes_changed_and_unavailable() -> None:
    available = probe_source(
        source(source_id="changed"),
        checked_at=NOW,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                headers={"content-type": "application/json"},
                json={"new_field": 1},
            )
        ),
    )
    unavailable = probe_source(
        source(source_id="offline"),
        checked_at=NOW,
        transport=httpx.MockTransport(lambda _request: httpx.Response(503)),
    )
    assessments = assess_schema_drift(
        (available, unavailable),
        {"changed": "0" * 64, "offline": "1" * 64},
    )
    assert assessments[0].state is SchemaDriftState.CHANGED
    assert assessments[1].state is SchemaDriftState.UNAVAILABLE
    assert "no schema-change claim" in assessments[1].detail


def test_drift_assessment_covers_unchanged_no_baseline_and_blocked() -> None:
    available = probe_source(
        source(source_id="stable"),
        checked_at=NOW,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                headers={"content-type": "text/csv"},
                content=b"id,name\n1,example\n",
            )
        ),
    )
    new = available.model_copy(update={"source_id": "new"})
    blocked = probe_source(
        source(
            source_id="licensed",
            access_mode=AccessMode.LICENSED_FEED,
            readiness=SourceReadiness.BLOCKED,
        ),
        checked_at=NOW,
    )
    assessments = assess_schema_drift(
        (available, new, blocked),
        {"stable": available.schema_fingerprint},
    )
    states = {item.source_id: item.state for item in assessments}
    assert states == {
        "licensed": SchemaDriftState.BLOCKED,
        "new": SchemaDriftState.NO_BASELINE,
        "stable": SchemaDriftState.UNCHANGED,
    }


def test_durable_report_contains_only_metadata_and_reusable_baseline() -> None:
    observation = probe_source(
        source(),
        checked_at=NOW,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                headers={"content-type": "application/json"},
                json={"secret_value": "must-not-persist"},
            )
        ),
    )
    assessments = assess_schema_drift((observation,), {})
    report_text = drift_report_json((observation,), assessments)
    report = json.loads(report_text)

    assert report["baseline"] == fingerprint_baseline((observation,))
    assert report["summary"]["no_baseline"] == 1
    assert "secret_value" not in report_text
    assert "must-not-persist" not in report_text
    assert set(report) == {
        "baseline",
        "observations",
        "schema_drift",
        "schema_version",
        "summary",
    }


def test_serialized_observations_are_valid_metadata_only_json() -> None:
    blocked = probe_source(
        source(
            access_mode=AccessMode.LICENSED_FEED,
            readiness=SourceReadiness.BLOCKED,
        ),
        checked_at=NOW,
    )
    payload = json.loads(observations_json((blocked,)))
    assert payload[0]["state"] == "blocked"
    assert set(payload[0]).isdisjoint({"payload", "body", "content"})


def test_invalid_bounds_are_rejected_without_network() -> None:
    with pytest.raises(ValueError, match="max_bytes"):
        probe_source(source(), checked_at=NOW, max_bytes=0)
