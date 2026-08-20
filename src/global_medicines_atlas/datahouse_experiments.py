"""Fail-closed contracts for optional datahouse experiments.

The module records experiment evidence without promoting an optional runtime or
moving authority away from immutable payloads and per-object receipts.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import platform
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Self, cast

EXPERIMENT_IDS = (
    "iceberg_rest",
    "iceberg_v3",
    "ducklake",
    "object_versioning",
    "batch_attestation",
    "delta_hudi",
)
_SHA256_HEX_LENGTH = 64


class ExperimentOutcome(StrEnum):
    """Allowed experiment outcomes."""

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    DEGRADED = "degraded"
    FAILED = "failed"
    NOT_RUN = "not_run"
    NOT_RUN_PREREQUISITE_UNMET = "not_run_prerequisite_unmet"


@dataclass(frozen=True)
class SpecificationPin:
    """Authoritative specification identity."""

    uri: str
    revision: str


@dataclass(frozen=True)
class ExperimentReceipt:
    """Serializable evidence for one optional experiment."""

    experiment_id: str
    outcome: ExperimentOutcome
    specification: SpecificationPin
    fixture_sha256: str
    limitations: tuple[str, ...]
    rollback_procedure: str
    dependencies: tuple[str, ...] = ()
    feature_flags: tuple[str, ...] = ()
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        if self.experiment_id not in EXPERIMENT_IDS:
            raise ValueError(f"unknown experiment ID: {self.experiment_id}")
        if not self.specification.uri.startswith("https://"):
            raise ValueError("specification URI must use HTTPS")
        if not self.specification.revision.strip():
            raise ValueError("specification revision is required")
        _validate_sha256(self.fixture_sha256)
        if not self.limitations:
            raise ValueError("at least one limitation is required")
        if not self.rollback_procedure.strip():
            raise ValueError("rollback procedure is required")

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical schema representation."""
        return {
            "schema_version": self.schema_version,
            "experiment_id": self.experiment_id,
            "outcome": self.outcome.value,
            "specification": {
                "uri": self.specification.uri,
                "revision": self.specification.revision,
            },
            "runtime": {
                "python": platform.python_version(),
                "dependencies": list(self.dependencies),
            },
            "fixture_sha256": self.fixture_sha256,
            "feature_flags": list(self.feature_flags),
            "limitations": list(self.limitations),
            "rollback_procedure": self.rollback_procedure,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        """Construct a validated receipt from a decoded object."""
        specification = value["specification"]
        runtime = value["runtime"]
        if not isinstance(specification, Mapping) or not isinstance(
            runtime, Mapping
        ):
            raise TypeError("specification and runtime must be objects")
        specification_values = cast("Mapping[str, Any]", specification)
        runtime_values = cast("Mapping[str, Any]", runtime)
        limitations = cast("Iterable[Any]", value["limitations"])
        dependencies = cast("Iterable[Any]", runtime_values["dependencies"])
        feature_flags = cast("Iterable[Any]", value["feature_flags"])
        return cls(
            experiment_id=str(value["experiment_id"]),
            outcome=ExperimentOutcome(str(value["outcome"])),
            specification=SpecificationPin(
                uri=str(specification_values["uri"]),
                revision=str(specification_values["revision"]),
            ),
            fixture_sha256=str(value["fixture_sha256"]),
            limitations=tuple(str(item) for item in limitations),
            rollback_procedure=str(value["rollback_procedure"]),
            dependencies=tuple(str(item) for item in dependencies),
            feature_flags=tuple(str(item) for item in feature_flags),
            schema_version=str(value["schema_version"]),
        )


_SPECIFICATIONS = {
    "iceberg_rest": SpecificationPin(
        "https://github.com/apache/iceberg/blob/apache-iceberg-1.10.2/open-api/rest-catalog-open-api.yaml",
        "apache-iceberg-1.10.2",
    ),
    "iceberg_v3": SpecificationPin(
        "https://github.com/apache/iceberg/blob/apache-iceberg-1.10.2/format/spec.md",
        "apache-iceberg-1.10.2-format-v3",
    ),
    "ducklake": SpecificationPin(
        "https://github.com/duckdb/ducklake-web/tree/v1.0/docs/stable/specification",
        "v1.0",
    ),
    "object_versioning": SpecificationPin(
        "https://github.com/treeverse/lakeFS/tree/v1.84.1",
        "v1.84.1",
    ),
    "batch_attestation": SpecificationPin(
        "https://www.rfc-editor.org/rfc/rfc6962",
        "RFC-6962",
    ),
    "delta_hudi": SpecificationPin(
        "https://github.com/delta-io/delta/releases/tag/v4.2.0",
        "delta-4.2.0-and-hudi-prerequisite-gate-v1",
    ),
}


def experiment_matrix(fixture: Path) -> tuple[ExperimentReceipt, ...]:
    """Create a deterministic initial matrix for a governed fixture."""
    digest = hashlib.sha256(fixture.read_bytes()).hexdigest()
    return tuple(
        ExperimentReceipt(
            experiment_id=experiment_id,
            outcome=ExperimentOutcome.NOT_RUN,
            specification=_SPECIFICATIONS[experiment_id],
            fixture_sha256=digest,
            limitations=("No executable result has been recorded.",),
            rollback_procedure=(
                "Remove disposable catalogue and derivative metadata; rebuild from "
                "the governed fixture and per-object receipts."
            ),
        )
        for experiment_id in EXPERIMENT_IDS
    )


def classify_prerequisite(
    experiment_id: str, evidence: Mapping[str, Any]
) -> ExperimentReceipt:
    """Fail closed when gated experiment prerequisites are not evidenced."""
    requirements = {
        "object_versioning": {
            "object_store",
            "versioning_or_worm",
            "replication",
            "checksum_inventory",
            "restore_rehearsal",
            "rpo_rto",
        },
        "delta_hudi": {
            "update_rate",
            "delete_rate",
            "concurrency",
            "transaction_requirements",
        },
    }
    required = requirements.get(experiment_id)
    if required is None:
        raise ValueError(f"no prerequisite gate for {experiment_id}")
    missing = sorted(key for key in required if not evidence.get(key))
    outcome = (
        ExperimentOutcome.NOT_RUN_PREREQUISITE_UNMET
        if missing
        else ExperimentOutcome.NOT_RUN
    )
    return ExperimentReceipt(
        experiment_id=experiment_id,
        outcome=outcome,
        specification=_SPECIFICATIONS[experiment_id],
        fixture_sha256=hashlib.sha256(b"prerequisite-evidence-v1").hexdigest(),
        limitations=(
            "Missing prerequisite evidence: " + ", ".join(missing)
            if missing
            else "Prerequisites evidenced; executable comparison not yet run.",
        ),
        rollback_procedure="No resource was provisioned and no core dependency was added.",
    )


def iceberg_rest_attempt(
    fixture: Path, *, endpoint: str | None
) -> ExperimentReceipt:
    """Record a fail-closed REST attempt without inventing infrastructure."""
    digest = hashlib.sha256(fixture.read_bytes()).hexdigest()
    if not endpoint:
        return ExperimentReceipt(
            experiment_id="iceberg_rest",
            outcome=ExperimentOutcome.FAILED,
            specification=_SPECIFICATIONS["iceberg_rest"],
            fixture_sha256=digest,
            feature_flags=("endpoint_unconfigured",),
            limitations=(
                (
                    "No disposable Iceberg REST endpoint or local container runtime "
                    "was available; lifecycle operations were not simulated."
                ),
            ),
            rollback_procedure="No catalogue resource was created.",
        )
    raise NotImplementedError(
        "A separately supplied endpoint requires an authenticated lifecycle adapter."
    )


def iceberg_v3_capabilities(
    *, advertised: set[str], requested: set[str], table_identity: str
) -> dict[str, Any]:
    """Classify v3 capabilities while preserving a v2-compatible identity."""
    if not table_identity.strip():
        raise ValueError("table identity is required")
    supported = sorted(requested & advertised)
    fallback = sorted(requested - advertised)
    return {
        "specification_revision": _SPECIFICATIONS["iceberg_v3"].revision,
        "supported": supported,
        "fallback": fallback,
        "table_identity": table_identity,
        "fallback_format_version": 2,
        "silent_downgrade": False,
    }


def ducklake_comparison(
    directory: Path, *, rows: Iterable[tuple[int, str]]
) -> dict[str, Any]:
    """Run a bounded DuckLake lifecycle over synthetic rows."""
    duckdb = importlib.import_module("duckdb")

    values = tuple(rows)
    directory.mkdir(parents=True, exist_ok=True)
    baseline = json.dumps(
        values, separators=(",", ":"), sort_keys=True
    ).encode()
    baseline_sha256 = hashlib.sha256(baseline).hexdigest()
    metadata = directory / "metadata.ducklake"
    data_path = directory / "data"
    connection = duckdb.connect()
    try:
        connection.execute("LOAD ducklake")
        connection.execute(
            f"ATTACH 'ducklake:{metadata}' AS experiment "
            f"(DATA_PATH '{data_path}/')"
        )
        connection.execute(
            "CREATE TABLE experiment.main.medicines(id INTEGER, name VARCHAR)"
        )
        connection.executemany(
            "INSERT INTO experiment.main.medicines VALUES (?, ?)", values
        )
        recovered = tuple(
            connection.execute(
                "SELECT id, name FROM experiment.main.medicines ORDER BY id"
            ).fetchall()
        )
    finally:
        connection.close()
    recovered_sha256 = hashlib.sha256(
        json.dumps(recovered, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
    return {
        "outcome": (
            ExperimentOutcome.SUPPORTED.value
            if recovered_sha256 == baseline_sha256
            else ExperimentOutcome.FAILED.value
        ),
        "duckdb_version": duckdb.__version__,
        "ducklake_specification": _SPECIFICATIONS["ducklake"].revision,
        "row_count": len(recovered),
        "baseline_sha256": baseline_sha256,
        "recovered_sha256": recovered_sha256,
        "catalogue_authoritative": False,
        "rollback": "Delete the disposable catalogue and data directory.",
    }


def decision_matrix(
    receipts: Iterable[ExperimentReceipt],
) -> dict[str, dict[str, Any]]:
    """Produce non-promotional dispositions from observed outcomes."""
    by_id = {receipt.experiment_id: receipt for receipt in receipts}
    missing = set(EXPERIMENT_IDS) - set(by_id)
    if missing:
        raise ValueError(
            "missing experiment receipts: " + ", ".join(sorted(missing))
        )
    dispositions = {
        ExperimentOutcome.SUPPORTED: "continue-experiment",
        ExperimentOutcome.DEGRADED: "continue-experiment",
        ExperimentOutcome.UNSUPPORTED: "reject",
        ExperimentOutcome.FAILED: "continue-experiment",
        ExperimentOutcome.NOT_RUN: "not-run",
        ExperimentOutcome.NOT_RUN_PREREQUISITE_UNMET: "not-run",
    }
    return {
        experiment_id: {
            "observed_outcome": by_id[experiment_id].outcome.value,
            "disposition": dispositions[by_id[experiment_id].outcome],
            "limitations": list(by_id[experiment_id].limitations),
            "deployment_authorized": False,
            "authority_preserved": "payload-and-per-object-receipts",
        }
        for experiment_id in EXPERIMENT_IDS
    }


def batch_manifest(
    objects: Mapping[str, str] | Iterable[tuple[str, str]],
) -> dict[str, Any]:
    """Build a deterministic additive Merkle-style batch receipt."""
    if isinstance(objects, Mapping):
        mapping = cast("Mapping[str, str]", objects)
        pairs = list(mapping.items())
    else:
        pairs = list(objects)
    identities = [identity for identity, _digest in pairs]
    if len(identities) != len(set(identities)):
        raise ValueError("duplicate content ID")
    leaves: list[dict[str, str]] = []
    for identity, digest in sorted(pairs):
        if not identity.strip():
            raise ValueError("content ID is required")
        _validate_sha256(digest)
        leaf = hashlib.sha256(
            f"leaf\0{identity}\0{digest}".encode()
        ).hexdigest()
        leaves.append({"content_id": identity, "sha256": digest, "leaf": leaf})
    root = _merkle_root([leaf["leaf"] for leaf in leaves])
    return {
        "schema_version": "1.0",
        "algorithm": "sha256-domain-separated-merkle-v1",
        "authority": "additive-to-per-object-receipts",
        "leaf_count": len(leaves),
        "leaves": leaves,
        "root": root,
    }


def verify_batch_manifest(
    manifest: Mapping[str, Any], objects: Mapping[str, str]
) -> bool:
    """Verify a manifest against authoritative per-object identities."""
    try:
        return manifest == batch_manifest(objects)
    except TypeError, ValueError:
        return False


def _merkle_root(leaves: list[str]) -> str:
    if not leaves:
        return hashlib.sha256(b"empty\0").hexdigest()
    level = leaves
    while len(level) > 1:
        if len(level) % 2:
            level = [*level, level[-1]]
        level = [
            hashlib.sha256(
                f"node\0{level[index]}\0{level[index + 1]}".encode()
            ).hexdigest()
            for index in range(0, len(level), 2)
        ]
    return level[0]


def _validate_sha256(digest: str) -> None:
    if len(digest) != _SHA256_HEX_LENGTH or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise ValueError(
            "SHA-256 digest must be 64 lowercase hexadecimal characters"
        )
