"""Build the maintainer-approved, fail-closed NZ public artifact manifest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT / "quality/qualifications/nz-public-artifact-manifest-20260821.json"
)

APPROVED_FILES = (
    "docs/migrations/nzmedicines-compatibility-notice.md",
    "docs/migrations/nzmedicines-external-gates.md",
    "docs/migrations/nzmedicines-history-restoration.md",
    "docs/migrations/nzmedicines-rights-disposition.md",
    "sources/nz/nzulm_fhir/__init__.py",
    "sources/nz/nzulm_fhir/adapter.py",
    "src/global_medicines_atlas/adapters/nz_medsafe.py",
    "src/global_medicines_atlas/adapters/nz_pharmac.py",
    "src/global_medicines_atlas/nz.py",
    "tests/fixtures/adapters/nz_medsafe_registry.csv",
    "tests/fixtures/adapters/nz_pharmac_schedule.xml",
    "tests/fixtures/nz/nzmt_synthetic_bundle.json",
    "tests/test_canonical_nz_adapter.py",
    "tests/test_nzulm_fhir_adapter.py",
    "tests/test_nzulm_fhir_properties.py",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_manifest() -> dict[str, Any]:
    """Return the exact, hash-bound approved NZ software/fixture cohort."""

    files: list[dict[str, object]] = []
    for relative in APPROVED_FILES:
        path = ROOT / relative
        if not path.is_file():
            raise FileNotFoundError(relative)
        files.append({
            "path": relative,
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        })
    return {
        "schema_id": "global-medicines-atlas.nz-public-artifact-manifest",
        "schema_version": 1,
        "decision_date": "2026-08-21",
        "decision_actor": "repository_maintainer",
        "decision_basis": (
            "Approved recommendation: publish only first-party code, "
            "synthetic/minimal fixtures, and already-approved metadata."
        ),
        "github_issues": [
            "https://github.com/edithatogo/global-medicines-atlas/issues/6",
            "https://github.com/edithatogo/global-medicines-atlas/issues/51",
        ],
        "artifact_scope": "software_and_synthetic_fixture_cohort_only",
        "approved_file_count": len(files),
        "approved_files": files,
        "source_family_decisions": {
            "nzmedicines_git_bundle": "local_only_not_redistributed",
            "nzmedicines_vendor_snapshot": (
                "removed_from_current_tree; historical Git exposure disclosed"
            ),
            "nzulm_nzmt": "local_only_pending_written_licensor_clearance",
            "nzf": "linked_content_excluded; structure_only_code_is_approved",
            "snomed_amt": "payloads_and_mapping_dumps_excluded",
            "rxnorm": "payloads_and_derived_mapping_dumps_excluded",
            "medsafe": "source_payloads_excluded; synthetic_fixture_approved",
            "pharmac": "source_payloads_excluded; synthetic_fixture_approved",
        },
        "excluded_path_prefixes": [
            "vendor/nzmedicines/",
            "local_data/",
            "build/",
        ],
        "preserved_bundle": {
            "filename": "nzmedicines-all.bundle",
            "sha256": (
                "f4414798f1b35558c69472d86d29b0b83facb2e799c9a20692b62fc889847223"
            ),
            "included": False,
        },
        "restricted_source_bytes_included": False,
        "derived_restricted_fields_included": False,
        "coverage_complete": False,
        "clinical_inference_permitted": False,
        "approval_invalidated_by": [
            "approved file digest or membership change",
            "source terms or attribution change",
            "fixture ceasing to be synthetic/minimal",
            "addition of source-derived fields",
        ],
    }


def main() -> int:
    """Write the deterministic manifest."""

    DEFAULT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_OUTPUT.write_text(
        json.dumps(build_manifest(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
