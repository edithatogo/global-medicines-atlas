"""Product provisioning preserves independently configured receipt authority."""

import hashlib
import json
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
import scripts.qualify_mbs_silver_v4_admission as mbs_v4_qualification
from scripts.qualify_mbs_silver_v4_admission import (
    fetch_receipt,
    normalize_receipt_time,
    raw_receipt_url,
)
from test_federation_admission import BODY, SCHEMA, URL, evidence

from global_medicines_atlas.federation_receipt_closure import (
    ReceiptPayload,
    verify_receipt_closure,
)
from global_medicines_atlas.platinum_admission import (
    ProductAdmissionProfile,
    admit_product_configuration,
)


def test_hosted_mbs_receipt_urls_are_immutable_and_allowlisted():
    commit = "a" * 40
    url = raw_receipt_url(commit, "quality/qualification.json")

    assert url == (
        "https://raw.githubusercontent.com/edithatogo/global-medicines-atlas/"
        f"{commit}/quality/qualification.json"
    )
    with pytest.raises(ValueError, match="allowlist"):
        fetch_receipt("file:///etc/passwd")


def test_hosted_mbs_receipt_times_are_normalized_to_utc_z():
    assert normalize_receipt_time("2026-10-25T08:26:05.677420+00:00") == (
        "2026-10-25T08:26:05.677420Z"
    )


def test_exact_six_mbs_profiles_close_receipts_and_prepare_consumer_canaries(
    monkeypatch, tmp_path
):
    commit = "a" * 40
    publication_objects = [
        {
            "path": f"silver/mbs/v4/2025-07-v3/{filename}",
            "sha256": digest,
            "byte_count": size,
        }
        for filename, digest, size in mbs_v4_qualification.OBJECTS.values()
    ]
    comment = json.dumps({
        "id": 5859624790,
        "body": json.dumps({
            "candidate_only": True,
            "dataset": mbs_v4_qualification.DATASET,
            "manifest_sha256": "bbdb1bdac49fc1a7f8399ca02cf52a9b0e3a1fbc31e472e3957f1d278ab39a59",
            "revision": "ba82cd1d0f9b0f28514df431b8da3a6c207d76fa",
            "verified_objects": publication_objects,
        }),
    }).encode()
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_SHA", commit)
    monkeypatch.setattr(
        mbs_v4_qualification,
        "fetch_receipt",
        lambda _url, _limit=mbs_v4_qualification.MAX_RECEIPT_BYTES: comment,
    )

    class Reader:
        def __init__(self, *, resources, **_kwargs):
            self.resources = {item.resource_id: item for item in resources}
            self.cached_bytes = 0

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        @contextmanager
        def open(self, resource_id):
            resource = self.resources[resource_id]
            yield SimpleNamespace(
                verified=SimpleNamespace(
                    contract_sha256=resource.binding.contract_sha256,
                    sha256=resource.binding.object.sha256,
                    byte_count=resource.binding.object.byte_count,
                    origin="remote",
                ),
                metadata=SimpleNamespace(
                    sha256=resource.binding.object.sha256,
                    byte_count=resource.binding.object.byte_count,
                ),
            )

        def evict(self):
            self.cached_bytes = 0

    consumer_calls = []

    def consumer_canary(_trust, _metadata, _schema, requests):
        consumer_calls.extend(requests)
        return {
            "status": "passed",
            "request_count": len(requests),
            "surface_request_counts": {
                "api": len(requests),
                "atlas": len(requests),
                "cli_json": len(requests),
                "cli_jsonl": len(requests),
            },
        }

    monkeypatch.setattr(mbs_v4_qualification, "StorageNeutralResolver", Reader)
    monkeypatch.setattr(
        mbs_v4_qualification,
        "run_product_delivery_qualification",
        consumer_canary,
    )
    result = mbs_v4_qualification.qualify(
        Path(__file__).resolve().parents[1], tmp_path, commit
    )

    assert result["status"] == "passed"
    assert result["verified_object_count"] == 6
    assert len(result["objects"]) == len(result["remote_reads"]) == 6
    assert all(len(item["receipt_roles"]) == 11 for item in result["objects"])
    assert result["historical_cache_cleanup"]["status"] == "passed"
    assert result["historical_cache_cleanup"]["remaining_entries"] == 0
    assert {item["semantic_dimension"] for item in result["objects"]} == {
        "service_benefit"
    }
    assert len(consumer_calls) == 6
    assert result["consumer_canary"]["surface_request_counts"] == {
        "api": 6,
        "atlas": 6,
        "cli_json": 6,
        "cli_jsonl": 6,
    }
    assert (tmp_path / "deployment-trust.json").is_file()
    assert len(tuple((tmp_path / "metadata" / "contracts").glob("*.json"))) == 6
    contracts = [
        json.loads(path.read_bytes())
        for path in (tmp_path / "metadata" / "contracts").glob("*.json")
    ]
    for contract in contracts:
        cache = contract["cache"]
        created_at = datetime.fromisoformat(cache["created_at"])
        expires_at = datetime.fromisoformat(cache["expires_at"])
        assert cache["state"] == "transient"
        assert created_at <= datetime.now(UTC) < expires_at
        assert expires_at - created_at == timedelta(hours=1)


