"""Validate an offline preregistration rehearsal without external access."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_bundle(bundle: Path) -> None:
    """Fail unless schemas, gates, declared files, and digests are valid."""
    package = _load(bundle / "01-structured-responses.json")
    package_schema = _load(ROOT / "schemas/osf-preregistration-package-v1.json")
    Draft202012Validator.check_schema(package_schema)
    Draft202012Validator(package_schema).validate(  # pyright: ignore[reportUnknownMemberType]
        package
    )
    manifest = _load(bundle / "osf-submission-manifest.json")
    manifest_schema = _load(ROOT / "schemas/osf-submission-manifest-v1.json")
    Draft202012Validator.check_schema(manifest_schema)
    Draft202012Validator(manifest_schema).validate(  # pyright: ignore[reportUnknownMemberType]
        manifest
    )
    if (
        package["external_actions_permitted"]
        or package["maintainer_review"]["complete"]
    ):
        raise ValueError(
            "offline rehearsal must preserve submission and review gates"
        )
    expected_names = {item["path"] for item in manifest["artifacts"]}
    actual_names = {path.name for path in bundle.iterdir() if path.is_file()}
    if actual_names != expected_names | {"osf-submission-manifest.json"}:
        raise ValueError("bundle files differ from the submission manifest")
    for item in manifest["artifacts"]:
        content = (bundle / item["path"]).read_bytes()
        if len(content) != item["bytes"]:
            raise ValueError(f"byte count mismatch: {item['path']}")
        if hashlib.sha256(content).hexdigest() != item["sha256"]:
            raise ValueError(f"checksum mismatch: {item['path']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bundle",
        type=Path,
        default=ROOT / "research/preregistration/submission",
    )
    arguments = parser.parse_args()
    validate_bundle(arguments.bundle.resolve())
    print(
        f"validated offline preregistration bundle: {arguments.bundle.resolve()}"
    )


if __name__ == "__main__":
    main()
