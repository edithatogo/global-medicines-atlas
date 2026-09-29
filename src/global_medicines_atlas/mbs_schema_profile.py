"""Opt-in schema declarations over unchanged native/typed MBS Silver values.

The caller declares a comparison schema profile separately from a source release
label. Neither is independently qualified. Existing Silver and published bytes
are not rewritten; this wrapper emits a new candidate representation only.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from hashlib import sha256
from typing import TYPE_CHECKING, Any, Literal, cast

from pydantic import ConfigDict, Field, model_validator

from .australian_source_contracts import TargetTable
from .historical_comparison import Digest, ProfileName
from .mbs_silver import iter_mbs_silver_batches, mbs_silver_schema
from .models import FrozenModel
from .receipts import SourceReceipt

if TYPE_CHECKING:
    import pyarrow as pa

    from .mbs_historical_comparison import MbsComparisonCohort


DECLARATION_METADATA_KEY = b"gma.mbs.schema_profile.v1"
MAX_DECLARATION_BYTES = 40 * 1024


class MbsSchemaProfileDeclaration(FrozenModel):
    """Receipt-bound declaration, never a qualification or rights receipt."""

    model_config = ConfigDict(revalidate_instances="always")
    schema_id: Literal["global-medicines-atlas.mbs-schema-profile"] = (
        "global-medicines-atlas.mbs-schema-profile"
    )
    schema_version: Literal[1] = 1
    status: Literal["declared"] = "declared"
    source_id: Literal["au-mbs"]
    source_revision: ProfileName
    b1_sha256: Digest
    b2_sha256: Digest
    comparison_schema_profile: ProfileName
    legacy_schema_era_meaning: Literal["source_release_revision"] = (
        "source_release_revision"
    )


class MbsNativeProfileBinding(FrozenModel):
    """Content-bound link from a native cohort to a declared schema profile.

    The release label, native comparison era, and schema profile remain
    separate identities. This sidecar never claims that the profile is
    qualified and never changes the native snapshot itself.
    """

    model_config = ConfigDict(revalidate_instances="always")
    schema_id: Literal["global-medicines-atlas.mbs-native-profile-binding"] = (
        "global-medicines-atlas.mbs-native-profile-binding"
    )
    schema_version: Literal[1] = 1
    status: Literal["declared"] = "declared"
    source_id: Literal["au-mbs"] = "au-mbs"
    source_revision: ProfileName
    schema_era: ProfileName
    comparison_schema_profile: ProfileName
    identity_profile: Literal["mbs-item-subitem-literal-v1"] = (
        "mbs-item-subitem-literal-v1"
    )
    selection_scope: str = Field(pattern=r"^mbs-native-keys-v1:[0-9a-f]{64}$")
    table: TargetTable
    cohort: Literal["synthetic", "legacy", "historical", "current"]
    native_snapshot_sha256: Digest
    native_cohort_sha256: Digest
    b1_sha256: Digest
    b2_sha256: Digest
    legacy_schema_era_meaning: Literal["comparison_schema_era"] = (
        "comparison_schema_era"
    )
    binding_sha256: Digest

    @model_validator(mode="after")
    def binding_is_content_bound(self) -> MbsNativeProfileBinding:
        if self.binding_sha256 != _native_binding_digest(self):
            raise ValueError("MBS native profile binding digest differs")
        return self


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()


def _canonical_sha256(value: object) -> str:
    encoder = json.JSONEncoder(
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    digest = sha256()
    for chunk in encoder.iterencode(value):
        digest.update(chunk.encode())
    return digest.hexdigest()


def _native_binding_digest(binding: MbsNativeProfileBinding) -> str:
    return sha256(
        _canonical_json(binding.model_dump(exclude={"binding_sha256"}))
    ).hexdigest()


def bind_mbs_profile_to_native_cohort(
    declaration: MbsSchemaProfileDeclaration,
    cohort: MbsComparisonCohort,
) -> MbsNativeProfileBinding:
    """Bind a schema declaration to one exact MBS native comparison cohort.

    The binding contains no native field values. It records exact snapshot and
    full cohort digests and repeats source release and B1/B2 identities so mismatched inputs
    fail closed before a candidate can be compared or exported.
    """

    try:
        return _bind_mbs_profile_to_native_cohort(declaration, cohort)

    except AttributeError, KeyError, TypeError, ValueError:
        raise ValueError(
            "invalid MBS native cohort identity or profile"
        ) from None


def _bind_mbs_profile_to_native_cohort(
    declaration: MbsSchemaProfileDeclaration,
    cohort: MbsComparisonCohort,
) -> MbsNativeProfileBinding:
    declaration = MbsSchemaProfileDeclaration.model_validate(
        declaration.model_dump(warnings=False)
    )
    cohort = type(cohort).model_validate(cohort.model_dump(warnings=False))
    snapshot = cohort.snapshot
    identity = (
        declaration.source_id,
        declaration.source_revision,
        declaration.b1_sha256,
        declaration.b2_sha256,
    )
    observed = (
        snapshot.source_id,
        snapshot.source_revision,
        snapshot.b1_sha256,
        snapshot.b2_sha256,
    )
    if identity != observed:
        return _invalid_native_binding()
    snapshot_payload = snapshot.model_dump(mode="json", warnings=False)
    cohort_payload = cohort.model_dump(mode="json", warnings=False)
    values: dict[str, Any] = {
        "source_revision": declaration.source_revision,
        "schema_era": snapshot.schema_era,
        "comparison_schema_profile": declaration.comparison_schema_profile,
        "identity_profile": snapshot.identity_profile,
        "selection_scope": snapshot.scope_id,
        "table": snapshot.table,
        "cohort": snapshot.cohort,
        "native_snapshot_sha256": _canonical_sha256(snapshot_payload),
        "native_cohort_sha256": _canonical_sha256(cohort_payload),
        "b1_sha256": snapshot.b1_sha256,
        "b2_sha256": snapshot.b2_sha256,
    }
    draft = MbsNativeProfileBinding.model_construct(**values)
    return MbsNativeProfileBinding.model_validate({
        **values,
        "binding_sha256": _native_binding_digest(draft),
    })


def _invalid_native_binding() -> MbsNativeProfileBinding:
    raise ValueError("invalid MBS native cohort identity or profile")


def _encoded_declaration(
    declaration: MbsSchemaProfileDeclaration, receipt: SourceReceipt
) -> bytes:
    expected = (
        (declaration.source_id, receipt.source.source_id),
        (declaration.source_revision, receipt.source.catalog_version),
        (declaration.b1_sha256, receipt.digest()),
        (declaration.b2_sha256, receipt.payload.sha256),
    )
    if any(declared != observed for declared, observed in expected):
        raise ValueError("schema declaration does not match receipt identity")
    encoded = json.dumps(
        declaration.model_dump(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    if len(encoded) > MAX_DECLARATION_BYTES:
        raise ValueError("schema declaration byte limit exceeded")
    return encoded


def _annotate(
    batch: pa.RecordBatch,
    table: TargetTable,
    declaration: MbsSchemaProfileDeclaration,
    encoded: bytes,
) -> pa.RecordBatch:
    metadata = dict(batch.schema.metadata or {})
    expected_schema = mbs_silver_schema(table).with_metadata(metadata)  # pyright: ignore[reportUnknownMemberType]
    if not batch.schema.equals(expected_schema, check_metadata=True):
        raise ValueError("MBS Silver column schema differs")
    expected_metadata = {
        b"source_id": b"au-mbs",
        b"schema_name": f"global-medicines-atlas.mbs-silver.{table}".encode(),
        b"schema_version": b"1.1",
        b"dimension": b"service_benefit",
        b"subject_kind": b"service",
        b"qualification": b"candidate",
        b"schema_era": declaration.source_revision.encode(),
        b"source_receipt_sha256": declaration.b1_sha256.encode(),
    }
    if any(
        metadata.get(key) != value for key, value in expected_metadata.items()
    ):
        raise ValueError("MBS Silver metadata identity differs")
    if any(key.startswith(b"gma.mbs.schema_profile.") for key in metadata):
        raise ValueError("MBS Silver already carries a schema declaration")
    for column, digest in (
        ("source_sha256", declaration.b2_sha256),
        ("receipt_sha256", declaration.b1_sha256),
    ):
        values = cast("pa.StringArray", batch.column(column)).to_pylist()
        if any(value != digest for value in values):
            raise ValueError("MBS Silver row lineage differs")
    return batch.replace_schema_metadata({
        **metadata,
        DECLARATION_METADATA_KEY: encoded,
    })


def iter_profiled_mbs_silver_batches(
    payload: bytes,
    receipt: SourceReceipt,
    *,
    table: TargetTable,
    declaration: MbsSchemaProfileDeclaration,
    date_format: str | None = None,
    rows_per_batch: int = 1024,
) -> Iterator[pa.RecordBatch]:
    """Add a bounded declaration to receipt-verified source-native candidates.

    Only the new namespaced metadata entry differs from the existing producer.
    Date conversion remains a separate explicit argument, not inferred from the
    profile. This is an in-memory transform, not acquisition or publication.
    """
    declaration = MbsSchemaProfileDeclaration.model_validate(
        declaration.model_dump()
    )
    receipt = SourceReceipt.model_validate(receipt.model_dump())
    encoded = _encoded_declaration(declaration, receipt)
    for batch in iter_mbs_silver_batches(
        payload,
        receipt,
        table=table,
        date_format=date_format,
        rows_per_batch=rows_per_batch,
    ):
        yield _annotate(batch, table, declaration, encoded)
