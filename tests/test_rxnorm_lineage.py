from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from global_medicines_atlas.receipts import RightsState
from global_medicines_atlas.rxnorm_lineage import (
    RxNormEndpointClass,
    RxNormLineage,
    RxNormQueryMethod,
)


def test_lineage_is_bound_to_exact_payload() -> None:
    payload = b'{"idGroup":{"rxnormId":["161"]}}'
    lineage = RxNormLineage.from_payload(
        payload=payload,
        release_identity="2026-07-07",
        query_method=RxNormQueryMethod.FIND_RXCUI_BY_STRING,
        endpoint_class=RxNormEndpointClass.LOCAL_RXNAV,
        source_uri="http://127.0.0.1:4000/REST/rxcui.json",
        retrieved_at=datetime(2026, 7, 29, tzinfo=UTC),
        rights_state=RightsState.UNKNOWN,
    )

    assert lineage.matches_payload(payload)
    assert not lineage.matches_payload(payload + b" ")
    assert lineage.receipt_id.startswith("rxnorm:local_rxnav:")


def test_permitted_rights_require_reference() -> None:
    with pytest.raises(
        ValidationError,
        match="permitted rights require a rights reference",
    ):
        RxNormLineage.from_payload(
            payload=b"fixture",
            release_identity="fixture-v1",
            query_method=RxNormQueryMethod.NORMALIZED_EXACT,
            endpoint_class=RxNormEndpointClass.LOCAL_FIXTURE,
            source_uri="local://fixture",
            retrieved_at=datetime(2026, 7, 29, tzinfo=UTC),
            rights_state=RightsState.PERMITTED,
        )
