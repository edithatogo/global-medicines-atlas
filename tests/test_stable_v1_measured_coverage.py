# pyright: reportPrivateUsage=false
"""Stable-v1 measured jurisdiction and source coverage qualification tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal, cast

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

import global_medicines_atlas.stable_v1_measured_coverage as coverage
from global_medicines_atlas.countries import SourceDimension
from global_medicines_atlas.source_catalog import load_source_catalog
from global_medicines_atlas.stable_v1_measured_coverage import (
    ContentBoundMeasuredCoverageReceipt,
    EvidenceMaturity,
    SourceCoverage,
    build_measured_coverage_receipt,
    require_coverage,
    verify_measured_coverage_receipt,
    write_measured_coverage_receipt,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/stable-v1-measured-coverage-v1.json"
COMMITTED_RECEIPT = (
    ROOT / "quality/qualifications/stable-v1-measured-coverage.json"
)


def test_portable_file_binding_normalizes_only_text(
    tmp_path: Path,
) -> None:
    text = tmp_path / "fixture.json"
    binary = tmp_path / "fixture.bin"
    text.write_bytes(b'{"a": 1}\r\n')
    binary.write_bytes(b"\x00\r\n\xff")

    assert coverage._portable_file_bytes(text) == b'{"a": 1}\n'
    assert coverage._portable_file_bytes(binary) == b"\x00\r\n\xff"


def test_live_receipt_integration_is_catalog_bound_and_fail_closed(
    tmp_path: Path,
) -> None:
    source = next(
        item
        for item in load_source_catalog()
        if item.source_id == "eu-union-register"
    )
    relative = coverage._LIVE_QUALIFICATIONS[source.source_id]
    destination = tmp_path / relative
    destination.parent.mkdir(parents=True)
    payload = json.loads((ROOT / relative).read_bytes())
    destination.write_text(json.dumps(payload), encoding="utf-8")

    assert coverage._validated_live_receipt_id(tmp_path, source) == (
        source.current_receipt_id
    )

    unbound = source.model_copy(update={"qualification_references": ()})
    with pytest.raises(ValueError, match="not catalog-bound"):
        coverage._validated_live_receipt_id(tmp_path, unbound)

    missing_receipt = source.model_copy(update={"current_receipt_id": None})
    with pytest.raises(ValueError, match="lacks catalog receipt identity"):
        coverage._validated_live_receipt_id(tmp_path, missing_receipt)

    payload["source_ids"] = ["wrong-source"]
    destination.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="source identity mismatch"):
        coverage._validated_live_receipt_id(tmp_path, source)

    payload = json.loads((ROOT / relative).read_bytes())
    payload["archive_checksum_verified"] = False
    destination.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="archive_checksum_verified"):
        coverage._validated_live_receipt_id(tmp_path, source)

    payload = json.loads((ROOT / relative).read_bytes())
    for invalid in (0, "1"):
        payload["accepted_admission_count"] = invalid
        destination.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ValueError, match="accepted_admission_count"):
            coverage._validated_live_receipt_id(tmp_path, source)


@pytest.fixture(scope="module")
def receipt() -> ContentBoundMeasuredCoverageReceipt:
    return build_measured_coverage_receipt(ROOT)


def test_receipt_measures_complete_catalog_and_local_evidence(
    receipt: ContentBoundMeasuredCoverageReceipt,
) -> None:
    totals = receipt.body.totals

    assert totals.catalog_jurisdictions == 45
    assert totals.represented_jurisdictions == 46
    assert totals.catalog_sources == 174
    assert totals.fixture_qualified_sources == 16
    assert totals.live_qualified_sources == 1
    assert totals.catalog_dimensions.model_dump() == {
        "regulatory": 91,
        "funding": 44,
        "formulary": 20,
        "terminology": 17,
    }
    assert totals.fixture_dimensions.model_dump() == {
        "regulatory": 9,
        "funding": 4,
        "formulary": 1,
        "terminology": 2,
    }
    assert totals.live_dimensions.model_dump() == {
        "regulatory": 1,
        "funding": 0,
        "formulary": 0,
        "terminology": 0,
    }
    assert receipt.body.external_network_used is False
    assert receipt.body.external_publication_performed is False
    assert receipt.body.exhaustive_global_coverage is False
    assert receipt.body.current_live_coverage_claimed is False


def test_every_catalog_resource_labels_declared_information(
    receipt: ContentBoundMeasuredCoverageReceipt,
) -> None:
    catalog = json.loads((ROOT / coverage.CATALOG_PATH).read_bytes())
    expected = {item["source_id"]: item for item in catalog["sources"]}
    actual = {item.source_id: item for item in receipt.body.sources}

    assert set(actual) == set(expected)
    for source_id, row in actual.items():
        catalog_row = expected[source_id]
        assert row.catalog_dimension.value == catalog_row["dimension"]
        assert row.catalog_information_domains == tuple(
            sorted(catalog_row["information_domains"])
        )
        assert row.catalog_record_entities == tuple(
            sorted(catalog_row["record_entities"])
        )
        assert row.catalog_available_fields == tuple(
            sorted(catalog_row["available_fields"])
        )


def test_fixture_dimensions_are_measured_not_assumed(
    receipt: ContentBoundMeasuredCoverageReceipt,
) -> None:
    rows = {item.source_id: item for item in receipt.body.sources}

    assert rows["nz-medsafe-products"].measured_fixture_dimensions == (
        SourceDimension.REGULATORY,
    )
    assert rows["nz-pharmac-schedule-xml"].measured_fixture_dimensions == (
        SourceDimension.FUNDING,
    )
    assert rows["nz-nzulm-bulk"].measured_fixture_dimensions == (
        SourceDimension.TERMINOLOGY,
    )
    cms = rows["us-cms-partd-formulary"]
    assert cms.catalog_dimension is SourceDimension.FUNDING
    assert cms.measured_fixture_dimensions == (SourceDimension.FORMULARY,)
    assert cms.catalog_fixture_dimension_agreement is False
    assert all(
        row.catalog_fixture_dimension_agreement is True
        for row in rows.values()
        if row.fixture_qualified and row is not cms
    )


def test_maturity_tracks_catalogue_fixture_and_receipt_backed_live_evidence(
    receipt: ContentBoundMeasuredCoverageReceipt,
) -> None:
    fixture_rows = [
        row for row in receipt.body.sources if row.fixture_qualified
    ]
    catalog_rows = [
        row for row in receipt.body.sources if not row.fixture_qualified
    ]

    assert fixture_rows
    assert catalog_rows
    union_register = next(
        row for row in fixture_rows if row.source_id == "eu-union-register"
    )
    assert union_register.highest_maturity == EvidenceMaturity.LIVE
    assert union_register.live_qualified is True
    assert union_register.live_receipt_id is not None
    assert all(
        row.highest_maturity == EvidenceMaturity.FIXTURE
        for row in fixture_rows
        if row is not union_register
    )
    assert all(
        row.highest_maturity == EvidenceMaturity.CATALOGUE
        for row in catalog_rows
    )
    assert sum(row.live_qualified for row in receipt.body.sources) == 1
    assert all(row.fixture_artifacts for row in fixture_rows)
    assert all(row.implementation_artifacts for row in fixture_rows)
    assert all(row.measured_fixture_records > 0 for row in fixture_rows)


def test_jurisdiction_rows_keep_dimensions_separate(
    receipt: ContentBoundMeasuredCoverageReceipt,
) -> None:
    rows = {item.jurisdiction: item for item in receipt.body.jurisdictions}

    assert rows["NZL"].regulatory_and_funding_both_catalogued is True
    assert rows["NZL"].regulatory_and_funding_both_fixture_qualified is True
    assert rows["USA"].fixture_dimensions.regulatory == 1
    assert rows["USA"].fixture_dimensions.formulary == 1
    assert rows["USA"].fixture_dimensions.funding == 0
    assert rows["GLOBAL"].catalog_source_count == 12
    assert rows["GLOBAL"].fixture_dimensions.terminology == 1
    assert rows["EU"].live_source_count == 1
    assert all(
        row.live_source_count == 0
        for jurisdiction, row in rows.items()
        if jurisdiction != "EU"
    )


def test_receipt_validates_against_json_schema(
    receipt: ContentBoundMeasuredCoverageReceipt,
) -> None:
    schema = json.loads(SCHEMA.read_bytes())
    Draft202012Validator(schema).validate(  # pyright: ignore[reportUnknownMemberType]
        receipt.model_dump(mode="json")
    )


def test_committed_receipt_is_current(
    receipt: ContentBoundMeasuredCoverageReceipt,
) -> None:
    committed = ContentBoundMeasuredCoverageReceipt.model_validate_json(
        COMMITTED_RECEIPT.read_bytes()
    )

    assert committed == receipt


def test_receipt_is_deterministic_content_bound_and_verifiable(
    receipt: ContentBoundMeasuredCoverageReceipt,
) -> None:
    repeated = build_measured_coverage_receipt(ROOT)

    assert repeated == receipt
    assert (
        receipt.receipt_sha256
        == hashlib.sha256(
            coverage._canonical_bytes(receipt.body.model_dump(mode="json"))
        ).hexdigest()
    )
    verify_measured_coverage_receipt(receipt, ROOT)


def test_writer_is_byte_deterministic(
    receipt: ContentBoundMeasuredCoverageReceipt,
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    write_measured_coverage_receipt(receipt, first)
    write_measured_coverage_receipt(receipt, second)

    assert first.read_bytes() == second.read_bytes()
    assert first.read_bytes().endswith(b"\n")
    assert not first.with_suffix(".json.tmp").exists()


def test_fail_closed_guard_accepts_only_supported_evidence(
    receipt: ContentBoundMeasuredCoverageReceipt,
) -> None:
    require_coverage(
        receipt,
        source_ids=("nz-medsafe-products",),
        maturity="catalogue",
        dimensions=(SourceDimension.REGULATORY,),
    )
    require_coverage(
        receipt,
        source_ids=("nz-medsafe-products",),
        maturity="fixture",
        dimensions=(SourceDimension.REGULATORY,),
    )
    require_coverage(
        receipt,
        source_ids=("us-cms-partd-formulary",),
        maturity="fixture",
        dimensions=(SourceDimension.FORMULARY,),
    )


@pytest.mark.parametrize(
    ("source_ids", "maturity", "dimensions", "message"),
    [
        (("not-a-source",), "catalogue", (), "unknown source"),
        (("ae-dha-prices",), "fixture", (), "catalogue maturity"),
        (("nz-medsafe-products",), "live", (), "fixture maturity"),
        (
            ("us-cms-partd-formulary",),
            "fixture",
            (SourceDimension.FUNDING,),
            "lacks fixture dimensions",
        ),
    ],
)
def test_fail_closed_guard_rejects_unsupported_coverage(
    receipt: ContentBoundMeasuredCoverageReceipt,
    source_ids: tuple[str, ...],
    maturity: Literal["catalogue", "fixture", "live"],
    dimensions: tuple[SourceDimension, ...],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        require_coverage(
            receipt,
            source_ids=source_ids,
            maturity=maturity,
            dimensions=dimensions,
        )


def test_tampered_digest_and_current_evidence_are_rejected(
    receipt: ContentBoundMeasuredCoverageReceipt,
) -> None:
    with pytest.raises(ValidationError, match="digest mismatch"):
        ContentBoundMeasuredCoverageReceipt.model_validate({
            "body": receipt.body.model_dump(mode="json"),
            "receipt_sha256": "f" * 64,
        })

    changed_body = receipt.body.model_copy(
        update={"limitations": (*receipt.body.limitations, "Changed claim.")}
    )
    changed = ContentBoundMeasuredCoverageReceipt(
        body=changed_body,
        receipt_sha256=coverage._digest_value(
            changed_body.model_dump(mode="json")
        ),
    )
    with pytest.raises(ValueError, match="current evidence"):
        verify_measured_coverage_receipt(changed, ROOT)


def _catalogue_source_payload(
    receipt: ContentBoundMeasuredCoverageReceipt,
) -> dict[str, object]:
    source = next(
        row for row in receipt.body.sources if not row.fixture_qualified
    )
    return source.model_dump(mode="json")


@pytest.mark.parametrize(
    ("update", "message"),
    [
        ({"jurisdictions": ["ZZZ", "AAA"]}, "sorted and unique"),
        ({"highest_maturity": "fixture"}, "highest maturity"),
        (
            {"catalog_fixture_dimension_agreement": True},
            "cannot claim fixture dimension agreement",
        ),
        (
            {"live_qualified": True, "highest_maturity": "live"},
            "requires exactly one receipt",
        ),
    ],
)
def test_source_model_rejects_incoherent_catalogue_evidence(
    receipt: ContentBoundMeasuredCoverageReceipt,
    update: dict[str, object],
    message: str,
) -> None:
    payload = _catalogue_source_payload(receipt)
    payload.update(update)
    with pytest.raises(ValidationError, match=message):
        SourceCoverage.model_validate(payload)


def test_source_model_rejects_incoherent_fixture_and_live_evidence(
    receipt: ContentBoundMeasuredCoverageReceipt,
) -> None:
    fixture = next(row for row in receipt.body.sources if row.fixture_qualified)
    payload = fixture.model_dump(mode="json")
    payload["fixture_artifacts"] = []
    with pytest.raises(ValidationError, match="requires measured evidence"):
        SourceCoverage.model_validate(payload)

    payload = fixture.model_dump(mode="json")
    payload["catalog_fixture_dimension_agreement"] = False
    with pytest.raises(ValidationError, match="agreement is misreported"):
        SourceCoverage.model_validate(payload)

    payload = fixture.model_dump(mode="json")
    payload.update({
        "fixture_qualified": False,
        "live_qualified": True,
        "highest_maturity": "live",
        "live_receipt_id": "receipt-1",
        "measured_fixture_dimensions": [],
        "catalog_fixture_dimension_agreement": None,
        "measured_fixture_records": 0,
        "fixture_artifacts": [],
        "implementation_artifacts": [],
        "implementations": [],
    })
    with pytest.raises(ValidationError, match="requires fixture qualification"):
        SourceCoverage.model_validate(payload)


def test_body_rejects_unsorted_denominator_sources_and_totals(
    receipt: ContentBoundMeasuredCoverageReceipt,
) -> None:
    payload = receipt.body.model_dump(mode="json")
    payload["catalog_jurisdiction_denominator"] = ["ZZZ", "AAA"]
    with pytest.raises(ValidationError, match="denominator"):
        coverage.MeasuredCoverageBody.model_validate(payload)

    payload = receipt.body.model_dump(mode="json")
    payload["sources"] = list(reversed(payload["sources"]))
    with pytest.raises(ValidationError, match="sources must be sorted"):
        coverage.MeasuredCoverageBody.model_validate(payload)

    payload = receipt.body.model_dump(mode="json")
    payload["jurisdictions"] = list(reversed(payload["jurisdictions"]))
    with pytest.raises(ValidationError, match="jurisdictions must be sorted"):
        coverage.MeasuredCoverageBody.model_validate(payload)

    payload = receipt.body.model_dump(mode="json")
    totals = cast("dict[str, object]", payload["totals"])
    totals["catalog_sources"] = 1
    with pytest.raises(ValidationError, match="totals disagree"):
        coverage.MeasuredCoverageBody.model_validate(payload)


def test_input_and_probe_boundaries_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not a file"):
        coverage._artifact(tmp_path, "missing.json")

    empty = tmp_path / "empty"
    empty.mkdir()
    spec = coverage._ProbeSpec("example", "example", "ZZZ", ("empty",), (), ())
    with pytest.raises(ValueError, match="no fixture artifacts"):
        coverage._fixture_artifacts(tmp_path, spec)

    unsupported = coverage._ProbeSpec(
        "unsupported", "unsupported", "ZZZ", (), (), ()
    )
    with pytest.raises(ValueError, match="unsupported fixture probe"):
        coverage._measure_probe(tmp_path, unsupported)


def test_build_rejects_unresolved_rxnorm_and_empty_nzulm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class EmptyResolver:
        def resolve(self, _query: str) -> tuple[object, ...]:
            return ()

    monkeypatch.setattr(coverage, "bootstrap_rxnorm_resolver", EmptyResolver)
    rxnorm = next(
        spec
        for spec in coverage._PROBES
        if spec.catalog_source_id == "global-rxnorm"
    )
    with pytest.raises(ValueError, match="unresolved alias"):
        coverage._measure_probe(ROOT, rxnorm)

    monkeypatch.undo()

    def empty_nzulm_records(_root: Path) -> tuple[object, ...]:
        return ()

    monkeypatch.setattr(coverage, "_load_nzulm_records", empty_nzulm_records)
    nzulm = next(
        spec
        for spec in coverage._PROBES
        if spec.catalog_source_id == "nz-nzulm-bulk"
    )
    with pytest.raises(ValueError, match="returned no resources"):
        coverage._measure_probe(ROOT, nzulm)
