"""PBS native value candidates preserve field lineage and unresolved meaning."""

from decimal import Decimal
from io import BytesIO
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml
from test_au_pbs_v3 import (
    _xml,  # ruff: ignore[import-private-name]
    _zip,  # ruff: ignore[import-private-name] -- synthetic archive
)
from test_australian_source_contracts import (
    _receipt,  # ruff: ignore[import-private-name]
)

from global_medicines_atlas import pbs_historical_qualification as qualification
from global_medicines_atlas.pbs_entities import iter_pbs_entity_batches
from global_medicines_atlas.pbs_historical_projections import (
    iter_pbs_historical_entity_batches,
)
from global_medicines_atlas.pbs_historical_qualification import (
    qualify_pbs_historical_projections,
)
from global_medicines_atlas.pbs_member_identity import (
    build_pbs_xml_member_binding,
)
from global_medicines_atlas.pbs_native_values import (
    iter_pbs_historical_value_batches,
    iter_pbs_value_batches,
)


def test_price_candidate_is_lossless_and_not_a_qualified_amount():
    payload = _xml().replace(
        b"</pbs:pharmaceutical-item>",
        b'<pbs:price currency="AUD">001.2300</pbs:price></pbs:pharmaceutical-item>',
    )
    rows = pa.Table.from_batches(
        list(iter_pbs_value_batches(payload, _receipt(payload, "au-pbs")))
    ).to_pylist()
    price = next(row for row in rows if row["native_text"] == "001.2300")
    assert price["candidate_decimal"] == Decimal("1.2300")
    assert price["native_currency"] == "AUD"
    assert price["interpretation_state"] == "native_unresolved"
    assert price["item_occurrence_id"] is not None


def price_payload(value, *, attribute=' currency="AUD"'):
    return _xml().replace(
        b"</pbs:pharmaceutical-item>",
        f"<pbs:price{attribute}>{value}</pbs:price></pbs:pharmaceutical-item>".encode(),
    )


@pytest.mark.parametrize(
    ("value", "status", "typed"),
    [
        ("001.2300", "lossless_candidate", Decimal("1.2300")),
        ("-0.01", "lossless_candidate", Decimal("-0.01")),
        ("1.1234567890", "lossless_candidate", Decimal("1.123456789")),
        ("1.1234567891", "unrepresentable", None),
        ("1" * 30, "unrepresentable", None),
        ("1" * 257, "unrepresentable", None),
        ("1e2", "unsupported_numeric_grammar", None),
        ("1,234.00", "unsupported_numeric_grammar", None),
        ("NaN", "unsupported_numeric_grammar", None),
        (" 1.23 ", "unsupported_numeric_grammar", None),
        ("   ", "blank", None),
        ("", "null", None),
    ],
)
def test_native_numeric_outcomes_are_visible_without_rounding(
    value, status, typed
):
    payload = price_payload(value)
    rows = [
        row
        for batch in iter_pbs_value_batches(
            payload, _receipt(payload, "au-pbs")
        )
        for row in batch.to_pylist()
    ]
    price = next(row for row in rows if row["mapping_target"] == "prices")
    assert price["candidate_conversion_status"] == status
    assert price["candidate_decimal"] == typed
    assert price["native_text"] == (value or None)
    assert price["semantic_evidence_sha256"] is None


def test_every_entity_and_native_slot_survives_parquet():
    payload = price_payload("001.2300")
    receipt = _receipt(payload, "au-pbs")
    native = pa.Table.from_batches(
        list(iter_pbs_entity_batches(payload, receipt))
    )
    values = pa.Table.from_batches(
        list(iter_pbs_value_batches(payload, receipt, rows_per_batch=2))
    )
    assert values.select(native.column_names).to_pylist() == native.to_pylist()
    assert all(
        row["interpretation_state"] == "native_unresolved"
        for row in values.to_pylist()
    )
    stream = BytesIO()
    pq.write_table(values, stream)
    restored = pq.read_table(BytesIO(stream.getvalue()))
    assert restored.equals(values, check_metadata=True)
    assert values.schema.metadata[b"domain_semantics_qualified"] == b"false"
    assert values.schema.metadata[b"cross_era_equivalence"] == b"unestablished"


@pytest.mark.parametrize(
    ("attribute", "currency", "state"),
    [
        ("", None, "missing_field"),
        (' currency=""', "", "value"),
        (' currency="aud"', "aud", "value"),
        (' currency="UNKNOWN"', "UNKNOWN", "value"),
    ],
)
def test_currency_is_literal_not_assumed_or_normalized(
    attribute, currency, state
):
    payload = price_payload("1", attribute=attribute)
    rows = [
        row
        for batch in iter_pbs_value_batches(
            payload, _receipt(payload, "au-pbs")
        )
        for row in batch.to_pylist()
    ]
    price = next(row for row in rows if row["mapping_target"] == "prices")
    assert price["native_currency"] == currency
    assert price["native_currency_state"] == state


def test_foreign_price_and_vocabulary_membership_are_not_inferred():
    payload = _xml().replace(
        b"</pbs:pharmaceutical-item>",
        b'<other:price xmlns:other="urn:other" currency="AUD">8.8</other:price></pbs:pharmaceutical-item>',
    )
    rows = [
        row
        for batch in iter_pbs_value_batches(
            payload, _receipt(payload, "au-pbs")
        )
        for row in batch.to_pylist()
    ]
    foreign = next(row for row in rows if row["native_text"] == "8.8")
    assert foreign["candidate_conversion_status"] == "not_price"
    assert foreign["candidate_decimal"] is None
    refs = [
        row
        for row in rows
        if row["mapping_target"] in {"amt_references", "classifications"}
    ]
    assert refs
    assert all(
        row["reference_meaning_state"] == "native_reference_only"
        for row in refs
    )


