from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pytest

from global_medicines_atlas import mbs_utilisation_value_observer as module
from global_medicines_atlas.mbs_utilisation_value_observer import (
    BENEFIT_HEADER,
    DEMOGRAPHICS_HEADERS,
    GROUP_HEADERS,
    SERVICES_HEADER,
    load_value_observer_cohort,
    observe_utilisation_csv_values,
)


def test_observer_reports_exact_decimal_and_missingness_without_row_values(
    tmp_path: Path,
) -> None:
    source = tmp_path / "demographics.csv"
    source.write_bytes(
        b"\xef\xbb\xbfYear,Month of Processing,Item Number,State,Age Range,Gender,Services,Benefit\n"
        b"2016,1,0101,NSW,0-4,Male,3,10.50\n"
        b"2016,1,0101,NSW,0-4,Male,-1,0\n"
        b"2016,1,0102,VIC,unknown,,2,2.000\n"
    )

    result = observe_utilisation_csv_values(
        source, expected_headers=DEMOGRAPHICS_HEADERS
    )

    assert result.record_count == 3
    assert result.rectangular_record_count == 3
    assert result.row_width_error_count == 0
    assert result.empty_cell_counts["Gender"] == 1
    assert result.services.valid_count == 3
    assert result.services.negative_count == 1
    assert result.services.max_scale == 0
    assert result.benefit.valid_count == 3
    assert result.benefit.max_scale == 3
    public = json.dumps(result.to_public_summary())
    assert "0101" not in public
    assert "NSW" not in public
    assert "10.50" not in public
    assert public.count('"column_count": 8') == 1


def test_observer_counts_invalid_numeric_tokens_without_leaking_them(
    tmp_path: Path,
) -> None:
    source = tmp_path / "group.csv"
    source.write_text(
        ",".join(GROUP_HEADERS)
        + "\n2016,July,01,02,0101,National,unknown,NaN\n"
        + "2016,July,01,02,0103,National,1e3,2.0e2\n"
        + "2016,July,01,02,0102,National,,\n",
        encoding="utf-8",
    )

    result = observe_utilisation_csv_values(
        source, expected_headers=GROUP_HEADERS
    )

    assert result.record_count == 3
    assert result.empty_cell_counts[SERVICES_HEADER] == 1
    assert result.empty_cell_counts[BENEFIT_HEADER] == 1
    assert result.services.invalid_count == 2
    assert result.services.empty_count == 1
    assert result.benefit.invalid_count == 2
    assert result.benefit.empty_count == 1
    summary = json.dumps(result.to_public_summary())
    assert "unknown" not in summary
    assert "NaN" not in summary


def test_invalid_numeric_tokens_use_disjoint_exhaustive_private_categories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(module, "MAX_NUMERIC_TOKEN_CHARS", 20)
    source = tmp_path / "categories.csv"
    source.write_text(
        ",".join(DEMOGRAPHICS_HEADERS)
        + "\n2016,1,0101,NSW,0-4,Male, 1,1\n"
        + "2016,1,0102,NSW,0-4,Male,1e3,1\n"
        + '2016,1,0103,NSW,0-4,Male,"1,000",1\n'
        + "2016,1,0104,NSW,0-4,Male,1_000,1\n"
        + '2016,1,0105,NSW,0-4,Male,"1,00",1\n'
        + "2016,1,0106,NSW,0-4,Male,NaN,1\n"
        + "2016,1,0107,NSW,0-4,Male,--,1\n"
        + "2016,1,0108,NSW,0-4,Male,123456789012345678901,1\n"
        + '2016,1,0109,NSW,0-4,Male,"1,000_000",1\n',
        encoding="utf-8",
    )

    result = observe_utilisation_csv_values(
        source, expected_headers=DEMOGRAPHICS_HEADERS
    )

    categories = result.services.invalid_category_counts
    assert result.services.invalid_count == 9
    assert set(categories) == set(module.INVALID_TOKEN_CATEGORIES)
    assert categories["comma_triplet_pattern"] == 1
    assert categories["underscore_triplet_pattern"] == 1
    assert categories["other_separator"] == 2
    assert sum(categories.values()) == result.services.invalid_count
    public_summary = json.loads(json.dumps(result.to_public_summary()))
    public_strings: set[str] = set()

    def collect_strings(value: Any) -> None:
        if isinstance(value, str):
            public_strings.add(value)
        elif isinstance(value, dict):
            string_mapping = cast("dict[str, Any]", value)
            for key, item in string_mapping.items():
                collect_strings(key)
                collect_strings(item)
        elif isinstance(value, list):
            sequence = cast("list[Any]", value)
            for item in sequence:
                collect_strings(item)

    collect_strings(public_summary)
    assert public_strings.isdisjoint({
        " 1",
        "1e3",
        "1,000",
        "NaN",
        "--",
        "123456",
    })


