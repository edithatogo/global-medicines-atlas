"""Run bounded source-health probes and emit metadata-only JSON."""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path
from typing import Final, Literal, cast

from pydantic import Field, model_validator

from global_medicines_atlas.models import FrozenModel
from global_medicines_atlas.source_catalog import load_source_catalog
from global_medicines_atlas.source_health import (
    assess_schema_drift,
    drift_report_json,
    probe_sources,
)

SHA256_HEX_LENGTH: Final = 64
TRUSTED_WORKFLOW: Final = ".github/workflows/source-health.yml"


class BaselineProvenance(FrozenModel):
    """Hosted identity that makes a source-health baseline admissible."""

    schema_id: Literal["global-medicines-atlas.source-health-baseline"] = (
        "global-medicines-atlas.source-health-baseline"
    )
    schema_version: Literal[1] = 1
    repository: str = Field(min_length=1)
    workflow: str = Field(min_length=1)
    branch: str = Field(min_length=1)
    conclusion: str = Field(min_length=1)
    run_id: int = Field(gt=0)
    commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    observation_id: int = Field(gt=0)
    report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def successful_main_run(self) -> BaselineProvenance:
        if self.branch != "main" or self.conclusion != "success":
            raise ValueError("baseline must come from a successful main run")
        if self.observation_id != self.run_id:
            raise ValueError("observation identity must equal the run identity")
        return self

    @classmethod
    def for_report(
        cls,
        report: Path,
        *,
        repository: str,
        workflow: str,
        branch: str,
        conclusion: str,
        run_id: int,
        commit: str,
        observation_id: int,
    ) -> BaselineProvenance:
        return cls(
            repository=repository,
            workflow=workflow,
            branch=branch,
            conclusion=conclusion,
            run_id=run_id,
            commit=commit,
            observation_id=observation_id,
            report_sha256=sha256(report.read_bytes()).hexdigest(),
        )

    def canonical_json(self) -> str:
        return (
            json.dumps(
                self.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("build/source-health.json"),
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        help="Previous metadata-only source-health report.",
    )
    parser.add_argument("--baseline-provenance", type=Path)
    parser.add_argument("--baseline-run-id", type=int)
    parser.add_argument("--baseline-commit")
    parser.add_argument("--repository")
    parser.add_argument("--workflow", default=TRUSTED_WORKFLOW)
    parser.add_argument("--branch")
    parser.add_argument("--conclusion")
    parser.add_argument("--run-id", type=int)
    parser.add_argument("--commit")
    parser.add_argument("--observation-id", type=int)
    parser.add_argument(
        "--provenance-output",
        type=Path,
        default=Path("build/source-health-provenance.json"),
    )
    parser.add_argument("--max-bytes", type=int, default=65_536)
    return parser.parse_args()


def load_baseline(path: Path | None) -> dict[str, str]:
    """Load fingerprints from a prior report, or start without a baseline."""

    if path is None or not path.exists():
        return {}
    document = cast("object", json.loads(path.read_text(encoding="utf-8")))
    if not isinstance(document, dict):
        raise TypeError("baseline report must be a JSON object")
    typed_document = cast("dict[str, object]", document)
    baseline = typed_document.get("baseline")
    if not isinstance(baseline, dict):
        raise TypeError("baseline report has no fingerprint baseline")
    typed_baseline = cast("dict[object, object]", baseline)
    fingerprints: dict[str, str] = {}
    for source_id, fingerprint in typed_baseline.items():
        if (
            not isinstance(source_id, str)
            or not isinstance(fingerprint, str)
            or len(fingerprint) != SHA256_HEX_LENGTH
            or any(
                character not in "0123456789abcdef" for character in fingerprint
            )
        ):
            raise ValueError("baseline contains an invalid fingerprint")
        fingerprints[source_id] = fingerprint
    return fingerprints


def load_trusted_baseline(
    report: Path,
    provenance_path: Path,
    *,
    expected_repository: str,
    expected_workflow: str,
    current_observation_id: int,
    expected_run_id: int | None = None,
    expected_commit: str | None = None,
) -> dict[str, str]:
    """Admit only a digest-bound, successful main-workflow predecessor."""

    provenance = BaselineProvenance.model_validate_json(
        provenance_path.read_text(encoding="utf-8")
    )
    if provenance.repository != expected_repository:
        raise ValueError("baseline repository identity is not trusted")
    if provenance.workflow != expected_workflow:
        raise ValueError("baseline workflow identity is not trusted")
    if expected_run_id is not None and provenance.run_id != expected_run_id:
        raise ValueError("baseline run identity does not match hosted run")
    if expected_commit is not None and provenance.commit != expected_commit:
        raise ValueError("baseline commit identity does not match hosted run")
    if provenance.report_sha256 != sha256(report.read_bytes()).hexdigest():
        raise ValueError("baseline report digest does not match provenance")
    if provenance.observation_id >= current_observation_id:
        raise ValueError("baseline observation identity is not monotonic")
    return load_baseline(report)


def main() -> int:
    args = parse_args()
    if args.baseline is not None:
        if (
            args.baseline_provenance is None
            or args.repository is None
            or args.observation_id is None
            or args.baseline_run_id is None
            or args.baseline_commit is None
        ):
            raise ValueError(
                "baseline comparison requires provenance, repository and "
                "current observation identity"
            )
        previous = load_trusted_baseline(
            args.baseline,
            args.baseline_provenance,
            expected_repository=args.repository,
            expected_workflow=args.workflow,
            current_observation_id=args.observation_id,
            expected_run_id=args.baseline_run_id,
            expected_commit=args.baseline_commit,
        )
    else:
        previous = {}
    observations = probe_sources(
        load_source_catalog(),
        max_bytes=args.max_bytes,
    )
    assessments = assess_schema_drift(observations, previous)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        drift_report_json(observations, assessments),
        encoding="utf-8",
        newline="\n",
    )
    provenance_values = (
        args.repository,
        args.branch,
        args.conclusion,
        args.run_id,
        args.commit,
        args.observation_id,
    )
    if any(value is not None for value in provenance_values):
        if any(value is None for value in provenance_values):
            raise ValueError("current provenance arguments must be complete")
        provenance = BaselineProvenance.for_report(
            args.output,
            repository=args.repository,
            workflow=args.workflow,
            branch=args.branch,
            conclusion=args.conclusion,
            run_id=args.run_id,
            commit=args.commit,
            observation_id=args.observation_id,
        )
        args.provenance_output.parent.mkdir(parents=True, exist_ok=True)
        args.provenance_output.write_text(
            provenance.canonical_json(), encoding="utf-8", newline="\n"
        )
    return int(any(item.state.value == "changed" for item in assessments))


if __name__ == "__main__":
    raise SystemExit(main())
