"""The PBS domain meaning profile is exact-source-bound and conservative."""

import json
from pathlib import Path

import pytest

from global_medicines_atlas.pbs_domain_field_semantics import (
    INVENTORY,
    qualify_pbs_domain_fields,
)

ROOT = Path(__file__).resolve().parents[1]


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


def test_exact_path_inventory_rejects_status_semantic_drift(tmp_path):
    for relative in (INVENTORY,):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = json.loads((ROOT / relative).read_bytes())
        payload["paths"].append({
            "native_fields": 1,
            "null_fields": 0,
            "schema_path": "/{http:~1~1schema.pbs.gov.au~1}status/text",
            "value_fields": 1,
        })
        destination.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="inventory digest differs"):
        qualify_pbs_domain_fields(tmp_path)


def test_wrong_inventory_member_is_rejected_before_qualification(tmp_path):
    destination = tmp_path / INVENTORY
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads((ROOT / INVENTORY).read_bytes())
    payload["member_sha256"] = "0" * 64
    destination.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="inventory digest differs"):
        qualify_pbs_domain_fields(tmp_path)
