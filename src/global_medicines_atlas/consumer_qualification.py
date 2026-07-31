"""Fail-closed package and public OpenAPI compatibility qualification."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from importlib.metadata import metadata, version
from typing import Any, cast

PACKAGE_NAME = "global-medicines-atlas"
REQUIRED_METADATA = ("Name", "Version", "Summary", "Requires-Python")
HTTP_METHODS = frozenset({"get", "head", "options"})


class CompatibilityError(ValueError):
    """The installed package or public API violates its stable contract."""


@dataclass(frozen=True)
class PackageIdentity:
    """Consumer-visible installed distribution identity."""

    name: str
    version: str
    summary: str
    requires_python: str


def installed_package_identity() -> PackageIdentity:
    """Read and validate metadata from the installed wheel or source archive."""
    values = metadata(PACKAGE_NAME)
    missing = [field for field in REQUIRED_METADATA if not values.get(field)]
    if missing:
        raise CompatibilityError(
            f"installed package metadata is incomplete: {', '.join(missing)}"
        )
    installed_version = version(PACKAGE_NAME)
    if values["Version"] != installed_version:
        raise CompatibilityError("metadata and runtime versions disagree")
    return PackageIdentity(
        name=values["Name"],
        version=installed_version,
        summary=values["Summary"],
        requires_python=values["Requires-Python"],
    )


def assert_openapi_compatible(
    baseline: Mapping[str, Any], current: Mapping[str, Any]
) -> None:
    """Reject removals and mutation operations in the versioned public API."""
    baseline_paths_value = baseline.get("paths")
    current_paths_value = current.get("paths")
    if not isinstance(baseline_paths_value, dict) or not isinstance(
        current_paths_value, dict
    ):
        raise CompatibilityError("OpenAPI paths must be objects")
    baseline_paths = cast("dict[str, object]", baseline_paths_value)
    current_paths = cast("dict[str, object]", current_paths_value)
    removed_paths = sorted(set(baseline_paths) - set(current_paths))
    if removed_paths:
        raise CompatibilityError(
            f"public OpenAPI paths removed: {removed_paths}"
        )
    for path, baseline_value in baseline_paths.items():
        current_value = current_paths[path]
        if not isinstance(baseline_value, dict) or not isinstance(
            current_value, dict
        ):
            raise CompatibilityError(
                f"OpenAPI path item must be an object: {path}"
            )
        baseline_operations = cast("dict[str, dict[str, Any]]", baseline_value)
        current_operations = cast("dict[str, dict[str, Any]]", current_value)
        baseline_methods = HTTP_METHODS & set(baseline_operations)
        current_methods = HTTP_METHODS & set(current_operations)
        removed_methods = sorted(baseline_methods - current_methods)
        if removed_methods:
            raise CompatibilityError(
                f"public OpenAPI methods removed from {path}: {removed_methods}"
            )
        mutation_methods = {"post", "put", "patch", "delete"} & set(
            current_operations
        )
        if mutation_methods:
            raise CompatibilityError(
                f"mutation operations are forbidden on {path}: "
                f"{sorted(mutation_methods)}"
            )
        for method in baseline_methods:
            baseline_id = baseline_operations[method].get("operationId")
            current_id = current_operations[method].get("operationId")
            if baseline_id != current_id:
                raise CompatibilityError(
                    f"operation identity changed for {method.upper()} {path}"
                )
