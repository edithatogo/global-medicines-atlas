"""The PBS domain meaning profile is exact-source-bound and conservative."""

import hashlib
import json
from pathlib import Path

import pytest

import global_medicines_atlas.pbs_domain_field_semantics as domain_semantics
from global_medicines_atlas.pbs_domain_field_semantics import (
    DATE_PROFILE,
    INVENTORY,
    OBSERVED,
    qualify_pbs_domain_fields,
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
    assert domains["document_valid_date"]["entity_count"] == 1
    assert domains["status"]["status"] == (
        "unresolved_no_explicit_status_field_qualified"
    )
    assert domains["status"]["meaning"] is None
    assert report["scope"]["complete_domain_semantics_qualified"] is False
    assert report["scope"]["source_values_emitted"] is False
    labels = report["source_label_observations"]
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
