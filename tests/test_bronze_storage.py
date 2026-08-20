"""Durable Bronze payload storage and independent sensitivity contracts."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pyarrow.parquet as pq
import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError
from tests.test_source_receipts import source_receipt

from global_medicines_atlas.bronze_landing import (
    BronzeLanding,
    land_bronze_payload,
)
from global_medicines_atlas.bronze_storage import (
    DurabilityPolicy,
    ImmutabilityMode,
    LocalFilesystemPayloadStore,
    ObjectStoragePayloadStore,
    ObjectStorageTarget,
    ObjectWriteResult,
    PayloadStorageReceipt,
    StoredObjectEvidence,
    create_checksum_inventory,
    rehearse_restore,
)
from global_medicines_atlas.receipts import (
    DataSensitivity,
    PayloadEvidence,
    PersonalDataState,
    PublicationDisposition,
    RightsState,
    SensitivityClassification,
    SourceReceipt,
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
            if self.objects[bucket, key, current] != payload:
                raise ValueError("immutable object conflict")
            version_id = current
        else:
            self.objects[bucket, key, version_id] = payload
            self.latest[bucket, key] = version_id
        return ObjectWriteResult(
            version_id=version_id,
            etag=checksum_sha256,
            object_lock_mode="COMPLIANCE" if object_lock_required else None,
        )

    def get_object(self, *, bucket: str, key: str, version_id: str) -> bytes:
        return self.objects[bucket, key, version_id]


class MissingVersionObjectClient(FakeObjectClient):
    """Provider fake that violates the durable version-identity contract."""

    def put_object_if_absent(
        self,
        *,
        bucket: str,
        key: str,
        payload: bytes,
        checksum_sha256: str,
        object_lock_required: bool,
    ) -> ObjectWriteResult:
        result = super().put_object_if_absent(
            bucket=bucket,
            key=key,
            payload=payload,
            checksum_sha256=checksum_sha256,
            object_lock_required=object_lock_required,
        )
        return result.model_copy(update={"version_id": None})


class CorruptingReadObjectClient(FakeObjectClient):
    """Provider fake that returns bytes different from the completed write."""

    def get_object(self, *, bucket: str, key: str, version_id: str) -> bytes:
        super().get_object(bucket=bucket, key=key, version_id=version_id)
        return b"corrupt"


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


def _landable(
    *, sensitivity: SensitivityClassification | None = None
) -> SourceReceipt:
    receipt = source_receipt()
    payload = PayloadEvidence.from_bytes(PAYLOAD)
    retrieval = receipt.retrieval.model_copy(update={"retrieved_at": NOW})
    updates: dict[str, object] = {
        "payload": payload,
        "retrieval": retrieval,
        "reuse": acquire_new_decision(receipt.source.source_id),
        "temporal": temporal_identity_from_source(
            retrieved_at=NOW,
            source_id=receipt.source.source_id,
            payload_sha256=payload.sha256,
            original_uri=str(retrieval.uri),
        ),
    }
    if sensitivity is not None:
        updates["sensitivity"] = sensitivity
    return receipt.model_copy(update=updates)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("update", "message"),
    [
        ({"immutability": ImmutabilityMode.NONE}, "versioning or Object Lock"),
        ({"replica_region": "ap-southeast-2"}, "geographically"),
        (
            {"replica_administrative_domain": "atlas-production"},
            "administratively",
        ),
        ({"rpo_seconds": None}, "RPO"),
        ({"rto_seconds": None}, "RTO"),
        ({"checksum_inventory_interval_hours": None}, "inventory cadence"),
        ({"restore_rehearsal_interval_days": None}, "rehearsal cadence"),
        ({"primary_region": ""}, "primary and replica identities"),
    ],
)
def test_durable_policy_fails_closed(
    update: dict[str, object], message: str
) -> None:
    payload = _durable_policy().model_dump(mode="python") | update
    with pytest.raises(ValidationError, match=message):
        DurabilityPolicy.model_validate(payload)


@pytest.mark.unit
def test_local_store_is_explicitly_development_only_and_immutable(
    tmp_path: Path,
) -> None:
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
    assert store.read_object(first.receipt.primary) == PAYLOAD
    with pytest.raises(ValueError, match="content_id"):
        store.store(
            PAYLOAD,
            acquisition_id="c" * 64,
            content_id="f" * 64,
            suffix=".json",
        )
    with pytest.raises(ValueError, match="suffix"):
        store.store(
            PAYLOAD,
            acquisition_id="c" * 64,
            content_id=PayloadEvidence.from_bytes(PAYLOAD).sha256,
            suffix="/../../escape",
        )
    remote_reference = first.receipt.primary.model_copy(
        update={"uri": "s3://outside/payload.json"}
    )
    with pytest.raises(ValueError, match="file URIs"):
        store.read_object(remote_reference)
    first.materialized_path.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="immutable"):
        store.store(
            PAYLOAD,
            acquisition_id="c" * 64,
            content_id=PayloadEvidence.from_bytes(PAYLOAD).sha256,
            suffix=".json",
        )


@pytest.mark.unit
def test_object_store_rejects_policy_and_reference_mismatches(
    tmp_path: Path,
) -> None:
    primary_target, replica_target = _targets()
    primary = FakeObjectClient()
    replica = FakeObjectClient()
    with pytest.raises(ValueError, match="durable policy"):
        ObjectStoragePayloadStore(
            staging_root=tmp_path,
            policy=DurabilityPolicy.local_development(),
            primary=(primary_target, primary),
            replicas=((replica_target, replica),),
        )
    with pytest.raises(ValueError, match="primary target"):
        ObjectStoragePayloadStore(
            staging_root=tmp_path,
            policy=_durable_policy(),
            primary=(
                primary_target.model_copy(update={"region": "eu-west-1"}),
                primary,
            ),
            replicas=((replica_target, replica),),
        )
    with pytest.raises(ValueError, match="independent replica target"):
        ObjectStoragePayloadStore(
            staging_root=tmp_path,
            policy=_durable_policy(),
            primary=(primary_target, primary),
            replicas=(
                (
                    replica_target.model_copy(update={"region": "eu-west-1"}),
                    replica,
                ),
            ),
        )
    with pytest.raises(ValueError, match="distinct bucket"):
        ObjectStoragePayloadStore(
            staging_root=tmp_path,
            policy=_durable_policy(),
            primary=(primary_target, primary),
            replicas=(
                (
                    replica_target.model_copy(
                        update={"bucket": primary_target.bucket}
                    ),
                    replica,
                ),
            ),
        )

    store = ObjectStoragePayloadStore(
        staging_root=tmp_path,
        policy=_durable_policy(),
        primary=(primary_target, primary),
        replicas=((replica_target, replica),),
    )
    with pytest.raises(ValueError, match="content_id"):
        store.store(
            PAYLOAD,
            acquisition_id="a" * 64,
            content_id="f" * 64,
            suffix=".json",
        )
    incomplete = StoredObjectEvidence(
        uri="s3://outside/key",
        key="key",
        region="ap-southeast-2",
        administrative_domain="atlas-production",
        sha256=PayloadEvidence.from_bytes(PAYLOAD).sha256,
        byte_count=len(PAYLOAD),
    )
    with pytest.raises(ValueError, match="bucket or version"):
        store.read_object(incomplete)
    outside = incomplete.model_copy(
        update={"bucket": "outside", "version_id": "version-1"}
    )
    with pytest.raises(ValueError, match="outside this storage topology"):
        store.read_object(outside)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("client_kind", "message"),
    [
        ("missing_version", "version identity"),
        ("corrupt_read", "checksum verification"),
    ],
)
def test_object_store_verifies_each_provider_write(
    tmp_path: Path, client_kind: str, message: str
) -> None:
    primary_target, replica_target = _targets()
    primary: FakeObjectClient
    if client_kind == "missing_version":
        primary = MissingVersionObjectClient()
    else:
        primary = CorruptingReadObjectClient()
    store = ObjectStoragePayloadStore(
        staging_root=tmp_path,
        policy=_durable_policy(),
        primary=(primary_target, primary),
        replicas=((replica_target, FakeObjectClient()),),
    )
    with pytest.raises(ValueError, match=message):
        store.store(
            PAYLOAD,
            acquisition_id="a" * 64,
            content_id=PayloadEvidence.from_bytes(PAYLOAD).sha256,
            suffix=".json",
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("scenario", "message"),
    [
        ("content_id", "content_id"),
        ("byte_count", "stored-copy identity"),
        ("no_replica", "replica receipt"),
        ("primary_region", "primary receipt"),
        ("replica_region", "independent replica receipt"),
        ("version_id", "version identities"),
        ("object_lock", "lock evidence"),
    ],
)
def test_storage_receipt_rejects_tampered_copy_evidence(
    tmp_path: Path,
    scenario: str,
    message: str,
) -> None:
    primary_target, replica_target = _targets()
    store = ObjectStoragePayloadStore(
        staging_root=tmp_path,
        policy=_durable_policy(),
        primary=(primary_target, FakeObjectClient()),
        replicas=((replica_target, FakeObjectClient()),),
    )
    stored = store.store(
        PAYLOAD,
        acquisition_id="a" * 64,
        content_id=PayloadEvidence.from_bytes(PAYLOAD).sha256,
        suffix=".json",
    )
    receipt = stored.receipt.model_dump(mode="python")
    primary = receipt["primary"]
    replica = receipt["replicas"][0]
    if scenario == "content_id":
        receipt["content_id"] = "f" * 64
    elif scenario == "byte_count":
        primary["byte_count"] = 0
    elif scenario == "no_replica":
        receipt["replicas"] = []
    elif scenario == "primary_region":
        primary["region"] = "ap-southeast-1"
    elif scenario == "replica_region":
        replica["region"] = "eu-west-1"
    elif scenario == "version_id":
        replica["version_id"] = None
    else:
        replica["object_lock_mode"] = None
    with pytest.raises(ValidationError, match=message):
        PayloadStorageReceipt.model_validate(receipt)


@pytest.mark.unit
def test_object_store_versions_replicates_inventories_and_restores(
    tmp_path: Path,
) -> None:
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

    inventory = create_checksum_inventory(
        store, (stored.receipt,), generated_at=NOW
    )
    assert inventory.checked_objects == 2
    assert inventory.inventory_sha256
    primary.objects.clear()
    rehearsal = rehearse_restore(
        store,
        (stored.receipt,),
        restore_root=tmp_path / "restore",
        completed_at=NOW,
    )
    assert rehearsal.restored_payloads == 1
    assert rehearsal.source_role == "replica"
    assert rehearsal.within_rto is True
    assert (
        tmp_path / "restore" / f"{stored.receipt.content_id}.json"
    ).read_bytes() == PAYLOAD


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
    assert replica_ref.version_id is not None
    replica.objects[
        replica_target.bucket, replica_ref.key, replica_ref.version_id
    ] = b"corrupt"
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
    require_publication_permitted(
        receipt.model_copy(update={"sensitivity": publishable})
    )
    with pytest.raises(ValueError, match="rights state"):
        require_publication_permitted(
            receipt.model_copy(
                update={
                    "rights_state": RightsState.RESTRICTED,
                    "sensitivity": publishable,
                }
            )
        )


@pytest.mark.unit
def test_legacy_receipt_digest_is_stable_until_sensitivity_is_bound(
    tmp_path: Path,
) -> None:
    legacy = _landable()
    assert legacy.sensitivity is None
    assert b'"sensitivity"' not in legacy.canonical_json()
    explicit = legacy.model_copy(
        update={
            "sensitivity": SensitivityClassification(
                reason_codes=("not_assessed",)
            )
        }
    )
    assert b'"sensitivity"' in explicit.canonical_json()
    assert explicit.digest() != legacy.digest()
    landing = land_bronze_payload(
        PAYLOAD,
        legacy,
        bronze_root=tmp_path / "bronze",
        media_hint="json",
    )
    persisted = json.loads(landing.receipt_path.read_bytes())
    assert persisted["sensitivity"]["publication"] == "review_required"


@pytest.mark.unit
def test_sensitivity_classification_fails_closed_when_unassessed() -> None:
    with pytest.raises(ValidationError, match="reason codes"):
        SensitivityClassification(reason_codes=())
    with pytest.raises(ValidationError, match="sensitivity is unknown"):
        SensitivityClassification(
            publication=PublicationDisposition.PERMITTED,
            reason_codes=("incorrectly_approved_without_assessment",),
        )


@pytest.mark.unit
def test_object_store_landing_persists_storage_and_sensitivity_evidence(
    tmp_path: Path,
) -> None:
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
    source_receipt_document = json.loads(landing.receipt_path.read_bytes())
    assert source_receipt_document["sensitivity"]["publication"] == (
        "review_required"
    )
    manifest = pq.read_table(  # pyright: ignore[reportUnknownMemberType]
        landing.acquisition_manifest_path
    )
    payload_location = cast("str", manifest["payload_location"].to_pylist()[0])
    assert payload_location.startswith("s3://")
    assert manifest["data_sensitivity"].to_pylist()[0] == "sensitive"
    assert (
        manifest["publication_disposition"].to_pylist()[0] == "review_required"
    )


@pytest.mark.unit
def test_storage_and_sensitivity_schemas_accept_canonical_contracts(
    tmp_path: Path,
) -> None:
    primary_target, replica_target = _targets()
    store = ObjectStoragePayloadStore(
        staging_root=tmp_path / "stage",
        policy=_durable_policy(),
        primary=(primary_target, FakeObjectClient()),
        replicas=((replica_target, FakeObjectClient()),),
    )
    stored = store.store(
        PAYLOAD,
        acquisition_id="a" * 64,
        content_id=PayloadEvidence.from_bytes(PAYLOAD).sha256,
        suffix=".json",
    )
    inventory = create_checksum_inventory(
        store, (stored.receipt,), generated_at=NOW
    )
    rehearsal = rehearse_restore(
        store,
        (stored.receipt,),
        restore_root=tmp_path / "restore",
        completed_at=NOW,
    )
    documents = {
        "bronze-storage-policy-v1.json": _durable_policy().model_dump(
            mode="json"
        ),
        "bronze-sensitivity-classification-v1.json": SensitivityClassification().model_dump(
            mode="json"
        ),
        "bronze-payload-storage-receipt-v1.json": stored.receipt.model_dump(
            mode="json"
        ),
        "bronze-checksum-inventory-v1.json": inventory.model_dump(mode="json"),
        "bronze-restore-rehearsal-v1.json": rehearsal.model_dump(mode="json"),
    }
    for filename, instance in documents.items():
        schema = json.loads(
            (ROOT / "schemas" / filename).read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(  # pyright: ignore[reportUnknownMemberType]
            instance
        )
