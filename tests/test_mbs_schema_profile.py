"""Synthetic opt-in declarations preserve legacy MBS Silver outputs."""

import json
from io import BytesIO

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from hypothesis import given
from hypothesis import strategies as st
from jsonschema import Draft202012Validator
from pydantic import ValidationError
from test_mbs_silver import (
    TABLES,
    _receipt,  # ruff: ignore[import-private-name] - shared synthetic fixture
    _xml,  # ruff: ignore[import-private-name] - shared synthetic fixture
)

import global_medicines_atlas.mbs_schema_profile as profile_module
from global_medicines_atlas.mbs_schema_profile import (
    DECLARATION_METADATA_KEY,
    MbsSchemaProfileDeclaration,
    iter_profiled_mbs_silver_batches,
)
from global_medicines_atlas.mbs_silver import iter_mbs_silver_batches


def declaration(payload, **changes):
    receipt = _receipt(payload)
    return MbsSchemaProfileDeclaration.model_validate({
        "source_id": "au-mbs",
        "source_revision": receipt.source.catalog_version,
        "b1_sha256": receipt.digest(),
        "b2_sha256": receipt.payload.sha256,
        "comparison_schema_profile": "synthetic-mbs-xml-v1",
        **changes,
    })


def profiled(payload, *, table="fees", profile=None, **kwargs):
    return list(
        iter_profiled_mbs_silver_batches(
            payload,
            _receipt(payload),
            table=table,
            declaration=declaration(payload) if profile is None else profile,
            **kwargs,
        )
    )


def parquet(batches):
    stream = BytesIO()
    pq.write_table(pa.Table.from_batches(batches), stream)
    return stream.getvalue()


@pytest.mark.parametrize("table", TABLES)
def test_opt_in_only_adds_namespaced_declaration(table):
    payload = _xml("<ScheduleFee>001.00</ScheduleFee>", count=3)
    original = list(
        iter_mbs_silver_batches(
            payload, _receipt(payload), table=table, rows_per_batch=2
        )
    )
    before = parquet(original)
    output = profiled(payload, table=table, rows_per_batch=2)
    assert [batch.num_rows for batch in output] == [2, 1]
    for expected, actual in zip(original, output, strict=True):
        metadata = dict(actual.schema.metadata)
        encoded = metadata.pop(DECLARATION_METADATA_KEY)
        assert metadata == expected.schema.metadata
        assert actual.to_pylist() == expected.to_pylist()
        assert (
            actual.schema.remove_metadata() == expected.schema.remove_metadata()
        )
        assert json.loads(encoded)["status"] == "declared"
        assert (
            json.loads(encoded)["legacy_schema_era_meaning"]
            == "source_release_revision"
        )
    assert (
        parquet(
            list(
                iter_mbs_silver_batches(
                    payload, _receipt(payload), table=table, rows_per_batch=2
                )
            )
        )
        == before
    )


def test_profiled_parquet_keeps_exact_metadata_and_native_rows():
    payload = _xml(
        "<ScheduleFee/>" + "<ItemStartDate>01.02.2025</ItemStartDate>", count=2
    )
    batches = profiled(payload, table="services", rows_per_batch=1)
    expected = pa.Table.from_batches(batches)
    restored = pq.read_table(BytesIO(parquet(batches)))
    assert restored.equals(expected, check_metadata=True)
    assert restored.schema.metadata[b"schema_era"] == b"synthetic-iso-v1"
    assert restored.schema.metadata[b"date_format"] == b"unspecified"
    assert len(set(restored.column("source_record_id").to_pylist())) == 2


@pytest.mark.parametrize(
    "changes",
    [
        {"source_revision": "other"},
        {"b1_sha256": "f" * 64},
        {"b2_sha256": "f" * 64},
    ],
)
def test_wrong_declaration_binding_rejects(changes):
    payload = _xml()
    with pytest.raises(ValueError, match="declaration"):
        profiled(payload, profile=declaration(payload, **changes))


def test_copied_invalid_declaration_is_revalidated():
    payload = _xml()
    bad = declaration(payload).model_copy(update={"status": "qualified"})
    with pytest.raises(ValidationError):
        profiled(payload, profile=bad)


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "qualified"},
        {"source_id": "au-pbs"},
        {"comparison_schema_profile": " "},
        {"source_revision": " padded"},
        {"b1_sha256": "invalid"},
        {"qualification": True},
    ],
)
def test_contract_cannot_promote_or_replace_identity(changes):
    with pytest.raises(ValidationError):
        declaration(_xml(), **changes)


def _yield_batch(monkeypatch, batch):
    def batches(*_args, **_kwargs):
        yield batch

    monkeypatch.setattr(profile_module, "iter_mbs_silver_batches", batches)


@pytest.mark.parametrize("column", ["source_sha256", "receipt_sha256"])
@pytest.mark.parametrize("value", [None, "f" * 64])
def test_each_row_lineage_is_checked(monkeypatch, column, value):
    payload = _xml(count=2)
    original = next(
        iter_mbs_silver_batches(payload, _receipt(payload), table="fees")
    )
    index = original.schema.get_field_index(column)
    values = original.column(column).to_pylist()
    values[-1] = value
    tampered = original.set_column(
        index, original.schema.field(index), pa.array(values, type=pa.string())
    )
    _yield_batch(monkeypatch, tampered)
    with pytest.raises(ValueError, match="row lineage"):
        profiled(payload)


