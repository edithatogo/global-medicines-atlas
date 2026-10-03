"""Bronze maturity qualification fails closed against repository evidence."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from scripts.qualify_bronze_maturity import main as qualify_bronze_main

from global_medicines_atlas import bronze_maturity as bronze_maturity_mod
from global_medicines_atlas.bronze_maturity import (
    CATALOG_RELATIVE,
    FDA_SHORTAGES_HISTORICAL_SNAPSHOT_COUNT,
    PROPERTY_IDS,
    SCHEMA_RELATIVE,
    classify_catalog_source,
    dump_report,
    evaluate_completeness,
    evaluate_repository,
    landing_source_ids,
    receipt_backed_landing_evidence,
    receipt_backed_landing_source_ids,
    reject_forbidden_evidence,
    run_adversarial_review,
)
from global_medicines_atlas.cms_partd_qualification import (
    RAW_RELATIVE,
    RECORDS_RELATIVE,
    RIGHTS_RELATIVE,
)

ROOT = Path(__file__).resolve().parents[1]
FIXED_CLOCK = datetime(2026, 8, 20, 6, 48, tzinfo=UTC)


def test_cms_source_record_qualification_counts_as_bronze_landing() -> None:
    evidence = receipt_backed_landing_evidence(
        ROOT, {"us-cms-partd-formulary", "us-cms-partd-spending"}
    )
    assert evidence == {
        "us-cms-partd-formulary": (
            "quality/qualifications/cms-partd-source-record-qualification-20260927.json"
        ),
        "us-cms-partd-spending": (
            "quality/qualifications/cms-partd-source-record-qualification-20260927.json"
        ),
    }


def test_fda_shortages_scoped_internal_receipt_counts_as_bronze_landing() -> (
    None
):
    evidence = receipt_backed_landing_evidence(ROOT, {"us-fda-drug-shortages"})
    assert evidence == {
        "us-fda-drug-shortages": (
            "quality/qualifications/fda-shortages-live-corpus-20260821.json"
        )
    }


def test_australian_mbs_accepted_raw_receipt_counts_as_bronze_landing() -> None:
    evidence = receipt_backed_landing_evidence(ROOT, {"au-mbs"})

    assert evidence == {
        "au-mbs": (
            "quality/qualifications/australian-mbs-bronze-source-receipt-20261003.json"
        )
    }
    receipt = json.loads(
        (
            ROOT
            / "quality/qualifications/australian-mbs-bronze-source-receipt-20261003.json"
        ).read_text(encoding="utf-8")
    )
    assert receipt["qualification_scope"] == "raw_b1_b2_only"
    assert receipt["b2"]["state"] == "external_reference_only"
    assert receipt["boundaries"]["source_record_projection_qualified"] is False
    assert receipt["boundaries"]["m112_federation_accepted"] is False


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("acquisition_id",), "0" * 64),
        (("receipt_id",), "mbs-release:wrong"),
        (("rights_state",), "unknown"),
        (("admission_state",), "quarantined"),
        (("b2", "state"), "retained"),
        (("files", "source_receipt", "sha256"), "0" * 64),
        (("effective_date",), "2026-07-01"),
        (("source_id",), "au-mbs-p7-legacy-workbook"),
    ],
)
def test_australian_mbs_receipt_rejects_mutated_identity_or_gate(
    path: tuple[str, ...], value: str
) -> None:
    relative = "quality/qualifications/australian-mbs-bronze-source-receipt-20261003.json"
    receipt = json.loads((ROOT / relative).read_text(encoding="utf-8"))
    target = receipt
    for segment in path[:-1]:
        target = target[segment]
    target[path[-1]] = value

    assert not bronze_maturity_mod._is_successful_australian_mbs_receipt(
        ROOT, receipt, "au-mbs"
    )


def test_australian_mbs_receipt_qualification_schema() -> None:
    receipt = json.loads(
        (
            ROOT
            / "quality/qualifications/australian-mbs-bronze-source-receipt-20261003.json"
        ).read_text(encoding="utf-8")
    )
    schema = json.loads(
        (
            ROOT / "schemas/australian-mbs-bronze-source-receipt-v1.json"
        ).read_text(encoding="utf-8")
    )

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(receipt)


def test_fda_shortages_success_predicate_accepts_qualified_receipt() -> None:
    receipt = json.loads(
        (
            ROOT
            / "quality/qualifications/fda-shortages-live-corpus-20260821.json"
        ).read_text(encoding="utf-8")
    )
    assert bronze_maturity_mod._is_successful_fda_shortages_receipt(
        receipt, "us-fda-drug-shortages"
    )
    assert FDA_SHORTAGES_HISTORICAL_SNAPSHOT_COUNT == 129


def test_nice_internal_acquisition_receipt_counts_as_bronze_landing() -> None:
    evidence = receipt_backed_landing_evidence(
        ROOT, {"gb-nice-medicines-utilisation"}
    )
    assert evidence == {
        "gb-nice-medicines-utilisation": (
            "quality/qualifications/nice-utilisation-acquisition-success-20260821.json"
        )
    }
    receipt = json.loads(
        (
            ROOT
            / "quality/qualifications/nice-utilisation-acquisition-success-20260821.json"
        ).read_text(encoding="utf-8")
    )
    assert receipt["source_records_projected"] is False
    assert receipt["external_publication_authorized"] is False


@pytest.mark.unit
def test_sweden_private_aggregate_receipt_counts_as_bronze_landing() -> None:
    evidence = receipt_backed_landing_evidence(
        ROOT, {bronze_maturity_mod.SWEDEN_SOURCE_ID}
    )
    assert evidence == {
        bronze_maturity_mod.SWEDEN_SOURCE_ID: bronze_maturity_mod.SWEDEN_QUALIFICATION_RELATIVE
    }
    receipt = json.loads(
        (ROOT / bronze_maturity_mod.SWEDEN_QUALIFICATION_RELATIVE).read_text(
            encoding="utf-8"
        )
    )
    assert receipt["rights_boundary"]["coarse_rights_state"] == "unknown"
    assert receipt["rights_boundary"]["publication_authorized"] is False


@pytest.mark.unit
def test_norpd_private_historical_report_counts_as_bronze_landing() -> None:
    evidence = receipt_backed_landing_evidence(
        ROOT, {bronze_maturity_mod.NORPD_SOURCE_ID}
    )
    assert evidence == {
        bronze_maturity_mod.NORPD_SOURCE_ID: bronze_maturity_mod.NORPD_QUALIFICATION_RELATIVE
    }
    receipt = json.loads(
        (ROOT / bronze_maturity_mod.NORPD_QUALIFICATION_RELATIVE).read_text(
            encoding="utf-8"
        )
    )
    assert receipt["report_period"] == "2014-2018"
    assert receipt["rights_boundary"]["coarse_rights_state"] == "unknown"
    assert receipt["rights_boundary"]["publication_authorized"] is False
    assert receipt["rights_boundary"]["post_2020_coverage_asserted"] is False


@pytest.mark.unit
def test_open_medic_all_release_receipt_counts_as_bronze_landing() -> None:
    evidence = receipt_backed_landing_evidence(
        ROOT, {bronze_maturity_mod.OPEN_MEDIC_SOURCE_ID}
    )
    assert evidence == {
        bronze_maturity_mod.OPEN_MEDIC_SOURCE_ID: (
            bronze_maturity_mod.OPEN_MEDIC_QUALIFICATION_RELATIVE
        )
    }


@pytest.mark.parametrize(
    "mutate",
    [
        lambda receipt: receipt.update(source_id="us-drugsfda"),
        lambda receipt: receipt.update(public_dataset="other/dataset"),
        lambda receipt: receipt.update(immutable_revision="0" * 40),
        lambda receipt: receipt.update(accepted_admission_count=11),
        lambda receipt: receipt.update(accepted_admission_count=12.0),
        lambda receipt: receipt.update(recovered_acquisition_count=11),
        lambda receipt: receipt.update(
            source_record_parquet_pairs_byte_identical=11
        ),
        lambda receipt: receipt.update(payload_byte_count=1),
        lambda receipt: receipt["items"].pop(),
        lambda receipt: receipt["items"][1].update(year=2014),
        lambda receipt: receipt["items"][0].update(admission="quarantined"),
        lambda receipt: receipt["items"][0].update(payload_sha256="bad"),
        lambda receipt: receipt["items"][0].update(payload_sha256="0" * 64),
        lambda receipt: receipt["items"][0].update(acquisition_id="0" * 64),
        lambda receipt: receipt["items"][0].update(
            source_records_sha256="0" * 64
        ),
        lambda receipt: receipt.update(
            canonical_medicine_identity_claimed=True
        ),
    ],
)
@pytest.mark.unit
def test_open_medic_receipt_rejects_release_scope_or_digest_drift(
    mutate,
) -> None:
    receipt = json.loads(
        (
            ROOT / bronze_maturity_mod.OPEN_MEDIC_QUALIFICATION_RELATIVE
        ).read_text(encoding="utf-8")
    )
    mutate(receipt)

    assert not bronze_maturity_mod._is_successful_open_medic_receipt(
        ROOT, receipt, bronze_maturity_mod.OPEN_MEDIC_SOURCE_ID
    )


@pytest.mark.parametrize(
    ("relative", "collection", "field", "value"),
    [
        (
            bronze_maturity_mod.OPEN_MEDIC_ACQUISITION_AUTHORIZATION_RELATIVE,
            "sources",
            "acquisition_authorized",
            False,
        ),
        (
            bronze_maturity_mod.OPEN_MEDIC_ACQUISITION_AUTHORIZATION_RELATIVE,
            "sources",
            "external_publication_authorized",
            False,
        ),
        (
            bronze_maturity_mod.OPEN_MEDIC_RIGHTS_DISPOSITION_RELATIVE,
            "entries",
            "public_derived_release",
            "not_approved",
        ),
        (
            bronze_maturity_mod.OPEN_MEDIC_RIGHTS_LEDGER_RELATIVE,
            "entries",
            "maintainer_licence_approved",
            False,
        ),
        (
            bronze_maturity_mod.OPEN_MEDIC_RIGHTS_LEDGER_RELATIVE,
            "entries",
            "publish_source_bytes",
            "unknown",
        ),
        (
            CATALOG_RELATIVE,
            "sources",
            "rights_status",
            "review_required",
        ),
    ],
)
@pytest.mark.unit
def test_open_medic_receipt_rejects_rights_or_authority_drift(
    tmp_path: Path,
    relative: str,
    collection: str,
    field: str,
    value: object,
) -> None:
    paths = (
        bronze_maturity_mod.OPEN_MEDIC_ACQUISITION_AUTHORIZATION_RELATIVE,
        bronze_maturity_mod.OPEN_MEDIC_RIGHTS_DISPOSITION_RELATIVE,
        bronze_maturity_mod.OPEN_MEDIC_RIGHTS_LEDGER_RELATIVE,
        bronze_maturity_mod.OPEN_MEDIC_RELEASE_MANIFEST_RELATIVE,
        CATALOG_RELATIVE,
    )
    for source_path in paths:
        target = tmp_path / source_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / source_path).read_bytes())
    authority_path = tmp_path / relative
    authority = json.loads(authority_path.read_text(encoding="utf-8"))
    row = next(
        entry
        for entry in authority[collection]
        if entry["source_id"] == bronze_maturity_mod.OPEN_MEDIC_SOURCE_ID
    )
    row[field] = value
    authority_path.write_text(json.dumps(authority), encoding="utf-8")
    receipt = json.loads(
        (
            ROOT / bronze_maturity_mod.OPEN_MEDIC_QUALIFICATION_RELATIVE
        ).read_text(encoding="utf-8")
    )

    assert not bronze_maturity_mod._is_successful_open_medic_receipt(
        tmp_path, receipt, bronze_maturity_mod.OPEN_MEDIC_SOURCE_ID
    )


@pytest.mark.unit
def test_open_medic_receipt_rejects_missing_rights_authority(
    tmp_path: Path,
) -> None:
    source_catalog = tmp_path / CATALOG_RELATIVE
    source_catalog.parent.mkdir(parents=True)
    source_catalog.write_bytes((ROOT / CATALOG_RELATIVE).read_bytes())
    release_manifest = (
        tmp_path / bronze_maturity_mod.OPEN_MEDIC_RELEASE_MANIFEST_RELATIVE
    )
    release_manifest.parent.mkdir(parents=True, exist_ok=True)
    release_manifest.write_bytes(
        (
            ROOT / bronze_maturity_mod.OPEN_MEDIC_RELEASE_MANIFEST_RELATIVE
        ).read_bytes()
    )
    receipt = json.loads(
        (
            ROOT / bronze_maturity_mod.OPEN_MEDIC_QUALIFICATION_RELATIVE
        ).read_text(encoding="utf-8")
    )

    assert not bronze_maturity_mod._is_successful_open_medic_receipt(
        tmp_path, receipt, bronze_maturity_mod.OPEN_MEDIC_SOURCE_ID
    )


@pytest.mark.parametrize(
    "contents",
    ["{", "[]", "{}", '{"sources": null}', '{"sources": []}'],
)
@pytest.mark.unit
def test_open_medic_source_entry_rejects_malformed_or_missing_ledger_rows(
    tmp_path: Path, contents: str
) -> None:
    ledger = tmp_path / "ledger.json"
    ledger.write_text(contents, encoding="utf-8")

    assert (
        bronze_maturity_mod._source_entry(
            tmp_path, "ledger.json", "sources", "fr-open-medic"
        )
        is None
    )


@pytest.mark.unit
def test_open_medic_source_entry_accepts_one_matching_row_among_other_values(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "ledger.json"
    ledger.write_text(
        json.dumps({
            "sources": [
                None,
                {"source_id": "other"},
                {"source_id": "fr-open-medic", "approved": True},
            ]
        }),
        encoding="utf-8",
    )

    assert bronze_maturity_mod._source_entry(
        tmp_path, "ledger.json", "sources", "fr-open-medic"
    ) == {"source_id": "fr-open-medic", "approved": True}


@pytest.mark.parametrize("items", [None, "not-a-list"])
@pytest.mark.unit
def test_open_medic_release_items_rejects_non_list_items(items: object) -> None:
    assert (
        bronze_maturity_mod._open_medic_release_items({"items": items}) is None
    )


@pytest.mark.unit
def test_open_medic_release_items_rejects_non_mapping_release() -> None:
    assert (
        bronze_maturity_mod._open_medic_release_items({"items": [None]}) is None
    )


@pytest.mark.parametrize("catalog", ["missing", "[]", '{"sources": null}'])
@pytest.mark.unit
def test_open_medic_rights_rejects_malformed_catalog(
    tmp_path: Path, catalog: str
) -> None:
    if catalog != "missing":
        catalog_path = tmp_path / CATALOG_RELATIVE
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        catalog_path.write_text(catalog, encoding="utf-8")

    assert not bronze_maturity_mod._open_medic_rights_valid(tmp_path)


@pytest.mark.unit
def test_open_medic_rights_rejects_duplicate_catalog_source(
    tmp_path: Path,
) -> None:
    paths = (
        bronze_maturity_mod.OPEN_MEDIC_ACQUISITION_AUTHORIZATION_RELATIVE,
        bronze_maturity_mod.OPEN_MEDIC_RIGHTS_DISPOSITION_RELATIVE,
        bronze_maturity_mod.OPEN_MEDIC_RIGHTS_LEDGER_RELATIVE,
        bronze_maturity_mod.OPEN_MEDIC_RELEASE_MANIFEST_RELATIVE,
        CATALOG_RELATIVE,
    )
    for relative in paths:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    catalog_path = tmp_path / CATALOG_RELATIVE
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    source = next(
        row
        for row in catalog["sources"]
        if row["source_id"] == bronze_maturity_mod.OPEN_MEDIC_SOURCE_ID
    )
    catalog["sources"].append(source)
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")

    assert not bronze_maturity_mod._open_medic_rights_valid(tmp_path)


@pytest.mark.unit
def test_open_medic_receipt_rejects_different_source_identity() -> None:
    receipt = json.loads(
        (
            ROOT / bronze_maturity_mod.OPEN_MEDIC_QUALIFICATION_RELATIVE
        ).read_text(encoding="utf-8")
    )

    assert not bronze_maturity_mod._is_successful_open_medic_receipt(
        ROOT, receipt, "other-source"
    )


@pytest.mark.unit
def test_open_medic_expected_release_manifest_is_content_bound(
    tmp_path: Path,
) -> None:
    relative = bronze_maturity_mod.OPEN_MEDIC_RELEASE_MANIFEST_RELATIVE
    target = tmp_path / relative
    target.parent.mkdir(parents=True)
    document = json.loads((ROOT / relative).read_text(encoding="utf-8"))
    document["releases"][0]["acquisition_id"] = "0" * 64
    target.write_text(json.dumps(document), encoding="utf-8")

    assert (
        bronze_maturity_mod._open_medic_expected_release_items(tmp_path) is None
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda manifest: manifest.update(releases=None),
        lambda manifest: manifest.update(releases=[]),
        lambda manifest: manifest["releases"].__setitem__(0, None),
        lambda manifest: manifest["releases"][0].update(
            public_archive_receipt_sha256="bad"
        ),
        lambda manifest: manifest["releases"][0].update(
            public_archive_payload_sha256="bad"
        ),
        lambda manifest: manifest["releases"][0].update(
            payload_sha256="0" * 64
        ),
        lambda manifest: manifest["releases"][0].update(
            public_archive_payload_byte_count=1
        ),
    ],
)
@pytest.mark.unit
def test_open_medic_manifest_release_projection_rejects_drift(mutate) -> None:
    manifest = json.loads(
        (
            ROOT / bronze_maturity_mod.OPEN_MEDIC_RELEASE_MANIFEST_RELATIVE
        ).read_text(encoding="utf-8")
    )
    mutate(manifest)

    assert (
        bronze_maturity_mod._open_medic_manifest_release_items(manifest) is None
    )


@pytest.mark.parametrize(
    "field",
    [
        "schema_id",
        "schema_version",
        "source_id",
        "public_dataset",
        "immutable_revision",
        "public_manifest_sha256",
    ],
)
@pytest.mark.unit
def test_open_medic_release_manifest_rejects_identity_drift(field: str) -> None:
    manifest = json.loads(
        (
            ROOT / bronze_maturity_mod.OPEN_MEDIC_RELEASE_MANIFEST_RELATIVE
        ).read_text(encoding="utf-8")
    )
    manifest[field] = "drifted"

    assert not bronze_maturity_mod._open_medic_release_manifest_identity_valid(
        manifest
    )


@pytest.mark.unit
def test_open_medic_expected_release_items_rejects_pinned_identity_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    relative = bronze_maturity_mod.OPEN_MEDIC_RELEASE_MANIFEST_RELATIVE
    manifest_path = tmp_path / relative
    manifest_path.parent.mkdir(parents=True)
    manifest = json.loads((ROOT / relative).read_text(encoding="utf-8"))
    manifest["immutable_revision"] = "drifted"
    encoded = json.dumps(manifest).encode()
    manifest_path.write_bytes(encoded)
    monkeypatch.setattr(
        bronze_maturity_mod,
        "OPEN_MEDIC_RELEASE_MANIFEST_SHA256",
        sha256(encoded).hexdigest(),
    )

    assert (
        bronze_maturity_mod._open_medic_expected_release_items(tmp_path) is None
    )


@pytest.mark.parametrize("contents", [None, "{"])
@pytest.mark.unit
def test_open_medic_expected_release_manifest_rejects_missing_or_invalid_json(
    tmp_path: Path, contents: str | None
) -> None:
    if contents is not None:
        manifest_path = (
            tmp_path / bronze_maturity_mod.OPEN_MEDIC_RELEASE_MANIFEST_RELATIVE
        )
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(contents, encoding="utf-8")

    assert (
        bronze_maturity_mod._open_medic_expected_release_items(tmp_path) is None
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda receipt: receipt.update(workflow_run="https://example.org/run"),
        lambda receipt: receipt.update(report_period="2021-2025"),
        lambda receipt: receipt.update(payload_sha256="0"),
        lambda receipt: receipt["retention"].update(revision="bad-revision"),
        lambda receipt: receipt["retention"].update(private=False),
        lambda receipt: receipt["retention"].update(gated=True),
        lambda receipt: receipt["retention"].update(archive_sha256="0"),
        lambda receipt: receipt["retention"].update(
            authenticated_pinned_revision_readback_verified=False
        ),
        lambda receipt: receipt["retention"].update(
            clean_room_recovered_payload_count=0
        ),
        lambda receipt: receipt["retention"].update(
            temporary_runner_payload_bytes_removed_after_digest_verification=False
        ),
        lambda receipt: receipt["rights_boundary"].update(
            external_publication_authorized=True
        ),
        lambda receipt: receipt["rights_boundary"].update(
            post_2020_coverage_asserted=True
        ),
    ],
)
@pytest.mark.unit
def test_norpd_landing_rejects_receipt_or_boundary_drift(mutate) -> None:
    receipt = json.loads(
        (ROOT / bronze_maturity_mod.NORPD_QUALIFICATION_RELATIVE).read_text(
            encoding="utf-8"
        )
    )
    mutate(receipt)
    assert not bronze_maturity_mod._is_successful_norpd_receipt(
        ROOT, receipt, bronze_maturity_mod.NORPD_SOURCE_ID
    )


@pytest.mark.parametrize("authorization_state", ["missing", "invalid_json"])
@pytest.mark.unit
def test_norpd_landing_rejects_unreadable_authorization(
    tmp_path: Path, authorization_state: str
) -> None:
    authorization_path = (
        tmp_path / bronze_maturity_mod.NORPD_AUTHORIZATION_RELATIVE
    )
    authorization_path.parent.mkdir(parents=True)
    if authorization_state == "invalid_json":
        authorization_path.write_text("{invalid", encoding="utf-8")
    receipt = json.loads(
        (ROOT / bronze_maturity_mod.NORPD_QUALIFICATION_RELATIVE).read_text(
            encoding="utf-8"
        )
    )

    assert not bronze_maturity_mod._is_successful_norpd_receipt(
        tmp_path, receipt, bronze_maturity_mod.NORPD_SOURCE_ID
    )


@pytest.mark.parametrize(
    "authorization",
    [
        None,
        {"sources": "not-a-list"},
        {"sources": []},
    ],
)
@pytest.mark.unit
def test_norpd_landing_rejects_malformed_authorization_structure(
    tmp_path: Path, authorization: object
) -> None:
    authorization_path = (
        tmp_path / bronze_maturity_mod.NORPD_AUTHORIZATION_RELATIVE
    )
    authorization_path.parent.mkdir(parents=True)
    authorization_path.write_text(json.dumps(authorization), encoding="utf-8")
    receipt = json.loads(
        (ROOT / bronze_maturity_mod.NORPD_QUALIFICATION_RELATIVE).read_text(
            encoding="utf-8"
        )
    )

    assert not bronze_maturity_mod._is_successful_norpd_receipt(
        tmp_path, receipt, bronze_maturity_mod.NORPD_SOURCE_ID
    )


@pytest.mark.unit
def test_norpd_landing_rejects_non_mapping_receipt_substructures(
    tmp_path: Path,
) -> None:
    authorization_path = (
        tmp_path / bronze_maturity_mod.NORPD_AUTHORIZATION_RELATIVE
    )
    authorization_path.parent.mkdir(parents=True)
    authorization_path.write_bytes(
        (ROOT / bronze_maturity_mod.NORPD_AUTHORIZATION_RELATIVE).read_bytes()
    )
    receipt = json.loads(
        (ROOT / bronze_maturity_mod.NORPD_QUALIFICATION_RELATIVE).read_text(
            encoding="utf-8"
        )
    )
    receipt["retention"] = []

    assert not bronze_maturity_mod._is_successful_norpd_receipt(
        tmp_path, receipt, bronze_maturity_mod.NORPD_SOURCE_ID
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda receipt: receipt.update(workflow_commit="0" * 40),
        lambda receipt: receipt["payload_sha256"].pop(),
        lambda receipt: receipt["retention"].update(archive_sha256="0" * 64),
        lambda receipt: receipt["rights_boundary"].update(
            external_publication_authorized=True
        ),
    ],
)
@pytest.mark.unit
def test_sweden_landing_rejects_receipt_or_boundary_drift(
    tmp_path: Path, mutate
) -> None:
    receipt = json.loads(
        (ROOT / bronze_maturity_mod.SWEDEN_QUALIFICATION_RELATIVE).read_text(
            encoding="utf-8"
        )
    )
    mutate(receipt)
    relative = bronze_maturity_mod.SWEDEN_QUALIFICATION_RELATIVE
    receipt_path = tmp_path / relative
    receipt_path.parent.mkdir(parents=True)
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    overrides = tmp_path / bronze_maturity_mod.LANDING_OVERRIDES_RELATIVE
    overrides.parent.mkdir(parents=True)
    overrides.write_text(
        json.dumps({
            "overrides": [
                {
                    "source_id": bronze_maturity_mod.SWEDEN_SOURCE_ID,
                    "state": "landed_and_evidenced",
                    "evidence_references": [relative],
                }
            ]
        }),
        encoding="utf-8",
    )
    assert (
        receipt_backed_landing_evidence(
            tmp_path, {bronze_maturity_mod.SWEDEN_SOURCE_ID}
        )
        == {}
    )


@pytest.mark.parametrize(
    "authorization_field",
    [
        "acquisition_authorized",
        "internal_retention_authorized",
        "public_release_authorized",
        "external_publication_authorized",
    ],
)
def test_nice_internal_landing_requires_source_specific_rights(
    tmp_path: Path, authorization_field: str
) -> None:
    receipt = json.loads(
        (
            ROOT
            / "quality/qualifications/nice-utilisation-acquisition-success-20260821.json"
        ).read_text(encoding="utf-8")
    )
    authorization = json.loads(
        (
            ROOT
            / "quality/qualifications/nice-utilisation-acquisition-authorization.json"
        ).read_text(encoding="utf-8")
    )
    authorization[authorization_field] = not authorization[authorization_field]
    authorization_path = (
        tmp_path
        / "quality/qualifications/nice-utilisation-acquisition-authorization.json"
    )
    authorization_path.parent.mkdir(parents=True)
    authorization_path.write_text(json.dumps(authorization), encoding="utf-8")
    receipt_path = (
        tmp_path
        / "quality/qualifications/nice-utilisation-acquisition-success-20260821.json"
    )
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    overrides_path = (
        tmp_path
        / "src/global_medicines_atlas/data/source_landing_overrides.json"
    )
    overrides_path.parent.mkdir(parents=True)
    overrides_path.write_text(
        json.dumps({
            "overrides": [
                {
                    "source_id": "gb-nice-medicines-utilisation",
                    "state": "landed_and_evidenced",
                    "evidence_references": [
                        "quality/qualifications/nice-utilisation-acquisition-success-20260821.json"
                    ],
                }
            ]
        }),
        encoding="utf-8",
    )

    assert (
        receipt_backed_landing_evidence(
            tmp_path, {"gb-nice-medicines-utilisation"}
        )
        == {}
    )


@pytest.mark.parametrize(
    "failure",
    [
        "missing_authorization",
        "invalid_authorization",
        "archive",
        "hashes",
        "truncated_payloads",
    ],
)
def test_nice_internal_landing_rejects_incomplete_receipt_metadata(
    tmp_path: Path, failure: str
) -> None:
    receipt = json.loads(
        (
            ROOT
            / "quality/qualifications/nice-utilisation-acquisition-success-20260821.json"
        ).read_text(encoding="utf-8")
    )
    authorization = json.loads(
        (
            ROOT
            / "quality/qualifications/nice-utilisation-acquisition-authorization.json"
        ).read_text(encoding="utf-8")
    )
    if failure == "archive":
        receipt["private_archive"] = None
    elif failure == "hashes":
        receipt["payload_sha256"] = {}
    elif failure == "truncated_payloads":
        receipt["payload_count"] = 1
        receipt["accepted_admission_count"] = 1
        receipt["acquisition_manifest_count"] = 1
        receipt["payload_sha256"] = receipt["payload_sha256"][:1]
        receipt["private_archive"]["restored_payload_count"] = 1
    receipt_path = (
        tmp_path
        / "quality/qualifications/nice-utilisation-acquisition-success-20260821.json"
    )
    receipt_path.parent.mkdir(parents=True)
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    authorization_path = (
        tmp_path
        / "quality/qualifications/nice-utilisation-acquisition-authorization.json"
    )
    if failure != "missing_authorization":
        authorization_path.write_text(
            "[]"
            if failure == "invalid_authorization"
            else json.dumps(authorization),
            encoding="utf-8",
        )
    overrides_path = (
        tmp_path
        / "src/global_medicines_atlas/data/source_landing_overrides.json"
    )
    overrides_path.parent.mkdir(parents=True)
    overrides_path.write_text(
        json.dumps({
            "overrides": [
                {
                    "source_id": "gb-nice-medicines-utilisation",
                    "state": "landed_and_evidenced",
                    "evidence_references": [
                        "quality/qualifications/nice-utilisation-acquisition-success-20260821.json"
                    ],
                }
            ]
        }),
        encoding="utf-8",
    )

    assert (
        receipt_backed_landing_evidence(
            tmp_path, {"gb-nice-medicines-utilisation"}
        )
        == {}
    )


@pytest.mark.parametrize(
    ("source_id", "field", "value"),
    [
        ("us-fda-orange-book", "prompt_complete", True),
        ("us-fda-drug-shortages", "prompt_complete", False),
        ("us-fda-drug-shortages", "schema_version", True),
        ("us-fda-drug-shortages", "current_source_record_rows", 0),
        ("us-fda-drug-shortages", "archive_checksums_verified", 0),
    ],
)
def test_fda_shortages_success_predicate_rejects_unqualified_receipt(
    source_id: str, field: str, value: object
) -> None:
    receipt = json.loads(
        (
            ROOT
            / "quality/qualifications/fda-shortages-live-corpus-20260821.json"
        ).read_text(encoding="utf-8")
    )
    receipt[field] = value
    assert not bronze_maturity_mod._is_successful_fda_shortages_receipt(
        receipt, source_id
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("internal_retention_authorized", False),
        ("current_source_record_projection_count", 0),
        ("current_recovered_source_record_projection_count", 0),
        ("current_source_record_parquet_pairs_byte_identical", 0),
        ("unique_historical_list_snapshots_archived", 128),
        ("external_publication_performed", True),
        ("historical_detail_snapshot_coverage_complete", True),
    ],
)
def test_fda_shortages_receipt_fails_closed_on_scope_or_evidence_drift(
    tmp_path: Path, field: str, value: object
) -> None:
    qualification = json.loads(
        (
            ROOT
            / "quality/qualifications/fda-shortages-live-corpus-20260821.json"
        ).read_text(encoding="utf-8")
    )
    qualification[field] = value
    receipt = (
        tmp_path
        / "quality/qualifications/fda-shortages-live-corpus-20260821.json"
    )
    receipt.parent.mkdir(parents=True)
    receipt.write_text(json.dumps(qualification), encoding="utf-8")
    overrides = tmp_path / bronze_maturity_mod.LANDING_OVERRIDES_RELATIVE
    overrides.parent.mkdir(parents=True)
    overrides.write_text(
        json.dumps({
            "overrides": [
                {
                    "source_id": "us-fda-drug-shortages",
                    "state": "landed_and_evidenced",
                    "evidence_references": [str(receipt.relative_to(tmp_path))],
                }
            ]
        }),
        encoding="utf-8",
    )
    assert (
        receipt_backed_landing_evidence(tmp_path, {"us-fda-drug-shortages"})
        == {}
    )


def test_cms_maturity_landing_rejects_rights_drift(tmp_path: Path) -> None:
    for relative in (RAW_RELATIVE, RECORDS_RELATIVE, RIGHTS_RELATIVE):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    overrides = tmp_path / bronze_maturity_mod.LANDING_OVERRIDES_RELATIVE
    overrides.parent.mkdir(parents=True, exist_ok=True)
    overrides.write_text(
        json.dumps({
            "overrides": [
                {
                    "source_id": "us-cms-partd-spending",
                    "state": "landed_and_evidenced",
                    "evidence_references": [RECORDS_RELATIVE],
                }
            ]
        }),
        encoding="utf-8",
    )
    rights = json.loads(
        (tmp_path / RIGHTS_RELATIVE).read_text(encoding="utf-8")
    )
    rights["external_publication_authorized"] = False
    (tmp_path / RIGHTS_RELATIVE).write_text(
        json.dumps(rights), encoding="utf-8"
    )
    assert (
        receipt_backed_landing_evidence(tmp_path, {"us-cms-partd-spending"})
        == {}
    )


@pytest.mark.unit
@pytest.mark.parametrize("path_kind", ["relative", "absolute"])
def test_qualification_cli_accepts_custom_output_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path_kind: str
) -> None:
    monkeypatch.chdir(tmp_path)
    target = Path("reports/bronze.json")
    if path_kind == "absolute":
        target = tmp_path / target
    assert qualify_bronze_main(["--output", str(target)]) == 0
    report = json.loads(target.read_text(encoding="utf-8"))
    assert report["report_complete"] is True
    assert report["qualification_state"] in {"blocked", "qualified"}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validator():
    schema = _load(ROOT / SCHEMA_RELATIVE)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _validate(report: dict[str, Any]) -> None:
    _validator().validate(  # pyright: ignore[reportUnknownMemberType]
        report
    )


@pytest.mark.unit
def test_licensed_and_credentialed_sources_are_excluded_not_incomplete() -> (
    None
):
    assert (
        classify_catalog_source({
            "source_id": "au-artg",
            "authentication": "none",
            "access_mode": "web_search",
        })
        == "bronze_in_scope"
    )
    assert (
        classify_catalog_source({
            "source_id": "au-pbs-embargo",
            "authentication": "manual_approval",
            "access_mode": "licensed_feed",
        })
        == "excluded"
    )
    assert (
        classify_catalog_source({
            "source_id": "nz-nzulm-bulk",
            "authentication": "account",
            "access_mode": "download",
        })
        == "excluded"
    )
    assert (
        classify_catalog_source({
            "source_id": "global-rxnorm",
            "authentication": "none",
            "access_mode": "api",
        })
        == "fixture_only"
    )


@pytest.mark.unit
def test_publication_and_stable_v1_success_are_forbidden_bronze_evidence() -> (
    None
):
    rejected = reject_forbidden_evidence((
        "src/global_medicines_atlas/bronze_landing.py",
        "quality/qualifications/stable-v1-contract.json",
        "docs/publication/data-layer-archive-receipt.md",
    ))
    assert "quality/qualifications/stable-v1-contract.json" in rejected
    assert "docs/publication/data-layer-archive-receipt.md" in rejected
    assert "src/global_medicines_atlas/bronze_landing.py" not in rejected


@pytest.mark.unit
def test_live_report_validates_and_does_not_declare_false_maturity() -> None:
    report = evaluate_repository(
        ROOT,
        clock=lambda: FIXED_CLOCK,
        git_commit="test",
    )
    _validate(report)
    assert [row["property_id"] for row in report["properties"]] == list(
        PROPERTY_IDS
    )
    assert report["report_complete"] is True
    assert (
        report["completeness_inventory"][
            "missing_coverage_is_not_negative_evidence"
        ]
        is True
    )
    inventory = report["completeness_inventory"]
    assert inventory["catalog_source_count"] == (
        inventory["bronze_in_scope_count"]
        + inventory["fixture_only_count"]
        + inventory["excluded_count"]
    )
    assert report["adversarial_review"]["actor"] == (
        "criteria-versus-code-tests-docs"
    )
    assert report["adversarial_review"]["kind"] == (
        "independent-repository-evidence-review"
    )
    assert "second maintainer" not in report["adversarial_review"]["method"]
    assert "not a person" in report["adversarial_review"]["method"]
    assert report["adversarial_review"]["passed"] is True
    blocked = [
        row["property_id"]
        for row in report["properties"]
        if row["state"] != "evidenced"
    ]
    if blocked:
        assert report["bronze_mature"] is False
        assert report["qualification_state"] == "blocked"
        assert report["blockers"]
    else:
        assert report["bronze_mature"] is True
        assert report["qualification_state"] == "qualified"
        assert report["blockers"] == []


@pytest.mark.unit
def test_schema_rejects_mature_declaration_with_blockers() -> None:
    report = evaluate_repository(
        ROOT,
        clock=lambda: FIXED_CLOCK,
        git_commit="test",
    )
    invalid = copy.deepcopy(report)
    invalid["bronze_mature"] = True
    invalid["qualification_state"] = "qualified"
    with pytest.raises(ValidationError):
        _validate(invalid)


@pytest.mark.unit
def test_adversarial_review_rejects_false_maturity_claim() -> None:
    report = evaluate_repository(
        ROOT,
        clock=lambda: FIXED_CLOCK,
        git_commit="test",
    )
    review = run_adversarial_review(
        ROOT,
        report["properties"],
        bronze_mature=True,
    )
    errors = [
        item["finding_id"]
        for item in review["findings"]
        if item["severity"] == "error"
    ]
    if any(row["state"] != "evidenced" for row in report["properties"]):
        assert "ADV-FALSE-MATURITY" in errors
        assert review["passed"] is False
    else:
        assert review["passed"] is True


@pytest.mark.unit
def test_excluded_sources_are_not_counted_as_missing_landing() -> None:
    report = evaluate_repository(
        ROOT,
        clock=lambda: FIXED_CLOCK,
        git_commit="test",
    )
    catalog = _load(
        ROOT / "src/global_medicines_atlas/data/medicine_source_catalog.json"
    )
    excluded = [
        source["source_id"]
        for source in catalog["sources"]
        if classify_catalog_source(source) == "excluded"
    ]
    assert excluded
    notes = next(
        row["notes"]
        for row in report["properties"]
        if row["property_id"] == "completeness"
    )
    for source_id in excluded[:5]:
        assert source_id not in notes


@pytest.mark.unit
def test_dump_report_round_trips() -> None:
    report = evaluate_repository(
        ROOT,
        clock=lambda: FIXED_CLOCK,
        git_commit="deadbeef",
    )
    payload = dump_report(report)
    assert payload.endswith("\n")
    assert json.loads(payload)["git_commit"] == "deadbeef"


@pytest.mark.unit
def test_committed_report_matches_schema_when_present() -> None:
    path = ROOT / "quality/qualifications/bronze-maturity.json"
    if not path.is_file():
        pytest.skip("report not generated yet")
    _validate(_load(path))
    assert _load(path)["bronze_mature"] is False


def _row(
    property_id: str,
    *,
    state: str = "evidenced",
    evidence: tuple[str, ...] = ("DATA_LICENSE.md",),
    blocker_ids: tuple[str, ...] = (),
    notes: str = "ok",
) -> dict[str, Any]:
    return {
        "property_id": property_id,
        "mandatory": True,
        "state": state,
        "requirement_ids": ["M-092"],
        "evidence": list(evidence),
        "blocker_ids": list(blocker_ids),
        "notes": notes,
    }


def _full_properties(**overrides: Any) -> list[dict[str, Any]]:
    rows = [_row(property_id) for property_id in PROPERTY_IDS]
    for key, value in overrides.items():
        rows[0][key] = value
    return rows


@pytest.mark.unit
def test_landing_source_ids_skips_undecodable_and_pyc_files(
    tmp_path: Path,
) -> None:
    adapters = tmp_path / "src/global_medicines_atlas/adapters"
    fixtures = tmp_path / "tests/fixtures/nested"
    adapters.mkdir(parents=True)
    fixtures.mkdir(parents=True)
    (adapters / "ok.py").write_text('"au-artg"\n', encoding="utf-8")
    (adapters / "skip.pyc").write_bytes(b"\x00compiled")
    (fixtures / "binary.bin").write_bytes(b"\xff\xfe")
    found = landing_source_ids(tmp_path, {"au-artg", "missing"})
    assert found == {"au-artg"}


@pytest.mark.unit
def test_receipt_backed_landing_requires_exact_nonpublication_receipt(
    tmp_path: Path,
) -> None:
    overrides = tmp_path / (
        "src/global_medicines_atlas/data/source_landing_overrides.json"
    )
    overrides.parent.mkdir(parents=True)
    receipts = tmp_path / "quality/qualifications"
    receipts.mkdir(parents=True)
    (receipts / "bronze.json").write_text(
        json.dumps({
            "schema_id": "global-medicines-atlas.example-live-qualification",
            "accepted_admission_count": 1,
            "source_ids": ["au-artg"],
        }),
        encoding="utf-8",
    )
    (receipts / "publication.json").write_text(
        json.dumps({"source_ids": ["au-pbs"]}), encoding="utf-8"
    )
    (receipts / "invalid.json").write_text("{", encoding="utf-8")
    publication_directory = tmp_path / "docs/publication"
    publication_directory.mkdir(parents=True)
    (publication_directory / "admission.json").write_text(
        json.dumps({
            "schema_id": "global-medicines-atlas.example-live-qualification",
            "accepted_admission_count": 1,
            "source_ids": ["publication-path"],
        }),
        encoding="utf-8",
    )
    overrides.write_text(
        json.dumps({
            "overrides": [
                {
                    "source_id": "au-artg",
                    "state": "landed_and_evidenced",
                    "evidence_references": [
                        "quality/qualifications/bronze.json"
                    ],
                },
                {
                    "source_id": "au-pbs",
                    "state": "landed_and_evidenced",
                    "evidence_references": [
                        "quality/qualifications/publication.json"
                    ],
                },
                {
                    "source_id": "missing-evidence",
                    "state": "landed_and_evidenced",
                    "evidence_references": [
                        None,
                        "quality/qualifications/missing.json",
                        "quality/qualifications/invalid.json",
                    ],
                },
                {
                    "source_id": "publication-path",
                    "state": "landed_and_evidenced",
                    "evidence_references": ["docs/publication/admission.json"],
                },
            ]
        }),
        encoding="utf-8",
    )
    assert receipt_backed_landing_source_ids(
        tmp_path, {"au-artg", "au-pbs", "missing-evidence", "publication-path"}
    ) == {"au-artg"}
    assert receipt_backed_landing_evidence(tmp_path, {"au-artg"}) == {
        "au-artg": "quality/qualifications/bronze.json"
    }


@pytest.mark.unit
def test_us_live_records_receipt_counts_only_recovered_source_products(
    tmp_path: Path,
) -> None:
    source_id = "us-openfda-faers"
    overrides = tmp_path / bronze_maturity_mod.LANDING_OVERRIDES_RELATIVE
    overrides.parent.mkdir(parents=True)
    overrides.write_text(
        json.dumps({
            "overrides": [
                {
                    "source_id": source_id,
                    "state": "landed_and_evidenced",
                    "evidence_references": [
                        "quality/qualifications/us-live-bronze-records.json"
                    ],
                }
            ]
        }),
        encoding="utf-8",
    )
    receipt = tmp_path / "quality/qualifications/us-live-bronze-records.json"
    receipt.parent.mkdir(parents=True)
    receipt.write_text(
        json.dumps({
            "schema_id": "global-medicines-atlas.us-live-bronze-records-qualification",
            "schema_version": 1,
            "evidence_class": "live_bounded_internal",
            "source_count": 1,
            "acquisition_succeeded_count": 1,
            "acquisition_failed_count": 0,
            "accepted_admission_count": 1,
            "quarantined_admission_count": 0,
            "recovered_acquisition_count": 1,
            "source_record_projection_count": 1,
            "recovered_source_record_projection_count": 1,
            "source_record_parquet_pairs_byte_identical": 1,
            "record_products": [{"source_id": source_id, "row_count": 4}],
            "coverage_complete": False,
            "external_publication_performed": False,
            "public_release_authorized": False,
        }),
        encoding="utf-8",
    )
    assert receipt_backed_landing_evidence(tmp_path, {source_id}) == {
        source_id: "quality/qualifications/us-live-bronze-records.json"
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    ("field", "value", "products"),
    [
        ("recovered_acquisition_count", 0, None),
        ("recovered_source_record_projection_count", 0, None),
        ("source_record_parquet_pairs_byte_identical", 0, None),
        ("external_publication_performed", True, None),
        ("coverage_complete", True, None),
        ("source_count", 0, None),
        ("acquisition_failed_count", 1, None),
        ("accepted_admission_count", 2, None),
        ("quarantined_admission_count", 1, None),
        ("source_record_projection_count", 0, None),
        (
            "acquisition_succeeded_count",
            1,
            [{"source_id": "other", "row_count": 4}],
        ),
        (
            "acquisition_succeeded_count",
            1,
            [{"source_id": "us-openfda-faers", "row_count": True}],
        ),
        (
            "acquisition_succeeded_count",
            1,
            [{"source_id": "us-openfda-faers", "row_count": 0}],
        ),
        (
            "acquisition_succeeded_count",
            1,
            [
                {"source_id": "us-openfda-faers", "row_count": 4},
                {"source_id": "us-openfda-faers", "row_count": 3},
            ],
        ),
        ("acquisition_succeeded_count", 1, [None]),
        ("acquisition_succeeded_count", 1, []),
    ],
)
def test_us_live_records_receipt_fails_closed_on_inconsistent_summary(
    tmp_path: Path,
    field: str,
    value: object,
    products: list[object] | None,
) -> None:
    source_id = "us-openfda-faers"
    overrides = tmp_path / bronze_maturity_mod.LANDING_OVERRIDES_RELATIVE
    overrides.parent.mkdir(parents=True)
    overrides.write_text(
        json.dumps({
            "overrides": [
                {
                    "source_id": source_id,
                    "state": "landed_and_evidenced",
                    "evidence_references": [
                        "quality/qualifications/us-live-bronze-records.json"
                    ],
                }
            ]
        }),
        encoding="utf-8",
    )
    receipt_data: dict[str, object] = {
        "schema_id": "global-medicines-atlas.us-live-bronze-records-qualification",
        "schema_version": 1,
        "evidence_class": "live_bounded_internal",
        "source_count": 1,
        "acquisition_succeeded_count": 1,
        "acquisition_failed_count": 0,
        "accepted_admission_count": 1,
        "quarantined_admission_count": 0,
        "recovered_acquisition_count": 1,
        "source_record_projection_count": 1,
        "recovered_source_record_projection_count": 1,
        "source_record_parquet_pairs_byte_identical": 1,
        "record_products": (
            [{"source_id": source_id, "row_count": 4}]
            if products is None
            else products
        ),
        "coverage_complete": False,
        "external_publication_performed": False,
        "public_release_authorized": False,
    }
    receipt_data[field] = value
    receipt = tmp_path / "quality/qualifications/us-live-bronze-records.json"
    receipt.parent.mkdir(parents=True)
    receipt.write_text(json.dumps(receipt_data), encoding="utf-8")
    assert receipt_backed_landing_evidence(tmp_path, {source_id}) == {}


@pytest.mark.integration
def test_repository_us_live_records_override_scope_is_exact() -> None:
    covered_ids = {
        "us-fda-nsde",
        "us-openfda-drugsfda",
        "us-openfda-faers",
        "us-openfda-nsde",
        "us-fda-orange-book",
        "us-fda-drug-shortages",
    }
    evidence = receipt_backed_landing_evidence(ROOT, covered_ids)
    assert set(evidence) == {
        "us-fda-drug-shortages",
        "us-fda-nsde",
        "us-fda-orange-book",
        "us-openfda-drugsfda",
        "us-openfda-faers",
        "us-openfda-nsde",
    }
    assert set(evidence.values()) == {
        "quality/qualifications/fda-shortages-live-corpus-20260821.json",
        "quality/qualifications/us-live-bronze-records-20260820.json",
    }


@pytest.mark.unit
def test_completeness_is_evidenced_when_every_in_scope_source_landed(
    tmp_path: Path,
) -> None:
    catalog = tmp_path / CATALOG_RELATIVE
    catalog.parent.mkdir(parents=True)
    catalog.write_text(
        json.dumps({
            "sources": [
                {
                    "source_id": "au-artg",
                    "authentication": "none",
                    "access_mode": "web_search",
                    "implemented_ingestion": True,
                },
                {
                    "source_id": "global-rxnorm",
                    "authentication": "none",
                    "access_mode": "api",
                },
                {
                    "source_id": "au-pbs-embargo",
                    "authentication": "manual_approval",
                    "access_mode": "licensed_feed",
                },
            ]
        }),
        encoding="utf-8",
    )
    spec = tmp_path / (
        "conductor/tracks/bronze_medallion_completion_20260819/spec.md"
    )
    spec.parent.mkdir(parents=True)
    spec.write_text("bronze\n", encoding="utf-8")
    contracts = (
        tmp_path / "src/global_medicines_atlas/adapters/fixture_contracts.py"
    )
    contracts.parent.mkdir(parents=True, exist_ok=True)
    contracts.write_text('SOURCE = "au-artg"\n', encoding="utf-8")
    property_row, inventory = evaluate_completeness(tmp_path)
    assert property_row["state"] == "evidenced"
    assert inventory["in_scope_without_landing_or_blocker"] == 0


@pytest.mark.unit
def test_adversarial_review_covers_fail_closed_branches(
    tmp_path: Path,
) -> None:
    forbidden_path = "docs/publication/data-layer-archive-receipt.md"
    (tmp_path / forbidden_path).parent.mkdir(parents=True)
    (tmp_path / forbidden_path).write_text("archive\n", encoding="utf-8")
    needle_path = "notes/later-layer.md"
    (tmp_path / needle_path).parent.mkdir(parents=True)
    (tmp_path / needle_path).write_text(
        "silver implementation complete\n",
        encoding="utf-8",
    )
    (tmp_path / "DATA_LICENSE.md").write_text("CC-BY-4.0\n", encoding="utf-8")

    forbidden = run_adversarial_review(
        tmp_path,
        _full_properties(evidence=[forbidden_path]),
        bronze_mature=False,
    )
    assert any(
        item["finding_id"] == "ADV-FORBIDDEN-EVIDENCE"
        and item["severity"] == "error"
        for item in forbidden["findings"]
    )

    missing = run_adversarial_review(
        tmp_path,
        _full_properties(evidence=["absent-evidence.md"]),
        bronze_mature=False,
    )
    assert any(
        item["finding_id"].startswith("ADV-MISSING-")
        for item in missing["findings"]
    )

    needle = run_adversarial_review(
        tmp_path,
        _full_properties(evidence=[needle_path]),
        bronze_mature=False,
    )
    assert any(
        item["finding_id"].startswith("ADV-NEEDLE-")
        for item in needle["findings"]
    )

    qualified = run_adversarial_review(
        tmp_path,
        _full_properties(),
        bronze_mature=True,
    )
    assert any(
        item["finding_id"] == "ADV-FALSE-MATURITY"
        and "Every mandatory property is evidenced" in item["detail"]
        for item in qualified["findings"]
    )

    mismatch = run_adversarial_review(
        tmp_path,
        [_row("completeness")],
        bronze_mature=False,
    )
    assert any(
        item["finding_id"] == "ADV-PROPERTY-SET" and item["severity"] == "error"
        for item in mismatch["findings"]
    )


@pytest.mark.unit
def test_duplicate_blocker_ids_are_emitted_once() -> None:
    blockers = bronze_maturity_mod._blockers_from_properties((
        _row("completeness", state="blocked", blocker_ids=("shared",)),
        _row("quarantine", state="blocked", blocker_ids=("shared",)),
    ))
    assert [item["blocker_id"] for item in blockers] == ["shared"]


@pytest.mark.unit
def test_evaluate_repository_fail_closes_inconsistent_maturity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "DATA_LICENSE.md").write_text("CC-BY-4.0\n", encoding="utf-8")
    inventory = {
        "catalog_source_count": 1,
        "bronze_in_scope_count": 1,
        "fixture_only_count": 0,
        "excluded_count": 0,
        "in_scope_without_landing_or_blocker": 0,
        "missing_coverage_is_not_negative_evidence": True,
    }

    def fake_completeness(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
        del root
        return _row("completeness"), inventory

    def fake_properties(rows: list[dict[str, Any]]):
        def inner(root: Path) -> list[dict[str, Any]]:
            del root
            return rows

        return inner

    inconsistent = _full_properties(blocker_ids=["stale"])
    monkeypatch.setattr(
        bronze_maturity_mod,
        "evaluate_properties",
        fake_properties(inconsistent),
    )
    monkeypatch.setattr(
        bronze_maturity_mod,
        "evaluate_completeness",
        fake_completeness,
    )
    blocked = evaluate_repository(tmp_path, git_commit=None)
    assert blocked["bronze_mature"] is False
    assert blocked["git_commit"] == "unspecified"
    assert blocked["blockers"]

    clean = _full_properties()
    monkeypatch.setattr(
        bronze_maturity_mod,
        "evaluate_properties",
        fake_properties(clean),
    )
    qualified = evaluate_repository(tmp_path, git_commit="abc")
    assert qualified["bronze_mature"] is True
    assert qualified["blockers"] == []

    poisoned = _full_properties(
        evidence=["docs/publication/data-layer-archive-receipt.md"],
    )
    (tmp_path / "docs/publication").mkdir(parents=True)
    (tmp_path / "docs/publication/data-layer-archive-receipt.md").write_text(
        "hf\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        bronze_maturity_mod,
        "evaluate_properties",
        fake_properties(poisoned),
    )
    review_failed = evaluate_repository(tmp_path, git_commit="abc")
    assert review_failed["bronze_mature"] is False
    assert review_failed["adversarial_review"]["passed"] is False
