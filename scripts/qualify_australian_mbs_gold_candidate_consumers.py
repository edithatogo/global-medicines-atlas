"""Qualify all current consumers of the pinned MBS Gold edge candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, cast

from qualify_australian_mbs_gold_real_silver import (
    ADMISSION_PATH,
    ROOT,
    SEMANTIC_PATH,
    _read_json,  # ruff: ignore[import-private-name] -- reuse qualifier  # pyright: ignore[reportPrivateUsage]
)
from qualify_australian_mbs_gold_real_silver import (
    OUTPUT_PATH as QUALIFICATION_PATH,
)

from global_medicines_atlas.atlas_browser_qualification import (
    qualify_candidate_atlas_browser,
)
from global_medicines_atlas.mbs_gold_consumer_qualification import (
    qualify_consumers,
)

V4_USE_AUTHORIZATION_PATH = Path(
    "quality/qualifications/"
    "australian-mbs-v4-candidate-use-authorization-20261017.json"
)
EXPECTED_V4_OBJECT_COUNT = 6


def candidate_v4_use_binding(
    admission: dict[str, Any],
    authorization: dict[str, Any],
    authorization_sha256: str,
) -> dict[str, object]:
    """Bind the maintainer's exact six-object candidate-use scope."""
    expected_authorization_keys = {
        "schema_id",
        "schema_version",
        "decision",
        "decision_by",
        "recorded_at",
        "source_identity",
        "dataset_identity",
        "scope",
        "authorized_objects",
        "boundaries",
    }
    if (
        authorization.get("schema_id")
        != "global-medicines-atlas.australian-mbs-v4-candidate-use-authorization"
        or authorization.get("schema_version") != 1
        or set(authorization) != expected_authorization_keys
    ):
        raise ValueError("candidate v4 authorization contract changed")
    if authorization.get("decision") != (
        "Authorize the exact six for candidate v4 qualification"
    ):
        raise ValueError("candidate v4 authorization decision is missing")
    if authorization.get("decision_by") != "maintainer":
        raise ValueError("candidate v4 authorization is not maintainer-issued")
    expected_scope = (
        "exact_six_july_2025_mbs_v3_silver_objects_for_candidate_v4_"
        "qualification_and_consumer_canaries"
    )
    if authorization.get("scope") != expected_scope:
        raise ValueError("candidate v4 authorization scope changed")
    source = admission.get("source_identity")
    public = admission.get("public_dataset_identity")
    if not isinstance(source, dict) or not isinstance(public, dict):
        raise TypeError("Silver admission identity is incomplete")
    source = cast("dict[str, Any]", source)
    public = cast("dict[str, Any]", public)
    if authorization.get("source_identity") != {
        "source_id": source.get("source_id"),
        "schema_era": source.get("schema_era"),
        "source_sha256": source.get("source_sha256"),
    }:
        raise ValueError("authorization source identity differs from admission")
    authorized_dataset = authorization.get("dataset_identity")
    if authorized_dataset != {
        "dataset": public.get("dataset"),
        "revision": public.get("current_revision"),
        "manifest_sha256": public.get("manifest_sha256"),
        "candidate_only": True,
    }:
        raise ValueError(
            "authorization dataset identity differs from admission"
        )
    tables = admission.get("tables")
    objects = authorization.get("authorized_objects")
    if not isinstance(tables, list) or not isinstance(objects, list):
        raise TypeError("authorization object list is missing")
    untyped_tables = cast("list[object]", tables)
    untyped_objects = cast("list[object]", objects)
    if any(not isinstance(item, dict) for item in untyped_tables) or any(
        not isinstance(item, dict) for item in untyped_objects
    ):
        raise TypeError("authorization contains an invalid object identity")
    table_records = cast("list[dict[str, Any]]", tables)
    authorized_objects = cast("list[dict[str, Any]]", objects)
    expected_objects = sorted(
        [
            {
                "name": item.get("name"),
                "path": item.get("path"),
                "sha256": item.get("sha256"),
                "byte_count": item.get("byte_count"),
            }
            for item in table_records
        ],
        key=lambda item: str(item["name"]),
    )
    actual_objects = sorted(
        authorized_objects, key=lambda item: str(item.get("name"))
    )
    if (
        len(expected_objects) != EXPECTED_V4_OBJECT_COUNT
        or actual_objects != expected_objects
    ):
        raise ValueError(
            "authorization must match the exact six Silver objects"
        )
    expected_boundaries = {
        "candidate_v4_qualification": True,
        "candidate_consumer_canaries": True,
        "public_release_or_publication": False,
        "production_admission_or_promotion": False,
        "new_rights_or_licensing_conclusion": False,
        "m110_gold_review_or_acceptance": False,
        "m112_federation_acceptance": False,
        "source_coverage_expansion": False,
    }
    if authorization.get("boundaries") != expected_boundaries:
        raise ValueError("candidate v4 authorization boundaries changed")
    return {
        "path": V4_USE_AUTHORIZATION_PATH.as_posix(),
        "sha256": authorization_sha256,
        "scope": expected_scope,
        "authorized_object_count": EXPECTED_V4_OBJECT_COUNT,
        "candidate_only": True,
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--edge-file", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    output = args.output.expanduser()
    qualification: dict[str, Any] = _read_json(QUALIFICATION_PATH)
    authorization = _read_json(V4_USE_AUTHORIZATION_PATH)
    admission = _read_json(ADMISSION_PATH)
    authorization_binding = candidate_v4_use_binding(
        admission,
        authorization,
        _sha256(ROOT / V4_USE_AUTHORIZATION_PATH),
    )
    receipt = qualify_consumers(
        args.edge_file.expanduser(),
        qualification,
        expected_bindings={
            "input_admission_sha256": _sha256(ROOT / ADMISSION_PATH),
            "input_semantic_manifest_sha256": _sha256(ROOT / SEMANTIC_PATH),
            "graph_sha256": cast("str", qualification["graph"]["graph_sha256"]),
        },
        browser_qualifier=qualify_candidate_atlas_browser,
    )
    receipt["candidate_v4_use_authorization"] = authorization_binding
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
        stream.write("\n")
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
