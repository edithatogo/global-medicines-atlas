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
    cases.append((changed, "payload paths must be unique"))

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
    "receipt",
    [
        "receipts/mbs-../../unrelated.json",
        "receipts//mbs-202608.json",
        "receipts%2fmbs-202608.json",
    ],
)
def test_requires_safe_content_addressed_receipt(receipt: str) -> None:
    document = _fixture("valid-mbs.json")
    document["provenance"]["receipt"] = receipt
    with pytest.raises(SourceMetadataError, match="receipt path must be safe"):
        validate_source_metadata(document)


@pytest.mark.parametrize(
    ("fixture", "url"),
    [
        (
            "valid-mbs.json",
            "https://www.mbsonline.gov.au/internet/mbsonline/publishing.nsf/Content/Downloads-202607",
        ),
        (
            "valid-pbs.json",
            "https://www.pbs.gov.au/browse/downloads-impersonation",
        ),
    ],
)
def test_binds_source_url_to_exact_profile_release(
    fixture: str, url: str
) -> None:
    document = _fixture(fixture)
    document["source"]["source_url"] = url
    with pytest.raises(SourceMetadataError, match="wrong source URL surface"):
        validate_source_metadata(document)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("coverage-exclusion", "exclusions are not approved"),
        ("payload-control", "payload path must be safe"),
        ("receipt-control", "receipt path must be safe"),
        ("source-version-alias", "canonical YYYY-MM"),
        ("media-type", "media type mismatch"),
        ("cross-source-citation", "wrong source dataset"),
    ],
)
def test_rejects_hostile_metadata_aliases(mutation: str, message: str) -> None:
    document = _fixture("valid-mbs.json")
    if mutation == "coverage-exclusion":
        document["coverage"]["exclusions"] = ["Absence proves non-approval."]
    elif mutation == "payload-control":
        document["provenance"]["payloads"][0]["path"] = "raw/file\x00.xml"
    elif mutation == "receipt-control":
        document["provenance"]["receipt"] = "receipts/mbs-foo\x00.json"
    elif mutation == "source-version-alias":
        document["source"]["source_version"] = "2026--08"
        document["data_card"]["version"] = "2026--08"
        document["croissant"]["version"] = "2026--08"
        document["version_history"][0]["source_version"] = "2026--08"
    elif mutation == "media-type":
        document["croissant"]["distributions"][0]["encoding_format"] = (
            "application/zip"
        )
    else:
        citation = deepcopy(document["citations"][0])
        citation["dataset"] = "edithatogo/australian-pbs-source-archive"
        document["citations"].append(citation)
    with pytest.raises(SourceMetadataError, match=message):
        validate_source_metadata(document)


def test_binds_pbs_version_and_effective_date_to_release() -> None:
    document = _fixture("valid-pbs.json")
    for target in (
        document["source"],
        document["data_card"],
        document["croissant"],
    ):
        target[
            "source_version" if target is document["source"] else "version"
        ] = "not-a-version"
    document["version_history"][0]["source_version"] = "not-a-version"
    with pytest.raises(SourceMetadataError, match="canonical YYYY-MM"):
        validate_source_metadata(document)

    document = _fixture("valid-pbs.json")
    document["source"]["effective_from"] = "1990-01-01"
    document["version_history"][0]["effective_from"] = "1990-01-01"
    with pytest.raises(
        SourceMetadataError, match="date does not match its source version"
    ):
        validate_source_metadata(document)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("wrong-release", "does not match the approved release"),
        ("retrieval", "does not match acquisition evidence"),
        ("history", "non-canonical source version"),
        ("future-history", "cannot include a future release"),
        ("unobserved-history", "requires observed release evidence"),
        ("citation", "absent from version history"),
    ],
)
def test_binds_all_release_identities(mutation: str, message: str) -> None:
    document = _fixture("valid-pbs.json")
    if mutation == "wrong-release":
        document["source"]["source_version"] = "1990-01"
        document["data_card"]["version"] = "1990-01"
        document["croissant"]["version"] = "1990-01"
        document["version_history"][0]["source_version"] = "1990-01"
    elif mutation == "retrieval":
        document["source"]["retrieved_at"] = "2099-01-01T00:00:00Z"
        document["data_card"]["created_at"] = "2099-01-01T00:00:00Z"
    elif mutation == "history":
        document["version_history"].append({
            "revision": "f" * 40,
            "source_version": "not-a-version",
            "effective_from": "2099-01-01",
            "status": "superseded",
        })
    elif mutation == "future-history":
        document["version_history"].append({
            "revision": "f" * 40,
            "source_version": "2026-05",
            "effective_from": "2026-05-01",
            "status": "superseded",
        })
    elif mutation == "unobserved-history":
        document["version_history"].append({
            "revision": "f" * 40,
            "source_version": "1900-01",
            "effective_from": "1900-01-01",
            "status": "superseded",
        })
    else:
        citation = deepcopy(document["citations"][0])
        citation["revision"] = "f" * 40
        document["citations"].append(citation)
    with pytest.raises(SourceMetadataError, match=message):
        validate_source_metadata(document)


