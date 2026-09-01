from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pytest

from global_medicines_atlas.federation_source_metadata import (
    SourceMetadataError,
    validate_source_metadata,
)

FIXTURES = Path(__file__).parent / "fixtures" / "federation_source_metadata"


def _fixture(name: str) -> dict[str, Any]:
    document = cast("dict[str, Any]", json.loads((FIXTURES / name).read_text()))
    if "$base" not in document:
        return document
    base = cast(
        "dict[str, Any]",
        json.loads((FIXTURES / document["$base"]).read_text()),
    )
    for dotted_path, value in document["$set"].items():
        target: Any = base
        parts = dotted_path.split(".")
        for part in parts[:-1]:
            if isinstance(target, list):
                target = cast("list[Any]", target)[int(part)]
            else:
                target = cast("dict[str, Any]", target)[part]
        if isinstance(target, list):
            target[int(parts[-1])] = value
        else:
            target[parts[-1]] = value
    return base


@pytest.mark.parametrize("name", ["valid-mbs.json", "valid-pbs.json"])
def test_source_metadata_valid_fixtures(name: str) -> None:
    document = _fixture(name)
    result = validate_source_metadata(document)
    assert result.dataset == document["dataset"]
    assert result.revision == document["revision"]
    assert result.source_ids == (document["source"]["source_id"],)


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("invalid-generic-card.json", "source-specific title"),
        ("invalid-croissant-digest.json", "Croissant distribution mismatch"),
        (
            "invalid-citation.json",
            "citation must identify this dataset revision",
        ),
        ("invalid-version-history.json", "current revision exactly once"),
    ],
)
def test_source_metadata_invalid_fixtures(name: str, message: str) -> None:
    document = _fixture(name)
    with pytest.raises(SourceMetadataError, match=message):
        validate_source_metadata(document)


def test_rejects_cross_source_dataset_alias() -> None:
    document = json.loads((FIXTURES / "valid-mbs.json").read_text())
    document["dataset"] = "edithatogo/australian-pbs-source-archive"
    with pytest.raises(SourceMetadataError, match="approved dataset"):
        validate_source_metadata(document)


def test_rejects_uncovered_payload() -> None:
    document = json.loads((FIXTURES / "valid-pbs.json").read_text())
    document["coverage"]["payload_paths"] = []
    with pytest.raises(SourceMetadataError, match="payload denominator"):
        validate_source_metadata(document)


def test_rejects_unresolved_rights_or_missing_correction_route() -> None:
    document = json.loads((FIXTURES / "valid-pbs.json").read_text())
    document["rights"]["permission_state"] = "unresolved"
    with pytest.raises(
        SourceMetadataError, match="permission must be approved"
    ):
        validate_source_metadata(document)

    document = json.loads((FIXTURES / "valid-pbs.json").read_text())
    document["maintenance"]["correction_url"] = document["source"][
        "authority_url"
    ]
    with pytest.raises(SourceMetadataError, match="correction route"):
        validate_source_metadata(document)


def test_rejects_provenance_or_temporal_mismatch() -> None:
    document = json.loads((FIXTURES / "valid-mbs.json").read_text())
    document["provenance"]["payloads"][0]["sha256"] = "f" * 64
    with pytest.raises(
        SourceMetadataError, match="Croissant distribution mismatch"
    ):
        validate_source_metadata(document)

    document = json.loads((FIXTURES / "valid-mbs.json").read_text())
    document["version_history"][0]["effective_from"] = "2026-09-01"
    with pytest.raises(SourceMetadataError, match="effective date mismatch"):
        validate_source_metadata(document)


def test_rejects_remaining_structural_aliases() -> None:
    base = _fixture("valid-mbs.json")
    cases: list[tuple[dict[str, Any], str]] = []

    changed = deepcopy(base)
    changed["croissant"]["name"] = "Generic source archive"
    cases.append((changed, "Croissant name requires"))

    changed = deepcopy(base)
    changed["provenance"]["payloads"].append(
        deepcopy(changed["provenance"]["payloads"][0])
    )
    cases.append((changed, "payload bindings must be unique"))

    changed = deepcopy(base)
    changed["coverage"]["exclusions"] = ["none", "none"]
    cases.append((changed, "coverage exclusions must be unique"))

    changed = deepcopy(base)
    changed["version_history"][0]["source_version"] = "2026-07"
    cases.append((changed, "source version mismatch"))

    changed = deepcopy(base)
    changed["version_history"].append({
        **deepcopy(changed["version_history"][0]),
        "status": "superseded",
    })
    cases.append((changed, "version history revisions must be unique"))

    for document, message in cases:
        with pytest.raises(SourceMetadataError, match=message):
            validate_source_metadata(document)


@pytest.mark.parametrize(
    "unsafe_path", ["/raw/mbs.xml", "../mbs.xml", "raw\\mbs.xml"]
)
def test_rejects_unsafe_payload_paths(unsafe_path: str) -> None:
    document = _fixture("valid-mbs.json")
    document["provenance"]["payloads"][0]["path"] = unsafe_path
    with pytest.raises(SourceMetadataError, match="payload path must be safe"):
        validate_source_metadata(document)
