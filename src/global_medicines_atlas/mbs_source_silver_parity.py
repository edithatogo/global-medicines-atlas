"""Verify existing MBS source-to-Silver candidates by exact row values.

This qualification reads only the already-inventoried July 2025 MBS source and
its existing public Parquet candidates. It makes no admission,
licensing, publication, or production-promotion decision.
"""

from __future__ import annotations

import hashlib
import io
from typing import Literal

import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import Field, model_validator

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
SILVER_MANIFEST_SHA256 = (
    "bbdb1bdac49fc1a7f8399ca02cf52a9b0e3a1fbc31e472e3957f1d278ab39a59"
)
SOURCE_REVISION = "2025-07-version-3"
SOURCE_URI = (
    "https://huggingface.co/datasets/edithatogo/"
    f"australian-mbs-source-archive/resolve/{SOURCE_DATASET_REVISION}/"
    f"{SOURCE_OBJECT_PATH}"
)
EXPECTED_ROWS = 5_989
EXPECTED_FIELDS = 17
MbsSilverTable = Literal[
    "services",
    "hierarchy",
    "descriptions",
    "fees",
    "benefits",
    "caps",
]
MBS_SILVER_TABLES: tuple[MbsSilverTable, ...] = (
    "services",
    "hierarchy",
    "descriptions",
    "fees",
    "benefits",
    "caps",
)


class MbsSilverObject(FrozenModel):
    """Exact public identity for one existing MBS Silver candidate table."""

    path: str
    byte_count: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_field_count: int = Field(gt=0)


MBS_SILVER_OBJECTS: dict[str, MbsSilverObject] = {
    "services": MbsSilverObject(
        path="silver/mbs/v4/2025-07-v3/services.parquet",
        byte_count=100_062,
        sha256=(
            "46e7e652d6561ee82758b540eaf3584649d3e7e57fb3a341968678d0c2a48535"
        ),
        source_field_count=13,
    ),
    "hierarchy": MbsSilverObject(
        path="silver/mbs/v4/2025-07-v3/hierarchy.parquet",
        byte_count=51_851,
        sha256=(
            "05387bab5cc578e9923bfaf8a518fde7a49b4b2cde3c4ac61276a6defb3d3756"
        ),
        source_field_count=4,
    ),
    "descriptions": MbsSilverObject(
        path="silver/mbs/v4/2025-07-v3/descriptions.parquet",
        byte_count=620_348,
        sha256=(
            "2822ed642938c8f6b7274a3ecee3c96effc73a6eeedff87b11ed04e12b1a2733"
        ),
        source_field_count=3,
    ),
    "fees": MbsSilverObject(
        path="silver/mbs/v4/2025-07-v3/fees.parquet",
        byte_count=93_072,
        sha256=(
            "d4b88d6b63fcdd768a2546046f0fd9f6428017e83a5a0b3ce56d3bbbffb1a420"
        ),
        source_field_count=6,
    ),
    "benefits": MbsSilverObject(
        path="silver/mbs/v4/2025-07-v3/benefits.parquet",
        byte_count=114_493,
        sha256=(
            "51b9775dc995d9e5d92a9d90a14493ac885475eef0fb648822b9b139006d5f5f"
        ),
        source_field_count=5,
    ),
    "caps": MbsSilverObject(
        path="silver/mbs/v4/2025-07-v3/caps.parquet",
        byte_count=60_259,
        sha256=(
            "767677eb483f2401bd5b8a9b9f3e255fff1aee769d0c9d1d4f7b98463e1c6cbb"
        ),
        source_field_count=9,
    ),
}


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


class MbsSilverTableParityReceipt(FrozenModel):
    """Value-free verification result for one MBS Silver table."""

    table: MbsSilverTable
    silver_object_path: str
    silver_object_bytes: int = Field(gt=0)
    silver_object_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    row_count: int = Field(ge=0)
    field_count: int = Field(gt=0)


