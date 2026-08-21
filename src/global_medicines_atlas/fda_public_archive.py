"""Build an exact-manifest publication candidate from the FDA cohort."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Final

from pydantic import Field, model_validator

from .models import FrozenModel

FDA_SOURCE_IDS: Final = frozenset({
    "us-drugsfda",
    "us-fda-drug-shortages",
    "us-fda-faers",
    "us-fda-ndc-directory",
    "us-fda-nsde",
    "us-fda-orange-book",
    "us-fda-recalls-notices",
    "us-fda-rems",
    "us-openfda-drugsfda",
    "us-openfda-enforcement",
    "us-openfda-faers",
    "us-openfda-ndc",
    "us-openfda-nsde",
})
SENSITIVE_SOURCE_IDS: Final = frozenset({
    "us-fda-faers",
    "us-openfda-faers",
    "us-fda-recalls-notices",
    "us-openfda-enforcement",
})
DATASET_CARD: Final = """---
license: other
pretty_name: Global Medicines Atlas FDA publication candidate
language:
- en
tags:
- medicines
- regulatory
- fda
---

# FDA publication candidate

This private review candidate contains a bounded 2026-08-21 acquisition of 13
official FDA and openFDA surfaces, plus acquisition and admission receipts. It
is not approved for public release, is not a complete historical mirror, and
is not clinical advice.

Official FDA and openFDA policy statements are retained as candidate rights
evidence only. The package excludes FDA marks, credentials, separately licensed
third-party vocabularies, and projected records for quarantined payloads. An
exact-manifest licensing conclusion and publication approval remain pending.

FAERS, enforcement, and recall material is classified as public regulatory
sensitive data. A report does not establish causation. Do not attempt
re-identification or use the data for decisions about individuals.

`manifest.json` is the exact byte-level publication boundary. Coverage and
admission limitations are recorded per source.
"""


class FdaPublicationCandidateEntry(FrozenModel):
    """One source payload staged for exact-manifest review."""

    source_id: str
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)
    admission_state: str
    projection_permitted: bool
    sensitivity: str


class FdaPublicationCandidateManifest(FrozenModel):
    """Exact private byte manifest proposed for publication review."""

    schema_id: str = "global-medicines-atlas.fda-public-archive"
    schema_version: int = 1
    source_count: int
    entries: tuple[FdaPublicationCandidateEntry, ...]
    excluded_components: tuple[str, ...]
    coverage_complete: bool = False
    clinical_inference_permitted: bool = False

    publication_approved: bool = False

    @model_validator(mode="after")
    def exact_source_set(self) -> FdaPublicationCandidateManifest:
        if self.publication_approved:
            raise ValueError("FDA candidate cannot encode publication approval")
        ids = {entry.source_id for entry in self.entries}
        if ids != set(FDA_SOURCE_IDS) or self.source_count != len(
            FDA_SOURCE_IDS
        ):
            raise ValueError(
                "FDA candidate must contain every proposed source once"
            )
        if len(ids) != len(self.entries):
            raise ValueError("FDA archive source IDs must be unique")
        return self


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_fda_publication_candidate(
    corpus: Path, output: Path
) -> FdaPublicationCandidateManifest:
    """Stage receipt-bound FDA payloads for exact-manifest review."""

    receipts_path = corpus / "evidence/redacted-acquisition-results.json"
    receipts = json.loads(receipts_path.read_text(encoding="utf-8"))
    by_id = {item["source_id"]: item for item in receipts}
    if set(by_id) != set(FDA_SOURCE_IDS) or len(receipts) != len(
        FDA_SOURCE_IDS
    ):
        raise ValueError(
            "acquisition receipt does not cover exact FDA source set"
        )
    if output.exists():
        raise FileExistsError(output)
    (output / "data").mkdir(parents=True)
    entries: list[FdaPublicationCandidateEntry] = []
    for source_id in sorted(FDA_SOURCE_IDS):
        candidates = tuple((corpus / "downloads").glob(f"{source_id}.*"))
        if len(candidates) != 1:
            raise ValueError(f"expected one payload for {source_id}")
        source = candidates[0]
        receipt = by_id[source_id]
        digest = _sha256(source)
        if digest != receipt["payload_sha256"]:
            raise ValueError(f"payload digest mismatch for {source_id}")
        target = output / "data" / source.name
        shutil.copyfile(source, target)
        admission = receipt["admission_state"]
        entries.append(
            FdaPublicationCandidateEntry(
                source_id=source_id,
                path=target.relative_to(output).as_posix(),
                sha256=digest,
                byte_count=target.stat().st_size,
                admission_state=admission,
                projection_permitted=admission == "accepted",
                sensitivity=(
                    "public_regulatory_sensitive"
                    if source_id in SENSITIVE_SOURCE_IDS
                    else "public"
                ),
            )
        )
    manifest = FdaPublicationCandidateManifest(
        source_count=len(entries),
        entries=tuple(entries),
        excluded_components=(
            "internal acquisition authorization",
            "credentials and request headers",
            "FDA marks and separately licensed third-party vocabularies",
            "record projections for quarantined payloads",
        ),
    )
    (output / "manifest.json").write_text(
        manifest.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    shutil.copyfile(
        receipts_path, output / "acquisition-admission-receipts.json"
    )
    (output / "README.md").write_text(DATASET_CARD, encoding="utf-8")
    return manifest
