"""Storage-neutral contracts for immutable Bronze payload truth."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from time import monotonic
from typing import Literal, Protocol, Self
from urllib.parse import unquote, urlparse

import orjson
from pydantic import AwareDatetime, Field, model_validator

from .models import FrozenModel
from .receipts import SHA256_PATTERN

_PAYLOAD_SUFFIXES = frozenset({
    ".bin",
    ".csv",
    ".json",
    ".pdf",
    ".tsv",
    ".xml",
    ".zip",
})


class ImmutabilityMode(StrEnum):
    """Physical controls preventing silent replacement of payload bytes."""

    NONE = "none"
    VERSIONING = "versioning"
    OBJECT_LOCK = "object_lock"
    WORM = "worm"


class DurabilityPolicy(FrozenModel):
    """Fail-closed operating contract for a Bronze payload store."""

    schema_id: Literal["global-medicines-atlas.bronze-storage-policy"] = (
        "global-medicines-atlas.bronze-storage-policy"
    )
    schema_version: Literal[1] = 1
    operation: Literal["local_development", "durable_object_storage"]
    immutability: ImmutabilityMode
    rpo_seconds: int | None = Field(default=None, gt=0)
    rto_seconds: int | None = Field(default=None, gt=0)
    checksum_inventory_interval_hours: int | None = Field(default=None, gt=0)
    restore_rehearsal_interval_days: int | None = Field(default=None, gt=0)
    primary_region: str | None = None
    primary_administrative_domain: str | None = None
    replica_region: str | None = None
    replica_administrative_domain: str | None = None

    @classmethod
    def local_development(cls) -> Self:
        """Return the explicitly non-production local policy."""

        return cls(
            operation="local_development",
            immutability=ImmutabilityMode.NONE,
        )

    @model_validator(mode="after")
    def validate_durable_operation(self) -> DurabilityPolicy:
        if self.operation == "local_development":
            return self
        if self.immutability is ImmutabilityMode.NONE:
            raise ValueError(
                "durable storage requires versioning or Object Lock/WORM"
            )
        if self.rpo_seconds is None:
            raise ValueError("durable storage requires an explicit RPO")
        if self.rto_seconds is None:
            raise ValueError("durable storage requires an explicit RTO")
        if self.checksum_inventory_interval_hours is None:
            raise ValueError(
                "durable storage requires checksum inventory cadence"
            )
        if self.restore_rehearsal_interval_days is None:
            raise ValueError(
                "durable storage requires restore rehearsal cadence"
            )
        required = (
            self.primary_region,
            self.primary_administrative_domain,
            self.replica_region,
            self.replica_administrative_domain,
        )
        if any(value is None or not value.strip() for value in required):
            raise ValueError(
                "durable storage requires primary and replica identities"
            )
        if self.primary_region == self.replica_region:
            raise ValueError("replication must be geographically independent")
        if (
            self.primary_administrative_domain
            == self.replica_administrative_domain
        ):
            raise ValueError("replication must be administratively independent")
        return self


class ObjectStorageTarget(FrozenModel):
    """A named object-storage failure domain."""

    bucket: str = Field(min_length=1)
    prefix: str = ""
    region: str = Field(min_length=1)
    administrative_domain: str = Field(min_length=1)
    uri_scheme: str = Field(default="s3", pattern=r"^[a-z][a-z0-9+.-]*$")


class ObjectWriteResult(FrozenModel):
    """Provider result retained without credentials or request metadata."""

    version_id: str | None = None
    etag: str | None = None
    object_lock_mode: str | None = None


class StoredObjectEvidence(FrozenModel):
    """Immutable identity of one physical payload copy."""

    uri: str = Field(min_length=1)
    bucket: str | None = None
    key: str = Field(min_length=1)
    region: str = Field(min_length=1)
    administrative_domain: str = Field(min_length=1)
    version_id: str | None = None
    etag: str | None = None
    object_lock_mode: str | None = None
    sha256: str = Field(pattern=SHA256_PATTERN)
    byte_count: int = Field(ge=0)


class PayloadStorageReceipt(FrozenModel):
    """Append-only evidence binding logical content to physical copies."""

    schema_id: Literal["global-medicines-atlas.bronze-payload-storage"] = (
        "global-medicines-atlas.bronze-payload-storage"
    )
    schema_version: Literal[1] = 1
    acquisition_id: str = Field(pattern=SHA256_PATTERN)
    content_id: str = Field(pattern=SHA256_PATTERN)
    payload_sha256: str = Field(pattern=SHA256_PATTERN)
    payload_byte_count: int = Field(ge=0)
    policy: DurabilityPolicy
    primary: StoredObjectEvidence
    replicas: tuple[StoredObjectEvidence, ...] = ()

    @model_validator(mode="after")
    def validate_copies(self) -> PayloadStorageReceipt:
        if self.content_id != self.payload_sha256:
            raise ValueError("content_id must equal the payload checksum")
        copies = (self.primary, *self.replicas)
        if any(
            item.sha256 != self.payload_sha256
            or item.byte_count != self.payload_byte_count
            for item in copies
        ):
            raise ValueError("stored-copy identity diverges from payload")
        if self.policy.operation == "durable_object_storage":
            if not self.replicas:
                raise ValueError("durable storage requires a replica receipt")
            if (
                self.primary.region != self.policy.primary_region
                or self.primary.administrative_domain
                != self.policy.primary_administrative_domain
            ):
                raise ValueError(
                    "primary receipt does not match durability policy"
                )
            if not any(
                item.region == self.policy.replica_region
                and item.administrative_domain
                == self.policy.replica_administrative_domain
                for item in self.replicas
            ):
                raise ValueError(
                    "independent replica receipt does not match durability policy"
                )
            if any(item.version_id is None for item in copies):
                raise ValueError(
                    "durable storage requires object version identities"
                )
            if self.policy.immutability in {
                ImmutabilityMode.OBJECT_LOCK,
                ImmutabilityMode.WORM,
            } and any(item.object_lock_mode is None for item in copies):
                raise ValueError(
                    "Object Lock/WORM policy requires lock evidence"
                )
        return self

    def canonical_json(self) -> bytes:
        return orjson.dumps(
            self.model_dump(mode="json"), option=orjson.OPT_SORT_KEYS
        )


@dataclass(frozen=True, slots=True)
class StoredPayload:
    """Storage receipt plus a local materialization for safe inspection."""

    materialized_path: Path
    receipt: PayloadStorageReceipt


class ObjectStorageClient(Protocol):
    """Minimal provider boundary implemented by S3-compatible clients."""

    def put_object_if_absent(
        self,
        *,
        bucket: str,
        key: str,
        payload: bytes,
        checksum_sha256: str,
        object_lock_required: bool,
    ) -> ObjectWriteResult: ...

    def get_object(
        self, *, bucket: str, key: str, version_id: str
    ) -> bytes: ...


class PayloadStore(Protocol):
    """Storage-neutral payload persistence and verification boundary."""

    policy: DurabilityPolicy

    def store(
        self,
        payload: bytes,
        *,
        acquisition_id: str,
        content_id: str,
        suffix: str,
    ) -> StoredPayload: ...

    def read_object(self, reference: StoredObjectEvidence) -> bytes: ...


def _write_immutable(path: Path, payload: bytes) -> None:
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError("content store immutable payload conflict")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _require_payload_suffix(suffix: str) -> None:
    if suffix not in _PAYLOAD_SUFFIXES:
        raise ValueError("payload suffix is not allowlisted")


class LocalFilesystemPayloadStore:
    """Content-addressed local store for development and tests."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.policy = DurabilityPolicy.local_development()

    def store(
        self,
        payload: bytes,
        *,
        acquisition_id: str,
        content_id: str,
        suffix: str,
    ) -> StoredPayload:
        _require_payload_suffix(suffix)
        digest = sha256(payload).hexdigest()
        if digest != content_id:
            raise ValueError("content_id does not match payload checksum")
        path = (
            self.root
            / "payloads"
            / "by_content"
            / content_id
            / f"payload{suffix}"
        )
        _write_immutable(path, payload)
        evidence = StoredObjectEvidence(
            uri=path.as_uri(),
            key=str(path.relative_to(self.root)),
            region="local",
            administrative_domain="development-workstation",
            sha256=digest,
            byte_count=len(payload),
        )
        return StoredPayload(
            materialized_path=path,
            receipt=PayloadStorageReceipt(
                acquisition_id=acquisition_id,
                content_id=content_id,
                payload_sha256=digest,
                payload_byte_count=len(payload),
                policy=self.policy,
                primary=evidence,
            ),
        )

    def read_object(self, reference: StoredObjectEvidence) -> bytes:
        parsed = urlparse(reference.uri)
        if parsed.scheme != "file":
            raise ValueError("local store can read only file URIs")
        return Path(unquote(parsed.path)).read_bytes()


