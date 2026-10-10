"""Verify one existing MBS source-to-Silver candidate by exact row values.

This qualification reads only the already-inventoried July 2025 MBS source and
its existing public services Parquet candidate. It makes no admission,
licensing, publication, or production-promotion decision.
"""

from __future__ import annotations

import hashlib
import io
from typing import Literal

import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import Field

from .mbs_silver import iter_mbs_silver_batches
from .models import FrozenModel
from .receipts import RightsState, SourceReceipt

DATASET = "edithatogo/australian-mbs-source-archive"
SOURCE_DATASET_REVISION = "4d1dae488ac43522f20e8320a8b2a56bf9138341"
SOURCE_OBJECT_PATH = "raw/mbs/2025-07/MBS-XML-20250701-Version-3.XML"
SOURCE_OBJECT_BYTES = 8_194_522
SOURCE_OBJECT_SHA256 = (
    "db873768c5795222455033e2bad28586f19bbf2a10c7d58f06a0671d9111a556"
)
SOURCE_RECEIPT_SHA256 = (
    "c8c3e3baeee4c08dba1a944c19652ec184d90de850968fc4d6a124747d994e03"
)
SILVER_DATASET_REVISION = "243f9ff5498816af6e4d9ae4db60528728f01834"
SILVER_OBJECT_PATH = "silver/mbs/v4/2025-07-v3/services.parquet"
SILVER_OBJECT_BYTES = 100_062
SILVER_OBJECT_SHA256 = (
    "46e7e652d6561ee82758b540eaf3584649d3e7e57fb3a341968678d0c2a48535"
)
QUALIFICATION_SHA256 = (
    "10a91301dfc9846ded0a5e64d98c77c35fa73dc567e6c340d70e2e03cea7662f"
)
SOURCE_REVISION = "2025-07-version-3"
SOURCE_URI = (
    "https://huggingface.co/datasets/edithatogo/"
    f"australian-mbs-source-archive/resolve/{SOURCE_DATASET_REVISION}/"
    f"{SOURCE_OBJECT_PATH}"
)
EXPECTED_ROWS = 5_989
EXPECTED_FIELDS = 17


class MbsSourceSilverParityReceipt(FrozenModel):
    """Value-free receipt for a single exact source-to-Silver comparison."""

    schema_id: Literal[
        "global-medicines-atlas.mbs-source-silver-parity-receipt"
    ]
    schema_version: Literal[1]
    dataset: Literal["edithatogo/australian-mbs-source-archive"]
    source_dataset_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_object_path: str
    source_object_bytes: int = Field(gt=0)
    source_object_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    silver_dataset_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    silver_object_path: str
    silver_object_bytes: int = Field(gt=0)
    silver_object_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    qualification_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_revision: Literal["2025-07-version-3"]
    row_count: int = Field(ge=0)
    field_count: int = Field(gt=0)
    source_to_silver_value_parity_verified: Literal[True] = True
    source_values_in_receipt: Literal[False] = False
    rights_conclusion: Literal[False] = False
    production_admission: Literal[False] = False
    public_data_mutation: Literal[False] = False
    production_promotion: Literal[False] = False


def _verify_identity(
    payload: bytes, *, expected_bytes: int, expected_sha256: str
) -> None:
    if len(payload) != expected_bytes:
        raise ValueError("pinned MBS object byte count differs")
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise ValueError("pinned MBS object digest differs")


def _receipt_binds_source(receipt: SourceReceipt, payload: bytes) -> bool:
    return all((
        receipt.digest() == SOURCE_RECEIPT_SHA256,
        receipt.source.source_id == "au-mbs",
        receipt.source.catalog_version == SOURCE_REVISION,
        str(receipt.retrieval.uri) == SOURCE_URI,
        receipt.rights_state is RightsState.PERMITTED,
        receipt.payload.matches(payload),
    ))


def verify_mbs_source_silver_parity(
    source_payload: bytes,
    source_receipt: SourceReceipt,
    silver_payload: bytes,
) -> MbsSourceSilverParityReceipt:
    """Compare every service field parsed from B2 with the pinned Parquet rows."""
    _verify_identity(
        source_payload,
        expected_bytes=SOURCE_OBJECT_BYTES,
        expected_sha256=SOURCE_OBJECT_SHA256,
    )
    _verify_identity(
        silver_payload,
        expected_bytes=SILVER_OBJECT_BYTES,
        expected_sha256=SILVER_OBJECT_SHA256,
    )
    if not _receipt_binds_source(source_receipt, source_payload):
        raise ValueError("MBS B1 receipt does not bind the exact source object")

    silver_batches = tuple(
        iter_mbs_silver_batches(
            source_payload,
            source_receipt,
            table="services",
            date_format="mbs-dmy",
        )
    )
    generated = pa.Table.from_batches(silver_batches)
    candidate = pq.read_table(  # pyright: ignore[reportUnknownMemberType]
        io.BytesIO(silver_payload)
    )
    if (
        generated.num_rows != EXPECTED_ROWS
        or generated.num_columns != EXPECTED_FIELDS
        or candidate.num_rows != EXPECTED_ROWS
        or candidate.num_columns != EXPECTED_FIELDS
        or not generated.schema.equals(candidate.schema, check_metadata=False)
    ):
        raise ValueError("MBS source-to-Silver schema or denominator differs")
    if not generated.equals(candidate, check_metadata=False):
        raise ValueError("MBS source-to-Silver row values differ")

    return MbsSourceSilverParityReceipt(
        schema_id="global-medicines-atlas.mbs-source-silver-parity-receipt",
        schema_version=1,
        dataset=DATASET,
        source_dataset_revision=SOURCE_DATASET_REVISION,
        source_object_path=SOURCE_OBJECT_PATH,
        source_object_bytes=len(source_payload),
        source_object_sha256=SOURCE_OBJECT_SHA256,
        source_receipt_sha256=SOURCE_RECEIPT_SHA256,
        silver_dataset_revision=SILVER_DATASET_REVISION,
        silver_object_path=SILVER_OBJECT_PATH,
        silver_object_bytes=len(silver_payload),
        silver_object_sha256=SILVER_OBJECT_SHA256,
        qualification_sha256=QUALIFICATION_SHA256,
        source_revision=SOURCE_REVISION,
        row_count=generated.num_rows,
        field_count=generated.num_columns,
    )