def test_observer_counts_ragged_rows_and_excludes_them_from_value_profiles(
    tmp_path: Path,
) -> None:
    source = tmp_path / "ragged.csv"
    source.write_text(
        ",".join(DEMOGRAPHICS_HEADERS)
        + "\n2016,1,0101,NSW,0-4,Male,-3,2.50\n"
        + "2016,1,0102,NSW,0-4,Male,-4\n",
        encoding="utf-8",
    )

    result = observe_utilisation_csv_values(
        source, expected_headers=DEMOGRAPHICS_HEADERS
    )

    assert result.record_count == 2
    assert result.rectangular_record_count == 1
    assert result.row_width_error_count == 1
    assert result.services.valid_count == 1
    assert result.services.negative_count == 1
    assert result.benefit.valid_count == 1
    assert result.to_public_summary()["status"] == "row_shape_findings"


@pytest.mark.parametrize(
    "contents",
    [
        b"",
        b"\xef\xbb\xbf",
        b"Year,Year\n2016,2016\n",
        b"Year,Month of Processing,Item Number,State,Age Range,Gender,Services,Benefit\n\xff\n",
        b'Year,Month of Processing,Item Number,State,Age Range,Gender,Services,Benefit\n"unterminated',
    ],
)
def test_observer_rejects_missing_or_malformed_csv(
    tmp_path: Path, contents: bytes
) -> None:
    source = tmp_path / "malformed.csv"
    source.write_bytes(contents)

    with pytest.raises(
        ValueError,
        match=r"CSV byte limit|CSV header is missing|reviewed CSV header differs|cannot be decoded",
    ):
        observe_utilisation_csv_values(
            source, expected_headers=DEMOGRAPHICS_HEADERS
        )


