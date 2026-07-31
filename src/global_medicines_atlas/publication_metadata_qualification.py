"""Fail-closed qualification of stable-v1 publication metadata."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, Literal, Self, cast
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from .publication_contracts import (
    CroissantMetadata,
    DatasetCard,
    PublicationIdentity,
    PublicationIdentityRegistry,
    PublicationPackage,
    PublicationState,
    PublicationSystem,
    PublicationVerificationReceipt,
)
from .publication_package import (
    GeneratedPublicationPackage,
    generate_publication_package,
)

NonBlank = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=2048),
]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]

_SCHEMA_ID = "global-medicines-atlas.stable-v1-publication-metadata"
_RESULT = "metadata_qualified_external_gates_blocked"
_RECEIPT_PATH = "quality/qualifications/stable-v1-publication-metadata.json"
_INPUT_PATHS = (
    "quality/qualifications/publication-identities.json",
    "release-inputs/publication-contract.json",
    "release-inputs/publication-qualification.json",
    "release-inputs/reviewed-rows.jsonl",
)
_IMPLEMENTATION_PATHS = (
    "schemas/publication-identity-registry-v1.json",
    "schemas/stable-v1-publication-metadata-qualification-v1.json",
    "scripts/qualify_stable_v1_publication_metadata.py",
    "src/global_medicines_atlas/publication_contracts.py",
    "src/global_medicines_atlas/publication_metadata_qualification.py",
    "src/global_medicines_atlas/publication_package.py",
    "uv.lock",
)
_GATE_ORDER = (
    "dataset-card",
    "croissant",
    "checksums",
    "identifier-links",
    "restricted-data-boundary",
    "external-identifiers",
    "licences",
    "publication",
)
_CHECKSUM_LINE = re.compile(r"^(?P<digest>[0-9a-f]{64})  (?P<path>[^\r\n]+)$")
_HOSTS_BY_SYSTEM: Mapping[PublicationSystem, frozenset[str]] = {
    PublicationSystem.GITHUB: frozenset({"github.com"}),
    PublicationSystem.HUGGING_FACE: frozenset({"huggingface.co"}),
    PublicationSystem.ZENODO: frozenset({"doi.org", "zenodo.org"}),
    PublicationSystem.OSF: frozenset({"osf.io"}),
}


class PublicationMetadataQualificationError(ValueError):
    """A release-candidate metadata claim could not be evidenced."""


class QualificationModel(BaseModel):
    """Immutable receipt model that rejects undocumented fields."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_default=True,
    )


class GateState(StrEnum):
    PASSED = "passed"
    BLOCKED = "blocked"


class ContentBinding(QualificationModel):
    path: NonBlank
    sha256: Sha256
    size: int = Field(ge=0)


class GateEvidence(QualificationModel):
    gate_id: NonBlank
    state: GateState
    evidence: tuple[NonBlank, ...] = Field(min_length=1)
    blockers: tuple[NonBlank, ...] = ()

    @model_validator(mode="after")
    def state_matches_blockers(self) -> Self:
        if self.state is GateState.PASSED and self.blockers:
            raise ValueError("passed metadata gate cannot contain blockers")
        if self.state is GateState.BLOCKED and not self.blockers:
            raise ValueError("blocked metadata gate requires blockers")
        if self.blockers != tuple(sorted(set(self.blockers))):
            raise ValueError("metadata gate blockers must be sorted and unique")
        return self


class IdentityEvidence(QualificationModel):
    object_id: NonBlank
    system: NonBlank
    object_role: NonBlank
    identifier: NonBlank | None
    identifier_state: NonBlank
    identifier_evidence: NonBlank | None
    licence_state: NonBlank
    licence_expression: NonBlank | None
    licence_decision_evidence: NonBlank | None
    related_object_ids: tuple[NonBlank, ...]


class PackageMetadataEvidence(QualificationModel):
    fixture_only: Literal[True]
    restricted_data_included: Literal[False]
    contract_version: NonBlank
    dataset_title: NonBlank
    dataset_version: NonBlank
    contract_sha256: Sha256
    generated_package_sha256: Sha256
    dataset_card_sha256: Sha256
    croissant_sha256: Sha256
    checksums_sha256: Sha256
    manifest_sha256: Sha256
    files: tuple[ContentBinding, ...] = Field(min_length=1)


class ExternalActions(QualificationModel):
    credentials_used: Literal[False] = False
    publication_performed: Literal[False] = False
    release_created: Literal[False] = False
    remote_write_attempted: Literal[False] = False
    signature_created: Literal[False] = False


