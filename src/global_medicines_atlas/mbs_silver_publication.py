"""Deterministic package preparation for authorized MBS Silver v4 objects."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path, PurePosixPath

import pyarrow as pa
import pyarrow.parquet as pq

from .australian_source_contracts import TargetTable
from .mbs_silver import iter_mbs_silver_batches
from .mbs_silver_qualification import (
    MbsSourceEraVerification,
    qualify_mbs_silver,
)
from .receipts import (
    EvidenceClass,
    PublicationDisposition,
    RightsState,
    SourceReceipt,
    require_publication_permitted,
)

DESTINATION_DATASET = "edithatogo/australian-mbs-source-archive"
DESTINATION_PREFIX = "silver/mbs/v4/2025-07-v3"
MBS_SOURCE_URI = (
    "https://huggingface.co/datasets/edithatogo/australian-mbs-source-archive/"
    "resolve/4d1dae488ac43522f20e8320a8b2a56bf9138341/"
    "raw/mbs/2025-07/MBS-XML-20250701-Version-3.XML"
)
MBS_SOURCE_PATH = "raw/mbs/2025-07/MBS-XML-20250701-Version-3.XML"
AUTHORIZATION_PATH = Path(
    "quality/qualifications/australian-health-legacy-publication-authorization.json"
)
DECISION_PATH = Path(
    "conductor/decisions/0009-australian-health-authority-and-public-data-plane.md"
)
_TABLES: tuple[TargetTable, ...] = (
    "services",
    "hierarchy",
    "descriptions",
    "fees",
    "benefits",
    "caps",
)
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")


@dataclass(frozen=True)
class MbsSilverPackageObject:
    """One locally staged object bound by the package manifest."""

    path_in_repo: str
    path: Path
    sha256: str
    byte_count: int
    role: str


@dataclass(frozen=True)
class MbsSilverV4Package:
    """Validated package ready for a hosted append-only transaction."""

    path: Path
    destination_dataset: str
    destination_prefix: str
    manifest_path: Path
    manifest_sha256: str
    objects: tuple[MbsSilverPackageObject, ...]

    @property
    def files(self) -> dict[str, Path]:
        """Return exact Hub paths mapped to staged files."""
        return {
            **{item.path_in_repo: item.path for item in self.objects},
            f"{self.destination_prefix}/manifest.json": self.manifest_path,
        }


def _digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


def _write_object(
    root: Path,
    path_in_repo: str,
    contents: bytes,
    role: str,
) -> MbsSilverPackageObject:
    relative = PurePosixPath(path_in_repo)
    if relative.is_absolute() or ".." in relative.parts or "\\" in path_in_repo:
        raise ValueError("unsafe MBS Silver v4 package path")
    target = root.joinpath(*relative.parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(contents)
    return MbsSilverPackageObject(
        path_in_repo=path_in_repo,
        path=target,
        sha256=_digest(contents),
        byte_count=len(contents),
        role=role,
    )


def _authorization_identity(
    repository_root: Path,
    receipt: SourceReceipt,
) -> tuple[str, str]:
    authorization_path = repository_root / AUTHORIZATION_PATH
    decision_path = repository_root / DECISION_PATH
    authorization_bytes = authorization_path.read_bytes()
    authorization = json.loads(authorization_bytes)
    decision = decision_path.read_text(encoding="utf-8")
    authorized_payloads = [
        item
        for donor in authorization.get("donors", [])
        for item in donor.get("payloads", [])
        if item.get("archive_path") == MBS_SOURCE_PATH
    ]
    authority_checks = (
        authorization.get("external_publication_authorized") is True,
        authorization.get("maintainer_asserted_redistribution_permission")
        is True,
        authorization.get("dataset") == DESTINATION_DATASET,
        authorization.get("visibility") == "public",
        authorization.get("gated") is False,
        len(authorized_payloads) == 1,
        "Status:** accepted" in decision,
        "raw and derived datasets" in decision,
    )
    payload_matches = len(authorized_payloads) == 1 and (
        authorized_payloads[0].get("sha256") == receipt.payload.sha256
        and authorized_payloads[0].get("bytes") == receipt.payload.byte_count
    )
    if not all(authority_checks) or not payload_matches:
        raise ValueError("MBS Silver source/destination authorization differs")
    return _digest(authorization_bytes), _digest(decision.encode("utf-8"))


def build_mbs_silver_v4_package(  # ruff: ignore[too-many-locals]
    payload: bytes,
    receipt: SourceReceipt,
    *,
    exact_commit: str,
    source_era_verification: MbsSourceEraVerification,
    output_dir: Path,
    repository_root: Path | None = None,
) -> MbsSilverV4Package:
    """Stage deterministic Parquet and receipts; never upload or log rows.

    The output contains six typed/native Parquet projections, one exact B1
    source receipt, a value-free candidate qualification, and a manifest that
    binds the source, authorizing decision, producer commit, and all objects.
    """
    if not _COMMIT.fullmatch(exact_commit):
        raise ValueError("exact producer commit must be lowercase Git SHA-1")
    receipt = SourceReceipt.model_validate(receipt.model_dump())
    source_era_verification = MbsSourceEraVerification.model_validate(
        source_era_verification.model_dump()
    )
    if not receipt.payload.matches(payload):
        raise ValueError("MBS Silver payload differs from the B1 receipt")
    if not all((
        receipt.source.source_id == "au-mbs",
        receipt.source.catalog_version == "2025-07-version-3",
        str(receipt.retrieval.uri) == MBS_SOURCE_URI,
        receipt.evidence_class is EvidenceClass.LIVE,
        receipt.rights_state is RightsState.PERMITTED,
        receipt.rights_reference is not None,
        receipt.sensitivity is not None,
        receipt.sensitivity is not None
        and receipt.sensitivity.publication is PublicationDisposition.PERMITTED,
    )):
        raise ValueError("MBS Silver B1 source receipt is not publishable")
    require_publication_permitted(receipt)
    if (
        receipt.transformation.transformation_id
        != "exact-public-source-restore-v1"
        or receipt.transformation.transformation_sha256
        != _digest(exact_commit.encode("ascii"))
    ):
        raise ValueError(
            "MBS Silver receipt is not bound to this producer commit"
        )

    root = repository_root or Path.cwd()
    authorization_sha256, decision_sha256 = _authorization_identity(
        root, receipt
    )
    qualification = qualify_mbs_silver(
        payload,
        receipt,
        date_format="mbs-dmy",
        source_era_verification=source_era_verification,
    )
    if qualification.blockers != ("public_v4_identity_unverified",):
        raise ValueError(
            "MBS Silver source era or conversion quality is blocked"
        )
    if qualification.source_sha256 != receipt.payload.sha256:
        raise ValueError("MBS Silver qualification differs from B2 identity")

    root_path = output_dir / DESTINATION_PREFIX
    root_path.mkdir(parents=True, exist_ok=True)
    objects: list[MbsSilverPackageObject] = []
    for table in _TABLES:
        batches = tuple(
            iter_mbs_silver_batches(
                payload,
                receipt,
                table=table,
                date_format="mbs-dmy",
            )
        )
        if not batches:
            raise ValueError("MBS Silver table is empty")
        output = BytesIO()
        pq.write_table(  # pyright: ignore[reportUnknownMemberType]
            pa.Table.from_batches(batches),
            output,
            compression="zstd",
            version="2.6",
            use_dictionary=False,
            write_statistics=True,
        )
        objects.append(
            _write_object(
                output_dir,
                f"{DESTINATION_PREFIX}/{table}.parquet",
                output.getvalue(),
                "source_faithful_silver_table",
            )
        )

    receipt_object = _write_object(
        output_dir,
        f"{DESTINATION_PREFIX}/source-receipt.json",
        receipt.canonical_json() + b"\n",
        "b1_source_receipt",
    )
    objects.append(receipt_object)
    qualification_object = _write_object(
        output_dir,
        f"{DESTINATION_PREFIX}/qualification.json",
        _json_bytes({
            "schema_id": "global-medicines-atlas.mbs-silver-qualification",
            "schema_version": 1,
            "candidate_only": True,
            "field_count": qualification.field_count,
            "field_occurrence_count": qualification.field_occurrence_count,
            "qualification": qualification.model_dump(mode="json"),
        }),
        "value_free_qualification",
    )
    objects.append(qualification_object)

    object_records = [
        {
            "path": item.path_in_repo,
            "role": item.role,
            "sha256": item.sha256,
            "byte_count": item.byte_count,
        }
        for item in objects
    ]
    manifest = {
        "schema_id": "global-medicines-atlas.mbs-silver-v4-manifest",
        "schema_version": 1,
        "product_version": "4",
        "candidate_only": True,
        "producer_commit": exact_commit,
        "dataset": DESTINATION_DATASET,
        "destination_prefix": DESTINATION_PREFIX,
        "source": {
            "source_id": receipt.source.source_id,
            "source_revision": receipt.source.catalog_version,
            "source_uri": MBS_SOURCE_URI,
            "source_path": MBS_SOURCE_PATH,
            "sha256": receipt.payload.sha256,
            "byte_count": receipt.payload.byte_count,
            "receipt_sha256": receipt.digest(),
        },
        "official_release": source_era_verification.model_dump(mode="json"),
        "authorization_basis": {
            "decision_path": DECISION_PATH.as_posix(),
            "decision_sha256": decision_sha256,
            "source_authorization_path": AUTHORIZATION_PATH.as_posix(),
            "source_authorization_sha256": authorization_sha256,
            "destination": DESTINATION_DATASET,
        },
        "qualification_sha256": qualification.qualification_sha256,
        "objects": object_records,
    }
    manifest_path = output_dir / f"{DESTINATION_PREFIX}/manifest.json"
    manifest_bytes = (
        json.dumps(
            manifest,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        ).encode("utf-8")
        + b"\n"
    )
    manifest_path.write_bytes(manifest_bytes)
    package = MbsSilverV4Package(
        path=root_path,
        destination_dataset=DESTINATION_DATASET,
        destination_prefix=DESTINATION_PREFIX,
        manifest_path=manifest_path,
        manifest_sha256=_digest(manifest_bytes),
        objects=tuple(objects),
    )
    validate_mbs_silver_v4_package(package)
    return package


def validate_mbs_silver_v4_package(package: MbsSilverV4Package) -> None:
    """Recheck manifest identity, exact members, sizes, and digests."""
    if (
        package.destination_dataset != DESTINATION_DATASET
        or package.destination_prefix != DESTINATION_PREFIX
        or package.manifest_path.is_symlink()
        or not package.manifest_path.resolve().is_relative_to(
            package.path.resolve()
        )
    ):
        raise ValueError("MBS Silver v4 package destination differs")
    try:
        manifest_bytes = package.manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("MBS Silver v4 manifest is unreadable") from error
    if (
        _digest(manifest_bytes) != package.manifest_sha256
        or manifest.get("schema_id")
        != "global-medicines-atlas.mbs-silver-v4-manifest"
        or manifest.get("dataset") != DESTINATION_DATASET
        or manifest.get("destination_prefix") != DESTINATION_PREFIX
        or manifest.get("candidate_only") is not True
    ):
        raise ValueError("MBS Silver v4 manifest identity differs")
    expected_paths = {item.path_in_repo: item for item in package.objects}
    if len(expected_paths) != len(package.objects):
        raise ValueError("duplicate MBS Silver v4 package object")
    if {
        json.dumps(
            item, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        for item in manifest.get("objects", [])
    } != {
        json.dumps(
            {
                "path": item.path_in_repo,
                "role": item.role,
                "sha256": item.sha256,
                "byte_count": item.byte_count,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        for item in package.objects
    }:
        raise ValueError("MBS Silver v4 manifest object inventory differs")
    for item in package.objects:
        if (
            item.path.is_symlink()
            or not item.path.resolve().is_relative_to(package.path.resolve())
            or not item.path.is_file()
        ):
            raise ValueError("MBS Silver v4 object path is unsafe or missing")
        contents = item.path.read_bytes()
        if len(contents) != item.byte_count or _digest(contents) != item.sha256:
            raise ValueError("MBS Silver v4 object digest differs")
    actual_files = {
        path.resolve() for path in package.path.rglob("*") if path.is_file()
    }
    expected_files = {
        *(item.path.resolve() for item in package.objects),
        package.manifest_path.resolve(),
    }
    if actual_files != expected_files:
        raise ValueError("MBS Silver v4 package has missing or extra files")