def test_binds_payload_and_receipt_to_observed_release() -> None:
    document = _fixture("valid-mbs.json")
    payload = {"path": "raw/pbs-202604.zip", "sha256": "b" * 64}
    document["provenance"]["payloads"] = [payload]
    document["croissant"]["distributions"] = [
        {**payload, "encoding_format": "application/zip"}
    ]
    document["coverage"]["payload_paths"] = [payload["path"]]
    with pytest.raises(SourceMetadataError, match="observed source release"):
        validate_source_metadata(document)

    document = _fixture("valid-mbs.json")
    document["provenance"]["receipt"] = "receipts/mbs-190001.json"
    document["provenance"]["receipt_sha256"] = "e" * 64
    with pytest.raises(SourceMetadataError, match="observed source release"):
        validate_source_metadata(document)


@pytest.mark.parametrize(
    ("field", "url"),
    [
        ("authority_url", "https://user:secret@www.health.gov.au/"),
        ("source_url", "https://user@www.mbsonline.gov.au/"),
    ],
)
def test_rejects_url_userinfo(field: str, url: str) -> None:
    document = _fixture("valid-mbs.json")
    document["source"][field] = url
    with pytest.raises(SourceMetadataError, match="must not contain userinfo"):
        validate_source_metadata(document)


def test_rejects_cross_source_hosts_and_ambiguous_paths() -> None:
    document = _fixture("valid-mbs.json")
    document["source"]["authority_url"] = "https://example.test/authority"
    with pytest.raises(SourceMetadataError, match="wrong authority host"):
        validate_source_metadata(document)

    document = _fixture("valid-mbs.json")
    document["source"]["authority"] = "Unrelated authority"
    with pytest.raises(SourceMetadataError, match="wrong authority identity"):
        validate_source_metadata(document)

    document = _fixture("valid-mbs.json")
    document["source"]["source_url"] = "https://www.pbs.gov.au/browse/downloads"
    with pytest.raises(SourceMetadataError, match="wrong source host"):
        validate_source_metadata(document)

    document = _fixture("valid-mbs.json")
    document["citations"][0]["source_url"] = "https://example.test/mbs"
    with pytest.raises(
        SourceMetadataError, match="outside the approved source"
    ):
        validate_source_metadata(document)

    document = _fixture("valid-mbs.json")
    second = deepcopy(document["provenance"]["payloads"][0])
    second["sha256"] = "e" * 64
    document["provenance"]["payloads"].append(second)
    document["croissant"]["distributions"].append({
        **second,
        "encoding_format": "application/xml",
    })
    document["coverage"]["payload_paths"].append(second["path"])
    with pytest.raises(
        SourceMetadataError, match="payload paths must be unique"
    ):
        validate_source_metadata(document)


@pytest.mark.parametrize(
    "unsafe_path",
    [
        "/raw/mbs.xml",
        "../mbs.xml",
        "raw\\mbs.xml",
        "%2e%2e/mbs.xml",
        "raw%5cmbs.xml",
        "raw%2fmbs.xml",
        ".",
    ],
)
def test_rejects_unsafe_payload_paths(unsafe_path: str) -> None:
    document = _fixture("valid-mbs.json")
    document["provenance"]["payloads"][0]["path"] = unsafe_path
    with pytest.raises(SourceMetadataError, match="payload path must be safe"):
        validate_source_metadata(document)


@pytest.mark.parametrize(
    ("field_path", "value"),
    [
        (("revision",), " 75f9f20a36ddb829dfe0ca88660664570782be02"),
        (("dataset",), "edithatogo/australian-mbs-source-archive "),
        (("provenance", "payloads", 0, "sha256"), "a" * 64 + "\n"),
        (("provenance", "payloads", 0, "path"), " raw/mbs-202608.xml"),
    ],
)
def test_rejects_padded_exact_identities(
    field_path: tuple[str | int, ...], value: str
) -> None:
    document = _fixture("valid-mbs.json")
    target: Any = document
    for part in field_path[:-1]:
        target = target[part]
    target[field_path[-1]] = value
    with pytest.raises(SourceMetadataError, match="must not be padded"):
        validate_source_metadata(document)