class PublicationMetadataQualificationReceipt(QualificationModel):
    schema_id: Literal[
        "global-medicines-atlas.stable-v1-publication-metadata"
    ] = _SCHEMA_ID
    schema_version: Literal[1] = 1
    qualification_id: Literal[
        "stable-v1-release-candidate-publication-metadata"
    ] = "stable-v1-release-candidate-publication-metadata"
    result: Literal["metadata_qualified_external_gates_blocked"] = _RESULT
    ready_for_publication: Literal[False] = False
    external_actions: ExternalActions = Field(default_factory=ExternalActions)
    inputs: tuple[ContentBinding, ...] = Field(min_length=1)
    implementation_inputs: tuple[ContentBinding, ...] = Field(min_length=1)
    package: PackageMetadataEvidence
    identities: tuple[IdentityEvidence, ...] = Field(min_length=4, max_length=4)
    gates: tuple[GateEvidence, ...] = Field(min_length=8, max_length=8)
    blockers: tuple[NonBlank, ...] = Field(min_length=1)
    receipt_sha256: Sha256

    @model_validator(mode="after")
    def receipt_is_fail_closed_and_canonical(self) -> Self:
        if tuple(item.gate_id for item in self.gates) != _GATE_ORDER:
            raise ValueError(
                "publication metadata gates are incomplete or unordered"
            )
        expected_states = (
            *(GateState.PASSED for _ in range(5)),
            *(GateState.BLOCKED for _ in range(3)),
        )
        if tuple(item.state for item in self.gates) != expected_states:
            raise ValueError(
                "publication metadata gate states are not fail-closed"
            )
        gate_blockers = tuple(
            sorted({
                blocker for gate in self.gates for blocker in gate.blockers
            })
        )
        if self.blockers != gate_blockers:
            raise ValueError(
                "receipt blockers must equal the gate blocker union"
            )
        for bindings in (
            self.inputs,
            self.implementation_inputs,
            self.package.files,
        ):
            paths = tuple(item.path for item in bindings)
            if paths != tuple(sorted(paths)) or len(paths) != len(set(paths)):
                raise ValueError(
                    "content bindings must have sorted unique paths"
                )
        return self


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _receipt_digest(receipt: PublicationMetadataQualificationReceipt) -> str:
    payload = receipt.model_dump(mode="json", exclude={"receipt_sha256"})
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def canonical_receipt_bytes(
    receipt: PublicationMetadataQualificationReceipt,
) -> bytes:
    """Serialize a receipt only when its self-identity is valid."""

    if receipt.receipt_sha256 != _receipt_digest(receipt):
        raise PublicationMetadataQualificationError(
            "publication metadata receipt self-hash is invalid"
        )
    return _canonical_json(receipt.model_dump(mode="json"))


def _contained_file(root: Path, relative: str) -> Path:
    posix = PurePosixPath(relative)
    if posix.is_absolute() or ".." in posix.parts or "\\" in relative:
        raise PublicationMetadataQualificationError(
            f"unsafe qualification input path: {relative}"
        )
    try:
        resolved_root = root.resolve(strict=True)
        resolved = resolved_root.joinpath(*posix.parts).resolve(strict=True)
        resolved.relative_to(resolved_root)
    except (OSError, ValueError) as error:
        raise PublicationMetadataQualificationError(
            f"qualification input is absent or escapes root: {relative}"
        ) from error
    if not resolved.is_file():
        raise PublicationMetadataQualificationError(
            f"qualification input is not a regular file: {relative}"
        )
    return resolved


def _binding(root: Path, relative: str) -> ContentBinding:
    path = _contained_file(root, relative)
    content = path.read_bytes()
    return ContentBinding(
        path=relative,
        sha256=hashlib.sha256(content).hexdigest(),
        size=len(content),
    )


def _load_rows(path: Path) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    for number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        try:
            value: object = json.loads(line)
        except json.JSONDecodeError as error:
            raise PublicationMetadataQualificationError(
                f"reviewed fixture row {number} is invalid JSON"
            ) from error
        if not isinstance(value, dict):
            raise PublicationMetadataQualificationError(
                f"reviewed fixture row {number} must be an object"
            )
        rows.append(cast("Mapping[str, Any]", value))
    if not rows:
        raise PublicationMetadataQualificationError(
            "reviewed fixture rows must not be empty"
        )
    return tuple(rows)


