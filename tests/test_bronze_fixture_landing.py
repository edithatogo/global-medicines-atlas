# pyright: reportUnknownMemberType=false
"""Governed fixture landing for the current public Bronze scope."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pyarrow.parquet as pq
import pytest
import scripts.apply_bronze_fixture_catalog as apply_catalog_script
from scripts.land_bronze_fixtures import main as landing_main

import global_medicines_atlas.bronze_fixture_landing as fixture_landing
from global_medicines_atlas.bronze_admission import BronzeAdmissionState
from global_medicines_atlas.bronze_fixture_landing import (
    CURRENT_SCOPE_FIXTURE_SOURCE_IDS,
    apply_fixture_qualification_to_catalog,
    governed_fixture_specs,
    land_governed_fixtures,
    validate_fixture_source,
)
from global_medicines_atlas.bronze_maturity import classify_catalog_source
from global_medicines_atlas.receipts import EvidenceClass, SourceReceipt
from global_medicines_atlas.reuse_gate import SEARCH_SURFACES, ReuseDisposition
from global_medicines_atlas.source_catalog import (
    AccessMode,
    load_source_catalog,
)

ROOT = Path(__file__).resolve().parents[1]
FIXED_RETRIEVED_AT = datetime(2026, 8, 20, 6, 0, tzinfo=UTC)


@pytest.mark.unit
def test_current_scope_fixture_inventory_is_explicit_and_complete() -> None:
    specs = governed_fixture_specs(ROOT)

    assert {spec.source_id for spec in specs} == set(
        CURRENT_SCOPE_FIXTURE_SOURCE_IDS
    )
    assert len(specs) == 17
    assert all(spec.payload_path.is_file() for spec in specs)
    assert {spec.source_id for spec in specs if spec.source_id == "ca-dpd"} == {
        "ca-dpd"
    }
    assert sum(spec.source_id == "ca-dpd" for spec in specs) == 2


@pytest.mark.unit
def test_catalog_declares_fixture_or_superseding_live_evidence() -> None:
    catalog = {source.source_id: source for source in load_source_catalog()}

    for source_id in CURRENT_SCOPE_FIXTURE_SOURCE_IDS:
        source = catalog[source_id]
        assert source.implemented_ingestion is True
        assert source.readiness.value == "implemented"
        if source_id == "eu-union-register":
            assert source.integration_layer.value == "live_receipt"
            assert source.qualification_state.value == "live_verified"
            assert source.current_receipt_id is not None
            continue
        assert source.integration_layer.value in {"fixture", "parser"}
        assert source.qualification_state.value == "fixture_verified"
        assert source.qualification_references
        assert source.current_receipt_id is None


@pytest.mark.unit
def test_every_unlanded_public_source_has_explicit_noncompletion_blocker() -> (
    None
):
    catalog_document = json.loads(
        (
            ROOT
            / "src/global_medicines_atlas/data/medicine_source_catalog.json"
        ).read_text(encoding="utf-8")
    )
    rights_document = json.loads(
        (
            ROOT / "quality/qualifications/source-rights-disposition.json"
        ).read_text(encoding="utf-8")
    )
    blockers = {
        row["source_id"]: row["blocker"] for row in rights_document["entries"]
    }
    in_scope = {
        row["source_id"]: row
        for row in catalog_document["sources"]
        if classify_catalog_source(row) == "bronze_in_scope"
    }

    assert in_scope
    assert all(
        row["implemented_ingestion"] is True or blockers.get(source_id)
        for source_id, row in in_scope.items()
    )
    assert all(
        blockers[source_id] == "source-specific rights receipt required"
        for source_id, row in in_scope.items()
        if row["implemented_ingestion"] is not True
    )


@pytest.mark.unit
def test_restricted_and_credentialed_payloads_remain_excluded() -> None:
    catalog = {source.source_id: source for source in load_source_catalog()}
    excluded = {
        "au-amt-rf2",
        "au-pbs-embargo",
        "eu-ema-pms-fhir",
        "eu-spor-rms-oms",
        "gb-nhs-dmd",
        "gb-trud-api",
        "nz-nzhts-fhir",
        "nz-nzulm-bulk",
        "us-rxnorm-api",
    }

    assert excluded.isdisjoint(CURRENT_SCOPE_FIXTURE_SOURCE_IDS)
    assert all(
        catalog[source_id].implemented_ingestion is False
        for source_id in excluded
    )
    assert all(
        catalog[source_id].current_receipt_id is None for source_id in excluded
    )


@pytest.mark.unit
def test_catalog_patch_is_complete_and_fails_closed_on_invalid_shapes() -> None:
    document = json.loads(
        (
            ROOT
            / "src/global_medicines_atlas/data/medicine_source_catalog.json"
        ).read_text(encoding="utf-8")
    )
    updated = apply_fixture_qualification_to_catalog(deepcopy(document))
    rows = {row["source_id"]: row for row in updated["sources"]}
    assert all(
        rows[source_id]["qualification_state"] == "fixture_verified"
        for source_id in CURRENT_SCOPE_FIXTURE_SOURCE_IDS
    )
    with pytest.raises(TypeError, match="sources must be a list"):
        apply_fixture_qualification_to_catalog({"sources": {}})
    with pytest.raises(TypeError, match="rows must be objects"):
        apply_fixture_qualification_to_catalog({"sources": ["invalid"]})
    with pytest.raises(KeyError, match="missing from catalog"):
        apply_fixture_qualification_to_catalog({"sources": []})


@pytest.mark.unit
def test_fixture_landing_preserves_bytes_receipts_parquet_and_reuse_gate(
    tmp_path: Path,
) -> None:
    bronze_root = tmp_path / "bronze"
    manifest = land_governed_fixtures(
        ROOT,
        bronze_root=bronze_root,
        retrieved_at=FIXED_RETRIEVED_AT,
    )

    assert manifest.schema_id == (
        "global-medicines-atlas.bronze-fixture-landing"
    )
    assert manifest.evidence_class == "synthetic_fixture_only"
    assert manifest.live_source_coverage_claimed is False
    assert len(manifest.landings) == 17
    assert set(manifest.source_ids) == set(CURRENT_SCOPE_FIXTURE_SOURCE_IDS)
    assert manifest.missing_source_ids == ()

    for item in manifest.landings:
        source = ROOT / item.fixture_path
        payload = bronze_root / item.payload_path
        receipt_path = bronze_root / item.receipt_path
        parquet = bronze_root / item.parquet_path
        lineage = bronze_root / item.lineage_path
        admission = bronze_root / item.admission_path
        assert payload.read_bytes() == source.read_bytes()
        receipt = SourceReceipt.model_validate_json(receipt_path.read_bytes())
        assert receipt.evidence_class is EvidenceClass.SYNTHETIC
        assert receipt.satisfies_live_gate is False
        assert receipt.reuse is not None
        assert receipt.reuse.searched_surfaces == SEARCH_SURFACES
        assert receipt.reuse.disposition is ReuseDisposition.REUSE
        assert any(
            candidate.locator == item.fixture_path
            for candidate in receipt.reuse.payload_candidates
        )
        assert pq.read_table(parquet).num_rows == 1
        assert lineage.is_file()
        assert admission.is_file()
        assert item.admission_state in {"accepted", "quarantined"}

    serialized = json.loads(manifest.canonical_json())
    assert "credential" not in json.dumps(serialized).casefold()


@pytest.mark.unit
def test_fixture_landing_is_deterministic_and_append_only(
    tmp_path: Path,
) -> None:
    bronze_root = tmp_path / "bronze"
    first = land_governed_fixtures(
        ROOT,
        bronze_root=bronze_root,
        retrieved_at=FIXED_RETRIEVED_AT,
    )
    second = land_governed_fixtures(
        ROOT,
        bronze_root=bronze_root,
        retrieved_at=FIXED_RETRIEVED_AT,
    )

    assert first.canonical_json() == second.canonical_json()
    assert first.digest() == second.digest()


@pytest.mark.unit
def test_credentialed_source_cannot_enter_fixture_landing() -> None:
    catalog = {source.source_id: source for source in load_source_catalog()}

    with pytest.raises(ValueError, match="no-credential"):
        validate_fixture_source(catalog["eu-ema-pms-fhir"])
    licensed = catalog["au-artg"].model_copy(
        update={"access_mode": AccessMode.LICENSED_FEED}
    )
    with pytest.raises(ValueError, match="no-credential"):
        validate_fixture_source(licensed)


@pytest.mark.unit
def test_missing_catalog_binding_stops_before_landing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog = tuple(
        source
        for source in load_source_catalog()
        if source.source_id != "au-artg"
    )
    monkeypatch.setattr(fixture_landing, "load_source_catalog", lambda: catalog)

    with pytest.raises(KeyError, match="absent from catalog"):
        land_governed_fixtures(
            ROOT,
            bronze_root=tmp_path / "bronze",
            retrieved_at=FIXED_RETRIEVED_AT,
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("outcome", "message"),
    [
        (object(), "not admitted"),
        (
            SimpleNamespace(
                admission=SimpleNamespace(
                    state=BronzeAdmissionState.QUARANTINED,
                    path=Path("admission.json"),
                )
            ),
            "must be accepted",
        ),
        (
            SimpleNamespace(
                admission=SimpleNamespace(
                    state=BronzeAdmissionState.ACCEPTED,
                    path=None,
                )
            ),
            "lacks a durable path",
        ),
        (
            SimpleNamespace(
                admission=SimpleNamespace(
                    state=BronzeAdmissionState.ACCEPTED,
                    path=Path("admission.json"),
                ),
                receipt=SimpleNamespace(temporal=None),
            ),
            "lacks temporal identity",
        ),
    ],
)
def test_fixture_projection_guards_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    outcome: object,
    message: str,
) -> None:
    def return_outcome(*_args: object, **_kwargs: object) -> object:
        return outcome

    monkeypatch.setattr(
        fixture_landing,
        "land_bronze_payload",
        return_outcome,
    )
    if isinstance(outcome, SimpleNamespace):
        monkeypatch.setattr(fixture_landing, "BronzeLanding", SimpleNamespace)

    with pytest.raises((TypeError, ValueError), match=message):
        land_governed_fixtures(
            ROOT,
            bronze_root=tmp_path / "bronze",
            retrieved_at=FIXED_RETRIEVED_AT,
        )


@pytest.mark.unit
def test_landing_cli_writes_manifest_and_rejects_naive_clock(
    tmp_path: Path,
) -> None:
    output = tmp_path / "bronze"
    assert (
        landing_main([
            "--output",
            str(output),
            "--retrieved-at",
            FIXED_RETRIEVED_AT.isoformat(),
        ])
        == 0
    )
    assert (output / "fixture-landing-manifest.json").is_file()
    with pytest.raises(SystemExit):
        landing_main([
            "--output",
            str(tmp_path / "invalid"),
            "--retrieved-at",
            "2026-08-20T06:00:00",
        ])


@pytest.mark.unit
def test_catalog_script_rewrites_an_explicit_temp_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = (
        ROOT / "src/global_medicines_atlas/data/medicine_source_catalog.json"
    )
    target = tmp_path / "medicine_source_catalog.json"
    target.write_bytes(source.read_bytes())
    monkeypatch.setattr(apply_catalog_script, "CATALOG", target)
    monkeypatch.setattr(apply_catalog_script, "ROOT", tmp_path)

    apply_catalog_script.main()

    updated = json.loads(target.read_text(encoding="utf-8"))
    rows = {row["source_id"]: row for row in updated["sources"]}
    assert rows["global-who-eml"]["qualification_state"] == ("fixture_verified")


@pytest.mark.unit
def test_drugsfda_fixture_reuses_local_payload_before_landing(
    tmp_path: Path,
) -> None:
    manifest = land_governed_fixtures(
        ROOT,
        bronze_root=tmp_path / "bronze",
        retrieved_at=FIXED_RETRIEVED_AT,
    )
    item = next(
        row for row in manifest.landings if row.source_id == "us-drugsfda"
    )
    receipt = SourceReceipt.model_validate_json(
        (tmp_path / "bronze" / item.receipt_path).read_bytes()
    )

    assert receipt.reuse is not None
    assert receipt.reuse.disposition is ReuseDisposition.REUSE
    assert receipt.reuse.searched_surfaces == SEARCH_SURFACES