TargetClient = tuple[ObjectStorageTarget, ObjectStorageClient]


class ObjectStoragePayloadStore:
    """Versioned, replicated object store with a disposable local stage."""

    def __init__(
        self,
        *,
        staging_root: Path,
        policy: DurabilityPolicy,
        primary: TargetClient,
        replicas: tuple[TargetClient, ...],
    ) -> None:
        if policy.operation != "durable_object_storage":
            raise ValueError("object storage requires a durable policy")
        self.staging_root = staging_root
        self.policy = policy
        self.primary = primary
        self.replicas = replicas
        targets = (primary[0], *(item[0] for item in replicas))
        if (
            targets[0].region != policy.primary_region
            or targets[0].administrative_domain
            != policy.primary_administrative_domain
        ):
            raise ValueError("primary target does not match durability policy")
        if not any(
            target.region == policy.replica_region
            and target.administrative_domain
            == policy.replica_administrative_domain
            for target in targets[1:]
        ):
            raise ValueError(
                "independent replica target does not match durability policy"
            )
        if any(target.bucket == targets[0].bucket for target in targets[1:]):
            raise ValueError(
                "independent replication requires a distinct bucket"
            )

    @staticmethod
    def _key(target: ObjectStorageTarget, content_id: str, suffix: str) -> str:
        leaf = f"payloads/by_content/{content_id}/payload{suffix}"
        return f"{target.prefix.strip('/')}/{leaf}" if target.prefix else leaf

    def _write_copy(
        self,
        target_client: TargetClient,
        payload: bytes,
        content_id: str,
        suffix: str,
    ) -> StoredObjectEvidence:
        target, client = target_client
        key = self._key(target, content_id, suffix)
        result = client.put_object_if_absent(
            bucket=target.bucket,
            key=key,
            payload=payload,
            checksum_sha256=content_id,
            object_lock_required=self.policy.immutability
            in {
                ImmutabilityMode.OBJECT_LOCK,
                ImmutabilityMode.WORM,
            },
        )
        if result.version_id is None:
            raise ValueError(
                "durable object write did not return a version identity"
            )
        observed = client.get_object(
            bucket=target.bucket,
            key=key,
            version_id=result.version_id,
        )
        if sha256(observed).hexdigest() != content_id or len(observed) != len(
            payload
        ):
            raise ValueError(
                "durable object checksum verification failed after write"
            )
        return StoredObjectEvidence(
            uri=f"{target.uri_scheme}://{target.bucket}/{key}",
            bucket=target.bucket,
            key=key,
            region=target.region,
            administrative_domain=target.administrative_domain,
            version_id=result.version_id,
            etag=result.etag,
            object_lock_mode=result.object_lock_mode,
            sha256=content_id,
            byte_count=len(payload),
        )

    def store(
        self,
        payload: bytes,
        *,
        acquisition_id: str,
        content_id: str,
        suffix: str,
    ) -> StoredPayload:
        _require_payload_suffix(suffix)
        if sha256(payload).hexdigest() != content_id:
            raise ValueError("content_id does not match payload checksum")
        primary = self._write_copy(self.primary, payload, content_id, suffix)
        replicas = tuple(
            self._write_copy(item, payload, content_id, suffix)
            for item in self.replicas
        )
        materialized = (
            self.staging_root
            / "payloads"
            / "by_content"
            / content_id
            / f"payload{suffix}"
        )
        _write_immutable(materialized, payload)
        return StoredPayload(
            materialized_path=materialized,
            receipt=PayloadStorageReceipt(
                acquisition_id=acquisition_id,
                content_id=content_id,
                payload_sha256=content_id,
                payload_byte_count=len(payload),
                policy=self.policy,
                primary=primary,
                replicas=replicas,
            ),
        )

    def read_object(self, reference: StoredObjectEvidence) -> bytes:
        if reference.bucket is None or reference.version_id is None:
            raise ValueError(
                "object reference lacks bucket or version identity"
            )
        for target, client in (self.primary, *self.replicas):
            if target.bucket == reference.bucket:
                return client.get_object(
                    bucket=reference.bucket,
                    key=reference.key,
                    version_id=reference.version_id,
                )
        raise ValueError("object reference is outside this storage topology")


