"""Tests for the source-neutral existing-public-object registration gate."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
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
        name_mapping_sha256="a" * 64,
        pyiceberg_version=registration.PYICEBERG_VERSION,
        row_count=3,
        column_names=("item", "description"),
    )
    assert receipt.rights_conclusion is False
    assert receipt.production_promotion is False
    assert receipt.public_data_mutation is False
    assert "rows" not in receipt.model_dump_json()


@pytest.mark.unit
def test_exact_public_object_registers_and_reads_back_in_disposable_catalog(  # ruff: ignore[too-many-statements] - test orchestration paths
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

    class FakePhysicalField:
        def __init__(self, name: str) -> None:
            self.name = name
            self.type = object()

    class FakePhysicalSchema:
        def __iter__(self) -> Any:
            return iter((
                FakePhysicalField("service_code"),
                FakePhysicalField("benefit"),
            ))

    @dataclass
    class FakeMappedField:
        field_id: int
        names: list[str]

    class FakeNameMapping:
        def __init__(self, fields: list[FakeMappedField]) -> None:
            self.fields = fields

        def model_dump_json(self, *, by_alias: bool) -> str:
            assert by_alias is True
            return json.dumps([
                {"field-id": field.field_id, "names": field.names}
                for field in self.fields
            ])

    class FakeScan:
        def __init__(self, *, should_fail: bool) -> None:
            self.should_fail = should_fail

        def to_arrow(self) -> FakeArrowTable:
            if self.should_fail:
                raise RuntimeError("injected scan failure")
            return FakeArrowTable()

    class FakeTable:
        def __init__(self) -> None:
            self.added: list[str] = []
            self.fail_scan = False

        def add_files(self, files: list[str]) -> None:
            self.added = files

        def scan(self) -> FakeScan:
            return FakeScan(should_fail=self.fail_scan)

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
        return FakePhysicalSchema()

    def read_table(_path: Path) -> FakeArrowTable:
        return FakeArrowTable()

    def load_catalog(*_args: Any, **_kwargs: Any) -> FakeCatalog:
        return fake_catalog

    schema_without_ids = object()

    def convert_without_ids(_schema: object) -> object:
        return schema_without_ids

    def assign_fresh_ids(schema: object) -> object:
        assert schema is schema_without_ids
        return fake_schema

    def create_name_mapping(schema: object) -> FakeNameMapping:
        assert schema is fake_schema
        return FakeNameMapping([
            FakeMappedField(field_id=1, names=["service_code"]),
            FakeMappedField(field_id=2, names=["benefit"]),
        ])

    def to_iceberg_schema(
        _schema: object, *, name_mapping: FakeNameMapping
    ) -> object:
        assert [field.names[0] for field in name_mapping.fields] == [
            "service_code",
            "benefit",
        ]
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
            _pyarrow_to_schema_without_ids=convert_without_ids,
            pyarrow_to_schema=to_iceberg_schema,
        ),
        "pyiceberg.schema": SimpleNamespace(
            assign_fresh_schema_ids=assign_fresh_ids
        ),
        "pyiceberg.table.name_mapping": SimpleNamespace(
            create_mapping_from_schema=create_name_mapping,
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

    fake_catalog.table.fail_scan = True
    with pytest.raises(RuntimeError, match="injected scan failure"):
        registration.run_public_parquet_registration(
            rest_uri="http://127.0.0.1:8181", temporary_directory=tmp_path
        )
    assert fake_catalog.dropped == [
        ("gma_public_parquet", "mbs_services"),
        ("gma_public_parquet",),
    ]
    fake_catalog.dropped.clear()
    fake_catalog.table.fail_scan = False

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
    assert "schema.name-mapping.default" in fake_catalog.properties
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


@pytest.mark.unit
def test_public_registration_rejects_unlocked_pyiceberg_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def wrong_version(_name: str) -> str:
        return "0.0"

    monkeypatch.setattr(
        registration.importlib.metadata, "version", wrong_version
    )
    with pytest.raises(RuntimeError, match="locked experiment"):
        registration.run_public_parquet_registration(
            rest_uri="http://127.0.0.1:8181",
            temporary_directory=tmp_path,
        )
    assert list(tmp_path.iterdir()) == []


@pytest.mark.unit
def test_public_registration_rejects_non_success_fetch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def locked_version(_name: str) -> str:
        return registration.PYICEBERG_VERSION

    class NonSuccessResponse:
        status = 404

        def __enter__(self) -> NonSuccessResponse:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    def open_not_found(_url: object, *, timeout: float) -> NonSuccessResponse:
        assert timeout == 30
        return NonSuccessResponse()

    monkeypatch.setattr(
        registration.urllib.request,
        "urlopen",
        open_not_found,
    )
    monkeypatch.setattr(
        registration.importlib.metadata, "version", locked_version
    )
    with pytest.raises(
        RuntimeError, match="anonymous public Parquet fetch failed"
    ):
        registration.run_public_parquet_registration(
            rest_uri="http://127.0.0.1:8181",
            temporary_directory=tmp_path,
        )
