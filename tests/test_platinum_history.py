from datetime import UTC, datetime

import pytest

from global_medicines_atlas.historical_change import (
    compare_historical_snapshots,
)
from global_medicines_atlas.platinum_history import (
    HistoricalChangeEnvelope,
    build_historical_change_envelope,
)


def test_envelope_binds_deterministic_change_digest_and_unknown_absence() -> None:
    change = compare_historical_snapshots(None, None)
    generated = datetime(2026, 1, 1, tzinfo=UTC)
    result = build_historical_change_envelope(change, generated_at=generated)
    assert isinstance(result, HistoricalChangeEnvelope)
    assert result.generated_at == generated
    assert result.change_sha256 == build_historical_change_envelope(
        change, generated_at=generated
    ).change_sha256
    assert result.comparison.comparison_state == "source_outage"
    assert result.absence_is_negative_evidence is False
    assert result.source_outage_is_negative_evidence is False


def test_envelope_rejects_tampered_digest() -> None:
    change = compare_historical_snapshots(None, None)
    result = build_historical_change_envelope(change)
    with pytest.raises(ValueError, match="digest"):
        HistoricalChangeEnvelope.model_validate(
            result.model_dump(mode="json") | {"change_sha256": "0" * 64}
        )
