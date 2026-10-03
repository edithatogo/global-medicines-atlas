"""Rights-bounded RxNorm identifier-only response projection.

This module never performs network I/O or writes response bytes. Callers may
pass a transient API response only when the source-specific acquisition gate
has been satisfied. The returned B2 record is an external reference and the
projection contains only NLM-created RxCUIs plus acquisition metadata.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from hashlib import sha256
from typing import Annotated, Literal, cast
from urllib.parse import SplitResult, parse_qsl, urlsplit

import orjson
from pydantic import AwareDatetime, Field, field_validator, model_validator

from .bronze_raw_evidence import (
    RawEvidenceKind,
    RawEvidenceManifest,
    RawEvidenceRecord,
    RawEvidenceState,
    build_raw_evidence_record,
)
from .models import FrozenModel
from .receipts import RightsState, SourceReceipt, require_temporal
from .reuse_gate import require_reuse_decision

SOURCE_ID = "us-rxnorm-api"
NLM_RIGHTS_REFERENCE = (
    "https://www.nlm.nih.gov/research/umls/rxnorm/docs/termsofservice.html"
)
RXNAV_HOST = "rxnav.nlm.nih.gov"
RXNAV_PATH = "/REST/rxcui.json"
RXNORM_RELEASE_HOST = "download.nlm.nih.gov"
RXNORM_RELEASE_PATH = "/umls/kss/rxnorm"
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_RXCUI_LENGTH = 18
RXCUI_PATTERN = rf"^[0-9]{{1,{MAX_RXCUI_LENGTH}}}$"
RxCui = Annotated[str, Field(pattern=RXCUI_PATTERN)]


class RxNormIdentifierProjection(FrozenModel):
    """Metadata and allowlisted identifiers derived from one API response."""

    schema_id: Literal[
        "global-medicines-atlas.rxnorm-identifier-projection"
    ] = "global-medicines-atlas.rxnorm-identifier-projection"
    schema_version: Literal[1] = 1
    source_id: Literal["us-rxnorm-api"] = SOURCE_ID
    endpoint: str = Field(min_length=1)
    release_identity: str = Field(min_length=1)
    retrieved_at: AwareDatetime
    rights_reference: Literal[
        "https://www.nlm.nih.gov/research/umls/rxnorm/docs/termsofservice.html"
    ] = NLM_RIGHTS_REFERENCE
    field_allowlist: tuple[Literal["idGroup.rxnormId"], ...] = (
        "idGroup.rxnormId",
    )
    source_response_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_response_byte_count: int = Field(gt=0, le=MAX_RESPONSE_BYTES)
    source_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    acquisition_id: str = Field(min_length=1)
    identifiers: tuple[RxCui, ...] = Field(min_length=1)
    raw_evidence: RawEvidenceManifest
    response_bytes_retained: Literal[False] = False
    vocabulary_terms_retained: Literal[False] = False

    @field_validator("endpoint")
    @classmethod
    def require_query_free_rxnav_endpoint(cls, value: str) -> str:
        return _validate_endpoint(
            value,
            message="endpoint must be the query-free HTTPS RxNav endpoint",
        )

    @field_validator("release_identity")
    @classmethod
    def require_release_identity(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("release identity is required")
        return value

    @model_validator(mode="after")
    def validate_projection_contract(self) -> RxNormIdentifierProjection:
        if self.field_allowlist != ("idGroup.rxnormId",):
            raise ValueError("projection field allowlist is not exact")
        if len(self.identifiers) != len(set(self.identifiers)):
            raise ValueError("duplicate RxCUI identifier")
        if self.raw_evidence.row_count != 1:
            raise ValueError("identifier projection requires one B2 reference")
        row = self.raw_evidence.rows[0]
        if not _b2_matches_projection(row, self):
            raise ValueError(
                "B2 evidence must be a matching external reference"
            )
        return self

    def canonical_json(self) -> bytes:
        """Serialize only the allowlisted projection and non-content metadata."""
        return (
            orjson.dumps(
                self.model_dump(mode="json"), option=orjson.OPT_SORT_KEYS
            )
            + b"\n"
        )


def project_rxnorm_identifiers(
    response: bytes,
    *,
    source_receipt: SourceReceipt,
    external_reference: str,
) -> RxNormIdentifierProjection:
    """Extract only RXCUIs from a transient response and bind external B2.

    The caller owns acquisition and must have passed its source-specific
    authority and reuse gates. This pure function performs no network or file
    I/O. The API route is recorded as retrieval provenance while B2 points at
    the immutable release archive identified by the receipt's source version.
    Query-bearing retrieval references are rejected because they may contain
    source vocabulary terms.
    """
    if source_receipt.source.source_id != SOURCE_ID:
        raise ValueError(f"source receipt must identify {SOURCE_ID}")
    if (
        source_receipt.rights_state is not RightsState.PERMITTED
        or str(source_receipt.rights_reference) != NLM_RIGHTS_REFERENCE
    ):
        raise ValueError("approved NLM identifier rights are required")
    require_reuse_decision(source_receipt.reuse, SOURCE_ID)
    if source_receipt.payload.sha256 != sha256(
        response
    ).hexdigest() or source_receipt.payload.byte_count != len(response):
        raise ValueError("response does not match source receipt")
    if not response:
        raise ValueError("response is empty")
    if len(response) > MAX_RESPONSE_BYTES:
        raise ValueError("response exceeds the identifier projection limit")

    endpoint = _validate_endpoint(external_reference)
    retrieval_uri = str(source_receipt.retrieval.uri)
    if not _is_identifier_lookup_uri(retrieval_uri, endpoint):
        raise ValueError("receipt URI must be an identifier-based RxNav lookup")
    document = _decode_response(response)
    id_group_value = document.get("idGroup")
    if not isinstance(id_group_value, Mapping):
        raise TypeError("idGroup must be an object")
    id_group = cast("Mapping[str, object]", id_group_value)
    raw_ids = id_group.get("rxnormId")
    if not isinstance(raw_ids, list) or not raw_ids:
        raise ValueError("rxnormId must be a non-empty list")
    ids = tuple(_validate_rxcui(item) for item in cast("list[object]", raw_ids))
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate RxCUI identifier")

    temporal = require_temporal(source_receipt.temporal)
    if not temporal.source_version or not temporal.source_version.strip():
        raise ValueError("RxNorm release identity is required")
    immutable_locator = _release_locator(temporal.source_version)
    record = build_raw_evidence_record(
        source_receipt,
        raw_locator=immutable_locator,
        state=RawEvidenceState.EXTERNAL_REFERENCE_ONLY,
        retain_bytes=False,
        kind=RawEvidenceKind.PAYLOAD,
        media_type="application/json",
    )
    return RxNormIdentifierProjection(
        endpoint=endpoint,
        release_identity=temporal.source_version,
        retrieved_at=source_receipt.retrieval.retrieved_at,
        source_response_sha256=source_receipt.payload.sha256,
        source_response_byte_count=source_receipt.payload.byte_count,
        source_receipt_sha256=source_receipt.digest(),
        acquisition_id=temporal.acquisition_id,
        identifiers=ids,
        raw_evidence=RawEvidenceManifest.from_rows((record,)),
    )


def _validate_endpoint(
    value: str,
    *,
    message: str = "external reference must be a query-free HTTPS RxNav endpoint",
) -> str:
    parsed = urlsplit(value)
    if not _is_rxnav_endpoint(parsed):
        raise ValueError(message)
    return value


def _is_rxnav_endpoint(parsed: SplitResult) -> bool:
    return (
        _has_canonical_rxnav_origin(parsed)
        and not parsed.query
        and not parsed.fragment
        and parsed.geturl() == f"https://{RXNAV_HOST}{RXNAV_PATH}"
    )


def _has_canonical_rxnav_origin(parsed: SplitResult) -> bool:
    return (
        parsed.scheme == "https"
        and parsed.netloc == RXNAV_HOST
        and parsed.path == RXNAV_PATH
    )


def _is_identifier_lookup_uri(value: str, endpoint: str) -> bool:
    parsed = urlsplit(value)
    if (
        not _has_canonical_rxnav_origin(parsed)
        or parsed.fragment
        or parsed.geturl().split("?", maxsplit=1)[0] != endpoint
    ):
        return False
    try:
        query = parse_qsl(
            parsed.query,
            keep_blank_values=True,
            strict_parsing=True,
            max_num_fields=3,
        )
    except ValueError:
        return False
    values = dict(query)
    if len(values) != len(query) or set(values) - {"idtype", "id", "allsrc"}:
        return False
    id_type = values.get("idtype", "")
    identifier = values.get("id", "")
    return (
        re.fullmatch(r"[A-Za-z0-9_-]{1,40}", id_type) is not None
        and re.fullmatch(r"[A-Za-z0-9._:/-]{1,128}", identifier) is not None
        and ("allsrc" not in values or values["allsrc"] in {"0", "1"})
    )


def _release_locator(release_identity: str) -> str:
    if (
        not release_identity.strip()
        or any(char in release_identity for char in "?#")
        or not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", release_identity)
    ):
        raise ValueError("invalid RxNorm release identity")
    return (
        f"https://{RXNORM_RELEASE_HOST}{RXNORM_RELEASE_PATH}/"
        f"{release_identity}/RxNorm_full_current.zip"
    )


def _b2_matches_projection(
    row: RawEvidenceRecord, projection: RxNormIdentifierProjection
) -> bool:
    return (
        row.source_id == projection.source_id
        and row.state is RawEvidenceState.EXTERNAL_REFERENCE_ONLY
        and row.kind is RawEvidenceKind.PAYLOAD
        and row.external_reference
        == _release_locator(projection.release_identity)
        and row.payload_sha256 is None
        and row.byte_count is None
        and row.content_id == projection.source_response_sha256
        and row.acquisition_id == projection.acquisition_id
    )


def _decode_response(response: bytes) -> Mapping[str, object]:
    try:
        document = json.loads(response)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("response is not valid JSON") from exc
    if not isinstance(document, dict):
        raise TypeError("response root must be an object")
    return cast("Mapping[str, object]", document)


def _validate_rxcui(value: object) -> str:
    if not isinstance(value, str) or not value.isascii() or not value.isdigit():
        raise ValueError("invalid RxCUI identifier")
    if not 1 <= len(value) <= MAX_RXCUI_LENGTH:
        raise ValueError("invalid RxCUI identifier")
    return value
