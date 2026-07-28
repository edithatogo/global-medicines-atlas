from __future__ import annotations

import httpx

from global_medicines_atlas.receipts import RightsState
from global_medicines_atlas.rxnorm_lineage import RxNormEndpointClass
from global_medicines_atlas.terminology import (
    RxNavApiResolver,
    bootstrap_rxnorm_resolver,
)


def test_terminology_result_is_candidate_only() -> None:
    match = bootstrap_rxnorm_resolver().resolve("paracetamol")[0]

    assert match.candidate_only is True
    assert match.lineage.endpoint_class is RxNormEndpointClass.LOCAL_FIXTURE
    assert match.lineage.rights_state is RightsState.UNKNOWN


def test_local_rxnav_precedes_public_endpoint() -> None:
    calls: list[str] = []

    def local_handler(_: httpx.Request) -> httpx.Response:
        calls.append("local")
        return httpx.Response(
            200,
            json={"idGroup": {"rxnormId": ["111"]}},
        )

    def public_handler(_: httpx.Request) -> httpx.Response:
        calls.append("public")
        return httpx.Response(
            200,
            json={"idGroup": {"rxnormId": ["222"]}},
        )

    local = RxNavApiResolver(
        base_url="http://127.0.0.1:4000/REST",
        endpoint_class=RxNormEndpointClass.LOCAL_RXNAV,
        release_identity="2026-07-07",
        transport=httpx.MockTransport(local_handler),
    )
    public = RxNavApiResolver(transport=httpx.MockTransport(public_handler))
    resolver = bootstrap_rxnorm_resolver(local, public)
    try:
        match = resolver.resolve("unlisted medicine")[0]
    finally:
        local.close()
        public.close()

    assert match.code == "111"
    assert calls == ["local"]
    assert match.lineage.endpoint_class is RxNormEndpointClass.LOCAL_RXNAV


def test_public_endpoint_is_used_after_local_unavailability() -> None:
    def local_handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("local service unavailable")

    def public_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"idGroup": {"rxnormId": ["222"]}},
        )

    local = RxNavApiResolver(
        base_url="http://127.0.0.1:4000/REST",
        endpoint_class=RxNormEndpointClass.LOCAL_RXNAV,
        transport=httpx.MockTransport(local_handler),
    )
    public = RxNavApiResolver(transport=httpx.MockTransport(public_handler))
    resolver = bootstrap_rxnorm_resolver(local, public)
    try:
        match = resolver.resolve("unlisted medicine")[0]
    finally:
        local.close()
        public.close()

    assert match.code == "222"
    assert match.lineage.endpoint_class is RxNormEndpointClass.PUBLIC_RXNAV


def test_all_unavailable_tiers_return_deterministic_empty_result() -> None:
    def unavailable(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    local = RxNavApiResolver(
        endpoint_class=RxNormEndpointClass.LOCAL_RXNAV,
        transport=httpx.MockTransport(unavailable),
    )
    public = RxNavApiResolver(transport=httpx.MockTransport(unavailable))
    resolver = bootstrap_rxnorm_resolver(local, public)
    try:
        first = resolver.resolve("unlisted medicine")
        second = resolver.resolve("unlisted medicine")
    finally:
        local.close()
        public.close()

    assert first == second == ()
