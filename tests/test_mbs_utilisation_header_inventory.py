from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from global_medicines_atlas import mbs_utilisation_header_inventory as module
from global_medicines_atlas.mbs_utilisation_header_inventory import (
    HeaderInventory,
    inventory_csv_header,
    load_header_inventory_contract,
    public_header_result,
)


def test_inventory_reads_only_first_record_and_hashes_canonical_header(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.csv"
    source.write_text(
        '"Year",ItemNumber\nnot,a,rectangular,row\n', encoding="utf-8"
    )

    result = inventory_csv_header(
        source,
        {"catalogue": ("Year", "ItemNumber")},
    )

    assert result.headers == ("Year", "ItemNumber")
    canonical = json.dumps(
        ["Year", "ItemNumber"], ensure_ascii=False, separators=(",", ":")
    ).encode()
    assert result.header_sha256 == hashlib.sha256(canonical).hexdigest()
    assert result.column_count == 2


def test_inventory_rejects_missing_empty_and_excessive_headers(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing.csv"
    missing.write_bytes(b"")
    empty = tmp_path / "empty.csv"
    empty.write_text(",\n", encoding="utf-8")
    excessive = tmp_path / "excessive.csv"
    excessive.write_text(",".join(f"c{i}" for i in range(10_001)) + "\n")

    for path in (missing, empty, excessive):
        with pytest.raises(ValueError, match="header"):
            inventory_csv_header(path, {})

    malformed = tmp_path / "malformed.csv"
    malformed.write_text('"unterminated', encoding="utf-8")
    with pytest.raises(ValueError, match="cannot be decoded"):
        inventory_csv_header(malformed, {})


def test_public_result_masks_unreviewed_header_tokens() -> None:
    result = inventory_csv_header_from_headers(
        ("Year", "NewPrivateColumn"),
        candidate_schemas={"compact": ("Year", "MonthofProcessing")},
    )

    public = public_header_result(
        result, frozenset({"Year", "MonthofProcessing"})
    )
    encoded = json.dumps(public)
    assert public["headers"] == ["Year"]
    assert public["unexpected_field_count"] == 1
    assert public["unexpected_headers_sha256"]
    assert "NewPrivateColumn" not in encoded
    assert public["schema_matches"] == []


def test_public_result_identifies_matching_candidate_schema() -> None:
    result = inventory_csv_header_from_headers(
        ("Year", "MonthofProcessing"),
        candidate_schemas={"compact": ("Year", "MonthofProcessing")},
    )

    public = public_header_result(
        result, frozenset({"Year", "MonthofProcessing"})
    )

    assert public["headers"] == ["Year", "MonthofProcessing"]
    assert public["unexpected_field_count"] == 0
    assert public["schema_matches"] == ["compact"]


def test_contract_selects_only_four_prior_verified_csvs_and_rejects_mutation(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[1]
    selected, schemas = load_header_inventory_contract(root)
    assert len(selected) == 4
    assert {
        row["raw_reference"]["path"].rsplit(".", 1)[-1] for row in selected
    } == {"csv"}
    assert len(schemas) == 4
    assert sorted(len(row["schema_candidate_ids"]) for row in selected) == [
        1,
        3,
        3,
        3,
    ]
    assert all(row["processing_admitted"] is False for row in selected)

    # Contract inputs are digest-pinned; a changed copy must fail closed.
    copied = tmp_path / "quality/qualifications"
    copied.mkdir(parents=True)
    (
        copied
        / "australian-mbs-utilisation-semantic-requirements-20261005.json"
    ).write_text("{}")
    with pytest.raises(ValueError, match="semantic requirements"):
        load_header_inventory_contract(tmp_path)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("duplicate_schema", "schema metadata"),
        ("schema_count", "exactly four reviewed"),
        ("unknown_resource", "no reviewed schema"),
        ("receipt_mismatch", "exact prior structural receipt"),
        ("receipt_url_mismatch", "exact prior structural receipt"),
        ("three_candidates", "exactly four distinct"),
        ("missing_receipt", "exact prior structural receipt"),
    ],
)
def test_contract_rejects_schema_receipt_and_scope_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    message: str,
) -> None:
    root = Path(__file__).resolve().parents[1]
    requirements = json.loads(
        (root / module.SEMANTIC_REQUIREMENTS_PATH).read_text()
    )
    structural = json.loads((root / module.STRUCTURAL_RECEIPT_PATH).read_text())
    selected = next(
        row
        for row in requirements["records"]
        if row["resource_id"] == "ff6d0692-4c6f-466b-9d93-015224d80b14"
    )
    if mutation == "duplicate_schema":
        requirements["csv_schema_metadata_snapshots"][1]["resource_id"] = (
            selected["resource_id"]
        )
    elif mutation == "schema_count":
        requirements["csv_schema_metadata_snapshots"].pop()
    elif mutation == "unknown_resource":
        selected["resource_id"] = "unreviewed-resource"
    elif mutation == "receipt_mismatch":
        receipt = next(
            item["document"]
            for item in structural["per_object_receipts"]
            if item["document"]["raw_reference"]["path"]
            == selected["raw_reference"]["path"]
        )
        receipt["acquisition_id"] = "0" * 64
    elif mutation == "receipt_url_mismatch":
        selected["structural_receipt_url"] = (
            "https://github.com/unreviewed/receipt"
        )
    elif mutation == "three_candidates":
        selected["hosted_inventory_candidate"] = False
    elif mutation == "missing_receipt":
        structural["per_object_receipts"] = [
            item
            for item in structural["per_object_receipts"]
            if item["document"]["raw_reference"]["path"]
            != selected["raw_reference"]["path"]
        ]

    contract = tmp_path / "quality/qualifications"
    contract.mkdir(parents=True)
    req_bytes = json.dumps(requirements).encode()
    structural_bytes = json.dumps(structural).encode()
    (contract / module.SEMANTIC_REQUIREMENTS_PATH.name).write_bytes(req_bytes)
    (contract / module.STRUCTURAL_RECEIPT_PATH.name).write_bytes(
        structural_bytes
    )
    monkeypatch.setattr(
        module,
        "SEMANTIC_REQUIREMENTS_SHA256",
        hashlib.sha256(req_bytes).hexdigest(),
    )
    monkeypatch.setattr(
        module,
        "STRUCTURAL_RECEIPT_SHA256",
        hashlib.sha256(structural_bytes).hexdigest(),
    )

    with pytest.raises(ValueError, match=message):
        load_header_inventory_contract(tmp_path)


