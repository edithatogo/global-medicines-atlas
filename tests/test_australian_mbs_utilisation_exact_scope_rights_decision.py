"""The MBS-utilisation rights approval is exact-scope and fail-closed."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from global_medicines_atlas.mbs_utilisation_rights_append import (
    validate_rights_append,
)
from global_medicines_atlas.receipts import (
    AcquisitionEvent,
    acquisition_event_id_for,
)

ROOT = Path(__file__).resolve().parents[1]
DECISION_PATH = (
    "quality/qualifications/"
    "australian-mbs-utilisation-exact-scope-rights-decision-20261004.json"
)
REGISTER_PATH = (
    "quality/qualifications/"
    "australian-m112-additional-deferred-source-candidates-20261004.json"
)
RECONCILIATION_PATH = (
    "quality/qualifications/"
    "australian-m112-utilisation-rights-reconciliation-20261004.json"
)
JOIN_PATH = (
    "quality/qualifications/"
    "australian-m112-receipt-sidecar-join-audit-20260930.json"
)


def _read(path: str) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_rights_decision_binds_all_and_only_the_14_joined_objects() -> None:
    decision = _read(DECISION_PATH)
    register = _read(REGISTER_PATH)
    joins = _read(JOIN_PATH)
    dataset = next(
        row
        for row in joins["datasets"]
        if row["dataset"] == decision["scope"]["dataset"]
    )
    objects = dataset["joined_objects"]

    assert decision["decision_authority"] == "sole maintainer"
    assert decision["scope"]["revision"] == dataset["revision"]
    assert decision["scope"]["manifest_sha256"] == dataset["manifest_sha256"]
    assert decision["scope"]["candidate_paths"] == len(objects) == 14
    assert decision["scope"]["source_id_counts"] == dataset["source_id_counts"]
    assert set(decision["scope"]["authorization_allowed_source_ids"]) == {
        "au-data-gov-mbs-demographics",
        "au-data-gov-mbs-group",
        "au-health-medicare-statistics",
    }
    assert decision["scope"][
        "authorized_source_ids_without_objects_in_scope"
    ] == ["au-health-medicare-statistics"]
    assert all(
        item["authorization_scope_match"]
        and item["path_matches_manifest"]
        and item["source_id_matches_manifest"]
        and item["category_matches_manifest"]
        and item["sha256_matches_manifest"]
        and item["byte_count_matches_manifest"]
        for item in objects
    )
    assert all(not item["rights_state_field_present"] for item in objects)

    sources = {item["source_id"] for item in objects}
    evidence_sources = {
        item["source_id"]
        for item in decision["official_evidence"]
        if "source_id" in item
    }
    assert evidence_sources == sources
    assert all(
        item["license"] == "Creative Commons Attribution 3.0 Australia"
        and item["metadata_response_sha256"]
        for item in decision["official_evidence"]
        if "source_id" in item
    )
    assert decision["disposition"]["redistribute"] == "permitted"
    assert decision["separate_open_gates"]["v4_admission"] is False
    assert decision["separate_open_gates"]["m112_federation_accepted"] is False
    assert (
        decision["separate_open_gates"][
            "approved_candidate_denominator_changed"
        ]
        is False
    )

    group = next(
        row
        for row in register["additional_deferred_sources"]
        if row["group_id"] == "au-mbs-utilisation-rights-ledger"
    )
    assert group["candidate_paths"] == 14
    reconciliation = _read(RECONCILIATION_PATH)
    assert reconciliation["supersedes"]["path"] == REGISTER_PATH
    assert (
        reconciliation["supersedes"]["sha256"]
        == hashlib.sha256((ROOT / REGISTER_PATH).read_bytes()).hexdigest()
    )
    assert reconciliation["rights_decision"]["path"] == DECISION_PATH
    assert (
        reconciliation["rights_decision"]["sha256"]
        == hashlib.sha256((ROOT / DECISION_PATH).read_bytes()).hexdigest()
    )
    disposition = reconciliation["current_disposition"]
    assert disposition["candidate_paths"] == 14
    assert disposition["rights_state"].startswith("maintainer-approved")
    assert "B1_B2_lineage" in disposition["lineage_state"]
    assert disposition["v4_admission"] is False
    assert disposition["consumer_canaries"] is False
    assert disposition["m112_federation_accepted"] is False
    assert disposition["candidate_denominator_changed"] is False


def test_prepared_object_rights_records_preserve_receipts_and_exact_scope() -> (
    None
):
    path = (
        "quality/qualifications/"
        "australian-mbs-utilisation-object-rights-metadata-20261004.json"
    )
    prepared = _read(path)
    decision = _read(DECISION_PATH)
    dataset = next(
        row
        for row in _read(JOIN_PATH)["datasets"]
        if row["dataset"] == decision["scope"]["dataset"]
    )
    for reference, source in [
        ("rights_decision", DECISION_PATH),
        ("receipt_join_audit", JOIN_PATH),
    ]:
        assert prepared[reference]["path"] == source
        assert (
            prepared[reference]["sha256"]
            == hashlib.sha256((ROOT / source).read_bytes()).hexdigest()
        )
    assert prepared["dataset"] == dataset["dataset"]
    assert prepared["source_revision"] == dataset["revision"]
    assert prepared["manifest_sha256"] == dataset["manifest_sha256"]
    records = prepared["records"]
    assert len(records) == len({row["path"] for row in records}) == 14
    assert {row["path"] for row in records} == {
        row["path"] for row in dataset["joined_objects"]
    }
    expected = {row["path"]: row for row in dataset["joined_objects"]}
    for row in records:
        original = expected[row["path"]]
        for field in (
            "source_id",
            "category",
            "sha256",
            "byte_count",
            "receipt_path",
            "receipt_sha256",
        ):
            assert row[field] == original[field]
        assert row["rights_state"] == "maintainer-approved-exact-object"
        assert row["reuse"] == decision["disposition"]
        assert row["approval_record"] == prepared["rights_decision"]
        assert row["recorded_at"] == prepared["recorded_at"]
    assert prepared["status"] == "prepared_not_published"
    assert prepared["historical_receipts_modified"] is False
    assert prepared["complete_b1_b2_lineage"] is False
    assert prepared["v4_admission"] is False
    assert prepared["consumer_canaries"] is False


def test_rights_append_contract_binds_exact_payload_and_preservation() -> None:
    contract = _read(
        "quality/qualifications/"
        "australian-mbs-utilisation-rights-append-contract-20261004.json"
    )
    payload_path = (
        "quality/qualifications/"
        "australian-mbs-utilisation-object-rights-metadata-20261004.json"
    )
    payload = (ROOT / payload_path).read_bytes()
    metadata = _read(payload_path)
    digest = hashlib.sha256(payload).hexdigest()
    addition = contract["addition"]
    assert addition == {
        "local_path": payload_path,
        "path": f"metadata/rights/mbs-utilisation/{digest}.json",
        "sha256": digest,
        "byte_count": len(payload),
    }
    assert contract["dataset"] == metadata["dataset"]
    assert contract["source_revision"] == metadata["source_revision"]
    assert (
        contract["expected_parent_revision"]
        == contract["parent_readback"]["revision"]
    )
    assert contract["rights_decision"] == metadata["rights_decision"]
    assert contract["source_manifest_sha256"] == metadata["manifest_sha256"]
    assert contract["status"] == "prepared_not_executed"
    controls = contract["execution_controls"]
    assert controls["origin"] == "github_actions_only"
    assert controls["environment"] == "australian-hf-publication"
    assert controls["exact_reviewed_main_commit_required"] is True
    assert controls["parent_compare_and_swap_required"] is True
    assert controls["durable_intent_before_write"] is True
    assert controls["allowed_operations"] == ["add_exact_metadata_object"]
    assert controls["historical_overwrite_allowed"] is False
    assert controls["raw_source_acquisition_allowed"] is False
    assert contract["verification"]["expected_inventory_delta"] == {
        "added": [addition["path"]],
        "removed": [],
        "modified": [],
    }
    assert (
        contract["verification"]["anonymous_all_object_digest_readback"] is True
    )
    assert contract["verification"]["durable_receipt_before_cleanup"] is True
    assert (
        contract["verification"]["preserve_failed_published_revision"] is True
    )
    assert contract["recovery"]["retry_after_ambiguous_write"] == (
        "read_back_and_reconcile_before_any_new_write"
    )
    assert contract["completion_claims"] == {
        "external_publication_performed": False,
        "complete_b1_b2_lineage": False,
        "v4_admission": False,
        "consumer_canaries": False,
        "m112_federation_accepted": False,
    }


def test_offline_validator_returns_exact_addition_and_preserved_provenance() -> (
    None
):
    contract = _read(
        "quality/qualifications/"
        "australian-mbs-utilisation-rights-append-contract-20261004.json"
    )
    payload = (ROOT / contract["addition"]["local_path"]).read_bytes()
    result = validate_rights_append(
        contract,
        payload,
        (ROOT / DECISION_PATH).read_bytes(),
        (ROOT / JOIN_PATH).read_bytes(),
    )
    assert result.payload == payload
    assert result.addition.path == contract["addition"]["path"]
    assert (
        len(result.required_objects) == 29
    )  # 14 raw + 14 receipts + manifest.
    assert result.source_revision == contract["source_revision"]
    # A reviewed new CAS parent must not require rewriting source provenance.
    contract["expected_parent_revision"] = "a" * 40
    contract["parent_readback"]["revision"] = "a" * 40
    advanced = validate_rights_append(
        contract,
        payload,
        (ROOT / DECISION_PATH).read_bytes(),
        (ROOT / JOIN_PATH).read_bytes(),
    )
    assert advanced.parent_revision == "a" * 40
    assert advanced.source_revision == result.source_revision


def test_offline_validator_rejects_scope_and_control_tampering() -> None:
    original = _read(
        "quality/qualifications/"
        "australian-mbs-utilisation-rights-append-contract-20261004.json"
    )
    payload = (ROOT / original["addition"]["local_path"]).read_bytes()
    decision = (ROOT / DECISION_PATH).read_bytes()
    joins = (ROOT / JOIN_PATH).read_bytes()
    changes = [
        ("dataset", "other/dataset"),
        ("source_revision", "b" * 40),
        ("schema_version", True),
        ("expected_parent_revision", "main"),
        ("status", "published"),
        ("rights_decision", {"path": DECISION_PATH, "sha256": "0" * 64}),
        ("execution_controls", {}),
        ("verification", {}),
        ("recovery", {}),
        ("completion_claims", {}),
    ]
    for key, value in changes:
        contract = copy.deepcopy(original)
        contract[key] = value
        with pytest.raises(
            (ValueError, TypeError), match=r"contract|CAS|metadata|rights"
        ):
            validate_rights_append(contract, payload, decision, joins)
    for wrong_payload, wrong_decision, wrong_joins in [
        (payload + b" ", decision, joins),
        (payload, decision + b" ", joins),
        (payload, decision, joins + b" "),
        (b"[]", decision, joins),
        (b" " * (1024 * 1024 + 1), decision, joins),
    ]:
        with pytest.raises(
            (ValueError, TypeError), match=r"contract|CAS|metadata|rights"
        ):
            validate_rights_append(
                original, wrong_payload, wrong_decision, wrong_joins
            )
    for mutation in (
        "duplicate",
        "unknown",
        "digest",
        "reuse",
        "approval",
        "top_extra",
        "row_extra",
    ):
        document = json.loads(payload)
        if mutation == "duplicate":
            document["records"][1] = document["records"][0]
        elif mutation == "unknown":
            document["records"][0]["path"] = "raw/unapproved.csv"
        elif mutation == "digest":
            document["records"][0]["sha256"] = "0" * 64
        elif mutation == "reuse":
            document["records"][0]["reuse"] = {}
        elif mutation == "top_extra":
            document["regulatory_approved"] = True
        elif mutation == "row_extra":
            document["records"][0]["later_revisions_authorized"] = True
        else:
            document["records"][0]["approval_record"] = {}
        altered = json.dumps(document).encode()
        contract = copy.deepcopy(original)
        digest = hashlib.sha256(altered).hexdigest()
        path = f"metadata/rights/mbs-utilisation/{digest}.json"
        contract["addition"].update(
            path=path, sha256=digest, byte_count=len(altered)
        )
        contract["verification"]["expected_inventory_delta"]["added"] = [path]
        with pytest.raises(
            (ValueError, TypeError), match=r"contract|CAS|metadata|rights"
        ):
            validate_rights_append(contract, altered, decision, joins)


def test_hosted_rights_publication_preserves_all_existing_objects() -> None:
    receipt = _read(
        "quality/qualifications/"
        "australian-mbs-utilisation-rights-publication-receipt-20261004.json"
    )
    contract_ref = receipt["append_contract"]
    assert (
        contract_ref["sha256"]
        == hashlib.sha256(
            (ROOT / contract_ref["path"]).read_bytes()
        ).hexdigest()
    )
    contract = _read(contract_ref["path"])
    assert receipt["payload"] == contract["addition"]
    assert receipt["source_revision"] == contract["source_revision"]
    assert receipt["workflow_conclusion"] == "success"
    events = receipt["hosted_receipts"]
    assert [event["document"]["status"] for event in events] == [
        "intent",
        "cas_acknowledged",
        "anonymously_verified",
        "cleanup_completed",
    ]
    for event in events:
        document = event["document"]
        assert event["author"] == "github-actions[bot]"
        assert (
            event["body_sha256"]
            == hashlib.sha256(
                json.dumps(
                    document, sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest()
        )
        assert document["code_commit"] == receipt["code_commit"]
        assert document["run_url"] == receipt["workflow_run"]
        assert document["authorization"] == receipt["rights_decision"]
    verified = events[2]["document"]
    assert verified["addition"] == {
        key: contract["addition"][key]
        for key in ("path", "byte_count", "sha256")
    }
    before = {row["path"]: row for row in verified["baseline"]}
    after = {row["path"]: row for row in verified["observed"]}
    assert len(before) == 30
    assert len(after) == 31
    assert after == {
        **before,
        verified["addition"]["path"]: verified["addition"],
    }
    assert verified["revision"] == receipt["publication_revision"]
    assert events[3]["document"]["temporary_cache_removed"] is True
    readback = receipt["independent_metadata_readback"]
    assert readback["sha256"] == contract["addition"]["sha256"]
    assert readback["byte_count"] == contract["addition"]["byte_count"]
    assert readback["exact_local_payload_match"] is True
    assert receipt["current_disposition"]["per_object_rights_metadata"] == (
        "published_and_digest_verified"
    )
    for key in (
        "complete_b1_b2_lineage",
        "v4_admission",
        "consumer_canaries",
        "m112_federation_accepted",
        "candidate_denominator_changed",
    ):
        assert receipt["current_disposition"][key] is False
    assert (
        receipt["supersedes"]["sha256"]
        == hashlib.sha256(
            (ROOT / receipt["supersedes"]["path"]).read_bytes()
        ).hexdigest()
    )


def test_acquisition_crosswalk_preserves_all_historical_receipt_identities() -> (
    None
):
    crosswalk = _read(
        "quality/qualifications/"
        "australian-mbs-utilisation-acquisition-crosswalk-20261004.json"
    )
    for reference in crosswalk["evidence_inputs"]:
        assert (
            reference["sha256"]
            == hashlib.sha256(
                (ROOT / reference["path"]).read_bytes()
            ).hexdigest()
        )
    publication = _read(crosswalk["evidence_inputs"][0]["path"])
    rights = _read(publication["payload"]["local_path"])
    verified = publication["hosted_receipts"][2]["document"]
    observed = {row["path"]: row for row in verified["observed"]}
    records = crosswalk["records"]
    assert len(records) == len({row["path"] for row in records}) == 14
    assert {row["path"] for row in records} == {
        row["path"] for row in rights["records"]
    }
    assert crosswalk["source_revision"] == publication["source_revision"]
    assert crosswalk["rights_revision"] == publication["publication_revision"]
    for row in records:
        receipt = row["historical_receipt"]
        raw = (ROOT / receipt["local_path"]).read_bytes()
        original = json.loads(raw)
        assert hashlib.sha256(raw).hexdigest() == receipt["sha256"]
        assert len(raw) == receipt["byte_count"]
        assert observed[receipt["archive_path"]]["sha256"] == receipt["sha256"]
        assert original["archive_path"] == row["path"]
        assert original["sha256"] == row["payload_sha256"]
        assert original["byte_count"] == row["byte_count"]
        assert original["source_id"] == row["source_id"]
        assert original["category"] == row["category"]
        acquisition = row["historical_acquisition"]
        assert acquisition["retrieved_at"] == original["retrieved_at"]
        assert acquisition["original_url"] == original["source_url"]
        assert acquisition["final_url"] == original["final_url"]
        assert (
            acquisition["source_native_period_label"]
            == original["period_label"]
        )
        for key in (
            "producer_acquisition_id",
            "source_published_at",
            "source_effective_at",
        ):
            assert acquisition[key] is None
        raw_reference = row["b2_raw_reference"]
        assert raw_reference["sha256"] == observed[row["path"]]["sha256"]
        assert (
            raw_reference["byte_count"] == observed[row["path"]]["byte_count"]
        )
        assert raw_reference["revision"] == crosswalk["source_revision"]
        assert raw_reference["url"].endswith(
            f"/{crosswalk['source_revision']}/{row['path']}"
        )
        pointer = row["rights_record"]["json_pointer"]
        selected = rights["records"][int(pointer.split("/")[-1])]
        assert selected["path"] == row["path"]
        assert selected["sha256"] == row["payload_sha256"]
        assert selected["receipt_sha256"] == receipt["sha256"]
        assert row["rights_record"]["revision"] == crosswalk["rights_revision"]
        assert row["identity_join_complete"] is True
        assert row["native_acquisition_event_selected"] is False
        assert row["native_admission_history_selected"] is False
        assert row["v4_admission"] is False
    assert not any(crosswalk["boundaries"].values())


def test_historical_event_import_preserves_receipt_evidence() -> None:
    crosswalk = _read(
        "quality/qualifications/"
        "australian-mbs-utilisation-acquisition-crosswalk-20261004.json"
    )
    imported = _read(
        "quality/qualifications/"
        "australian-mbs-utilisation-acquisition-import-20261004.json"
    )
    assert (
        imported["crosswalk_sha256"]
        == hashlib.sha256(
            (ROOT / imported["crosswalk_path"]).read_bytes()
        ).hexdigest()
    )
    assert len(imported["records"]) == len(crosswalk["records"]) == 14
    for row, original in zip(
        imported["records"], crosswalk["records"], strict=True
    ):
        receipt = _read(original["historical_receipt"]["local_path"])
        event_bytes = (ROOT / row["event_path"]).read_bytes()
        event = AcquisitionEvent.model_validate_json(event_bytes)
        assert event_bytes == event.canonical_json()
        assert hashlib.sha256(event_bytes).hexdigest() == row["event_sha256"]
        assert row["historical_receipt"] == original["historical_receipt"]
        assert row["b2_raw_reference"] == original["b2_raw_reference"]
        assert row["rights_record"] == original["rights_record"]
        assert row["producer_acquisition_id"] is None
        assert row["admission_record"] is None
        assert event.acquisition_id == acquisition_event_id_for(
            source_id=receipt["source_id"],
            payload_sha256=receipt["sha256"],
            retrieved_at=datetime.fromisoformat(receipt["retrieved_at"]),
            original_uri=receipt["source_url"],
        )
        assert event.content_id == event.payload_sha256 == receipt["sha256"]
        assert event.source_id == receipt["source_id"]
        assert event.retrieved_at == datetime.fromisoformat(
            receipt["retrieved_at"]
        )
        assert event.source_version is None
        assert event.source_published_at is None
        assert event.source_effective_at is None
        assert event.valid_from is None
        assert event.valid_to is None
        assert event.retrieval is not None
        assert str(event.retrieval.uri) == receipt["source_url"]
        assert event.retrieval.retrieved_at == event.retrieved_at
        assert event.retrieval.http is not None
        assert str(event.retrieval.http.final_uri) == receipt["final_url"]
        assert (
            event.retrieval.http.observed_byte_length == receipt["byte_count"]
        )
        assert event.retrieval.http.http_status is None
        assert event.retrieval.http.acquisition_agent_version is None
    assert len({row["acquisition_id"] for row in imported["records"]}) == 14
    assert not any(imported["boundaries"].values())


def test_lifecycle_reconciliation_does_not_invent_native_records() -> None:
    audit = _read(
        "quality/qualifications/"
        "australian-mbs-utilisation-lifecycle-reconciliation-20261004.json"
    )
    imported = _read(audit["inputs"]["event_import"]["path"])
    for binding in audit["inputs"].values():
        assert (
            hashlib.sha256((ROOT / binding["path"]).read_bytes()).hexdigest()
            == (binding["sha256"])
        )
    tree = _read(audit["inputs"]["public_tree"]["path"])
    assert tree["pagination_complete"] is True
    assert tree["revision"] == "87d63977f546dc5cc7c4f5371e37e77a7dfc0ddf"
    hosted = _read(audit["inputs"]["hosted_verification"]["path"])
    verified = next(
        row["document"]
        for row in hosted["hosted_receipts"]
        if row["document"]["status"] == "anonymously_verified"
    )
    assert verified["revision"] == tree["revision"]
    digests = {row["path"]: row for row in verified["observed"]}
    files = {row["path"]: row for row in tree["files"]}
    assert len(files) == 31
    assert len(audit["records"]) == len(imported["records"]) == 14
    for row, event in zip(audit["records"], imported["records"], strict=True):
        assert row["acquisition_id"] == event["acquisition_id"]
        assert row["event_path"] == event["event_path"]
        assert row["raw_reference"] == event["b2_raw_reference"]
        assert (
            files[row["raw_reference"]["path"]]["size"]
            == (row["raw_reference"]["byte_count"])
        )
        observed = digests[row["raw_reference"]["path"]]
        assert observed["sha256"] == row["raw_reference"]["sha256"]
        assert observed["byte_count"] == row["raw_reference"]["byte_count"]
        lfs = files[row["raw_reference"]["path"]].get("lfs")
        if lfs is not None:
            assert lfs["oid"] == row["raw_reference"]["sha256"]
        assert row["source_receipt"] is None
        assert row["payload_storage_receipt"] is None
        assert row["admission_history"] is None
        assert row["source_receipt_gaps"] == [
            "native_source_catalog_identity",
            "pinned_transformation_and_output_evidence",
        ]
        assert row["durable_storage_gaps"] == [
            "geographic_primary_and_independent_replica_identity",
            "replica_version_and_checksum_receipts",
            "rpo_rto_and_inventory_restore_cadences",
        ]
    assert audit["counts"]["immutable_raw_references_reconciled"] == 14
    assert audit["counts"]["native_source_receipts_selected"] == 0
    assert audit["counts"]["native_storage_receipts_selected"] == 0
    assert not any(audit["boundaries"].values())
