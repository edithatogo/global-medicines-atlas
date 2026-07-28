"""Validate maintainer-owned ecosystem reuse and anti-duplication policy."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import TypedDict, cast

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REGISTRY = PROJECT_ROOT / ".context" / "ecosystem.toml"
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
ALLOWED_DISPOSITIONS = {
    "adopt-pattern",
    "consume-contract",
    "evaluate",
    "extend-in-place",
    "integrated",
    "interoperate",
}


class EcosystemReceipt(TypedDict):
    github_resources: int
    hugging_face_resources: int
    authorities: int
    licence_reviews: int
    status: str


def _tables(
    document: dict[str, object], key: str
) -> tuple[dict[str, object], ...]:
    value = document.get(key)
    if not isinstance(value, list):
        raise TypeError(f"{key} must be an array of tables")
    tables: list[dict[str, object]] = []
    for item in cast("list[object]", value):
        if not isinstance(item, dict):
            raise TypeError(f"{key} must be an array of tables")
        tables.append(cast("dict[str, object]", item))
    return tuple(tables)


def validate_ecosystem() -> EcosystemReceipt:
    """Return a receipt or fail when ownership and reuse boundaries drift."""
    with REGISTRY.open("rb") as stream:
        document = tomllib.load(stream)
    owner = document.get("owner")
    if owner != "edithatogo" or document.get("policy") != "reuse-before-build":
        raise ValueError(
            "Ecosystem owner and reuse-before-build policy are mandatory"
        )

    github = _tables(document, "github")
    hugging_face = _tables(document, "hugging_face")
    resources = (*github, *hugging_face)
    required = {
        "id",
        "repository",
        "url",
        "snapshot",
        "licence",
        "authority",
        "disposition",
    }
    for resource in resources:
        missing = required.difference(resource)
        if missing:
            raise ValueError(
                f"Ecosystem resource missing fields: {sorted(missing)}"
            )
        repository = resource["repository"]
        if not isinstance(repository, str) or not repository.startswith(
            f"{owner}/"
        ):
            raise ValueError(f"Resource is not maintainer-owned: {repository}")
        if resource["disposition"] not in ALLOWED_DISPOSITIONS:
            raise ValueError(
                f"Unsupported disposition: {resource['disposition']}"
            )

    github_snapshots = tuple(resource["snapshot"] for resource in github)
    if any(
        not isinstance(value, str) or not SHA_PATTERN.fullmatch(value)
        for value in github_snapshots
    ):
        raise ValueError("GitHub resources require immutable commit snapshots")

    authorities = tuple(str(resource["authority"]) for resource in resources)
    if len(authorities) != len(set(authorities)):
        raise ValueError(
            "Each reusable capability must have one declared authority"
        )

    integrated = (
        resource
        for resource in github
        if resource["disposition"] == "integrated"
    )
    for resource in integrated:
        boundary = PROJECT_ROOT / str(resource.get("local_boundary", ""))
        if not boundary.exists():
            raise FileNotFoundError(f"Integrated boundary missing: {boundary}")

    receipt: EcosystemReceipt = {
        "github_resources": len(github),
        "hugging_face_resources": len(hugging_face),
        "authorities": len(authorities),
        "licence_reviews": sum(
            resource["licence"] in {"other", "review-required"}
            for resource in resources
        ),
        "status": "pass",
    }
    output = PROJECT_ROOT / "build" / "ecosystem-validation.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return receipt


def main() -> None:
    """Validate the registry and print its bounded receipt."""
    print(json.dumps(validate_ecosystem(), sort_keys=True))


if __name__ == "__main__":
    main()
