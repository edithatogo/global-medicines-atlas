from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from scripts.check_source_health import (
    BaselineProvenance,
    load_trusted_baseline,
)

import global_medicines_atlas.source_health as source_health_module
from global_medicines_atlas.acquisition import (
    AcquisitionPolicy,
    BoundIPAddressTransport,
    Resolver,
)
from global_medicines_atlas.countries import SourceDimension
from global_medicines_atlas.source_catalog import (
    AccessMode,
    MedicineDataSource,
    SourceReadiness,
)
from global_medicines_atlas.source_health import (
    AdapterParityState,
    EscalationState,
    ProbeState,
    RetryAttempt,
    SchemaDriftState,
    SourceHealthObservation,
    SourceHealthReceipt,
    assess_schema_drift,
    build_source_health_receipt,
    compare_schema_fingerprints,
    drift_report_json,
    fingerprint_baseline,
    observations_json,
    probe_source,
    probe_sources,
    schema_fingerprint,
    source_health_receipt_json,
)

NOW = datetime(2026, 7, 29, tzinfo=UTC)
FIXTURES = Path(__file__).parent / "fixtures" / "source_health"


def test_baseline_requires_trusted_main_workflow_and_exact_digest(
    tmp_path: Path,
) -> None:
    report = tmp_path / "source-health.json"
    report.write_text(
        json.dumps({"baseline": {"example": "a" * 64}}) + "\n",
        encoding="utf-8",
    )
    provenance = BaselineProvenance.for_report(
        report,
        repository="edithatogo/global-medicines-atlas",
        workflow=".github/workflows/source-health.yml",
        branch="main",
        conclusion="success",
        run_id=41,
        commit="b" * 40,
        observation_id=41,
    )
    metadata = tmp_path / "source-health-provenance.json"
    metadata.write_text(provenance.canonical_json(), encoding="utf-8")

    assert load_trusted_baseline(
        report,
        metadata,
        expected_repository="edithatogo/global-medicines-atlas",
        expected_workflow=".github/workflows/source-health.yml",
        current_observation_id=42,
        expected_run_id=41,
        expected_commit="b" * 40,
    ) == {"example": "a" * 64}

    for field, replacement in (
        ("workflow", ".github/workflows/other.yml"),
        ("branch", "feature"),
        ("conclusion", "failure"),
        ("report_sha256", "c" * 64),
        ("observation_id", 42),
        ("run_id", 40),
        ("commit", "d" * 40),
    ):
        changed = provenance.model_copy(update={field: replacement})
        metadata.write_text(changed.canonical_json(), encoding="utf-8")
        with pytest.raises(
            ValueError, match=r"baseline|successful|observation|digest"
        ):
            load_trusted_baseline(
                report,
                metadata,
                expected_repository="edithatogo/global-medicines-atlas",
                expected_workflow=".github/workflows/source-health.yml",
                current_observation_id=42,
                expected_run_id=41,
                expected_commit="b" * 40,
            )


def source(
    *,
    source_id: str = "example",
    access_mode: AccessMode = AccessMode.API,
    readiness: SourceReadiness = SourceReadiness.CANDIDATE,
) -> MedicineDataSource:
    return MedicineDataSource.from_legacy(
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
        expected_cadence=timedelta(days=1),
        transport=httpx.MockTransport(lambda _request: httpx.Response(503)),
    )
    assert result.state is ProbeState.UNAVAILABLE
    assert result.status_code == 503
    assert result.schema_fingerprint is None
    assert result.expected_cadence_seconds == 86_400


@pytest.mark.edge
@pytest.mark.parametrize(
    "endpoint",
    [
        "https://127.0.0.1/api",
        "https://169.254.169.254/latest/meta-data/",
        "https://[::1]/api",
    ],
)
def test_probe_rejects_private_networks_before_transport(
    endpoint: str,
) -> None:
    private_source = source().model_copy(update={"api_url": endpoint})
    result = probe_source(
        private_source,
        checked_at=NOW,
        transport=httpx.MockTransport(
            lambda _request: pytest.fail("transport must not be called")
        ),
    )

    assert result.state is ProbeState.UNAVAILABLE
    assert "DestinationPolicyError" in result.detail
    assert result.status_code is None


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


def test_production_probe_honours_zero_redirect_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inner = httpx.MockTransport(
        lambda request: httpx.Response(
            302,
            headers={"location": "https://example.test/redirected"},
            request=request,
        )
    )
    bound = BoundIPAddressTransport(
        policy=AcquisitionPolicy(
            allowed_hosts=("example.test",),
            max_redirects=0,
        ),
        resolver=lambda _host: ("93.184.216.34",),
        inner=inner,
    )

    def use_bound_transport(
        _uri: str,
        _policy: AcquisitionPolicy,
        *,
        resolver: Resolver | None,
        transport: httpx.BaseTransport | None,
    ) -> httpx.BaseTransport:
        del resolver, transport
        return bound

    monkeypatch.setattr(
        source_health_module,
        "transport_for_destination",
        use_bound_transport,
    )

    result = probe_source(
        source(),
        checked_at=NOW,
        acquisition_policy=AcquisitionPolicy(max_redirects=0),
    )

    assert result.state is ProbeState.UNAVAILABLE
    assert "TooManyRedirects" in result.detail


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