class ChecksumInventory(FrozenModel):
    """Compact verification result for every authoritative physical copy."""

    schema_version: Literal[1] = 1
    generated_at: AwareDatetime
    checked_payloads: int = Field(ge=0)
    checked_objects: int = Field(ge=0)
    inventory_sha256: str = Field(pattern=SHA256_PATTERN)


class RestoreRehearsalReceipt(FrozenModel):
    """Evidence that payload bytes were read, restored, and re-hashed."""

    schema_version: Literal[1] = 1
    completed_at: AwareDatetime
    source_role: Literal["primary", "replica"]
    restored_payloads: int = Field(ge=0)
    elapsed_seconds: float = Field(ge=0)
    rto_seconds: int
    within_rto: bool
    restored_inventory_sha256: str = Field(pattern=SHA256_PATTERN)


def create_checksum_inventory(
    store: PayloadStore,
    receipts: tuple[PayloadStorageReceipt, ...],
    *,
    generated_at: datetime | None = None,
) -> ChecksumInventory:
    """Read and verify all primary and replica copies."""

    rows: list[dict[str, object]] = []
    for receipt in receipts:
        for reference in (receipt.primary, *receipt.replicas):
            payload = store.read_object(reference)
            digest = sha256(payload).hexdigest()
            if (
                digest != reference.sha256
                or len(payload) != reference.byte_count
            ):
                raise ValueError(
                    f"checksum inventory failed for {reference.uri}"
                )
            rows.append({
                "uri": reference.uri,
                "version_id": reference.version_id,
                "sha256": digest,
                "byte_count": len(payload),
            })
    encoded = orjson.dumps(
        sorted(rows, key=lambda row: str(row["uri"])),
        option=orjson.OPT_SORT_KEYS,
    )
    return ChecksumInventory(
        generated_at=generated_at or datetime.now(UTC),
        checked_payloads=len(receipts),
        checked_objects=len(rows),
        inventory_sha256=sha256(encoded).hexdigest(),
    )


