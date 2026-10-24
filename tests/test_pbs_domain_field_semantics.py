"""The PBS domain meaning profile is exact-source-bound and conservative."""

import hashlib
import json
import runpy
import sys
from pathlib import Path

import pytest

import global_medicines_atlas.pbs_domain_field_semantics as domain_semantics
from global_medicines_atlas.pbs_domain_field_semantics import (
    DATE_PROFILE,
    INVENTORY,
    OBSERVED,
    qualify_pbs_domain_fields,
    qualify_pbs_source_label_observations,
)

ROOT = Path(__file__).resolve().parents[1]


def _copy_receipts(root: Path, tmp_path: Path) -> None:
    for relative in (INVENTORY, OBSERVED, DATE_PROFILE):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((root / relative).read_bytes())


def _write_json(root: Path, relative: str, payload: dict) -> None:
    destination = root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload), encoding="utf-8")


def _canonical_digest(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()


def test_qualifies_only_bounded_pbs_v3_source_meanings():
    report = qualify_pbs_domain_fields(ROOT)
    domains = report["domains"]

    assert report["source"]["member_sha256"] == (
        "73d34185fe6ae7fd9a788a68448e20934b38553d42361117faa96cdb07f54f43"
    )
    assert report["source"]["native_fields"] == 18_208_758
    assert domains["item"]["entity_count"] == 58_774
    assert domains["product"]["entity_count"] == 238_514
    assert domains["restriction"]["entity_count"] == 2_120_959
    assert domains["price"]["entity_count"] == 4_940_077
    assert domains["effective_date"]["entity_count"] == 2_799
    assert domains["effective_date"]["meaning"] == (
        "source schedule and item-effectivity date roles"
    )
    assert domains["restriction_effective_date"]["field_count"] == 3_028
    assert domains["restriction_effective_date"]["status"] == (
        "qualified_exact_source_path_role_date_grammar_unqualified"
    )
    assert any(
        "XSD date grammar is not qualified" in limit
        for limit in domains["restriction_effective_date"]["limits"]
    )
    assert domains["document_valid_date"]["entity_count"] == 1
    assert domains["status"]["status"] == (
        "unresolved_no_explicit_status_field_qualified"
    )
    assert domains["status"]["meaning"] is None
    amount_roles = report["source_schema_field_meanings"]["pbs_amount_text"]
    assert amount_roles == {
        "pbs_amount_fields": 891_163,
        "product_price_fields": 817_216,
        "patient_contribution_fields": 2_279,
        "status": "qualified_exact_pinned_v3_schema_role",
        "meaning": (
            "PBS amount content is defined by the source schema as a dollar "
            "value; nested price and patient-contribution contexts retain "
            "their distinct source roles"
        ),
        "limits": [
            "the schema does not supply an explicit currency code for these fields",
            "the exact schema minor release used for the archive is not separately bound by the value-free path inventory",
            "native lexemes, precision classification, amount category references, and monetary values remain unresolved",
            "a source price amount is not thereby a payable benefit or patient cost",
            "patient-contribution role does not establish the amount actually paid by a patient",
            "applies only to exact PBS namespace amount/text paths in the pinned v3 member",
        ],
    }
    assert report["source_schema_field_meanings"]["restriction"]["status"] == (
        "qualified_exact_pinned_v3_schema_label"
    )
    assert report["scope"]["complete_domain_semantics_qualified"] is False
    assert report["scope"]["source_values_emitted"] is False
    assert report["scope"]["new_sources"] == 0


def test_source_amount_role_counts_require_exact_pbs_qnames():
    inventory = {
        "paths": [
            {
                "schema_path": (
                    "/{http:~1~1schema.pbs.gov.au~1}root/"
                    "{http:~1~1schema.pbs.gov.au~1}amount/text"
                ),
                "native_fields": 3,
            },
            {
                "schema_path": (
                    "/{http:~1~1schema.pbs.gov.au~1}root/"
                    "{http:~1~1schema.pbs.gov.au~1}price/"
                    "{http:~1~1schema.pbs.gov.au~1}contribution/"
                    "{http:~1~1schema.pbs.gov.au~1}amount/text"
                ),
                "native_fields": 5,
            },
            {
                "schema_path": (
                    "/{http:~1~1schema.pbs.gov.au~1}root/"
                    "{urn:extension}amount/text"
                ),
                "native_fields": 7,
            },
        ]
    }
    assert domain_semantics._pbs_amount_role_counts(inventory) == {
        "pbs_amount_fields": 8,
        "product_price_fields": 0,
        "patient_contribution_fields": 5,
    }


def test_restriction_date_role_requires_exact_path_count(tmp_path, monkeypatch):
    _copy_receipts(ROOT, tmp_path)
    inventory_path = tmp_path / INVENTORY
    inventory = json.loads(inventory_path.read_bytes())
    target = [
        row
        for row in inventory["paths"]
        if row["schema_path"]
        == domain_semantics.RESTRICTION_EFFECTIVE_DATE_TEXT_PATH
    ]
    assert len(target) == 1
    target[0]["native_fields"] += 1
    encoded = json.dumps(inventory).encode()
    inventory_path.write_bytes(encoded)
    monkeypatch.setattr(
        domain_semantics,
        "INVENTORY_SHA256",
        hashlib.sha256(encoded).hexdigest(),
    )
    with pytest.raises(
        ValueError, match="restriction effective-date path count differs"
    ):
        qualify_pbs_domain_fields(tmp_path)


def test_domain_writer_default_preserves_historical_receipt(
    tmp_path, monkeypatch
):
    _copy_receipts(ROOT, tmp_path)
    historical = tmp_path / (
        "quality/qualifications/pbs-domain-field-semantics-20261023.json"
    )
    historical.parent.mkdir(parents=True, exist_ok=True)
    historical_bytes = (
        ROOT / "quality/qualifications/pbs-domain-field-semantics-20261023.json"
    ).read_bytes()
    historical.write_bytes(historical_bytes)

    monkeypatch.setattr(
        sys,
        "argv",
        ["qualify_pbs_domain_fields.py", "--root", str(tmp_path)],
    )
    script = runpy.run_path(
        str(ROOT / "scripts/qualify_pbs_domain_fields.py"),
        run_name="pbs_domain_field_writer_test",
    )
    assert script["main"]() == 0

    output = tmp_path / (
        "quality/qualifications/pbs-domain-field-semantics-20261025-v3.json"
    )
    assert output.is_file()
    assert historical.read_bytes() == historical_bytes
    envelope = json.loads(output.read_bytes())
    assert envelope["report"]["profile_id"] == (
        "pbs-v3-pinned-2026-04-01-domain-fields-v3"
    )
    assert (
        hashlib.sha256(
            json.dumps(
                envelope["report"],
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
        == envelope["report_sha256"]
    )


def test_source_label_overlay_keeps_values_unresolved():
    report = qualify_pbs_source_label_observations(ROOT)
    labels = report["observations"]
    assert {
        label: observation["native_fields"]
        for label, observation in labels.items()
    } == {
        "brand_name_text": 6_084,
        "ex_manufacturer_amount_text": 57_922,
        "copayment_amount_text": 2,
        "threshold_amount_text": 2,
        "fee_definition_amount_text": 193,
    }
    assert all(
        observation["status"] == "source_path_label_only"
        and observation["interpretation_state"] == "native_unresolved"
        for observation in labels.values()
    )
    assert report["scope"]["domain_value_semantics_qualified"] is False
    assert report["scope"]["source_values_emitted"] is False


def test_exact_path_inventory_rejects_status_semantic_drift(
    tmp_path, monkeypatch
):
    _copy_receipts(ROOT, tmp_path)
    payload = json.loads((tmp_path / INVENTORY).read_bytes())
    payload["paths"].append({
        "native_fields": 1,
        "null_fields": 0,
        "schema_path": "/{http:~1~1schema.pbs.gov.au~1}status/text",
        "value_fields": 1,
    })
    encoded = json.dumps(payload).encode()
    (tmp_path / INVENTORY).write_bytes(encoded)
    # Rebind the fixture digest so this test reaches the semantic status guard.
    digest = hashlib.sha256(encoded).hexdigest()
    monkeypatch.setattr(domain_semantics, "INVENTORY_SHA256", digest)
    with pytest.raises(ValueError, match="unreviewed status path"):
        qualify_pbs_domain_fields(tmp_path)


def test_inventory_denominator_drift_is_rejected_after_digest_binding(
    tmp_path, monkeypatch
):
    _copy_receipts(ROOT, tmp_path)
    payload = json.loads((tmp_path / INVENTORY).read_bytes())
    payload["native_fields"] += 1
    encoded = json.dumps(payload).encode()
    (tmp_path / INVENTORY).write_bytes(encoded)
    monkeypatch.setattr(
        domain_semantics,
        "INVENTORY_SHA256",
        hashlib.sha256(encoded).hexdigest(),
    )
    with pytest.raises(ValueError, match="source denominator differs"):
        qualify_pbs_domain_fields(tmp_path)


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("status", "observed structural receipt differs"),
        ("member", "observed structural receipt differs"),
    ],
)
def test_observed_receipt_drift_is_rejected_after_report_digest_binding(
    tmp_path, mutation, expected
):
    _copy_receipts(ROOT, tmp_path)
    envelope = json.loads((tmp_path / OBSERVED).read_bytes())
    qualification = envelope["report"]["qualification"]
    if mutation == "status":
        qualification["domain_semantics_qualified"] = True
    else:
        qualification["member_binding_sha256"] = "0" * 64
    envelope["report_sha256"] = _canonical_digest(envelope["report"])
    _write_json(tmp_path, OBSERVED, envelope)
    with pytest.raises(ValueError, match=expected):
        qualify_pbs_domain_fields(tmp_path)


def test_date_receipt_source_drift_is_rejected(tmp_path):
    _copy_receipts(ROOT, tmp_path)
    profile = json.loads((tmp_path / DATE_PROFILE).read_bytes())
    profile["source"]["revision"] = "0" * 40
    _write_json(tmp_path, DATE_PROFILE, profile)
    with pytest.raises(ValueError, match="exact-source date receipt differs"):
        qualify_pbs_domain_fields(tmp_path)


def test_wrong_inventory_member_is_rejected_before_qualification(tmp_path):
    destination = tmp_path / INVENTORY
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads((ROOT / INVENTORY).read_bytes())
    payload["member_sha256"] = "0" * 64
    destination.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="inventory digest differs"):
        qualify_pbs_domain_fields(tmp_path)
