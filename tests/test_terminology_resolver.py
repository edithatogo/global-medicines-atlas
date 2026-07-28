"""Offline and optional remote RxNorm/RxNav resolver tests."""

from __future__ import annotations

import httpx

from global_medicines_atlas.receipts import RightsState
from global_medicines_atlas.rxnorm_lineage import (
    RxNormEndpointClass,
    RxNormQueryMethod,
)
from global_medicines_atlas.terminology import (
    MatchMethod,
    RxNavApiResolver,
    TieredResolver,
    bootstrap_rxnorm_resolver,
)


def test_bootstrap_resolver_maps_nz_name_without_network() -> None:
    match = bootstrap_rxnorm_resolver().resolve("  PARACETAMOL  ")[0]

    assert match.code == "161"
    assert match.display == "Acetaminophen"
    assert match.method == MatchMethod.NORMALIZED
    assert match.provenance.source_uri.startswith("local://")
    assert match.lineage.release_identity == "v1"
    assert match.lineage.query_method is RxNormQueryMethod.NORMALIZED_EXACT
    assert match.lineage.endpoint_class is RxNormEndpointClass.LOCAL_FIXTURE
    assert match.lineage.rights_state is RightsState.UNKNOWN
    assert match.candidate_only


def test_remote_adapter_uses_rxnav_compatible_contract() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/REST/rxcui.json"
        assert request.url.params["name"] == "example medicine"
        return httpx.Response(200, json={"idGroup": {"rxnormId": ["12345"]}})

    remote = RxNavApiResolver(transport=httpx.MockTransport(handler))
    try:
        match = remote.resolve("example medicine")[0]
    finally:
        remote.close()

    assert match.code == "12345"
    assert match.method == MatchMethod.REMOTE
    assert match.provenance.source_id == "nlm-rxnav-api"
    assert match.lineage.matches_payload(b'{"idGroup":{"rxnormId":["12345"]}}')
    assert match.lineage.endpoint_class is RxNormEndpointClass.PUBLIC_RXNAV


def test_remote_adapter_rejects_malformed_identifier_collection() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"idGroup": {"rxnormId": "12345"}})

    remote = RxNavApiResolver(transport=httpx.MockTransport(handler))
    try:
        assert remote.resolve("example medicine") == ()
    finally:
        remote.close()


def test_tiered_resolver_fails_closed_when_remote_is_unavailable() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    remote = RxNavApiResolver(transport=httpx.MockTransport(handler))
    resolver = bootstrap_rxnorm_resolver(public_rxnav=remote)
    try:
        assert resolver.resolve("not in local fixture") == ()
        assert resolver.resolve("ibuprofen")[0].code == "5640"
    finally:
        remote.close()


def test_tiered_resolver_fails_closed_when_remote_times_out() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    remote = RxNavApiResolver(transport=httpx.MockTransport(handler))
    resolver = bootstrap_rxnorm_resolver(public_rxnav=remote)
    try:
        assert resolver.resolve("not in local fixture") == ()
    finally:
        remote.close()


def test_tiered_resolver_does_not_call_remote_after_local_match() -> None:
    class ExplodingResolver:
        def resolve(self, query: str):
            raise AssertionError(f"Remote called for {query}")

    resolver = TieredResolver(
        bootstrap_rxnorm_resolver(),
        ExplodingResolver(),
    )

    assert resolver.resolve("warfarin")[0].code == "11289"
