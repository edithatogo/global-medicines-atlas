"""Durable Bronze payload storage and independent sensitivity contracts."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pyarrow.parquet as pq
import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError
from tests.test_source_receipts import source_receipt

from global_medicines_atlas.bronze_landing import BronzeLanding, land_bronze_payload
from global_medicines_atlas.bronze_storage import (
    DurabilityPolicy,
    ImmutabilityMode,
    LocalFilesystemPayloadStore,
    ObjectStoragePayloadStore,
    ObjectStorageTarget,
    ObjectWriteResult,
    create_checksum_inventory,
    rehearse_restore,
)
from global_medicines_atlas.receipts import (
    DataSensitivity,
    PayloadEvidence,
    PersonalDataState,
    PublicationDisposition,
    SensitivityClassification,
    require_publication_permitted,
    temporal_identity_from_source,
)
from global_medicines_atlas.reuse_gate import acquire_new_decision

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = b'{"application_number":"012345"}'
NOW = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)


class FakeObjectClient:
    """Small S3-compatible boundary fake; no remote credentials required."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str, str], bytes] = {}
        self.latest: dict[tuple[str, str], str] = {}

    def put_object_if_absent(
        self,
        *,
        bucket: str,
        key: str,
        payload: bytes,
        checksum_sha256: str,
        object_lock_required: bool,
    ) -> ObjectWriteResult:
        version_id = f"version-{len(self.objects) + 1}"
        current = self.latest.get((bucket, key))
        if current is not None:
            if self.objects[(bucket, key, current)] != payload:
                raise ValueError("immutable object conflict")
            version_id = current
        else:
            self.objects[(bucket, key, version_id)] = payload
            self.latest[(bucket, key)] = version_id
        return ObjectWriteResult(
            version_id=version_id,
            etag=checksum_sha256,
            object_lock_mode="COMPLIANCE" if object_lock_required else None,
        )

    def get_object(self, *, bucket: str, key: str, version_id: str) -> bytes:
        return self.objects[(bucket, key, version_id)]


def _durable_policy() -> DurabilityPolicy:
    return DurabilityPolicy(
        operation="durable_object_storage",
        immutability=ImmutabilityMode.OBJECT_LOCK,
        rpo_seconds=900,
        rto_seconds=3600,
        checksum_inventory_interval_hours=24,
        restore_rehearsal_interval_days=30,
        primary_region="ap-southeast-2",
        primary_administrative_domain="atlas-production",
        replica_region="ap-southeast-1",
        replica_administrative_domain="atlas-recovery",
    )


def _targets() -> tuple[ObjectStorageTarget, ObjectStorageTarget]:
    return (
        ObjectStorageTarget(
            bucket="gma-bronze-primary",
            prefix="bronze",
            region="ap-southeast-2",
            administrative_domain="atlas-production",
        ),
        ObjectStorageTarget(
            bucket="gma-bronze-replica",
            prefix="bronze",
            region="ap-southeast-1",
            administrative_domain="atlas-recovery",
        ),
    )


def _landable(*, sensitivity: SensitivityClassification) -> object:
    receipt = source_receipt()
    payload = PayloadEvidence.from_bytes(PAYLOAD)
    retrieval = receipt.retrieval.model_copy(update={"retrieved_at": NOW})
    return receipt.model_copy(
        update={
            "payload": payload,
            "retrieval": retrieval,
            "reuse": acquire_new_decision(receipt.source.source_id),
            "sensitivity": sensitivity,
            "temporal": temporal_identity_from_source(
                retrieved_at=NOW,
                source_id=receipt.source.source_id,
                payload_sha256=payload.sha256,
                original_uri=str(retrieval.uri),
            ),
        }
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("update", "message"),
    [
        ({"immutability": ImmutabilityMode.NONE}, "versioning or Object Lock"),
        ({"replica_region": "ap-southeast-2"}, "geographically"),
        ({"replica_administrative_domain": "atlas-production"}, "administratively"),
        ({"rpo_seconds": None}, "RPO"),
        ({"rto_seconds": None}, "RTO"),
    ],
)
def test_durable_policy_fails_closed(update: dict[str, object], message: str) -> None:
    payload = _durable_policy().model_dump(mode="python") | update
    with pytest.raises(ValidationError, match=message):
        DurabilityPolicy.model_validate(payload)


@pytest.mark.unit
def test_local_store_is_explicitly_development_only_and_immutable(tmp_path: Path) -> None:
    store = LocalFilesystemPayloadStore(tmp_path / "bronze")
    first = store.store(
        PAYLOAD,
        acquisition_id="a" * 64,
        content_id=PayloadEvidence.from_bytes(PAYLOAD).sha256,
        suffix=".json",
    )
    second = store.store(
        PAYLOAD,
        acquisition_id="b" * 64,
        content_id=PayloadEvidence.from_bytes(PAYLOAD).sha256,
        suffix=".json",
    )
    assert first.materialized_path == second.materialized_path
    assert first.receipt.policy.operation == "local_development"
    first.materialized_path.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="immutable"):
        store.store(
            PAYLOAD,
            acquisition_id="c" * 64,
            content_id=PayloadEvidence.from_bytes(PAYLOAD).sha256,
            suffix=".json",
        )


