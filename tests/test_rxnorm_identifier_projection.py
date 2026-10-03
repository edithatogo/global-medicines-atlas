from __future__ import annotations

import json
from hashlib import sha256

import pytest
from pydantic import AnyUrl, ValidationError
from tests.test_source_receipts import source_receipt

from global_medicines_atlas.bronze_raw_evidence import (
    RawEvidenceManifest,
    RawEvidenceState,
)
from global_medicines_atlas.receipts import EvidenceClass, RightsState
from global_medicines_atlas.reuse_gate import acquire_new_decision
from global_medicines_atlas.rxnorm_identifier_projection import (
    MAX_RESPONSE_BYTES,
    RxNormIdentifierProjection,
    project_rxnorm_identifiers,
)

NLM_RIGHTS_URL = (
    "https://www.nlm.nih.gov/research/umls/rxnorm/docs/termsofservice.html"
)
RXNAV_ENDPOINT = "https://rxnav.nlm.nih.gov/REST/rxcui.json"
RXNAV_REQUEST = f"{RXNAV_ENDPOINT}?idtype=NDC&id=0009-7529"


def _receipt(response: bytes, *, source_id: str = "us-rxnorm-api"):
    base = source_receipt(evidence_class=EvidenceClass.SYNTHETIC)
    return base.model_copy(
        update={
            "source": base.source.model_copy(
                update={
                    "catalog_id": "medicine-source-catalog",
                    "source_id": source_id,
                    "jurisdiction": "USA",
                    "authority": "U.S. National Library of Medicine",
                    "dataset_title": "RxNorm identifiers only",
                }
            ),
            "retrieval": base.retrieval.model_copy(
                update={"uri": AnyUrl(RXNAV_REQUEST)}
            ),
            "payload": base.payload.from_bytes(response),
            "rights_state": RightsState.PERMITTED,
            "rights_reference": AnyUrl(NLM_RIGHTS_URL),
            "reuse": acquire_new_decision(source_id),
            "temporal": base.temporal.model_copy(
                update={
                    "source_version": "2026-09-01",
                    "content_id": sha256(response).hexdigest(),
                }
            ),
        }
    )


@pytest.mark.unit
def test_projection_keeps_only_allowlisted_rxcui_fields_and_external_b2() -> (
    None
):
    response = (
        b'{"idGroup":{"rxnormId":["123","456"],'
        b'"name":"protected vocabulary term"},"ignored":"also secret"}'
    )
    receipt = _receipt(response)

    projection = project_rxnorm_identifiers(
        response,
        source_receipt=receipt,
        external_reference=RXNAV_ENDPOINT,
    )

    assert projection.source_id == "us-rxnorm-api"
    assert projection.identifiers == ("123", "456")
    assert projection.source_response_sha256 == sha256(response).hexdigest()
    assert projection.source_response_byte_count == len(response)
    assert projection.source_receipt_sha256 == receipt.digest()
    assert projection.acquisition_id == receipt.temporal.acquisition_id
    assert b"protected vocabulary term" not in projection.canonical_json()
    assert b"ignored" not in projection.canonical_json()
    assert b"0009-7529" not in projection.canonical_json()
    assert response not in projection.canonical_json()

    b2 = projection.raw_evidence.rows[0]
    assert b2.state is RawEvidenceState.EXTERNAL_REFERENCE_ONLY
    assert b2.external_reference == (
        "https://download.nlm.nih.gov/umls/kss/rxnorm/"
        "2026-09-01/RxNorm_full_current.zip"
    )
    assert b2.payload_sha256 is None
    assert b2.byte_count is None
    assert b2.content_id == sha256(response).hexdigest()
    assert b2.acquisition_id == receipt.temporal.acquisition_id
    assert projection.raw_evidence.row_count == 1
    assert json.loads(projection.canonical_json())["identifiers"] == [
        "123",
        "456",
    ]


@pytest.mark.unit
def test_projection_model_rejects_allowlist_and_b2_identity_drift() -> None:
    response = b'{"idGroup":{"rxnormId":["123"]}}'
    projection = project_rxnorm_identifiers(
        response,
        source_receipt=_receipt(response),
        external_reference=RXNAV_ENDPOINT,
    )
    values = projection.model_dump()
    with pytest.raises(ValidationError, match="field_allowlist"):
        RxNormIdentifierProjection.model_validate({
            **values,
            "field_allowlist": ("idGroup.name",),
        })

    row = projection.raw_evidence.rows[0].model_copy(
        update={"acquisition_id": "different-acquisition"}
    )
    with pytest.raises(ValidationError, match="matching external reference"):
        RxNormIdentifierProjection.model_validate({
            **values,
            "raw_evidence": RawEvidenceManifest.from_rows((row,)),
        })


