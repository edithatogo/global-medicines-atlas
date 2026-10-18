"""Synthetic receipt closure and independent trust for raw MBS B2 candidates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from global_medicines_atlas.federation_admission import TrustedAdmissionProfile
from global_medicines_atlas.federation_reader import SCHEMA_SHA256_V4_1
from global_medicines_atlas.federation_receipt_closure import (
    ReceiptPayload,
    ReceiptRole,
)
from global_medicines_atlas.mbs_raw_b2_federation_profile import (
    MbsRawB2CandidateProfile,
    qualify_mbs_raw_b2_candidate,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = (ROOT / "contracts/medallion/v4.1/federation.schema.json").read_bytes()
BODY = b"synthetic opaque receipt bytes; no authority claims"
URL = "https://example.org/receipts/mbs-raw-b2-synthetic.json"
RECEIPT_SHA256 = hashlib.sha256(BODY).hexdigest()


def evidence() -> tuple[
    bytes, tuple[ReceiptPayload, ...], MbsRawB2CandidateProfile
]:
    document: dict[str, Any] = json.loads(
        (
            ROOT / "contracts/medallion/v4.1/fixtures/valid-raw-b2.json"
        ).read_bytes()
    )
    document["source"]["source_id"] = "au-mbs"
    reference = {"url": URL, "sha256": RECEIPT_SHA256}
    document["publication"]["receipt"] = reference
    document["verification"]["receipt"] = reference
    document["rights"]["authorization"] = reference
    document["discovery"]["estate_entry"] = reference
    document["lineage"]["inputs"] = [reference]
    document["lineage"]["v1_conformance"] = reference
    document["lineage"]["v3_replay"] = reference
    document["recovery"]["checksum_inventory"] = reference
    document["cache"]["cleanup_receipt"] = reference
    contract = json.dumps(document, sort_keys=True).encode()

    def role(pointer: str) -> ReceiptRole:
        return ReceiptRole(role=pointer, url=URL, sha256=RECEIPT_SHA256)

    trusted = TrustedAdmissionProfile(
        producer_repository="example/producer",
        contract_repository="edithatogo/global-medicines-atlas",
        contract_commit="a" * 40,
        schema_sha256=SCHEMA_SHA256_V4_1,
        dataset="example/synthetic-mbs",
        revision="a" * 40,
        path="raw/synthetic.xml",
        byte_count=11,
        sha256="d" * 64,
        source_id="au-mbs",
        acquisition_id="synthetic-acquisition",
        layer="bronze",
        bronze_stratum="B2",
        representation="raw",
        schema_era="synthetic-v1",
        comparison_cohort="synthetic",
        effective_date="2026-08-01",
        retrieved_at="2026-08-30T00:00:00Z",
        evidence_kind="synthetic",
        authorization=role("/rights/authorization"),
        lineage=(
            role("/lineage/inputs/0"),
            role("/lineage/v1_conformance"),
            role("/lineage/v3_replay"),
        ),
    )
    return (
        contract,
        (ReceiptPayload(url=URL, payload=BODY),),
        MbsRawB2CandidateProfile(trusted=trusted),
    )


def test_synthetic_raw_b2_closure_and_independent_admission_are_candidate_only():
    contract, receipts, profile = evidence()

    result = qualify_mbs_raw_b2_candidate(
        contract, receipts, schema=SCHEMA, profile=profile
    )

    roles = {item.role for item in result.receipt_closure.roles}
    assert result.status == "candidate_only"
    assert result.dataset == "example/synthetic-mbs"
    assert result.path == "raw/synthetic.xml"
    assert result.object_sha256 == "d" * 64
    assert "/lineage/v1_conformance" in roles
    assert "/lineage/v3_replay" in roles
    assert "/lineage/v2_field_lineage" not in roles


@pytest.mark.parametrize(
    "identity",
    ["path", "sha256", "acquisition_id", "revision"],
)
def test_coherent_contract_identity_substitution_fails_independent_profile(
    identity: str,
):
    contract, receipts, profile = evidence()
    document = json.loads(contract)
    if identity == "path":
        for section in ("location", "verification", "rights"):
            document[section]["path"] = "raw/substituted.xml"
    elif identity == "sha256":
        for section in ("location", "verification"):
            document[section]["sha256"] = "e" * 64
        document["rights"]["subject_sha256"] = "e" * 64
    elif identity == "acquisition_id":
        document["source"]["acquisition_id"] = "substituted-acquisition"
    else:
        for section in ("location", "verification"):
            document[section]["revision"] = "b" * 40
    substituted = json.dumps(document, sort_keys=True).encode()

    with pytest.raises(ValueError, match="independently trusted"):
        qualify_mbs_raw_b2_candidate(
            substituted, receipts, schema=SCHEMA, profile=profile
        )


def test_missing_receipt_bytes_fail_closure():
    contract, _, profile = evidence()

    with pytest.raises(ValueError, match="missing or extra supplied receipt"):
        qualify_mbs_raw_b2_candidate(
            contract, (), schema=SCHEMA, profile=profile
        )


def test_contract_missing_required_lineage_role_fails_closed():
    contract, receipts, profile = evidence()
    document = json.loads(contract)
    document["lineage"]["v1_conformance"] = None
    altered = json.dumps(document, sort_keys=True).encode()

    with pytest.raises(ValueError, match="invalid federation contract"):
        qualify_mbs_raw_b2_candidate(
            altered, receipts, schema=SCHEMA, profile=profile
        )


def test_unauthorised_source_layer_scope_is_rejected():
    _, _, profile = evidence()
    untrusted_scope = profile.trusted.model_copy(
        update={"layer": "silver", "bronze_stratum": None}
    )

    with pytest.raises(ValueError, match="candidate profile scope"):
        MbsRawB2CandidateProfile(trusted=untrusted_scope)


def test_raw_b2_profile_requires_exact_v41_schema_and_required_roles():
    _, _, profile = evidence()
    incomplete_lineage = profile.trusted.model_copy(
        update={"lineage": profile.trusted.lineage[:-1]}
    )
    wrong_schema = profile.trusted.model_copy(
        update={"schema_sha256": "f" * 64}
    )

    with pytest.raises(ValueError, match="candidate profile scope"):
        MbsRawB2CandidateProfile(trusted=incomplete_lineage)
    with pytest.raises(ValueError, match="candidate profile scope"):
        MbsRawB2CandidateProfile(trusted=wrong_schema)
