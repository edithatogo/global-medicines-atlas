"""Bounded hosted registration of one already-published MBS Parquet table."""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import urllib.request
from pathlib import Path
from typing import Literal

from pydantic import Field

from .iceberg_interop import assert_disposable_rest_uri
from .models import FrozenModel

DATASET = "edithatogo/australian-mbs-source-archive"
REVISION = "243f9ff5498816af6e4d9ae4db60528728f01834"
OBJECT_PATH = "silver/mbs/v4/2025-07-v3/services.parquet"
OBJECT_SHA256 = (
    "46e7e652d6561ee82758b540eaf3584649d3e7e57fb3a341968678d0c2a48535"
)
OBJECT_BYTES = 100_062
SOURCE_ID = "au-mbs"
SOURCE_REVISION = "2025-07-version-3"
SOURCE_SHA256 = (
    "db873768c5795222455033e2bad28586f19bbf2a10c7d58f06a0671d9111a556"
)
QUALIFICATION_SHA256 = (
    "10a91301dfc9846ded0a5e64d98c77c35fa73dc567e6c340d70e2e03cea7662f"
)
PYICEBERG_VERSION = "0.11.1"
HTTP_OK = 200


class PublicParquetIcebergReceipt(FrozenModel):
    schema_id: Literal["global-medicines-atlas.public-parquet-iceberg-receipt"]
    schema_version: Literal[1]
    dataset: Literal["edithatogo/australian-mbs-source-archive"]
    dataset_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    object_path: Literal["silver/mbs/v4/2025-07-v3/services.parquet"]
    object_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    object_bytes: int = Field(gt=0)
    source_id: Literal["au-mbs"]
    source_revision: Literal["2025-07-version-3"]
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    qualification_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    name_mapping_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    pyiceberg_version: Literal["0.11.1"]
    row_count: int = Field(ge=0)
    column_names: tuple[str, ...] = Field(min_length=1)
    anonymous_digest_verified: Literal[True] = True
    existing_public_object_only: Literal[True] = True
    disposable_catalog_registration: Literal[True] = True
    catalogue_cleanup_verified: Literal[True] = True
    source_values_in_receipt: Literal[False] = False
    rights_conclusion: Literal[False] = False
    production_promotion: Literal[False] = False
    public_data_mutation: Literal[False] = False


def verify_payload(payload: bytes) -> None:
    """Fail closed unless the exact inventoried object is returned."""

    if len(payload) != OBJECT_BYTES:
        raise ValueError(
            "public Parquet byte count differs from pinned inventory"
        )
    if hashlib.sha256(payload).hexdigest() != OBJECT_SHA256:
        raise ValueError("public Parquet digest differs from pinned inventory")


def public_object_url() -> str:
    return f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/{OBJECT_PATH}"