def test_rate_limit_degrades_without_retrying_or_retaining_details() -> None:
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(
            429,
            headers={"retry-after": "3600"},
            request=request,
        )

    result = probe_source(
        source(),
        checked_at=NOW,
        transport=httpx.MockTransport(handler),
    )

    assert requests == 1
    assert result.state is ProbeState.UNAVAILABLE
    assert result.status_code == 429
    assert "3600" not in result.detail


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
    stable_fingerprint = available.schema_fingerprint
    assert stable_fingerprint is not None
    assessments = assess_schema_drift(
        (available, new, blocked),
        {"stable": stable_fingerprint},
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
    with pytest.raises(ValueError, match="expected_cadence"):
        probe_source(
            source(),
            checked_at=NOW,
            expected_cadence=timedelta(0),
        )


def test_probe_records_source_update_and_freshness_against_cadence() -> None:
    result = probe_source(
        source(),
        checked_at=NOW,
        expected_cadence=timedelta(days=7),
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                headers={
                    "content-type": "application/json",
                    "last-modified": "Mon, 20 Jul 2026 00:00:00 GMT",
                },
                json={"id": 1},
            )
        ),
    )

    assert result.expected_cadence_seconds == 604_800
    assert result.source_updated_at == datetime(2026, 7, 20, tzinfo=UTC)
    assert result.freshness_age_seconds == 777_600
    assert result.is_fresh is False


def test_retry_history_and_consecutive_failures_are_deterministic() -> None:
    retry_history = (
        RetryAttempt(
            attempt=2,
            attempted_at=NOW,
            outcome=ProbeState.UNAVAILABLE,
            status_code=503,
            retry_after_seconds=30,
        ),
        RetryAttempt(
            attempt=1,
            attempted_at=NOW - timedelta(seconds=5),
            outcome=ProbeState.UNAVAILABLE,
            status_code=503,
        ),
    )
    observation = SourceHealthObservation(
        source_id="example",
        checked_at=NOW,
        state=ProbeState.UNAVAILABLE,
        detail="upstream unavailable",
    )

    receipt = build_source_health_receipt(
        observation,
        previous_consecutive_failures=2,
        retry_history=retry_history,
    )

    assert receipt.consecutive_failures == 3
    assert [attempt.attempt for attempt in receipt.retry_history] == [1, 2]
    assert receipt.escalation is EscalationState.OPEN


def test_success_resets_failures_and_resolves_matching_escalation() -> None:
    observation = SourceHealthObservation(
        source_id="example",
        checked_at=NOW,
        state=ProbeState.AVAILABLE,
        detail="available",
    )
    receipt = build_source_health_receipt(
        observation,
        previous_consecutive_failures=7,
        previous_escalation_open=True,
    )

    assert receipt.consecutive_failures == 0
    assert receipt.escalation is EscalationState.RESOLVED


def test_escalation_dedup_key_is_stable_for_repeated_failure_class() -> None:
    first = build_source_health_receipt(
        SourceHealthObservation(
            source_id="example",
            checked_at=NOW,
            state=ProbeState.UNAVAILABLE,
            status_code=503,
            detail="HTTPStatusError: source unavailable or unreadable",
        ),
        previous_consecutive_failures=2,
    )
    repeated = build_source_health_receipt(
        first.observation.model_copy(
            update={"checked_at": NOW + timedelta(hours=1)}
        ),
        previous_consecutive_failures=3,
        previous_escalation_open=True,
    )

    assert first.deduplication_key == repeated.deduplication_key
    assert first.escalation is EscalationState.OPEN
    assert repeated.escalation is EscalationState.DEDUPLICATED


def test_adapter_output_parity_is_explicit_without_payload_retention() -> None:
    observation = SourceHealthObservation(
        source_id="example",
        checked_at=NOW,
        state=ProbeState.AVAILABLE,
        detail="available",
    )

    matching = build_source_health_receipt(
        observation,
        adapter_output_fingerprint="a" * 64,
        expected_adapter_output_fingerprint="a" * 64,
    )
    changed = build_source_health_receipt(
        observation,
        adapter_output_fingerprint="b" * 64,
        expected_adapter_output_fingerprint="a" * 64,
    )
    unknown = build_source_health_receipt(observation)

    assert matching.adapter_output_parity is AdapterParityState.MATCHED
    assert changed.adapter_output_parity is AdapterParityState.CHANGED
    assert unknown.adapter_output_parity is AdapterParityState.NOT_ASSESSED


def test_receipt_serialization_is_stable_metadata_only_and_self_identifying() -> (
    None
):
    receipt = build_source_health_receipt(
        SourceHealthObservation(
            source_id="example",
            checked_at=NOW,
            state=ProbeState.UNAVAILABLE,
            endpoint="https://example.test/api?token=must-not-be-copied",
            detail="token=must-not-be-copied",
        ),
        previous_consecutive_failures=2,
    )

    first = source_health_receipt_json(receipt)
    second = source_health_receipt_json(
        SourceHealthReceipt.model_validate_json(first)
    )
    payload = json.loads(first)

    assert first == second
    assert payload["schema_version"] == 1
    assert payload["receipt_id"].startswith("sha256:")
    assert payload["deduplication_key"].startswith("source-health:")
    assert "must-not-be-copied" not in first
    assert payload["observation"]["endpoint"] is None


def test_receipt_contract_matches_committed_golden_fixture() -> None:
    observation = SourceHealthObservation(
        source_id="example-source",
        checked_at=NOW,
        state=ProbeState.UNAVAILABLE,
        status_code=503,
        expected_cadence_seconds=86_400,
        source_updated_at=datetime(2026, 7, 27, tzinfo=UTC),
        freshness_age_seconds=172_800,
        is_fresh=False,
        detail="HTTPStatusError: upstream details withheld",
    )

    actual = source_health_receipt_json(
        build_source_health_receipt(
            observation,
            previous_consecutive_failures=2,
        )
    )

    assert actual == (FIXTURES / "unavailable-escalation-v1.json").read_text(
        encoding="utf-8"
    )