def _assert_fixture_boundary(
    contract: PublicationPackage,
    qualification: PublicationVerificationReceipt,
    rows: tuple[Mapping[str, Any], ...],
) -> None:
    if not contract.contract_version.startswith("fixture-dry-run-"):
        raise PublicationMetadataQualificationError(
            "publication metadata qualification requires fixture-only inputs"
        )
    if qualification.state is not PublicationState.QUALIFIED:
        raise PublicationMetadataQualificationError(
            "fixture package requires a qualified local receipt"
        )
    if (
        qualification.public_uri is not None
        or "no-maintainer-approval" not in qualification.verifier
    ):
        raise PublicationMetadataQualificationError(
            "fixture qualification must deny public and maintainer approval claims"
        )
    evidence_hosts = {item.evidence_uri.host for item in qualification.evidence}
    if not evidence_hosts or any(
        host is None or not host.endswith(".invalid") for host in evidence_hosts
    ):
        raise PublicationMetadataQualificationError(
            "fixture qualification evidence must use reserved .invalid hosts"
        )
    source_ids = {item.source_id for item in contract.dataset_card.provenance}
    source_hosts = {
        urlsplit(item.source_uri).hostname
        for item in contract.dataset_card.provenance
    }
    jurisdictions = {
        jurisdiction
        for coverage in contract.dataset_card.coverage
        for jurisdiction in coverage.jurisdictions
    }
    row_sources = {row.get("source_id") for row in rows}
    if (
        source_ids != {"synthetic-fixture"}
        or source_hosts != {"fixtures.invalid"}
        or jurisdictions != {"ZZ-FIXTURE"}
        or row_sources != {"synthetic-fixture"}
    ):
        raise PublicationMetadataQualificationError(
            "restricted or non-fixture data crossed the qualification boundary"
        )
    limitations = " ".join(contract.dataset_card.limitations).casefold()
    if (
        "fixture" not in limitations
        or "not for production or public release" not in limitations
    ):
        raise PublicationMetadataQualificationError(
            "dataset card must explicitly deny production and public release use"
        )


def _member(package: GeneratedPublicationPackage, path: str) -> bytes:
    try:
        return package.file(path).content
    except KeyError as error:
        raise PublicationMetadataQualificationError(
            f"generated package is missing required metadata: {path}"
        ) from error


def _load_object(content: bytes, label: str) -> dict[str, Any]:
    try:
        value: object = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PublicationMetadataQualificationError(
            f"{label} is not valid UTF-8 JSON"
        ) from error
    if not isinstance(value, dict):
        raise PublicationMetadataQualificationError(
            f"{label} must be a JSON object"
        )
    return cast("dict[str, Any]", value)


def _verify_dataset_card(
    package: GeneratedPublicationPackage, contract: PublicationPackage
) -> DatasetCard:
    payload = _load_object(
        _member(package, "metadata/dataset-card.json"), "dataset card"
    )
    card = DatasetCard.model_validate(payload)
    if card != contract.dataset_card:
        raise PublicationMetadataQualificationError(
            "generated dataset card does not match the reviewed contract"
        )
    return card


def _verify_croissant(
    package: GeneratedPublicationPackage,
    contract: PublicationPackage,
    card: DatasetCard,
) -> CroissantMetadata:
    payload = _load_object(
        _member(package, "metadata/croissant.json"), "Croissant record"
    )
    croissant = CroissantMetadata.model_validate(payload)
    if croissant.name != card.title or croissant.version != card.version:
        raise PublicationMetadataQualificationError(
            "Croissant record does not match the dataset card"
        )
    if croissant.description != contract.croissant.description:
        raise PublicationMetadataQualificationError(
            "Croissant description does not match the reviewed contract"
        )
    parquet = package.file("data/medicines.parquet")
    distributions = tuple(
        item for item in croissant.distributions if item.name == parquet.path
    )
    if len(distributions) != 1:
        raise PublicationMetadataQualificationError(
            "Croissant must contain exactly one canonical Parquet distribution"
        )
    distribution = distributions[0]
    if (
        distribution.content_url != parquet.path
        or distribution.encoding_format != "application/vnd.apache.parquet"
        or distribution.sha256 != parquet.sha256
    ):
        raise PublicationMetadataQualificationError(
            "Croissant distribution is not bound to canonical Parquet bytes"
        )
    return croissant