def test_changed_column_schema_is_rejected(monkeypatch):
    payload = _xml()
    batch = next(
        iter_mbs_silver_batches(payload, _receipt(payload), table="fees")
    )
    _yield_batch(monkeypatch, batch.remove_column(0))
    with pytest.raises(ValueError, match="column schema"):
        profiled(payload)


@pytest.mark.parametrize(
    ("name", "value", "reason"),
    [
        (b"schema_era", b"wrong", "metadata identity"),
        (b"source_receipt_sha256", b"f" * 64, "metadata identity"),
        (b"qualification", b"qualified", "metadata identity"),
        (b"gma.mbs.schema_profile.v2", b"unrecognized", "already carries"),
    ],
)
def test_metadata_identity_and_profile_collisions_reject(
    monkeypatch, name, value, reason
):
    payload = _xml()
    batch = next(
        iter_mbs_silver_batches(payload, _receipt(payload), table="fees")
    )
    tampered = batch.replace_schema_metadata({
        **batch.schema.metadata,
        name: value,
    })
    _yield_batch(monkeypatch, tampered)
    with pytest.raises(ValueError, match=reason):
        profiled(payload)


def test_metadata_wrapper_preserves_native_buffers(monkeypatch):
    payload = _xml(count=2)
    batch = next(
        iter_mbs_silver_batches(payload, _receipt(payload), table="fees")
    )
    _yield_batch(monkeypatch, batch)
    output = profiled(payload)[0]
    for index in range(batch.num_columns):
        assert [
            buffer.address if buffer else None
            for buffer in output.column(index).buffers()
        ] == [
            buffer.address if buffer else None
            for buffer in batch.column(index).buffers()
        ]


def test_declaration_size_limit_is_exact(monkeypatch):
    payload = _xml()
    encoded = profiled(payload)[0].schema.metadata[DECLARATION_METADATA_KEY]
    monkeypatch.setattr(profile_module, "MAX_DECLARATION_BYTES", len(encoded))
    assert (
        profiled(payload)[0].schema.metadata[DECLARATION_METADATA_KEY]
        == encoded
    )
    monkeypatch.setattr(
        profile_module, "MAX_DECLARATION_BYTES", len(encoded) - 1
    )
    with pytest.raises(ValueError, match="byte limit"):
        profiled(payload)


def test_source_payload_binding_remains_required():
    payload = _xml()
    with pytest.raises(ValueError, match="source bytes"):
        list(
            iter_profiled_mbs_silver_batches(
                payload + b" ",
                _receipt(payload),
                table="fees",
                declaration=declaration(payload),
            )
        )


def test_same_profile_across_releases_keeps_distinct_lineage():
    outputs = []
    for revision, fee in (("2026-01", "1.00"), ("2026-02", "2.00")):
        payload = _xml(f"<ScheduleFee>{fee}</ScheduleFee>")
        receipt = _receipt(payload)
        receipt = receipt.model_copy(
            update={
                "source": receipt.source.model_copy(
                    update={"catalog_version": revision}
                )
            }
        )
        profile = declaration(
            payload, source_revision=revision, b1_sha256=receipt.digest()
        )
        batches = list(
            iter_profiled_mbs_silver_batches(
                payload, receipt, table="fees", declaration=profile
            )
        )
        outputs.append(
            json.loads(batches[0].schema.metadata[DECLARATION_METADATA_KEY])
        )
        assert batches[0].schema.metadata[b"schema_era"] == revision.encode()
    assert (
        outputs[0]["comparison_schema_profile"]
        == outputs[1]["comparison_schema_profile"]
    )
    assert outputs[0]["source_revision"] != outputs[1]["source_revision"]
    assert outputs[0]["b1_sha256"] != outputs[1]["b1_sha256"]
    assert outputs[0]["b2_sha256"] != outputs[1]["b2_sha256"]


@given(st.text(max_size=30))
def test_declared_profile_json_preserves_literal_unicode(value):
    payload = _xml()
    profile = declaration(
        payload, comparison_schema_profile=f"profile:{value}:v1"
    )
    encoded = profiled(payload, profile=profile)[0].schema.metadata[
        DECLARATION_METADATA_KEY
    ]
    assert MbsSchemaProfileDeclaration.model_validate_json(encoded) == profile


def test_json_schema_never_admits_qualified_status():
    payload = declaration(_xml()).model_dump(mode="json")
    validator = Draft202012Validator(
        MbsSchemaProfileDeclaration.model_json_schema()
    )
    validator.validate(payload)
    payload["status"] = "qualified"
    assert not validator.is_valid(payload)


def test_new_profile_does_not_select_date_convention():
    payload = _xml("<ItemStartDate>01.02.2025</ItemStartDate>")
    profile = declaration(payload, comparison_schema_profile="mbs-dmy")
    output = profiled(payload, profile=profile, table="services")[0]
    assert output.schema.metadata[b"date_format"] == b"unspecified"
    assert output.column("ItemStartDate").to_pylist()[0]["typed_value"] is None
    explicit = profiled(
        payload, profile=profile, table="services", date_format="mbs-dmy"
    )[0]
    assert explicit.schema.metadata[b"date_format"] == b"mbs-dmy"
    assert (
        explicit.column("ItemStartDate").to_pylist()[0]["typed_value"]
        is not None
    )