def test_invalid_source_or_batch_size_fails_closed():
    payload = _xml()
    receipt = _receipt(payload, "au-pbs")
    with pytest.raises(ValueError, match="source bytes"):
        list(iter_pbs_value_batches(payload + b" ", receipt))
    with pytest.raises(ValueError, match="batch size"):
        list(iter_pbs_value_batches(payload, receipt, rows_per_batch=0))


def test_historical_values_preserve_original_archive_member_identity():
    payload = price_payload("1.23")
    archive = _zip([("release/SCH-fixture.xml", payload)])
    parent = _receipt(archive, "au-pbs-historical-xml")
    binding = build_pbs_xml_member_binding(archive, parent)
    batches = list(
        iter_pbs_historical_value_batches(
            archive, payload, parent, binding, rows_per_batch=2
        )
    )
    table = pa.Table.from_batches(batches)
    native = pa.Table.from_batches(
        list(
            iter_pbs_historical_entity_batches(
                archive, payload, parent, binding
            )
        )
    )
    assert table.select(native.column_names).to_pylist() == native.to_pylist()
    rows = table.to_pylist()
    assert all(row["source_id"] == "au-pbs-historical-xml" for row in rows)
    assert all(row["receipt_sha256"] == parent.digest() for row in rows)
    assert all(row["member_binding_sha256"] == binding.digest() for row in rows)
    assert all(row["archive_sha256"] == parent.payload.sha256 for row in rows)
    assert (
        table.schema.metadata[b"member_binding_sha256"]
        == binding.digest().encode()
    )
    with pytest.raises(ValueError, match=r"archive|source bytes"):
        list(
            iter_pbs_historical_value_batches(
                archive + b"changed", payload, parent, binding
            )
        )


@pytest.mark.parametrize(
    ("native", "status"),
    [("1.1234567891", "unrepresentable"), ("1.23", "lossless_candidate")],
)
def test_values_projection_has_complete_native_parity_and_visible_outcomes(
    native, status
):
    payload = price_payload(native)
    archive = _zip([("release/SCH-fixture.xml", payload)])
    parent = _receipt(archive, "au-pbs-historical-xml")
    binding = build_pbs_xml_member_binding(archive, parent)
    report = qualify_pbs_historical_projections(
        archive, payload, parent, binding, projection="values"
    )
    values = report["projections"]["values"]
    assert values["native_fields"] == report["native_fields"]
    assert values["native_digest"] == report["native_digest"]
    assert values["rows"] == report["elements"]
    assert values["parquet_roundtrip_verified"] is True
    assert values["value_status_counts"][status] == 1
    assert values["interpretation_state_counts"] == {
        "native_unresolved": report["elements"]
    }
    assert sum(values["value_status_counts"].values()) == report["elements"]
    assert report["domain_semantics_qualified"] is False
    assert "1.1234567891" not in str(report)


def test_registered_values_mode_is_read_only_and_sends_no_comments():
    document = yaml.load(
        (
            Path(__file__).resolve().parents[1]
            / ".github/workflows/pbs-historical-qualification.yml"
        ).read_text(),
        Loader=yaml.BaseLoader,
    )
    inputs = document["on"]["workflow_dispatch"]["inputs"]
    assert inputs["qualification_scope"]["default"] == "structural"
    jobs = document["jobs"]
    assert (
        jobs["native-values"]["if"]
        == "inputs.qualification_scope == 'native-values'"
    )
    assert jobs["native-values"]["permissions"] == {"contents": "read"}
    for name, job in jobs.items():
        assert job["permissions"] == {"contents": "read"}
        if name not in {
            "native-values",
            "native-value-package",
            "native-schema-inventory",
        }:
            assert "inputs.qualification_scope != 'native-values'" in job["if"]
        for step in job["steps"]:
            assert "gh issue comment" not in step.get("run", "")


@pytest.mark.parametrize("change", ["round", "promote", "unsupported"])
def test_qualifier_rejects_lossy_or_promoted_candidates(monkeypatch, change):
    payload = price_payload("1.1234567891")
    archive = _zip([("release/SCH-fixture.xml", payload)])
    parent = _receipt(archive, "au-pbs-historical-xml")
    binding = build_pbs_xml_member_binding(archive, parent)
    original = qualification.iter_pbs_historical_value_batches

    def changed(*args, **kwargs):
        for batch in original(*args, **kwargs):
            rows = batch.to_pylist()
            for row in rows:
                if row["mapping_target"] == "prices":
                    if change == "promote":
                        row["interpretation_state"] = "interpreted"
                    else:
                        row["candidate_decimal"] = Decimal("1.123456789")
                        if change == "round":
                            row["candidate_conversion_status"] = (
                                "lossless_candidate"
                            )
            yield pa.RecordBatch.from_pylist(rows, schema=batch.schema)

    monkeypatch.setattr(
        qualification, "iter_pbs_historical_value_batches", changed
    )
    with pytest.raises(ValueError, match=r"PBS .*value|PBS numeric"):
        qualify_pbs_historical_projections(
            archive, payload, parent, binding, projection="values"
        )
