"""Contract for the prepared PBS public API terms request."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).parents[1]
TRACK = ROOT / "conductor/tracks/australian_benefits_silver_gold_20260829"
PREFLIGHT = (
    ROOT
    / "quality/qualifications/australian-pbs-api-public-access-preflight-20260929.json"
)


def test_pbs_terms_request_is_scoped_and_unsent() -> None:
    request = (TRACK / "pbs-public-api-terms-request.md").read_text(
        encoding="utf-8"
    )
    preflight = cast("dict[str, Any]", json.loads(PREFLIGHT.read_text()))

    assert "**Status:** prepared, not sent." in request
    assert "HPP.Support@Health.gov.au" in request
    assert "will not access" in request
    assert "embargo data" in request
    assert preflight["source_id"] == "au-pbs-api"
    assert preflight["payload_requests_made"] is False
    assert preflight["embargo_access_attempted"] is False
    assert preflight["contact"]["message_sent"] is False


def test_pbs_public_access_does_not_promote_rights_or_domain_acceptance() -> (
    None
):
    preflight = cast("dict[str, Any]", json.loads(PREFLIGHT.read_text()))
    observed = cast("dict[str, Any]", preflight["observed_public_api_contract"])
    rights = cast("dict[str, Any]", preflight["rights_observation"])

    assert observed["public_api_available_without_login"] is True
    assert observed["history_months"] == 12
    assert observed["shared_rate_limit_seconds"] == 20
    assert rights["explicit_public_api_reuse_licence_identified"] is False
    assert rights["internal_long_term_retention_authorized"] is False
    assert rights["source_byte_redistribution_authorized"] is False
    assert rights["derived_data_publication_authorized"] is False
    assert "does not change acquisition authorization" in preflight["boundary"]