def test_observer_rejects_different_reviewed_header_order(
    tmp_path: Path,
) -> None:
    source = tmp_path / "different.csv"
    source.write_text(
        ",".join(reversed(DEMOGRAPHICS_HEADERS)) + "\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match="reviewed CSV header differs"):
        observe_utilisation_csv_values(
            source, expected_headers=DEMOGRAPHICS_HEADERS
        )


def test_observer_rejects_csv_over_byte_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(module, "MAX_CSV_BYTES", 10)
    source = tmp_path / "large.csv"
    source.write_text(",".join(DEMOGRAPHICS_HEADERS), encoding="utf-8")

    with pytest.raises(ValueError, match="CSV byte limit"):
        observe_utilisation_csv_values(
            source, expected_headers=DEMOGRAPHICS_HEADERS
        )


def test_observer_rejects_csv_over_row_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(module, "MAX_CSV_ROWS", 1)
    source = tmp_path / "too-many-rows.csv"
    source.write_text(
        ",".join(DEMOGRAPHICS_HEADERS)
        + "\n2016,1,0101,NSW,0-4,Male,1,1\n"
        + "2016,1,0102,VIC,0-4,Female,2,2\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="CSV row limit"):
        observe_utilisation_csv_values(
            source, expected_headers=DEMOGRAPHICS_HEADERS
        )


@pytest.mark.parametrize(
    "headers",
    [
        (),
        ("Services", "Services", "Benefit"),
        tuple(name for name in DEMOGRAPHICS_HEADERS if name != "Services"),
        tuple(name for name in DEMOGRAPHICS_HEADERS if name != "Benefit"),
        DEMOGRAPHICS_HEADERS
        + tuple(f"extra-{index}" for index in range(10_000)),
    ],
)
def test_observer_rejects_invalid_reviewed_profile(
    tmp_path: Path, headers: tuple[str, ...]
) -> None:
    source = tmp_path / "profile.csv"
    source.write_text("placeholder", encoding="utf-8")

    with pytest.raises(ValueError, match="reviewed CSV profile"):
        observe_utilisation_csv_values(source, expected_headers=headers)


def test_observer_restores_csv_field_limit_after_decode_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    previous = module.csv.field_size_limit()
    monkeypatch.setattr(module, "MAX_CSV_FIELD_BYTES", 1)
    source = tmp_path / "large-field.csv"
    source.write_text(",".join(DEMOGRAPHICS_HEADERS), encoding="utf-8")

    with pytest.raises(ValueError, match="cannot be decoded or parsed"):
        observe_utilisation_csv_values(
            source, expected_headers=DEMOGRAPHICS_HEADERS
        )

    assert module.csv.field_size_limit() == previous


def test_cohort_is_bound_to_the_four_prior_exact_header_receipts() -> None:
    root = Path(__file__).resolve().parents[1]

    selected = load_value_observer_cohort(root)

    assert len(selected) == 4
    assert len({row["raw_reference"]["path"] for row in selected}) == 4
    assert all(row["processing_admitted"] is False for row in selected)
    assert all(row["expected_headers"] for row in selected)
    demographics = [
        row
        for row in selected
        if "/demographics/" in row["raw_reference"]["path"]
    ]
    assert len(demographics) == 3
    assert (
        sum(
            row["resource_id"] != row["observed_schema_id"]
            for row in demographics
        )
        == 2
    )
    assert all(
        "/issues/340#issuecomment-" in row["prior_header_receipt_url"]
        for row in selected
    )


def test_cohort_rejects_a_changed_header_qualification_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "header-qualification.json"
    path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        module,
        "HEADER_INVENTORY_QUALIFICATION_PATH",
        Path("header-qualification.json"),
    )
    monkeypatch.setattr(
        module, "HEADER_INVENTORY_QUALIFICATION_SHA256", "0" * 64
    )

    with pytest.raises(ValueError, match="qualification digest differs"):
        load_value_observer_cohort(tmp_path)


def test_cohort_rejects_prior_admission_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "header-qualification.json"
    path.write_text(
        json.dumps({
            "candidate_source_count": 4,
            "processing_admitted": True,
            "semantic_validation": False,
            "source_inventory_expanded": False,
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        module,
        "HEADER_INVENTORY_QUALIFICATION_PATH",
        Path("header-qualification.json"),
    )
    monkeypatch.setattr(
        module,
        "HEADER_INVENTORY_QUALIFICATION_SHA256",
        hashlib.sha256(path.read_bytes()).hexdigest(),
    )

    with pytest.raises(ValueError, match="out of scope"):
        load_value_observer_cohort(tmp_path)


@pytest.mark.parametrize(
    ("failure", "message"),
    [
        ("short-selection", "exactly four previously inventoried"),
        ("missing-prior", "header inventory source set differs"),
        ("schema-match", "no unique reviewed schema"),
        ("identity", "source binding differs"),
        ("receipt", "source binding differs"),
    ],
)
def test_cohort_fails_closed_on_stale_receipt_bindings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
    message: str,
) -> None:
    headers_payload = json.dumps(
        list(DEMOGRAPHICS_HEADERS), ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    header_sha256 = hashlib.sha256(headers_payload).hexdigest()
    selected: list[dict[str, Any]] = []
    prior: list[dict[str, Any]] = []
    for index in range(4):
        path = f"raw/mbs/utilisation/test-{index}.csv"
        selected.append({
            "raw_reference": {
                "path": path,
                "revision": "revision",
                "sha256": f"source-{index}",
                "byte_count": 100,
            },
            "acquisition_id": f"acquisition-{index}",
            "resource_id": "catalogue-resource",
            "schema_candidate_ids": ["demographics-schema"],
        })
        prior.append({
            "path": path,
            "acquisition_id": f"acquisition-{index}",
            "source_revision": "revision",
            "source_sha256": f"source-{index}",
            "byte_count": 100,
            "schema_matches": ["demographics-schema"],
            "header_sha256": header_sha256,
            "column_count": len(DEMOGRAPHICS_HEADERS),
            "unexpected_field_count": 0,
            "anonymous_digest_verified": True,
            "cache_removed_after_receipt": True,
            "receipt_url": f"https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-{index + 1}",
        })
    if failure == "short-selection":
        selected.pop()
    elif failure == "missing-prior":
        selected[0]["raw_reference"]["path"] = "missing.csv"
    elif failure == "schema-match":
        prior[0]["schema_matches"] = []
    elif failure == "receipt":
        prior[0]["anonymous_digest_verified"] = False
    else:
        prior[0]["source_sha256"] = "stale-source"

    qualification_path = tmp_path / "qualification.json"
    qualification_path.write_text(
        json.dumps({
            "candidate_source_count": 4,
            "receipts_independently_read_back": True,
            "processing_admitted": False,
            "semantic_validation": False,
            "source_inventory_expanded": False,
            "records": prior,
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        module,
        "HEADER_INVENTORY_QUALIFICATION_PATH",
        Path("qualification.json"),
    )
    monkeypatch.setattr(
        module,
        "HEADER_INVENTORY_QUALIFICATION_SHA256",
        hashlib.sha256(qualification_path.read_bytes()).hexdigest(),
    )

    def fake_contract(
        _root: Path,
    ) -> tuple[list[dict[str, Any]], dict[str, tuple[str, ...]]]:
        return selected, {"demographics-schema": tuple(DEMOGRAPHICS_HEADERS)}

    monkeypatch.setattr(
        module,
        "load_header_inventory_contract",
        fake_contract,
    )

    with pytest.raises(ValueError, match=message):
        load_value_observer_cohort(tmp_path)


def test_header_reconciliation_keeps_cross_resource_matches_as_shape_only() -> (
    None
):
    root = Path(__file__).resolve().parents[1]
    qualification_path = (
        root
        / "quality/qualifications/australian-mbs-utilisation-header-inventory-20261006.json"
    )
    reconciliation = json.loads(
        (
            root
            / "quality/qualifications/australian-mbs-utilisation-header-schema-reconciliation-20261006.json"
        ).read_bytes()
    )

    assert (
        hashlib.sha256(qualification_path.read_bytes()).hexdigest()
        == reconciliation["header_inventory_qualification_sha256"]
    )
    assert reconciliation["candidate_source_count"] == 4
    assert reconciliation["semantic_equivalence_inferred"] is False
    assert (
        sum(
            not record["matched_own_catalogue_schema"]
            for record in reconciliation["records"]
        )
        == 2
    )


def test_hosted_runner_is_protected_bounded_and_metadata_only() -> None:
    root = Path(__file__).resolve().parents[1]
    runner = (
        root / "scripts/observe_mbs_utilisation_csv_values.py"
    ).read_text()
    workflow = (
        root / ".github/workflows/australian-mbs-utilisation-value-observer.yml"
    ).read_text()

    ast.parse(runner)
    assert "load_value_observer_cohort(ROOT)" in runner
    assert "verify_staged_identity(path, reference)" in runner
    assert "persist_receipt(document, receipts)" in runner
    assert "target.unlink()" in runner
    assert '"processing_admitted": False' in runner
    assert '"semantic_mapping_selected": False' in runner
    assert "capture_output=True" in runner
    assert "timeout=WORKER_SECONDS" in runner
    assert '"HF_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"' in runner
    assert "group: australian-mbs-utilisation-harvest" in workflow
    assert "environment: australian-hf-publication" in workflow
    assert "contents: read" in workflow
    assert "issues: write" in workflow
    assert "type: string" in workflow
