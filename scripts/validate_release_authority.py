"""Validate one exact, independently approved release action."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUTHORITY = (
    ROOT / "quality/qualifications/release-authority-v1.0.0rc1.json"
)
SCHEMA = ROOT / "schemas/release-authority-v1.json"


def validate_release_authority(
    *,
    authority_path: Path,
    tag: str,
    release_type: str,
    artifact_scope: str,
) -> dict[str, object]:
    """Fail unless runtime inputs equal the exact approved release contract."""

    authority = json.loads(authority_path.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    ).validate(authority)  # pyright: ignore[reportUnknownMemberType]
    expected = {
        "approved_tag": tag,
        "release_type": release_type,
        "artifact_scope": artifact_scope,
    }
    mismatches = [
        name
        for name, observed in expected.items()
        if authority[name] != observed
    ]
    if mismatches:
        raise ValueError(
            "release action is not approved: " + ", ".join(mismatches)
        )
    evidence = ROOT / str(authority["approval_evidence"])
    if not evidence.is_file():
        raise ValueError("release approval evidence is missing")
    return authority


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authority", type=Path, default=DEFAULT_AUTHORITY)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--release-type", required=True)
    parser.add_argument("--artifact-scope", required=True)
    args = parser.parse_args(argv)
    authority = validate_release_authority(
        authority_path=args.authority,
        tag=args.tag,
        release_type=args.release_type,
        artifact_scope=args.artifact_scope,
    )
    print(json.dumps(authority, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