@pytest.mark.unit
def test_object_store_versions_replicates_inventories_and_restores(tmp_path: Path) -> None:
    primary_target, replica_target = _targets()
    primary = FakeObjectClient()
    replica = FakeObjectClient()
    store = ObjectStoragePayloadStore(
        staging_root=tmp_path / "stage",
        policy=_durable_policy(),
        primary=(primary_target, primary),
        replicas=((replica_target, replica),),
    )
    stored = store.store(
        PAYLOAD,
        acquisition_id="a" * 64,
        content_id=PayloadEvidence.from_bytes(PAYLOAD).sha256,
        suffix=".json",
    )

    assert stored.receipt.primary.version_id == "version-1"
    assert stored.receipt.primary.object_lock_mode == "COMPLIANCE"
    assert len(stored.receipt.replicas) == 1
    assert stored.receipt.primary.uri.startswith("s3://gma-bronze-primary/")
    assert stored.materialized_path.read_bytes() == PAYLOAD

    inventory = create_checksum_inventory(store, (stored.receipt,), generated_at=NOW)
    assert inventory.checked_objects == 2
    assert inventory.inventory_sha256
    rehearsal = rehearse_restore(
        store,
        (stored.receipt,),
        restore_root=tmp_path / "restore",
        completed_at=NOW,
    )
    assert rehearsal.restored_payloads == 1
    assert rehearsal.within_rto is True
    assert (tmp_path / "restore" / f"{stored.receipt.content_id}.json").read_bytes() == PAYLOAD


@pytest.mark.unit
def test_checksum_inventory_detects_replica_corruption(tmp_path: Path) -> None:
    primary_target, replica_target = _targets()
    primary = FakeObjectClient()
    replica = FakeObjectClient()
    store = ObjectStoragePayloadStore(
        staging_root=tmp_path / "stage",
        policy=_durable_policy(),
        primary=(primary_target, primary),
        replicas=((replica_target, replica),),
    )
    stored = store.store(
        PAYLOAD,
        acquisition_id="a" * 64,
        content_id=PayloadEvidence.from_bytes(PAYLOAD).sha256,
        suffix=".json",
    )
    replica_ref = stored.receipt.replicas[0]
    replica.objects[(replica_target.bucket, replica_ref.key, replica_ref.version_id)] = b"corrupt"
    with pytest.raises(ValueError, match="checksum"):
        create_checksum_inventory(store, (stored.receipt,), generated_at=NOW)


@pytest.mark.unit
def test_rights_and_sensitivity_are_independent_publication_gates() -> None:
    review_required = SensitivityClassification(
        data_sensitivity=DataSensitivity.SENSITIVE,
        personal_data=PersonalDataState.POSSIBLE,
        publication=PublicationDisposition.REVIEW_REQUIRED,
        reason_codes=("public_free_text_may_identify_reporter",),
    )
    receipt = _landable(sensitivity=review_required)
    assert receipt.rights_state.value == "permitted"
    with pytest.raises(ValueError, match="sensitivity/publication"):
        require_publication_permitted(receipt)

    publishable = review_required.model_copy(
        update={"publication": PublicationDisposition.PERMITTED}
    )
    require_publication_permitted(receipt.model_copy(update={"sensitivity": publishable}))


@pytest.mark.unit
def test_object_store_landing_persists_storage_and_sensitivity_evidence(tmp_path: Path) -> None:
    primary_target, replica_target = _targets()
    store = ObjectStoragePayloadStore(
        staging_root=tmp_path / "bronze" / "stage",
        policy=_durable_policy(),
        primary=(primary_target, FakeObjectClient()),
        replicas=((replica_target, FakeObjectClient()),),
    )
    sensitivity = SensitivityClassification(
        data_sensitivity=DataSensitivity.SENSITIVE,
        personal_data=PersonalDataState.POSSIBLE,
        publication=PublicationDisposition.REVIEW_REQUIRED,
        reason_codes=("free_text",),
    )
    landing = land_bronze_payload(
        PAYLOAD,
        _landable(sensitivity=sensitivity),
        bronze_root=tmp_path / "bronze",
        media_hint="json",
        payload_store=store,
    )
    assert isinstance(landing, BronzeLanding)
    assert landing.storage_receipt_path.is_file()
    persisted = json.loads(landing.storage_receipt_path.read_bytes())
    assert persisted["primary"]["uri"].startswith("s3://")
    manifest = pq.read_table(landing.acquisition_manifest_path)
    assert manifest["payload_location"][0].as_py().startswith("s3://")
    assert manifest["data_sensitivity"][0].as_py() == "sensitive"
    assert manifest["publication_disposition"][0].as_py() == "review_required"


@pytest.mark.unit
def test_storage_and_sensitivity_schemas_accept_canonical_contracts() -> None:
    documents = {
        "bronze-storage-policy-v1.json": _durable_policy().model_dump(mode="json"),
        "bronze-sensitivity-classification-v1.json": SensitivityClassification().model_dump(mode="json"),
    }
    for filename, instance in documents.items():
        schema = json.loads((ROOT / "schemas" / filename).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(instance)