def rehearse_restore(
    store: PayloadStore,
    receipts: tuple[PayloadStorageReceipt, ...],
    *,
    restore_root: Path,
    completed_at: datetime | None = None,
) -> RestoreRehearsalReceipt:
    """Restore authoritative objects to an empty target and verify exact bytes."""

    rto = store.policy.rto_seconds
    if rto is None:
        raise ValueError("restore rehearsal requires an explicit RTO")
    started = monotonic()
    rows: list[dict[str, object]] = []
    source_role: Literal["primary", "replica"] = "primary"
    for receipt in receipts:
        reference = receipt.primary
        if store.policy.operation == "durable_object_storage":
            reference = next(
                (
                    item
                    for item in receipt.replicas
                    if item.region == store.policy.replica_region
                    and item.administrative_domain
                    == store.policy.replica_administrative_domain
                ),
                None,
            )
            if reference is None:
                raise ValueError(
                    "restore rehearsal requires the independent replica"
                )
            source_role = "replica"
        payload = store.read_object(reference)
        digest = sha256(payload).hexdigest()
        if digest != receipt.payload_sha256:
            raise ValueError("restored payload checksum mismatch")
        suffix = Path(receipt.primary.key).suffix or ".bin"
        destination = restore_root / f"{receipt.content_id}{suffix}"
        _write_immutable(destination, payload)
        rows.append({"content_id": receipt.content_id, "sha256": digest})
    elapsed = monotonic() - started
    encoded = orjson.dumps(rows, option=orjson.OPT_SORT_KEYS)
    return RestoreRehearsalReceipt(
        completed_at=completed_at or datetime.now(UTC),
        source_role=source_role,
        restored_payloads=len(rows),
        elapsed_seconds=elapsed,
        rto_seconds=rto,
        within_rto=elapsed <= rto,
        restored_inventory_sha256=sha256(encoded).hexdigest(),
    )


def write_payload_storage_receipt(
    receipt: PayloadStorageReceipt,
    *,
    bronze_root: Path,
    source_id: str,
) -> Path:
    """Persist a storage receipt without permitting history replacement."""

    path = (
        bronze_root / "storage" / source_id / f"{receipt.acquisition_id}.json"
    )
    _write_immutable(path, receipt.canonical_json() + b"\n")
    return path