def _verify_checksums(package: GeneratedPublicationPackage) -> None:
    content = _member(package, "SHA256SUMS")
    try:
        lines = content.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise PublicationMetadataQualificationError(
            "SHA256SUMS is not valid UTF-8"
        ) from error
    parsed: list[tuple[str, str]] = []
    for line in lines:
        match = _CHECKSUM_LINE.fullmatch(line)
        if match is None:
            raise PublicationMetadataQualificationError(
                "SHA256SUMS contains a malformed entry"
            )
        parsed.append((match.group("path"), match.group("digest")))
    if parsed != sorted(parsed) or len(parsed) != len({
        path for path, _ in parsed
    }):
        raise PublicationMetadataQualificationError(
            "SHA256SUMS entries must have sorted unique paths"
        )
    expected = {
        item.path: item.sha256
        for item in package.files
        if item.path not in {"SHA256SUMS", "package-manifest.json"}
    }
    if dict(parsed) != expected:
        raise PublicationMetadataQualificationError(
            "SHA256SUMS does not bind every exact package payload"
        )


def _verify_manifest(
    package: GeneratedPublicationPackage,
    contract: PublicationPackage,
    qualification: PublicationVerificationReceipt,
) -> None:
    manifest = _load_object(
        _member(package, "package-manifest.json"), "package manifest"
    )
    expected_files = [
        {"path": item.path, "sha256": item.sha256, "size": item.size}
        for item in package.files
        if item.path != "package-manifest.json"
    ]
    if manifest != {
        "contract_sha256": contract.sha256(),
        "files": expected_files,
        "format_version": "1",
        "staged_sha256": qualification.package_sha256,
    }:
        raise PublicationMetadataQualificationError(
            "package manifest does not bind the exact candidate metadata"
        )


def _normalized_identifier(identity: PublicationIdentity) -> str | None:
    if identity.identifier is None:
        return None
    parsed = urlsplit(identity.identifier)
    host = parsed.hostname.casefold() if parsed.hostname else None
    if (
        parsed.scheme.casefold() != "https"
        or host not in _HOSTS_BY_SYSTEM[identity.system]
    ):
        raise PublicationMetadataQualificationError(
            f"{identity.object_id} identifier host or URL shape is invalid"
        )
    if parsed.username is not None or parsed.password is not None:
        raise PublicationMetadataQualificationError(
            f"{identity.object_id} identifier host or URL shape is invalid"
        )
    if parsed.query or parsed.fragment or not parsed.path.strip("/"):
        raise PublicationMetadataQualificationError(
            f"{identity.object_id} identifier host or URL shape is invalid"
        )
    return f"https://{host}{parsed.path.rstrip('/')}".casefold()


def _identity_evidence(
    registry: PublicationIdentityRegistry,
) -> tuple[IdentityEvidence, ...]:
    by_id = {item.object_id: item for item in registry.identities}
    normalized = tuple(
        value
        for item in registry.identities
        if (value := _normalized_identifier(item)) is not None
    )
    if len(normalized) != len(set(normalized)):
        raise PublicationMetadataQualificationError(
            "publication identifiers overlap after normalization"
        )
    for item in registry.identities:
        for related in item.related_object_ids:
            if item.object_id not in by_id[related].related_object_ids:
                raise PublicationMetadataQualificationError(
                    "publication identity links must be reciprocal"
                )
    order = {system: index for index, system in enumerate(PublicationSystem)}
    return tuple(
        IdentityEvidence(
            object_id=item.object_id,
            system=item.system.value,
            object_role=item.object_role.value,
            identifier=item.identifier,
            identifier_state=item.identifier_state.value,
            identifier_evidence=item.identifier_evidence,
            licence_state=item.licence_state.value,
            licence_expression=item.licence_expression,
            licence_decision_evidence=item.licence_decision_evidence,
            related_object_ids=tuple(sorted(item.related_object_ids)),
        )
        for item in sorted(
            registry.identities, key=lambda value: order[value.system]
        )
    )


def _gate(
    gate_id: str,
    state: GateState,
    evidence: tuple[str, ...],
    blockers: tuple[str, ...] = (),
) -> GateEvidence:
    return GateEvidence(
        gate_id=gate_id,
        state=state,
        evidence=evidence,
        blockers=tuple(sorted(set(blockers))),
    )


def _load_qualification_inputs(
    root: Path,
) -> tuple[
    PublicationPackage,
    PublicationVerificationReceipt,
    PublicationIdentityRegistry,
    tuple[Mapping[str, Any], ...],
]:
    contract = PublicationPackage.model_validate_json(
        _contained_file(root, _INPUT_PATHS[1]).read_text(encoding="utf-8")
    )
    qualification = PublicationVerificationReceipt.model_validate_json(
        _contained_file(root, _INPUT_PATHS[2]).read_text(encoding="utf-8")
    )
    registry = PublicationIdentityRegistry.model_validate_json(
        _contained_file(root, _INPUT_PATHS[0]).read_text(encoding="utf-8")
    )
    rows = _load_rows(_contained_file(root, _INPUT_PATHS[3]))
    return contract, qualification, registry, rows