def run_public_parquet_registration(  # ruff: ignore[too-many-locals] - end-to-end lane
    *, rest_uri: str, temporary_directory: Path
) -> PublicParquetIcebergReceipt:
    """Fetch one exact public object, verify it, and register it in disposable REST."""

    assert_disposable_rest_uri(rest_uri)
    if importlib.metadata.version("pyiceberg") != PYICEBERG_VERSION:
        raise RuntimeError(
            "PyIceberg version does not match the locked experiment"
        )
    temporary_directory.mkdir(parents=True, exist_ok=True)
    parquet_path = temporary_directory / "services.parquet"
    request = urllib.request.Request(  # ruff: ignore[suspicious-url-open-usage] - immutable HF URL
        public_object_url(),
        headers={"User-Agent": "global-medicines-atlas-e2e"},
    )
    # Exact immutable Hugging Face URL only; no user-supplied scheme or host.
    with urllib.request.urlopen(  # ruff: ignore[suspicious-url-open-usage] - immutable HF URL
        request, timeout=30
    ) as response:
        if response.status != HTTP_OK:
            raise RuntimeError("anonymous public Parquet fetch failed")
        payload = response.read(OBJECT_BYTES + 1)
    verify_payload(payload)
    parquet_path.write_bytes(payload)

    parquet = importlib.import_module("pyarrow.parquet")
    catalog_module = importlib.import_module("pyiceberg.catalog")
    pyiceberg_arrow = importlib.import_module("pyiceberg.io.pyarrow")
    pyiceberg_schema = importlib.import_module("pyiceberg.schema")
    name_mapping_type = importlib.import_module("pyiceberg.table.name_mapping")
    arrow_schema = parquet.read_schema(parquet_path)
    field_names = tuple(field.name for field in arrow_schema)
    if (
        not field_names
        or any(not name or name.strip() != name for name in field_names)
        or len(set(field_names)) != len(field_names)
    ):
        raise ValueError("public Parquet schema has invalid or duplicate names")
    # PyIceberg 0.11.1 exposes no public Arrow-to-schema path before a mapping
    # exists. Use its pinned converter, assign fresh field IDs, and emit the
    # resulting public name mapping for nested as well as flat Parquet fields.
    schema_without_ids = pyiceberg_arrow._pyarrow_to_schema_without_ids(
        arrow_schema
    )
    schema_with_ids = pyiceberg_schema.assign_fresh_schema_ids(
        schema_without_ids
    )
    name_mapping = name_mapping_type.create_mapping_from_schema(schema_with_ids)
    name_mapping_json = name_mapping.model_dump_json(by_alias=True)
    table_schema = pyiceberg_arrow.pyarrow_to_schema(
        arrow_schema, name_mapping=name_mapping
    )
    arrow_table = parquet.read_table(parquet_path)
    catalog = catalog_module.load_catalog(
        "gma-public-parquet", type="rest", uri=rest_uri
    )
    namespace = ("gma_public_parquet",)
    identifier = (*namespace, "mbs_services")
    catalog.create_namespace(namespace)
    table = catalog.create_table(
        identifier,
        schema=table_schema,
        properties={
            "format-version": "2",
            "gma.dataset": DATASET,
            "gma.dataset-revision": REVISION,
            "gma.object-path": OBJECT_PATH,
            "gma.object-sha256": OBJECT_SHA256,
            "gma.source-id": SOURCE_ID,
            "gma.source-revision": SOURCE_REVISION,
            "gma.source-sha256": SOURCE_SHA256,
            "gma.qualification-sha256": QUALIFICATION_SHA256,
            "gma.candidate-only": "true",
            "schema.name-mapping.default": name_mapping_json,
        },
    )
    table.add_files([parquet_path.as_uri()])
    observed = table.scan().to_arrow()
    if observed.num_rows != arrow_table.num_rows or not observed.schema.equals(
        arrow_table.schema, check_metadata=False
    ):
        raise ValueError(
            "Iceberg scan differs from the exact public Parquet object"
        )
    try:
        catalog.drop_table(identifier)
        catalog.drop_namespace(namespace)
    except Exception as exc:
        raise RuntimeError("disposable catalogue cleanup failed") from exc
    return PublicParquetIcebergReceipt(
        schema_id="global-medicines-atlas.public-parquet-iceberg-receipt",
        schema_version=1,
        dataset=DATASET,
        dataset_revision=REVISION,
        object_path=OBJECT_PATH,
        object_sha256=OBJECT_SHA256,
        object_bytes=len(payload),
        source_id=SOURCE_ID,
        source_revision=SOURCE_REVISION,
        source_sha256=SOURCE_SHA256,
        qualification_sha256=QUALIFICATION_SHA256,
        name_mapping_sha256=hashlib.sha256(
            name_mapping_json.encode("utf-8")
        ).hexdigest(),
        pyiceberg_version=PYICEBERG_VERSION,
        row_count=observed.num_rows,
        column_names=tuple(observed.column_names),
    )
