"""Tests for the source-neutral existing-public-object registration gate."""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from global_medicines_atlas import iceberg_public_parquet as registration


@pytest.mark.unit
def test_public_object_identity_is_immutable_and_existing() -> None:
    assert registration.DATASET == "edithatogo/australian-mbs-source-archive"
    assert registration.REVISION == "243f9ff5498816af6e4d9ae4db60528728f01834"
    assert registration.OBJECT_PATH.endswith("/services.parquet")
    assert registration.public_object_url() == (
        "https://huggingface.co/datasets/edithatogo/"
        "australian-mbs-source-archive/resolve/"
        "243f9ff5498816af6e4d9ae4db60528728f01834/"
        "silver/mbs/v4/2025-07-v3/services.parquet"
    )


@pytest.mark.unit
def test_exact_existing_payload_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = b"bounded fixture"
    monkeypatch.setattr(registration, "OBJECT_BYTES", len(payload))
    monkeypatch.setattr(
        registration, "OBJECT_SHA256", hashlib.sha256(payload).hexdigest()
    )
    registration.verify_payload(payload)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("payload", "size", "digest"),
    [
        (b"wrong-size", 2, hashlib.sha256(b"wrong-size").hexdigest()),
        (b"wrong-digest", 12, "0" * 64),
    ],
)
def test_public_payload_must_match_exact_count_and_digest(
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
    size: int,
    digest: str,
) -> None:
    monkeypatch.setattr(registration, "OBJECT_BYTES", size)
    monkeypatch.setattr(registration, "OBJECT_SHA256", digest)
    with pytest.raises(ValueError, match="pinned inventory"):
        registration.verify_payload(payload)


@pytest.mark.unit
def test_receipt_is_explicitly_non_promotional_and_value_free() -> None:
    receipt = registration.PublicParquetIcebergReceipt(
        schema_id="global-medicines-atlas.public-parquet-iceberg-receipt",
        schema_version=1,
        dataset=registration.DATASET,
        dataset_revision=registration.REVISION,
        object_path=registration.OBJECT_PATH,
        object_sha256=registration.OBJECT_SHA256,
        object_bytes=registration.OBJECT_BYTES,
        source_id=registration.SOURCE_ID,
        source_revision=registration.SOURCE_REVISION,
        source_sha256=registration.SOURCE_SHA256,
        qualification_sha256=registration.QUALIFICATION_SHA256,
        pyiceberg_version=registration.PYICEBERG_VERSION,
        row_count=3,
        column_names=("item", "description"),
    )
    assert receipt.rights_conclusion is False
    assert receipt.production_promotion is False
    assert receipt.public_data_mutation is False
    assert "rows" not in receipt.model_dump_json()


@pytest.mark.unit
def test_exact_public_object_registers_and_reads_back_in_disposable_catalog(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    payload = b"exact public parquet bytes"
    monkeypatch.setattr(registration, "OBJECT_BYTES", len(payload))
    monkeypatch.setattr(
        registration, "OBJECT_SHA256", hashlib.sha256(payload).hexdigest()
    )

    class FakeResponse:
        status = 200

        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self, _limit: int) -> bytes:
            return payload

    class FakeArrowSchema:
        def equals(self, other: object, *, check_metadata: bool) -> bool:
            return other is self and check_metadata is False

    class FakeArrowTable:
        num_rows = 2
        column_names = ("service_code", "benefit")
        schema = FakeArrowSchema()

    class FakeScan:
        def to_arrow(self) -> FakeArrowTable:
            return FakeArrowTable()

    class FakeTable:
        def __init__(self) -> None:
            self.added: list[str] = []

        def add_files(self, files: list[str]) -> None:
            self.added = files

        def scan(self) -> FakeScan:
            return FakeScan()

    class FakeCatalog:
        def __init__(self) -> None:
            self.table = FakeTable()
            self.properties: dict[str, str] = {}
            self.dropped: list[tuple[str, ...]] = []

        def create_namespace(self, _namespace: tuple[str, ...]) -> None:
            return None

        def create_table(
            self,
            _identifier: tuple[str, ...],
            *,
            schema: object,
            properties: dict[str, str],
        ) -> FakeTable:
            self.properties = properties
            assert schema is fake_schema
            return self.table

        def drop_table(self, identifier: tuple[str, ...]) -> None:
            self.dropped.append(identifier)

        def drop_namespace(self, namespace: tuple[str, ...]) -> None:
            self.dropped.append(namespace)

    fake_schema = object()
    fake_catalog = FakeCatalog()

    def read_schema(_path: Path) -> object:
        return object()

    def read_table(_path: Path) -> FakeArrowTable:
        return FakeArrowTable()

    def load_catalog(*_args: Any, **_kwargs: Any) -> FakeCatalog:
        return fake_catalog

    def to_iceberg_schema(_schema: object) -> object:
        return fake_schema

    def get_module(name: str, _package: str | None = None) -> Any:
        return modules[name]

    def get_version(_name: str) -> str:
        return registration.PYICEBERG_VERSION

    def open_url(_url: object, *, timeout: float) -> FakeResponse:
        assert timeout == 30
        return FakeResponse()

    fake_arrow = SimpleNamespace(
        read_schema=read_schema,
        read_table=read_table,
    )
    modules: dict[str, Any] = {
        "pyarrow.parquet": fake_arrow,
        "pyiceberg.catalog": SimpleNamespace(load_catalog=load_catalog),
        "pyiceberg.io.pyarrow": SimpleNamespace(
            pyarrow_to_schema=to_iceberg_schema
        ),
    }
    monkeypatch.setattr(
        registration.importlib.metadata,
        "version",
        get_version,
    )
    monkeypatch.setattr(registration.importlib, "import_module", get_module)
    monkeypatch.setattr(
        registration.urllib.request,
        "urlopen",
        open_url,
    )

    receipt = registration.run_public_parquet_registration(
        rest_uri="http://127.0.0.1:8181", temporary_directory=tmp_path
    )

    assert receipt.row_count == 2
    assert receipt.column_names == ("service_code", "benefit")
    assert receipt.object_sha256 == hashlib.sha256(payload).hexdigest()
    assert receipt.anonymous_digest_verified is True
    assert receipt.catalogue_cleanup_verified is True
    assert (
        fake_catalog.properties["gma.dataset-revision"] == registration.REVISION
    )
    assert fake_catalog.properties["gma.candidate-only"] == "true"
    assert fake_catalog.table.added == [
        (tmp_path / "services.parquet").as_uri()
    ]
    assert fake_catalog.dropped == [
        ("gma_public_parquet", "mbs_services"),
        ("gma_public_parquet",),
    ]


@pytest.mark.unit
def test_public_registration_rejects_non_loopback_before_fetch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fetched = False

    def unexpected_fetch(*_args: object, **_kwargs: object) -> None:
        nonlocal fetched
        fetched = True
        raise AssertionError("must not fetch")

    monkeypatch.setattr(
        registration.urllib.request, "urlopen", unexpected_fetch
    )
    with pytest.raises(ValueError, match="loopback"):
        registration.run_public_parquet_registration(
            rest_uri="http://catalog.example:8181",
            temporary_directory=tmp_path,
        )
    assert fetched is False
