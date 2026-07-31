"""Deterministic simulation tests for source-health state transitions."""

from datetime import UTC, datetime

from global_medicines_atlas.source_health import (
    EscalationState,
    ProbeState,
    SourceHealthObservation,
    build_source_health_receipt,
)

NOW = datetime(2026, 8, 1, tzinfo=UTC)


def _simulate(
    states: tuple[ProbeState, ...],
) -> tuple[tuple[int, str, str], ...]:
    failures = 0
    escalation_open = False
    trace: list[tuple[int, str, str]] = []
    for state in states:
        receipt = build_source_health_receipt(
            SourceHealthObservation(
                source_id="simulated-source",
                checked_at=NOW,
                state=state,
                detail=(
                    "TimeoutError: simulated"
                    if state is ProbeState.UNAVAILABLE
                    else "simulated source available"
                ),
            ),
            previous_consecutive_failures=failures,
            previous_escalation_open=escalation_open,
            escalation_threshold=3,
        )
        failures = receipt.consecutive_failures
        if receipt.escalation is EscalationState.OPEN:
            escalation_open = True
        elif receipt.escalation is EscalationState.RESOLVED:
            escalation_open = False
        trace.append((failures, receipt.escalation.value, receipt.receipt_id))
    return tuple(trace)


def test_identical_event_schedules_produce_identical_state_and_receipts() -> (
    None
):
    schedule = (
        ProbeState.UNAVAILABLE,
        ProbeState.UNAVAILABLE,
        ProbeState.UNAVAILABLE,
        ProbeState.UNAVAILABLE,
        ProbeState.AVAILABLE,
    )

    assert _simulate(schedule) == _simulate(schedule)


def test_failure_and_recovery_schedule_crosses_exact_boundaries() -> None:
    trace = _simulate((
        ProbeState.UNAVAILABLE,
        ProbeState.UNAVAILABLE,
        ProbeState.UNAVAILABLE,
        ProbeState.UNAVAILABLE,
        ProbeState.AVAILABLE,
    ))

    assert [(failures, escalation) for failures, escalation, _ in trace] == [
        (1, "none"),
        (2, "none"),
        (3, "open"),
        (4, "deduplicated"),
        (0, "resolved"),
    ]