def product_inputs():
    raw, _, subject = evidence()
    document = json.loads(raw)
    document["source"].update(
        layer="silver", bronze_stratum=None, representation="projection"
    )
    reference = {"url": URL, "sha256": hashlib.sha256(BODY).hexdigest()}
    document["lineage"]["inputs"] = [reference]
    document["lineage"]["promotion_receipt"] = reference
    raw = json.dumps(document).encode()
    closure = verify_receipt_closure(
        raw, (ReceiptPayload(url=URL, payload=BODY),), schema=SCHEMA
    )
    subject = subject.model_copy(
        update={
            "layer": "silver",
            "bronze_stratum": None,
            "representation": "projection",
            "lineage": tuple(
                role
                for role in closure.roles
                if role.role.startswith("/lineage/")
            ),
        }
    )
    semantic = json.dumps({
        "version": "1.0",
        "resource_id": "synthetic.source-structure",
        "semantic_dimension": "source_structure",
        "entity_granularity": "provenance_record",
        "contract_sha256": closure.contract_sha256,
    }).encode()
    profile = ProductAdmissionProfile(
        resource_id="synthetic.source-structure",
        semantic_dimension="source_structure",
        entity_granularity="provenance_record",
        semantic_sha256=hashlib.sha256(semantic).hexdigest(),
        subject=subject,
        receipt_roles=closure.roles,
    )
    return raw, semantic, profile


def provision(raw, semantic, profile, payload=BODY):
    return admit_product_configuration(
        raw,
        (ReceiptPayload(url=URL, payload=payload),),
        semantic,
        schema=SCHEMA,
        profile=profile,
        contract_path="contracts/object.json",
        semantic_path="semantics/object.json",
    )


def test_closed_product_configuration_retains_exact_trusted_identity():
    raw, semantic, profile = product_inputs()
    result = provision(raw, semantic, profile)

    assert result.admission.contract_sha256 == hashlib.sha256(raw).hexdigest()
    assert result.binding.object.sha256 == profile.subject.sha256
    assert result.semantic_sha256 == hashlib.sha256(semantic).hexdigest()
    assert result.semantic_dimension == "source_structure"
    assert result.admission.evidence_kind == "synthetic"


def test_self_consistent_subject_cannot_replace_operator_expectations():
    raw, semantic, profile = product_inputs()
    changed = profile.model_copy(
        update={
            "subject": profile.subject.model_copy(
                update={"path": "different.xml"}
            )
        }
    )
    with pytest.raises(ValueError, match="independently trusted"):
        provision(raw, semantic, changed)


@pytest.mark.parametrize("duplicate", [False, True])
def test_all_receipt_roles_need_independent_trust(duplicate):
    raw, semantic, profile = product_inputs()
    roles = profile.receipt_roles
    altered = roles + roles[:1] if duplicate else roles[:-1]
    changed = profile.model_copy(update={"receipt_roles": altered})
    with pytest.raises(ValueError, match=r"duplicated|trusted roles"):
        provision(raw, semantic, changed)


def test_wrong_receipt_bytes_do_not_provision_resource():
    raw, semantic, profile = product_inputs()
    with pytest.raises(ValueError, match="digest"):
        provision(raw, semantic, profile, payload=b"different receipt")


def test_semantic_claims_cannot_be_promoted_by_rehashing_a_manifest():
    raw, semantic, profile = product_inputs()
    value = json.loads(semantic)
    value["semantic_dimension"] = "regulatory"
    forged = json.dumps(value).encode()
    changed = profile.model_copy(
        update={"semantic_sha256": hashlib.sha256(forged).hexdigest()}
    )
    with pytest.raises(ValueError, match="semantic claims"):
        provision(raw, forged, changed)


def test_semantic_digest_is_checked_before_resource_is_provisioned():
    raw, semantic, profile = product_inputs()
    with pytest.raises(ValueError, match="independent trust"):
        provision(raw, semantic + b" ", profile)