@pytest.mark.parametrize(
    ("contents", "expected_digest", "message"),
    [
        (None, "0" * 64, "unavailable"),
        (b"[]", hashlib.sha256(b"[]").hexdigest(), "not an object"),
        (
            b"not-json",
            hashlib.sha256(b"not-json").hexdigest(),
            "Expecting value",
        ),
        (b"{}", "0" * 64, "digest differs"),
    ],
)
def test_bound_json_failures_are_closed(
    tmp_path: Path,
    contents: bytes | None,
    expected_digest: str,
    message: str,
) -> None:
    path = tmp_path / "contract.json"
    if contents is not None:
        path.write_bytes(contents)
    with pytest.raises((ValueError, TypeError), match=message):
        module._read_bound_json(
            tmp_path, Path("contract.json"), expected_digest, "fixture"
        )


def test_workflow_is_main_only_bounded_and_uses_existing_serialized_gate() -> (
    None
):
    root = Path(__file__).resolve().parents[1]
    workflow = (
        root
        / ".github/workflows/australian-mbs-utilisation-header-inventory.yml"
    ).read_text()
    assert "workflow_dispatch:" in workflow
    assert "environment: australian-hf-publication" in workflow
    assert "group: australian-mbs-utilisation-harvest" in workflow
    assert "issues: write" in workflow
    assert "inventory_mbs_utilisation_csv_headers.py" in workflow
    runner = (
        root / "scripts/inventory_mbs_utilisation_csv_headers.py"
    ).read_text()
    assert "--exact-commit" in runner
    assert "WORKER_SECONDS = 60" in runner
    assert "WORKER_MEMORY_BYTES = 1_073_741_824" in runner
    assert "RECEIPT_URL_PATTERN.fullmatch" in runner
    assert '"processing_admitted": False' in runner
    assert '"semantic_validation": False' in runner


def inventory_csv_header_from_headers(
    headers: tuple[str, ...],
    *,
    candidate_schemas: dict[str, tuple[str, ...]],
) -> HeaderInventory:
    """Keep public-result tests independent from filesystem parsing."""
    canonical = json.dumps(
        list(headers), ensure_ascii=False, separators=(",", ":")
    ).encode()
    return HeaderInventory(
        headers=headers,
        header_sha256=hashlib.sha256(canonical).hexdigest(),
        column_count=len(headers),
        schema_matches=tuple(
            name
            for name, schema in candidate_schemas.items()
            if headers == schema
        ),
    )
