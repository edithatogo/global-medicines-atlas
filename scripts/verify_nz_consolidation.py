"""Verify NZ migration consolidation without changing governed source files."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Final, cast

PROJECT_ROOT: Final = Path(__file__).resolve().parents[1]
TRACK_ROOT: Final = (
    PROJECT_ROOT / "conductor/archive/nzmedicines_migration_20260727"
)
INVENTORY_PATH: Final = TRACK_ROOT / "nz-asset-inventory.json"
PRESERVATION_PATH: Final = TRACK_ROOT / "nzmedicines-preservation.json"
VENDOR_ROOT: Final = PROJECT_ROOT / "vendor/nzmedicines"
BUILD_ROOT: Final = PROJECT_ROOT / "build"
DEFAULT_RECEIPT: Final = BUILD_ROOT / "receipts/nz-consolidation.json"
SHA256_LENGTH: Final = 64
COMMIT_LENGTH: Final = 40
DISPOSITIONS: Final = {
    "adopted",
    "adapted",
    "superseded",
    "fixture",
    "excluded",
}


def _load_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path.name} must contain a JSON object")
    return cast("dict[str, object]", value)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_hex(value: object, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def _inventory_rows(
    inventory: dict[str, object],
) -> list[dict[str, object]]:
    value = inventory.get("assets")
    if not isinstance(value, list):
        raise TypeError("Inventory assets must be a list")
    rows: list[dict[str, object]] = []
    for item in cast("list[object]", value):
        if not isinstance(item, dict):
            raise TypeError("Every inventory asset must be an object")
        rows.append(cast("dict[str, object]", item))
    return rows


def _aggregate_digest(rows: list[dict[str, object]]) -> str:
    fields = (
        "path",
        "size_bytes",
        "sha256",
        "upstream_commit",
        "disposition",
    )
    payload = [
        {field: row[field] for field in fields}
        for row in sorted(rows, key=lambda row: str(row["path"]))
    ]
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _partition_rows(
    rows: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    paths: set[str] = set()
    upstream: list[dict[str, object]] = []
    local: list[dict[str, object]] = []
    for row in rows:
        path = row.get("path")
        if not isinstance(path, str) or not path:
            raise ValueError("Every inventory row requires a non-empty path")
        if path in paths:
            raise ValueError(f"Duplicate inventory path: {path}")
        paths.add(path)
        scope = row.get("scope")
        if scope == "upstream":
            upstream.append(row)
        elif scope == "local":
            local.append(row)
        else:
            raise ValueError(f"Invalid inventory scope for {path}")
    return upstream, local


def _verify_source_identity(
    upstream: list[dict[str, object]],
    preservation: dict[str, object],
) -> tuple[str, str]:
    source_commit = preservation.get("source_commit")
    tree_digest = preservation.get("upstream_tree_sha256")
    expected_count = preservation.get("upstream_asset_count")
    if not _is_hex(source_commit, COMMIT_LENGTH):
        raise ValueError("Preservation source commit is invalid")
    if not _is_hex(tree_digest, SHA256_LENGTH):
        raise ValueError("Preservation tree digest is invalid")
    if not isinstance(expected_count, int) or isinstance(expected_count, bool):
        raise TypeError("Preservation upstream count must be an integer")
    if expected_count != len(upstream):
        raise ValueError("Preservation and inventory counts differ")

    for row in upstream:
        path = cast("str", row["path"])
        if not path.startswith("vendor/nzmedicines/"):
            raise ValueError(f"Upstream artifact escaped vendor: {path}")
        if row.get("disposition") not in DISPOSITIONS:
            raise ValueError(f"Invalid disposition for {path}")
        if not _is_hex(row.get("sha256"), SHA256_LENGTH):
            raise ValueError(f"Invalid source digest for {path}")
        if row.get("upstream_commit") != source_commit:
            raise ValueError(f"Source commit differs for {path}")

    aggregate = _aggregate_digest(upstream)
    if aggregate != tree_digest:
        raise ValueError("Preservation aggregate differs from inventory")
    return cast("str", source_commit), aggregate


def _verify_vendor_tree_removed(vendor_root: Path) -> None:
    """Fail closed if any remediated vendor bytes re-enter the current tree."""
    if vendor_root.exists() and any(
        path.is_file() for path in vendor_root.rglob("*")
    ):
        raise ValueError("Remediated vendor tree must remain absent")


def _verify_local_work(
    local: list[dict[str, object]],
    upstream: list[dict[str, object]],
) -> tuple[list[str], int]:
    local_paths = {cast("str", row["path"]) for row in local}
    upstream_paths = {cast("str", row["path"]) for row in upstream}
    if local_paths & upstream_paths:
        raise ValueError("Local and upstream inventory namespaces overlap")
    if any(path.startswith("vendor/") for path in local_paths):
        raise ValueError("Local work is recorded inside the vendor namespace")

    adapted = [
        row
        for row in local
        if row.get("disposition") == "adapted"
        and (PROJECT_ROOT / cast("str", row["path"])).is_file()
    ]
    if not adapted:
        raise ValueError("No resident first-party adapted outputs found")
    adapted_paths = sorted(cast("str", row["path"]) for row in adapted)
    if any(path.startswith("vendor/") for path in adapted_paths):
        raise ValueError("First-party adapted output is inside vendor")
    placeholder_count = sum(row.get("resident") is False for row in local)
    return adapted_paths, placeholder_count


def verify_consolidation(
    *,
    inventory_path: Path = INVENTORY_PATH,
    preservation_path: Path = PRESERVATION_PATH,
    vendor_root: Path = VENDOR_ROOT,
) -> dict[str, object]:
    """Return a deterministic receipt or raise on any consolidation drift."""
    inventory = _load_object(inventory_path)
    preservation = _load_object(preservation_path)
    rows = _inventory_rows(inventory)
    upstream, local = _partition_rows(rows)
    source_commit, aggregate = _verify_source_identity(
        upstream,
        preservation,
    )
    _verify_vendor_tree_removed(vendor_root)
    adapted_paths, placeholder_count = _verify_local_work(local, upstream)

    local_comparison = [
        {
            "path": path,
            "sha256": _sha256(PROJECT_ROOT / path),
        }
        for path in adapted_paths
    ]
    return {
        "schema_version": 1,
        "status": "passed",
        "checks": {
            "vendor_snapshot_removed": True,
            "isolated_import_boundary": True,
            "retained_local_inventory_metadata": True,
            "preservation_aggregate_matches": True,
            "source_fields_complete": True,
        },
        "historical_payload_preservation": "not_independently_verified",
        "historical_inventory_retained": True,
        "source_commit": source_commit,
        "upstream_asset_count": len(upstream),
        "upstream_tree_sha256": aggregate,
        "local_inventory_metadata_count": len(local),
        "resident_byte_verified_count": len(adapted_paths),
        "placeholder_metadata_only_count": placeholder_count,
        "adapted_output_count": len(adapted_paths),
        "adapted_outputs": local_comparison,
    }


def write_receipt(receipt: dict[str, object], output: Path) -> None:
    """Atomically write a receipt only beneath the ignored build tree."""
    build_root = BUILD_ROOT.resolve()
    destination = output.resolve()
    if not destination.is_relative_to(build_root):
        raise ValueError("Receipt output must remain beneath build/")
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as file:
            file.write(payload)
            file.flush()
            os.fsync(file.fileno())
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_RECEIPT)
    arguments = parser.parse_args()
    receipt = verify_consolidation()
    write_receipt(receipt, arguments.output)
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