class MbsSourceSilverTablesParityReceipt(FrozenModel):
    """Value-free receipt for all six exact MBS source-to-Silver tables."""

    schema_id: Literal[
        "global-medicines-atlas.mbs-source-silver-tables-parity-receipt"
    ]
    schema_version: Literal[1]
    dataset: Literal["edithatogo/australian-mbs-source-archive"]
    source_dataset_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_object_path: str
    source_object_bytes: int = Field(gt=0)
    source_object_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    silver_dataset_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    silver_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    qualification_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_revision: Literal["2025-07-version-3"]
    tables: tuple[MbsSilverTableParityReceipt, ...]
    source_to_silver_value_parity_verified: Literal[True] = True
    source_values_in_receipt: Literal[False] = False
    rights_conclusion: Literal[False] = False
    production_admission: Literal[False] = False
    public_data_mutation: Literal[False] = False
    production_promotion: Literal[False] = False

    @model_validator(mode="after")
    def require_exact_table_set(self) -> MbsSourceSilverTablesParityReceipt:
        """Require each pinned source-faithful table exactly once, in order."""
        actual_tables = tuple(item.table for item in self.tables)
        if actual_tables != MBS_SILVER_TABLES:
            raise ValueError("MBS parity receipt must contain all six tables")
        return self


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


def verify_mbs_source_silver_tables_parity(
    source_payload: bytes,
    source_receipt: SourceReceipt,
    silver_payloads: dict[str, bytes],
) -> MbsSourceSilverTablesParityReceipt:
    """Compare all six exact public table candidates with the pinned XML."""
    _verify_identity(
        source_payload,
        expected_bytes=SOURCE_OBJECT_BYTES,
        expected_sha256=SOURCE_OBJECT_SHA256,
    )
    if not _receipt_binds_source(source_receipt, source_payload):
        raise ValueError("MBS B1 receipt does not bind the exact source object")
    if set(silver_payloads) != set(MBS_SILVER_TABLES):
        raise ValueError("MBS parity requires the exact six-table set")
    if set(MBS_SILVER_OBJECTS) != set(MBS_SILVER_TABLES):
        raise ValueError("pinned MBS table identities are incomplete")

    table_receipts: list[MbsSilverTableParityReceipt] = []
    for table_name in MBS_SILVER_TABLES:
        expected = MBS_SILVER_OBJECTS[table_name]
        payload = silver_payloads[table_name]
        _verify_identity(
            payload,
            expected_bytes=expected.byte_count,
            expected_sha256=expected.sha256,
        )
        batches = tuple(
            iter_mbs_silver_batches(
                source_payload,
                source_receipt,
                table=table_name,
                date_format="mbs-dmy",
            )
        )
        generated = pa.Table.from_batches(batches)
        candidate = pq.read_table(  # pyright: ignore[reportUnknownMemberType]
            io.BytesIO(payload)
        )
        expected_field_count = expected.source_field_count + 4
        if (
            generated.num_rows != EXPECTED_ROWS
            or generated.num_columns != expected_field_count
            or candidate.num_rows != EXPECTED_ROWS
            or candidate.num_columns != expected_field_count
            or not generated.schema.equals(
                candidate.schema, check_metadata=False
            )
        ):
            raise ValueError(f"MBS {table_name} schema or denominator differs")
        if not generated.equals(candidate, check_metadata=False):
            raise ValueError(
                f"MBS {table_name} source-to-Silver row values differ"
            )
        table_receipts.append(
            MbsSilverTableParityReceipt(
                table=table_name,
                silver_object_path=expected.path,
                silver_object_bytes=len(payload),
                silver_object_sha256=expected.sha256,
                row_count=generated.num_rows,
                field_count=generated.num_columns,
            )
        )

    return MbsSourceSilverTablesParityReceipt(
        schema_id=(
            "global-medicines-atlas.mbs-source-silver-tables-parity-receipt"
        ),
        schema_version=1,
        dataset=DATASET,
        source_dataset_revision=SOURCE_DATASET_REVISION,
        source_object_path=SOURCE_OBJECT_PATH,
        source_object_bytes=SOURCE_OBJECT_BYTES,
        source_object_sha256=SOURCE_OBJECT_SHA256,
        source_receipt_sha256=SOURCE_RECEIPT_SHA256,
        silver_dataset_revision=SILVER_DATASET_REVISION,
        silver_manifest_sha256=SILVER_MANIFEST_SHA256,
        qualification_sha256=QUALIFICATION_SHA256,
        source_revision=SOURCE_REVISION,
        tables=tuple(table_receipts),
    )