@pytest.mark.unit
@pytest.mark.parametrize(
    ("response", "message"),
    [
        (b"", "response is empty"),
        (b"not json", "response is not valid JSON"),
        (b"[]", "response root must be an object"),
        (b'{"idGroup":{}}', "rxnormId must be a non-empty list"),
        (
            b'{"idGroup":{"rxnormId":"123"}}',
            "rxnormId must be a non-empty list",
        ),
        (
            b'{"idGroup":{"rxnormId":["123","123"]}}',
            "duplicate RxCUI identifier",
        ),
        (
            b'{"idGroup":{"rxnormId":["12x"]}}',
            "invalid RxCUI identifier",
        ),
        (
            b'{"idGroup":{"rxnormId":[123]}}',
            "invalid RxCUI identifier",
        ),
    ],
)
def test_rejects_malformed_or_ambiguous_response(
    response: bytes, message: str
) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        project_rxnorm_identifiers(
            response,
            source_receipt=_receipt(response),
            external_reference=RXNAV_ENDPOINT,
        )


@pytest.mark.unit
def test_rejects_source_receipt_scope_digest_and_rights_drift() -> None:
    response = b'{"idGroup":{"rxnormId":["123"]}}'
    wrong_source = _receipt(response, source_id="global-rxnorm")
    with pytest.raises(ValueError, match="us-rxnorm-api"):
        project_rxnorm_identifiers(
            response,
            source_receipt=wrong_source,
            external_reference=RXNAV_ENDPOINT,
        )

    stale_receipt = _receipt(b'{"idGroup":{"rxnormId":["999"]}}')
    with pytest.raises(ValueError, match="does not match source receipt"):
        project_rxnorm_identifiers(
            response,
            source_receipt=stale_receipt,
            external_reference=RXNAV_ENDPOINT,
        )

    restricted = _receipt(response).model_copy(
        update={"rights_state": RightsState.UNKNOWN}
    )
    with pytest.raises(ValueError, match="approved NLM identifier rights"):
        project_rxnorm_identifiers(
            response,
            source_receipt=restricted,
            external_reference=RXNAV_ENDPOINT,
        )

    wrong_rights_reference = _receipt(response).model_copy(
        update={"rights_reference": AnyUrl("https://example.invalid/terms")}
    )
    with pytest.raises(ValueError, match="approved NLM identifier rights"):
        project_rxnorm_identifiers(
            response,
            source_receipt=wrong_rights_reference,
            external_reference=RXNAV_ENDPOINT,
        )

    wrong_reuse_source = _receipt(response).model_copy(
        update={
            "reuse": _receipt(response).reuse.model_copy(
                update={"source_id": "global-rxnorm"}
            )
        }
    )
    with pytest.raises(ValueError, match="reuse gate source_id"):
        project_rxnorm_identifiers(
            response,
            source_receipt=wrong_reuse_source,
            external_reference=RXNAV_ENDPOINT,
        )

    incomplete_reuse = _receipt(response).model_copy(
        update={
            "reuse": _receipt(response).reuse.model_copy(
                update={"searched_surfaces": ()}
            )
        }
    )
    with pytest.raises(ValueError, match="must search"):
        project_rxnorm_identifiers(
            response,
            source_receipt=incomplete_reuse,
            external_reference=RXNAV_ENDPOINT,
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "uri",
    [
        "http://rxnav.nlm.nih.gov/REST/rxcui.json",
        "https://example.invalid/REST/rxcui.json",
        "https://rxnav.nlm.nih.gov/REST/rxcui.json?name=aspirin",
    ],
)
def test_rejects_external_references_outside_query_free_rxnav_endpoint(
    uri: str,
) -> None:
    response = b'{"idGroup":{"rxnormId":["123"]}}'
    base = _receipt(response)
    receipt = base.model_copy(
        update={
            "retrieval": base.retrieval.model_copy(update={"uri": AnyUrl(uri)})
        }
    )
    with pytest.raises(ValueError, match="query-free HTTPS RxNav endpoint"):
        project_rxnorm_identifiers(
            response,
            source_receipt=receipt,
            external_reference=uri,
        )


