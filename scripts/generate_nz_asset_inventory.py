"""Generate the NZ migration inventory without hydrating source payloads."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import stat
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, cast

PROJECT_ROOT: Final = Path(__file__).resolve().parents[1]
TRACK_ROOT: Final = (
    PROJECT_ROOT / "conductor/archive/nzmedicines_migration_20260727"
)
JSON_OUTPUT: Final = TRACK_ROOT / "nz-asset-inventory.json"
CSV_OUTPUT: Final = TRACK_ROOT / "nz-asset-disposition.csv"
UPSTREAM_ROOT: Final = PROJECT_ROOT / "vendor/nzmedicines"
UPSTREAM_COMMIT: Final = "6a8ecfae67f15d635750d11d5f446b93d76c1865"
PRESERVATION_MANIFEST: Final = TRACK_ROOT / "nzmedicines-preservation.json"
EXPECTED_UPSTREAM_TREE_DIGEST: Final = (
    "0217b32a00b231b910d07df8d85b25aa2a884404e1b823b71d222259ceba150e"
)
EXPECTED_BUNDLE_DIGEST: Final = (
    "f4414798f1b35558c69472d86d29b0b83facb2e799c9a20692b62fc889847223"
)
SHA256_PATTERN: Final = re.compile(r"[0-9a-f]{64}")
COMMIT_PATTERN: Final = re.compile(r"[0-9a-f]{40}")

LOCAL_ROOTS: Final = (
    Path("nzulm_2023_data"),
    Path("medsafe_exports"),
    Path("terminology/nzulm"),
    Path("sources/nz/nzulm_fhir"),
)
LOCAL_FILES: Final = (
    Path("nzulm_2023.zip"),
    Path("nzulm.db"),
    Path("scripts/integrate_nzulm_2023.py"),
    Path("scripts/medsafe_scraper.py"),
    Path("scripts/refresh_medsafe_edges.sh"),
    Path("tests/test_nzulm_ingestor.py"),
    Path("tests/test_nzulm_fhir_adapter.py"),
    Path("tests/test_nzulm_fhir_properties.py"),
    Path("docs/adr/004-nzulm-integration.md"),
    Path("docs/nzulm_2023_integration.md"),
    Path("docs/medsafe_sqlite.md"),
    Path("comparisons/atc_enriched/medsafe_products_with_atc.csv"),
    Path("medsafe_applications_paracetamol.csv"),
    Path("medsafe_products_paracetamol.csv"),
)

DOCUMENT_SUFFIXES: Final = {".docx", ".pdf", ".txt", ".xlsx"}
NZMT_HIERARCHY_STEMS: Final = {
    "ct_dump",
    "ctpp_dump",
    "mhm_dump",
    "mp_dump",
    "mp_has_substance_dump",
    "mpp_dump",
    "mpuu_dump",
    "mpuusai_dump",
    "msp_dump",
    "pf_dump",
    "pmi_dump",
    "psrt_dump",
    "substance_dump",
    "tht_dump",
    "tp_dump",
    "tpp_dump",
    "tpuu_dump",
    "udfi_dump",
    "uom_dump",
}


@dataclass(frozen=True, slots=True)
class Asset:
    path: str
    scope: str
    family: str
    format: str
    size_bytes: int
    modified_utc: str
    resident: bool
    disposition: str
    rights_boundary: str
    rationale: str
    conflict: str
    local_enhancement: str
    sha256: str | None = None
    upstream_commit: str | None = None


def relative(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def is_resident(path: Path) -> bool:
    attributes = getattr(path.stat(), "st_file_attributes", 0)
    hydration_flags = (
        getattr(stat, "FILE_ATTRIBUTE_OFFLINE", 0x1000)
        | getattr(stat, "FILE_ATTRIBUTE_RECALL_ON_OPEN", 0x40000)
        | getattr(stat, "FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS", 0x400000)
    )
    return not bool(attributes & hydration_flags)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def local_classification(path: Path) -> tuple[str, str, str, str, str, str]:
    stem = path.stem.lower()
    suffix = path.suffix.lower()
    relative_path = relative(path)

    if "__pycache__" in path.parts or suffix == ".pyc":
        return (
            "generated_cache",
            "excluded",
            "not-for-publication",
            "Interpreter cache; reproducible from source.",
            "Not a governed source asset.",
            "None.",
        )
    if relative_path.endswith((".sqlite-shm", ".sqlite-wal")):
        return (
            "database_sidecar",
            "excluded",
            "local-only",
            "Ephemeral SQLite sidecar; not an authoritative dataset.",
            "May represent an interrupted or open local database state.",
            "None.",
        )
    if relative_path in {"nzulm_2023.zip", "nzulm_2023_data/nzulm_2023.zip"}:
        return (
            "release_archive",
            "superseded",
            "local-only-review-required",
            (
                "Preserved release archive; extracted source family is the "
                "working input."
            ),
            (
                "Duplicate archive surfaces require digest comparison before "
                "deletion."
            ),
            "Recoverable source-release boundary.",
        )
    if relative_path == "nzulm.db":
        return (
            "legacy_derived_database",
            "adapted",
            "local-only",
            "Existing derived database retained as migration and parity input.",
            (
                "Opaque derivation and recency must not be treated as "
                "authoritative."
            ),
            (
                "Useful regression and migration surface for DuckDB/Parquet "
                "outputs."
            ),
        )
    if relative_path.startswith("medsafe_exports/"):
        return (
            "medsafe_derived_export",
            "adapted",
            "local-only-review-required",
            "Reusable regulatory export derived from Medsafe source data.",
            "Derived formats can drift from the embedded NZULM Medsafe tables.",
            "CSV, Parquet, XLSX, and SQLite parity surfaces already exist.",
        )
    if relative_path.startswith("terminology/nzulm/"):
        return (
            "nzmt_ingestor",
            "adapted",
            "source-code",
            "Existing maintainer-owned NZ terminology ingestion capability.",
            (
                "Legacy contracts require alignment with the canonical global "
                "model."
            ),
            "Builds on prior local implementation instead of replacing it.",
        )
    if relative_path.startswith("sources/nz/nzulm_fhir/"):
        return (
            "nz_fhir_adapter",
            "adapted",
            "source-code",
            (
                "First-party provenance-bearing adapter over preserved FHIR "
                "fixtures."
            ),
            "FHIR projection is not the canonical medicine data model.",
            "Python 3.14 contracts, properties, and source digests.",
        )
    if relative_path.startswith(("scripts/", "tests/", "docs/")):
        return (
            "implementation_support",
            "adapted",
            "source-code-or-documentation",
            (
                "Existing implementation, validation, or design surface to "
                "retain and evolve."
            ),
            (
                "Some legacy documentation may overstate completion or "
                "current recency."
            ),
            "Maintainer-owned implementation and test evidence.",
        )
    if relative_path.startswith("comparisons/"):
        return (
            "derived_comparison",
            "adapted",
            "local-only-review-required",
            (
                "Derived Medsafe/ATC comparison output retained as regression "
                "evidence."
            ),
            "Must not be presented as a current regulatory status source.",
            "Existing cross-terminology enrichment output.",
        )
    if relative_path in {
        "medsafe_applications_paracetamol.csv",
        "medsafe_products_paracetamol.csv",
    }:
        return (
            "curated_sample",
            "fixture",
            "local-only-review-required",
            "Small Medsafe sample suitable for deterministic adapter fixtures.",
            "Sample is not evidence of complete regulatory coverage.",
            "Existing paracetamol regression data.",
        )
    if path.parent.name == "nzulm_2023_data":
        if stem.startswith("ms_") or stem == "medsafe_restrictions_dump":
            family = "medsafe_regulatory_source"
        elif stem.startswith(("hml_", "ps_")) or stem in {
            "nzmt_pharmac_subsidy_codes_dump",
            "prescribing_term_selection_list_dump",
        }:
            family = "funding_formulary_source"
        elif stem in NZMT_HIERARCHY_STEMS:
            family = "nzmt_hierarchy_source"
        elif any(
            token in stem
            for token in ("atc", "snomed", "gtin", "pharmacode", "related_ids")
        ):
            family = "terminology_mapping_source"
        elif suffix in DOCUMENT_SUFFIXES:
            family = "governance_and_schema_documentation"
        else:
            family = "nzmt_supporting_source"
        return (
            family,
            "adopted",
            "local-only-review-required",
            (
                "Source-native 2023 NZULM/NZMT release asset retained without "
                "transformation."
            ),
            (
                "Static 2023 release is stale for current-status claims and "
                "has mixed rights."
            ),
            (
                "Richer hierarchy, Medsafe, subsidy, identifier, and mapping "
                "coverage than upstream FHIR examples."
            ),
        )
    raise ValueError(f"No local classification rule for {relative_path}")


def upstream_classification(path: Path) -> tuple[str, str, str, str, str, str]:
    relative_upstream = path.relative_to(UPSTREAM_ROOT).as_posix()
    if relative_upstream == ".github/workflows/regenerate-indexes.yml":
        return (
            "upstream_workflow",
            "superseded",
            "source-code",
            (
                "Preserved for provenance; replaced by tested first-party "
                "generation commands."
            ),
            (
                "Unpinned inline workflow is not suitable for the target CI "
                "boundary."
            ),
            "Python 3.14 harness and dedicated CI profiles.",
        )
    if relative_upstream == "readme.md":
        return (
            "upstream_design_rationale",
            "adapted",
            "source-documentation",
            (
                "FHIR mapping rationale is retained and corrected in "
                "first-party documentation."
            ),
            (
                "Projection examples do not establish current registry or "
                "standards conformance."
            ),
            "Canonical/projection separation and explicit provenance.",
        )
    if path.name in {"index.txt", "substance.txt", "_index.json"}:
        return (
            "upstream_generated_index",
            "fixture",
            "source-fixture-review-required",
            "Golden fixture for deterministic index regeneration.",
            "Generated indexes are not authoritative source records.",
            "Deterministic regeneration and negative-control testing target.",
        )
    if relative_upstream.startswith("document-references/"):
        return (
            "upstream_fhir_document_reference",
            "fixture",
            "source-fixture-review-required",
            (
                "Preserved FHIR DocumentReference fixture with immutable "
                "provenance."
            ),
            (
                "Referenced NZF content and URLs require independent "
                "rights/currentness review."
            ),
            (
                "Local source boundaries prevent referenced content from "
                "becoming canonical."
            ),
        )
    if relative_upstream.startswith("medications/"):
        return (
            "upstream_fhir_medication",
            "fixture",
            "source-fixture-review-required",
            (
                "Preserved Medication/Bundle fixture for adapter and "
                "projection parity."
            ),
            (
                "Sparse examples cannot replace the complete local NZMT "
                "hierarchy or status data."
            ),
            (
                "Local source corpus supplies hierarchy, Medsafe, subsidy, "
                "GTIN, pharmacode, ATC, and SNOMED mappings."
            ),
        )
    if relative_upstream.startswith("substance/"):
        return (
            "upstream_fhir_substance",
            "fixture",
            "source-fixture-review-required",
            "Preserved Substance fixture for adapter and projection parity.",
            (
                "Substance examples are incomplete relative to the local NZMT "
                "corpus."
            ),
            (
                "Local substance and SNOMED mapping tables provide broader "
                "coverage."
            ),
        )
    raise ValueError(f"No upstream classification rule for {relative_upstream}")


def asset(path: Path, *, scope: str) -> Asset:
    stat_result = path.stat()
    classifier = (
        upstream_classification if scope == "upstream" else local_classification
    )
    family, disposition, rights, rationale, conflict, enhancement = classifier(
        path
    )
    return Asset(
        path=relative(path),
        scope=scope,
        family=family,
        format=path.suffix.lower().lstrip(".") or "none",
        size_bytes=stat_result.st_size,
        modified_utc=datetime.fromtimestamp(
            stat_result.st_mtime, UTC
        ).isoformat(),
        resident=is_resident(path),
        disposition=disposition,
        rights_boundary=rights,
        rationale=rationale,
        conflict=conflict,
        local_enhancement=enhancement,
        sha256=sha256(path) if scope == "upstream" else None,
        upstream_commit=UPSTREAM_COMMIT if scope == "upstream" else None,
    )


def discover_local() -> list[Path]:
    paths: set[Path] = set()
    for root in LOCAL_ROOTS:
        absolute = PROJECT_ROOT / root
        paths.update(
            path
            for path in absolute.rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix != ".pyc"
        )
    for relative_path in LOCAL_FILES:
        path = PROJECT_ROOT / relative_path
        if path.is_file():
            paths.add(path)
    return sorted(paths)


def discover_upstream() -> list[Path]:
    return sorted(path for path in UPSTREAM_ROOT.rglob("*") if path.is_file())


def upstream_manifest(
    inventory: dict[str, object],
) -> dict[str, dict[str, object]]:
    """Extract and validate the immutable upstream tree manifest."""
    rows_value = inventory.get("assets")
    if not isinstance(rows_value, list):
        raise TypeError("Inventory assets must be a list")
    row_values = cast("list[object]", rows_value)

    manifest: dict[str, dict[str, object]] = {}
    for row_value in row_values:
        if not isinstance(row_value, dict):
            continue
        row = cast("dict[str, object]", row_value)
        if row.get("scope") != "upstream":
            continue
        path = row.get("path")
        if not isinstance(path, str):
            raise TypeError("Upstream manifest path must be a string")
        if path in manifest:
            raise ValueError(f"Duplicate upstream manifest path: {path}")
        required = ("size_bytes", "sha256", "upstream_commit", "disposition")
        missing = [field for field in required if row.get(field) in {None, ""}]
        if missing:
            raise ValueError(
                f"Upstream manifest entry {path} is missing: "
                f"{', '.join(missing)}"
            )
        if row["upstream_commit"] != UPSTREAM_COMMIT:
            raise ValueError(f"Unexpected source commit for {path}")
        size_bytes = row["size_bytes"]
        if (
            not isinstance(size_bytes, int)
            or isinstance(size_bytes, bool)
            or size_bytes < 0
        ):
            raise TypeError(
                f"Upstream manifest size_bytes must be a non-negative "
                f"integer for {path}"
            )
        digest = row["sha256"]
        if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
            raise ValueError(
                f"Upstream manifest SHA-256 must be 64 lowercase hex "
                f"characters for {path}"
            )
        manifest[path] = row

    if not manifest:
        raise ValueError("Inventory has no upstream manifest entries")
    asset_count = inventory.get("upstream_asset_count")
    if (
        not isinstance(asset_count, int)
        or isinstance(asset_count, bool)
        or asset_count < 0
    ):
        raise TypeError(
            "Inventory upstream_asset_count must be a non-negative integer"
        )
    if asset_count != len(manifest):
        raise ValueError(
            "Upstream manifest count does not match upstream_asset_count"
        )
    return manifest


def aggregate_manifest_digest(
    manifest: dict[str, dict[str, object]],
) -> str:
    """Return the canonical digest for source-boundary manifest fields."""
    fields = (
        "path",
        "size_bytes",
        "sha256",
        "upstream_commit",
        "disposition",
    )
    rows = [
        {field: row[field] if field != "path" else path for field in fields}
        for path, row in sorted(manifest.items())
    ]
    payload = json.dumps(
        rows,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def verify_preservation_identity(
    manifest: dict[str, dict[str, object]],
) -> None:
    """Bind inventory rows to fixed snapshot, commit, and bundle identities."""
    preservation_value = json.loads(
        PRESERVATION_MANIFEST.read_text(encoding="utf-8")
    )
    if not isinstance(preservation_value, dict):
        raise TypeError("Preservation manifest must be a JSON object")
    preservation = cast("dict[str, object]", preservation_value)

    expected_values = (
        ("source_commit", UPSTREAM_COMMIT, COMMIT_PATTERN),
        (
            "upstream_tree_sha256",
            EXPECTED_UPSTREAM_TREE_DIGEST,
            SHA256_PATTERN,
        ),
        ("bundle_sha256", EXPECTED_BUNDLE_DIGEST, SHA256_PATTERN),
    )
    for field, expected, pattern in expected_values:
        value = preservation.get(field)
        if not isinstance(value, str) or not pattern.fullmatch(value):
            raise ValueError(
                f"Preservation manifest {field} has invalid digest syntax"
            )
        if value != expected:
            raise ValueError(
                f"Preservation manifest {field} differs from fixed identity"
            )

    asset_count = preservation.get("upstream_asset_count")
    if (
        not isinstance(asset_count, int)
        or isinstance(asset_count, bool)
        or asset_count < 0
    ):
        raise TypeError(
            "Preservation upstream_asset_count must be a non-negative integer"
        )
    if asset_count != len(manifest):
        raise ValueError("Preservation upstream asset count differs")

    bundle_size = preservation.get("bundle_size_bytes")
    if (
        not isinstance(bundle_size, int)
        or isinstance(bundle_size, bool)
        or bundle_size < 0
    ):
        raise TypeError(
            "Preservation bundle_size_bytes must be a non-negative integer"
        )

    if aggregate_manifest_digest(manifest) != EXPECTED_UPSTREAM_TREE_DIGEST:
        raise ValueError("Upstream aggregate tree digest differs")


def verify_upstream_tree(inventory: dict[str, object]) -> None:
    """Verify the vendor snapshot against its committed tree manifest."""
    manifest = upstream_manifest(inventory)
    verify_preservation_identity(manifest)
    discovered = {relative(path): path for path in discover_upstream()}
    expected_paths = set(manifest)
    actual_paths = set(discovered)
    missing = sorted(expected_paths - actual_paths)
    extra = sorted(actual_paths - expected_paths)
    if missing or extra:
        details: list[str] = []
        if missing:
            details.append(f"missing={missing}")
        if extra:
            details.append(f"extra={extra}")
        raise ValueError(
            "Upstream tree membership differs: " + "; ".join(details)
        )

    for path in sorted(expected_paths):
        expected = manifest[path]
        actual_path = discovered[path]
        actual_size = actual_path.stat().st_size
        if actual_size != expected["size_bytes"]:
            raise ValueError(
                f"Upstream file size differs for {path}: "
                f"expected {expected['size_bytes']}, got {actual_size}"
            )
        if sha256(actual_path) != expected["sha256"]:
            raise ValueError(f"Upstream file SHA-256 differs for {path}")
        _, disposition, _, _, _, _ = upstream_classification(actual_path)
        if disposition != expected["disposition"]:
            raise ValueError(f"Upstream disposition differs for {path}")


def generate() -> dict[str, object]:
    assets = [
        *(asset(path, scope="upstream") for path in discover_upstream()),
        *(asset(path, scope="local") for path in discover_local()),
    ]
    counts: dict[str, int] = {}
    for item in assets:
        counts[item.disposition] = counts.get(item.disposition, 0) + 1
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "generation_mode": (
            "filesystem metadata only for local payloads; SHA-256 for "
            "preserved upstream snapshot"
        ),
        "upstream_commit": UPSTREAM_COMMIT,
        "asset_count": len(assets),
        "upstream_asset_count": sum(
            item.scope == "upstream" for item in assets
        ),
        "local_asset_count": sum(item.scope == "local" for item in assets),
        "disposition_counts": dict(sorted(counts.items())),
        "assets": [asdict(item) for item in assets],
    }


def write_outputs(inventory: dict[str, object]) -> None:
    JSON_OUTPUT.write_text(
        json.dumps(inventory, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    rows_value = inventory["assets"]
    if not isinstance(rows_value, list):
        raise TypeError("Inventory assets must be a list")
    row_values = cast("list[object]", rows_value)
    rows: list[dict[str, object]] = []
    for row_value in row_values:
        if not isinstance(row_value, dict):
            raise TypeError("Inventory contains a non-mapping asset row")
        candidate = cast("dict[object, object]", row_value)
        if not all(isinstance(key, str) for key in candidate):
            raise ValueError("Inventory asset row has a non-string key")
        rows.append(cast("dict[str, object]", row_value))
    if not rows:
        raise ValueError("Inventory has no asset rows")
    with CSV_OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer: csv.DictWriter[str] = csv.DictWriter(
            handle, fieldnames=list(rows[0].keys())
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Verify the immutable upstream tree without requiring local-only "
            "payloads."
        ),
    )
    parser.add_argument(
        "--check-local",
        action="store_true",
        help=(
            "Also require governed local-only assets and compare the full "
            "inventory."
        ),
    )
    args = parser.parse_args()
    if args.check:
        committed = json.loads(JSON_OUTPUT.read_text(encoding="utf-8"))
        verify_upstream_tree(committed)
        if not args.check_local:
            return
        missing_local = [
            path.as_posix()
            for path in (*LOCAL_ROOTS, *LOCAL_FILES)
            if not (PROJECT_ROOT / path).exists()
        ]
        if missing_local:
            raise SystemExit(
                "Required local inventory assets are missing: "
                + ", ".join(missing_local)
            )
        inventory = generate()
        for volatile in ("generated_at",):
            committed.pop(volatile, None)
            inventory.pop(volatile, None)
        if committed != inventory:
            raise SystemExit("NZ asset inventory is stale; regenerate it.")
        return
    inventory = generate()
    write_outputs(inventory)


if __name__ == "__main__":
    main()