def _build_gates(
    identities: tuple[IdentityEvidence, ...],
) -> tuple[GateEvidence, ...]:
    identifier_blockers = tuple(
        f"{item.object_id}:identifier-{item.identifier_state}"
        for item in identities
        if item.identifier_state != "verified"
    )
    licence_blockers = tuple(
        f"{item.object_id}:licence-{item.licence_state}"
        for item in identities
        if item.licence_state != "approved"
    )
    publication_blockers = (
        "maintainer-release-approval:missing",
        "production-package:not-qualified",
        "publication:not-performed",
        "release:not-created",
        "signature:not-created",
    )
    return (
        _gate(
            "dataset-card", GateState.PASSED, ("metadata/dataset-card.json",)
        ),
        _gate("croissant", GateState.PASSED, ("metadata/croissant.json",)),
        _gate(
            "checksums",
            GateState.PASSED,
            ("SHA256SUMS", "package-manifest.json"),
        ),
        _gate(
            "identifier-links",
            GateState.PASSED,
            ("quality/qualifications/publication-identities.json",),
        ),
        _gate(
            "restricted-data-boundary",
            GateState.PASSED,
            (
                "release-inputs/publication-contract.json",
                "release-inputs/reviewed-rows.jsonl",
            ),
        ),
        _gate(
            "external-identifiers",
            GateState.BLOCKED,
            ("quality/qualifications/publication-identities.json",),
            identifier_blockers,
        ),
        _gate(
            "licences",
            GateState.BLOCKED,
            ("quality/qualifications/publication-identities.json",),
            licence_blockers,
        ),
        _gate(
            "publication",
            GateState.BLOCKED,
            ("release-inputs/v0.7-fixture-production-qualification.json",),
            publication_blockers,
        ),
    )


def _package_evidence(
    package: GeneratedPublicationPackage,
    contract: PublicationPackage,
    card: DatasetCard,
) -> PackageMetadataEvidence:
    return PackageMetadataEvidence(
        fixture_only=True,
        restricted_data_included=False,
        contract_version=contract.contract_version,
        dataset_title=card.title,
        dataset_version=card.version,
        contract_sha256=contract.sha256(),
        generated_package_sha256=package.sha256,
        dataset_card_sha256=package.file("metadata/dataset-card.json").sha256,
        croissant_sha256=package.file("metadata/croissant.json").sha256,
        checksums_sha256=package.file("SHA256SUMS").sha256,
        manifest_sha256=package.file("package-manifest.json").sha256,
        files=tuple(
            ContentBinding(path=item.path, sha256=item.sha256, size=item.size)
            for item in package.files
        ),
    )


def qualify_publication_metadata(
    root: Path,
) -> PublicationMetadataQualificationReceipt:
    """Qualify local metadata while preserving every external gate."""

    root = root.resolve(strict=True)
    contract, qualification, registry, rows = _load_qualification_inputs(root)
    _assert_fixture_boundary(contract, qualification, rows)
    package = generate_publication_package(contract, qualification, rows)
    card = _verify_dataset_card(package, contract)
    _verify_croissant(package, contract, card)
    _verify_checksums(package)
    _verify_manifest(package, contract, qualification)
    identities = _identity_evidence(registry)
    gates = _build_gates(identities)
    preliminary = PublicationMetadataQualificationReceipt(
        inputs=tuple(_binding(root, path) for path in _INPUT_PATHS),
        implementation_inputs=tuple(
            _binding(root, path) for path in _IMPLEMENTATION_PATHS
        ),
        package=_package_evidence(package, contract, card),
        identities=identities,
        gates=gates,
        blockers=tuple(
            sorted({blocker for gate in gates for blocker in gate.blockers})
        ),
        receipt_sha256="0" * 64,
    )
    return preliminary.model_copy(
        update={"receipt_sha256": _receipt_digest(preliminary)}
    )


def verify_publication_metadata_receipt(
    root: Path,
    receipt_path: Path | None = None,
) -> PublicationMetadataQualificationReceipt:
    """Recompute every input and reject any stale or altered receipt."""

    path = receipt_path or _contained_file(root, _RECEIPT_PATH)
    observed = PublicationMetadataQualificationReceipt.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    canonical_receipt_bytes(observed)
    expected = qualify_publication_metadata(root)
    if observed != expected:
        raise PublicationMetadataQualificationError(
            "publication metadata receipt does not match current inputs"
        )
    return observed
