"""Build the deterministic, strictly offline OSF preregistration rehearsal."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "research/preregistration/osf-preregistration-v1.json"
DEFAULT_OUTPUT = ROOT / "research/preregistration/submission"
MANIFEST_NAME = "osf-submission-manifest.json"


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _narrative(package: dict[str, Any]) -> bytes:
    questions = "\n".join(f"- {item}" for item in package["research_questions"])
    responses = "\n\n".join(
        f"### {key.replace('_', ' ').title()}\n\n{value}"
        for key, value in package["registration_responses"].items()
    )
    return f"""# OSF preregistration cover: Global Medicines Atlas

> Offline rehearsal only. Status: `{package["status"]}`. This document has not
> been submitted or registered, and it does not authorize an external action.

## Summary

{package["summary"]}

## Research questions

{questions}

## Structured registration responses

{responses}

## Outcome boundary

Regulatory approval and public funding are separate outcomes. Absence of an
observation is insufficient evidence, not a negative status. No clinical,
causal, individual-patient, or exhaustive-global-coverage claim is permitted.

## Review and submission gate

Maintainer review is incomplete and required before any OSF, Hugging Face, or
Zenodo record is created or submitted.
""".encode()


def _readme() -> bytes:
    return b"""# Offline preregistration rehearsal

This directory is generated without network access. It is an OSF-ready draft,
not a registration or publication receipt.

Build from the repository root:

```console
python -m scripts.build_academic_preregistration --output research/preregistration/submission
```

Validate every schema, attachment, checksum, and documented boundary:

```console
python -m scripts.validate_academic_preregistration --bundle research/preregistration/submission
```

External submission requires explicit maintainer approval and is intentionally
not implemented by either command.
"""


def build_bundle(
    source: Path, output: Path | None, root: Path = ROOT
) -> dict[str, bytes]:
    """Return bundle bytes and optionally write them to ``output``."""
    package = json.loads(source.read_text(encoding="utf-8"))
    artifacts: dict[str, bytes] = {
        "00-cover-preregistration.md": _narrative(package),
        "01-structured-responses.json": _json_bytes(package),
        "02-academic-protocol.md": (
            root / "docs/research/academic-protocol.md"
        ).read_bytes(),
        "03-analysis-plan.md": (
            root / "docs/research/academic-analysis-plan.md"
        ).read_bytes(),
        "04-amendment-history.md": (
            root / package["registers"]["amendments"]
        ).read_bytes(),
        "05-deviation-register.txt": (
            root / package["registers"]["deviations"]
        ).read_bytes(),
        "06-data-management-and-ethics.md": (
            root / "research/preregistration/data-management-and-ethics.md"
        ).read_bytes(),
        "07-citations.json": (
            root / "research/preregistration/citations.json"
        ).read_bytes(),
        "README.md": _readme(),
    }
    media_types = {
        ".json": "application/json",
        ".md": "text/markdown",
        ".txt": "text/plain",
    }
    manifest = {
        "schema_id": "global-medicines-atlas.osf-submission-manifest",
        "schema_version": 1,
        "submission_state": "offline_rehearsal_only",
        "network_access": "prohibited",
        "source_contract": source.relative_to(root).as_posix(),
        "artifacts": [
            {
                "path": name,
                "media_type": media_types[Path(name).suffix],
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
            for name, content in sorted(artifacts.items())
        ],
    }
    artifacts[MANIFEST_NAME] = _json_bytes(manifest)
    if output is not None:
        output.mkdir(parents=True, exist_ok=True)
        for name, content in artifacts.items():
            (output / name).write_bytes(content)
    return artifacts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    build_bundle(arguments.input.resolve(), arguments.output.resolve())


if __name__ == "__main__":
    main()