@pytest.mark.unit
def test_rejects_receipt_without_reuse_gate() -> None:
    response = b'{"idGroup":{"rxnormId":["123"]}}'
    receipt = _receipt(response).model_copy(update={"reuse": None})
    with pytest.raises(ValueError, match="reuse gate required"):
        project_rxnorm_identifiers(
            response,
            source_receipt=receipt,
            external_reference=RXNAV_ENDPOINT,
        )


@pytest.mark.unit
def test_rejects_receipt_without_release_identity() -> None:
    response = b'{"idGroup":{"rxnormId":["123"]}}'
    receipt = _receipt(response)
    receipt = receipt.model_copy(
        update={
            "temporal": receipt.temporal.model_copy(
                update={"source_version": None}
            )
        }
    )
    with pytest.raises(ValueError, match="release identity is required"):
        project_rxnorm_identifiers(
            response,
            source_receipt=receipt,
            external_reference=RXNAV_ENDPOINT,
        )


@pytest.mark.unit
def test_rejects_oversized_transient_response_before_parsing() -> None:
    response = b" " * (MAX_RESPONSE_BYTES + 1)
    with pytest.raises(
        ValueError, match="exceeds the identifier projection limit"
    ):
        project_rxnorm_identifiers(
            response,
            source_receipt=_receipt(response),
            external_reference=RXNAV_ENDPOINT,
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "endpoint",
    [
        "https://rxnav.nlm.nih.gov:443/REST/rxcui.json",
        "https://user:pass@rxnav.nlm.nih.gov/REST/rxcui.json",
        "https://rxnav.nlm.nih.gov/REST/other.json",
        "https://rxnav.nlm.nih.gov/REST/rxcui.json#fragment",
    ],
)
def test_rejects_noncanonical_endpoint_details(endpoint: str) -> None:
    response = b'{"idGroup":{"rxnormId":["123"]}}'
    with pytest.raises(ValueError, match="query-free HTTPS RxNav endpoint"):
        project_rxnorm_identifiers(
            response,
            source_receipt=_receipt(response),
            external_reference=endpoint,
        )


@pytest.mark.unit
def test_rejects_receipt_endpoint_that_does_not_match_projection_reference() -> (
    None
):
    response = b'{"idGroup":{"rxnormId":["123"]}}'
    receipt = _receipt(response).model_copy(
        update={
            "retrieval": _receipt(response).retrieval.model_copy(
                update={
                    "uri": AnyUrl(
                        "https://rxnav.nlm.nih.gov/REST/other.json"
                        "?idtype=NDC&id=0009-7529"
                    )
                }
            )
        }
    )
    with pytest.raises(ValueError, match="identifier-based RxNav lookup"):
        project_rxnorm_identifiers(
            response,
            source_receipt=receipt,
            external_reference=RXNAV_ENDPOINT,
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "query",
    [
        "name=aspirin&search=0",
        "idtype=NDC&id=0009-7529&name=aspirin",
        "idtype=NDC&id=0009-7529&idtype=ATC",
        "idtype=NDC&id=0009%207529",
        "idtype=NDC&id=0009-7529&allsrc=2",
    ],
)
def test_rejects_name_search_or_ambiguous_lookup_receipt_queries(
    query: str,
) -> None:
    response = b'{"idGroup":{"rxnormId":["123"]}}'
    receipt = _receipt(response).model_copy(
        update={
            "retrieval": _receipt(response).retrieval.model_copy(
                update={"uri": AnyUrl(f"{RXNAV_ENDPOINT}?{query}")}
            )
        }
    )
    with pytest.raises(ValueError, match="identifier-based RxNav lookup"):
        project_rxnorm_identifiers(
            response,
            source_receipt=receipt,
            external_reference=RXNAV_ENDPOINT,
        )


@pytest.mark.unit
def test_rejects_non_object_id_group() -> None:
    response = b'{"idGroup":[]} '
    with pytest.raises(TypeError, match="idGroup must be an object"):
        project_rxnorm_identifiers(
            response,
            source_receipt=_receipt(response),
            external_reference=RXNAV_ENDPOINT,
        )


@pytest.mark.unit
def test_rejects_rxcuids_longer_than_schema_bound() -> None:
    response = b'{"idGroup":{"rxnormId":["1234567890123456789"]}}'
    with pytest.raises(ValueError, match="invalid RxCUI identifier"):
        project_rxnorm_identifiers(
            response,
            source_receipt=_receipt(response),
            external_reference=RXNAV_ENDPOINT,
        )