@pytest.mark.parametrize("alias", ["raw/./mbs.xml", "raw//mbs.xml"])
def test_rejects_noncanonical_payload_path_aliases(alias: str) -> None:
    document = _fixture("valid-mbs.json")
    document["provenance"]["payloads"][0]["path"] = alias
    with pytest.raises(SourceMetadataError, match="safe and relative"):
        validate_source_metadata(document)


def test_bounds_citation_records_before_semantic_iteration() -> None:
    document = _fixture("valid-mbs.json")
    document["citations"] *= 33
    with pytest.raises(SourceMetadataError, match="at most 32 items"):
        validate_source_metadata(document)


def test_binds_rights_evidence_to_source_profile() -> None:
    document = _fixture("valid-mbs.json")
    document["rights"]["permission_reference"] = "https://example.test/claim"
    with pytest.raises(
        SourceMetadataError, match="rights evidence does not match"
    ):
        validate_source_metadata(document)

    document = _fixture("valid-mbs.json")
    document["rights"]["attribution"] = "Unrelated publisher"
    with pytest.raises(
        SourceMetadataError, match="rights evidence does not match"
    ):
        validate_source_metadata(document)


@pytest.mark.parametrize("field", ["intended_uses", "limitations"])
def test_bounds_data_card_collections(field: str) -> None:
    document = _fixture("valid-mbs.json")
    document["data_card"][field] *= 33
    with pytest.raises(SourceMetadataError, match="at most 32 items"):
        validate_source_metadata(document)


def test_binds_data_card_claims_to_source_profile() -> None:
    document = _fixture("valid-mbs.json")
    document["data_card"]["intended_uses"] = ["Clinical decisions"]
    with pytest.raises(SourceMetadataError, match="claims do not match"):
        validate_source_metadata(document)

    document = _fixture("valid-mbs.json")
    document["data_card"]["limitations"] = [
        "Missing coverage proves non-approval."
    ]
    with pytest.raises(SourceMetadataError, match="claims do not match"):
        validate_source_metadata(document)


def test_binds_data_card_summary_to_source_profile() -> None:
    document = _fixture("valid-mbs.json")
    document["data_card"]["summary"] = "Missing coverage proves non-approval."
    with pytest.raises(SourceMetadataError, match="claims do not match"):
        validate_source_metadata(document)


def test_requires_https_for_public_metadata_urls() -> None:
    document = _fixture("valid-mbs.json")
    document["source"]["authority_url"] = "http://www.health.gov.au/"
    with pytest.raises(SourceMetadataError, match="must use HTTPS"):
        validate_source_metadata(document)


def test_restricts_correction_route_to_approved_repository() -> None:
    document = _fixture("valid-mbs.json")
    document["maintenance"]["correction_url"] = (
        "https://example.test/collect-corrections"
    )
    with pytest.raises(
        SourceMetadataError, match="outside the approved repository"
    ):
        validate_source_metadata(document)


def test_rejects_remaining_profile_surface_mismatches() -> None:
    base = _fixture("valid-mbs.json")
    cases: list[tuple[dict[str, Any], str]] = []

    mutations = (
        (
            ("source", "authority_url"),
            "https://www.health.gov.au/about-us",
            "wrong authority URL",
        ),
        (
            ("source", "source_url"),
            "https://www.mbsonline.gov.au/unrelated",
            "wrong source URL surface",
        ),
        (
            ("citations", 0, "source_url"),
            "https://www.mbsonline.gov.au/unrelated",
            "wrong source URL surface",
        ),
        (("data_card", "version"), "2026-07", "versions must match"),
        (
            ("rights", "reviewed_at"),
            "2026-08-31",
            "rights review cannot follow",
        ),
        (("coverage", "scope"), "All MBS history", "coverage scope"),
        (
            ("provenance", "receipt"),
            "receipts/pbs-202608.json",
            "receipt does not match",
        ),
        (
            ("provenance", "receipt"),
            "receipts/mbs-202608.txt",
            "receipt does not match",
        ),
        (
            ("citations", 0, "accessed_at"),
            "2026-08-31",
            "citation access cannot follow",
        ),
        (
            ("maintenance", "withdrawal_policy"),
            "Never withdraw",
            "withdrawal policy",
        ),
    )
    for path, value, message in mutations:
        changed = deepcopy(base)
        target: Any = changed
        for part in path[:-1]:
            target = target[part]
        target[path[-1]] = value
        cases.append((changed, message))

    for document, message in cases:
        with pytest.raises(SourceMetadataError, match=message):
            validate_source_metadata(document)
