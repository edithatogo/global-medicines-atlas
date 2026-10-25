"""Product provisioning preserves independently configured receipt authority."""

import hashlib
import json

import pytest
from test_federation_admission import BODY, SCHEMA, URL, evidence

from global_medicines_atlas.federation_receipt_closure import (
    ReceiptPayload,
    verify_receipt_closure,
)
from global_medicines_atlas.platinum_admission import (
    ProductAdmissionProfile,
    admit_product_configuration,
)


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
