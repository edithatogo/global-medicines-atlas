"""Fail-closed aggregation of independently qualified PBS projections."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import cast

import pytest
from scripts import aggregate_historical_pbs_qualification as cli

from global_medicines_atlas import pbs_qualification_aggregate as aggregate
from global_medicines_atlas.pbs_qualification_aggregate import (
    REVISION,
    aggregate_shards,
)

PROJECTIONS = ("native", "domain", "entities", "references", "dates")
PHASES = ("native", "domain", "entities", "dates")


def shard(
    name: str, *, index: int | None = None, count: int = 4
) -> dict[str, object]:
    window = name == "references"
    start = index if index is not None else 0
    report: dict[str, object] = {
        "schema_version": 1,
        "status": "passed",
        "workflow_commit": "a" * 40,
        "run_id": "123",
        "run_attempt": "1",
        "dataset": "edithatogo/australian-pbs-source-archive",
        "revision": REVISION,
        "manifest_sha256": "c" * 64,
        "source_receipt_file_sha256": "d" * 64,
        "archive_path": "raw/source.zip",
        "member_path": "raw/member.xml",
        "anonymous_public_checks": 2,
        "publication_performed": False,
        "qualification": {
            "schema_version": 1,
            "qualification": "structural_storage_candidate_only",
            "projection_shard": name,
            "source_id": "au-pbs-historical-xml",
            "parent_receipt_sha256": "e" * 64,
            "archive_sha256": "f" * 64,
            "member_sha256": "1" * 64,
            "member_binding_sha256": "2" * 64,
            "native_fields": 12,
            "elements": 4,
            "native_digest": "3" * 64,
            "projections": {
                name: {
                    "rows": 1
                    if window
                    else (12 if name in {"native", "domain"} else 4),
                    "native_fields": 3 if window else 12,
                    "native_digest": f"{start + 4:x}" * 64
                    if window
                    else "3" * 64,
                    "parquet_roundtrip_verified": True,
                }
            },
            "date_profile": "not-selected",
            "domain_semantics_qualified": False,
            "publication_performed": False,
        },
    }
    if window:
        qualification = report["qualification"]
        assert isinstance(qualification, dict)
        qualification["reference_window"] = {
            "index": start,
            "count": count,
            "start_row": start,
            "stop_row": start + 1,
            "total_rows": count,
        }
        projection = qualification["projections"]
        assert isinstance(projection, dict)
        projection["references"]["native_digest_scope"] = "ordered-window"
    return report


def complete() -> list[dict[str, object]]:
    return [shard(name) for name in PHASES] + [
        shard("references", index=index) for index in range(4)
    ]


def test_aggregate_requires_exact_complete_projection_set() -> None:
    result = aggregate_shards(list(reversed(complete())))
    assert result["status"] == "passed"
    assert result["projection_shards"] == list(PROJECTIONS)
    assert list(result["qualification"]["projections"]) == list(PROJECTIONS)
    assert result["qualification"]["native_fields"] == 12
    assert result["qualification"]["native_digest"] == "3" * 64
    assert result["publication_performed"] is False


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ((0, "status"), "incomplete"),
        ((0, "workflow_commit"), "9" * 40),
        ((0, "revision"), "9" * 40),
        ((0, "qualification", "native_fields"), 11),
        ((0, "qualification", "native_digest"), "9" * 64),
        ((0, "qualification", "projections", "native", "rows"), 11),
        (
            (
                0,
                "qualification",
                "projections",
                "native",
                "parquet_roundtrip_verified",
            ),
            False,
        ),
    ],
)
def test_aggregate_rejects_identity_denominator_digest_and_parquet_drift(
    path: tuple[object, ...], value: object
) -> None:
    reports = complete()
    target = reports
    for key in path[:-1]:
        target = target[key]  # type: ignore[index,assignment]
    target[path[-1]] = value  # type: ignore[index]
    with pytest.raises(ValueError, match="PBS qualification shards"):
        aggregate_shards(reports)


def test_aggregate_rejects_missing_duplicate_and_extra_shards() -> None:
    baseline = complete()
    for candidate in (
        baseline[:-1],
        [*baseline[:-1], deepcopy(baseline[0])],
        [*baseline, shard("extra")],
    ):
        with pytest.raises(ValueError, match="PBS qualification shards"):
            aggregate_shards(candidate)


def test_cli_writes_digest_bound_success_and_incomplete_receipts(
    tmp_path: Path,
) -> None:
    receipts = tmp_path / "receipts"
    receipts.mkdir()
    for ordinal, report in enumerate(complete()):
        path = receipts / f"pbs-{ordinal}-receipt.json"
        canonical = json.dumps(
            report, sort_keys=True, separators=(",", ":")
        ).encode()
        path.write_text(
            json.dumps({
                "report": report,
                "report_sha256": hashlib.sha256(canonical).hexdigest(),
            })
        )
    output = tmp_path / "aggregate.json"
    arguments = [
        "--receipts",
        str(receipts),
        "--exact-commit",
        "a" * 40,
        "--output",
        str(output),
    ]
    assert cli.main(arguments) == 0
    envelope = json.loads(output.read_text())
    assert envelope["report"]["status"] == "passed"
    (receipts / "pbs-7-receipt.json").unlink()
    assert cli.main(arguments) == 1
    assert json.loads(output.read_text())["report"]["status"] == "incomplete"


@pytest.mark.parametrize(
    "reports",
    [None, [], [None] * 8],
)
def test_aggregate_rejects_invalid_containers(reports: object) -> None:
    with pytest.raises(ValueError, match="PBS qualification shards"):
        aggregate_shards(reports)


@pytest.mark.parametrize("case", ["qualification", "projection-set", "projection"])
def test_aggregate_rejects_malformed_phase_receipts(case: str) -> None:
    reports = complete()
    if case == "qualification":
        reports[0]["qualification"] = None
    else:
        qualification = reports[0]["qualification"]
        assert isinstance(qualification, dict)
        projections = qualification["projections"]
        assert isinstance(projections, dict)
        if case == "projection-set":
            projections["extra"] = {}
        else:
            projections["native"] = None
    with pytest.raises(ValueError, match="PBS qualification shards"):
        aggregate_shards(reports)


@pytest.mark.parametrize(
    ("case", "value"),
    [
        ("window", None),
        ("scope", "full"),
        ("digest", "bad"),
        ("total", 0),
        ("range", 2),
        ("rows", 2),
        ("fields", -1),
        ("field-total", 4),
    ],
)
def test_reference_aggregate_rejects_window_drift(case: str, value: object) -> None:
    reports = complete()
    qualification = reports[4]["qualification"]
    assert isinstance(qualification, dict)
    projection = qualification["projections"]
    assert isinstance(projection, dict)
    reference = projection["references"]
    assert isinstance(reference, dict)
    if case == "window":
        qualification["reference_window"] = value
    elif case == "scope":
        reference["native_digest_scope"] = value
    elif case == "digest":
        reference["native_digest"] = value
    elif case == "total":
        qualification["elements"] = value
        for report in reports:
            item = report["qualification"]
            assert isinstance(item, dict)
            item["elements"] = value
    elif case == "range":
        window = qualification["reference_window"]
        assert isinstance(window, dict)
        window["stop_row"] = value
    elif case == "rows":
        reference["rows"] = value
    elif case == "fields":
        reference["native_fields"] = value
    else:
        reference["native_fields"] = value
    with pytest.raises(ValueError, match="PBS qualification shards"):
        aggregate_shards(reports)


def test_empty_reference_aggregate_fails_closed() -> None:
    with pytest.raises(ValueError, match="PBS qualification shards"):
        aggregate._aggregate_references(  # pyright: ignore[reportPrivateUsage]
            [], cast("dict[str, object]", shard("native")["qualification"])
        )
