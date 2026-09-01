"""Fail-closed aggregation of independently qualified PBS projections."""

import hashlib
import json
import py_compile
from copy import deepcopy
from pathlib import Path
from typing import cast

import pytest
from scripts import aggregate_historical_pbs_qualification as cli

from global_medicines_atlas import pbs_qualification_aggregate as aggregate
from global_medicines_atlas.pbs_qualification_aggregate import (
    MEMBER_BINDING_SHA256,
    PARENT_RECEIPT_SHA256,
    REVISION,
    aggregate_shards,
)

PROJECTIONS = ("native", "domain", "entities", "references", "dates")
PHASES = ("native", "domain", "entities", "dates")


def test_aggregate_cli_compiles_as_repository_script() -> None:
    py_compile.compile(
        "scripts/aggregate_historical_pbs_qualification.py", doraise=True
    )


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
        "manifest_sha256": aggregate.MANIFEST.sha256,
        "source_receipt_file_sha256": aggregate.RECEIPT.sha256,
        "archive_path": aggregate.ARCHIVE.path,
        "member_path": aggregate.MEMBER.path,
        "member_retrieval": "extracted-from-verified-archive",
        "public_objects": {
            name: {
                "path": pin.path,
                "sha256": pin.sha256,
                "byte_count": pin.byte_count,
            }
            for name, pin in (
                ("manifest", aggregate.MANIFEST),
                ("source_receipt", aggregate.RECEIPT),
                ("archive", aggregate.ARCHIVE),
                ("member", aggregate.MEMBER),
            )
        },
        "anonymous_public_checks": 2,
        "publication_performed": False,
        "qualification": {
            "schema_version": 1,
            "qualification": "structural_storage_candidate_only",
            "projection_shard": name,
            "source_id": "au-pbs-historical-xml",
            "parent_receipt_sha256": PARENT_RECEIPT_SHA256,
            "archive_sha256": aggregate.ARCHIVE.sha256,
            "member_sha256": aggregate.MEMBER.sha256,
            "member_binding_sha256": MEMBER_BINDING_SHA256,
            "native_fields": 12,
            "elements": 4,
            "native_digest": "3" * 64,
            "projections": {
                name: {
                    "rows": 1
                    if window
                    else (12 if name in {"native", "domain"} else 4),
                    "native_fields": 3 if window else 12,
                    "unmapped_rows": 0,
                    "duplicate_literal_rows": 0,
                    "ambiguous_reference_rows": 0,
                    "unresolved_reference_rows": 0,
                    "date_unselected_rows": 0,
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
        qualification["preparation_manifest_sha256"] = "8" * 64
        qualification["expected_reference_projection"] = {
            key: projection["references"][key]
            for key in ("rows", "native_fields", "native_digest")
        }
    return report


def complete() -> list[dict[str, object]]:
    return [shard(name) for name in PHASES] + [
        shard("references", index=index) for index in range(4)
    ]


def test_aggregate_requires_exact_complete_projection_set() -> None:
    result = aggregate_shards(list(reversed(complete())))
    assert result["status"] == "passed"


def test_aggregate_accepts_hosted_sorted_key_receipt_roundtrip() -> None:
    reports = json.loads(json.dumps(complete(), sort_keys=True))
    result = aggregate_shards(reports)
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


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("dataset",), "mutated/dataset"),
        (("revision",), "9" * 40),
        (("manifest_sha256",), "9" * 64),
        (("source_receipt_file_sha256",), "9" * 64),
        (("archive_path",), "raw/mutated.zip"),
        (("member_path",), "bronze/mutated.xml"),
        (("member_retrieval",), "direct"),
        (("qualification", "source_id"), "mutated"),
        (("qualification", "parent_receipt_sha256"), "9" * 64),
        (("qualification", "archive_sha256"), "9" * 64),
        (("qualification", "member_sha256"), "9" * 64),
        (("qualification", "member_binding_sha256"), "9" * 64),
        (("qualification", "date_profile"), "selected"),
        (("qualification", "domain_semantics_qualified"), True),
    ],
)
def test_aggregate_rejects_authoritative_value_mutated_in_every_shard(
    path: tuple[str, ...], value: object
) -> None:
    reports = complete()
    for report in reports:
        target: dict[str, object] = report
        for key in path[:-1]:
            child = target[key]
            assert isinstance(child, dict)
            target = child
        target[path[-1]] = value
    with pytest.raises(ValueError, match="PBS qualification shards"):
        aggregate_shards(reports)


def test_aggregate_rejects_public_pin_mutated_in_every_shard() -> None:
    reports = complete()
    for report in reports:
        public_objects = report["public_objects"]
        assert isinstance(public_objects, dict)
        archive = public_objects["archive"]
        assert isinstance(archive, dict)
        archive["sha256"] = "9" * 64
    with pytest.raises(ValueError, match="PBS qualification shards"):
        aggregate_shards(reports)


@pytest.mark.parametrize("mutation", ["missing", "extra", "bool-counter"])
def test_aggregate_rejects_non_exact_projection_counter_schema(
    mutation: str,
) -> None:
    reports = complete()
    qualification = reports[0]["qualification"]
    assert isinstance(qualification, dict)
    projections = qualification["projections"]
    assert isinstance(projections, dict)
    projection = projections["native"]
    assert isinstance(projection, dict)
    if mutation == "missing":
        projection.pop("unmapped_rows")
    elif mutation == "extra":
        projection["invented_rows"] = 7
    else:
        projection["unmapped_rows"] = False
    with pytest.raises(ValueError, match="PBS qualification shards"):
        aggregate_shards(reports)


def test_reference_aggregate_sums_only_declared_counters() -> None:
    reports = complete()
    for index, report in enumerate(reports[4:], 1):
        qualification = report["qualification"]
        assert isinstance(qualification, dict)
        projections = qualification["projections"]
        assert isinstance(projections, dict)
        projection = projections["references"]
        assert isinstance(projection, dict)
        projection["unmapped_rows"] = index
        projection["date_unselected_rows"] = index * 2
    result = aggregate_shards(reports)
    reference = result["qualification"]["projections"]["references"]
    assert reference["unmapped_rows"] == 10
    assert reference["date_unselected_rows"] == 20
    assert "invented_rows" not in reference


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
        path = receipts / f"pbs-{ordinal}-receipt-1.json"
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
        "--reference-shards",
        "4",
        "--output",
        str(output),
    ]
    assert cli.main(arguments) == 0
    envelope = json.loads(output.read_text())
    assert envelope["report"]["status"] == "passed"
    (receipts / "pbs-7-receipt-1.json").unlink()
    assert cli.main(arguments) == 1
    assert json.loads(output.read_text())["report"]["status"] == "incomplete"


def test_retry_selection_uses_latest_equal_success_and_rejects_conflict() -> (
    None
):
    reports = complete()
    retry = deepcopy(reports[0])
    retry["run_attempt"] = "2"
    selected, conflicts = cli._latest_successes(  # pyright: ignore[reportPrivateUsage]
        [*reports, retry], 4
    )
    assert not conflicts
    assert len(selected) == 8
    assert (
        next(
            report
            for report in selected
            if cast("dict[str, object]", report["qualification"])[
                "projection_shard"
            ]
            == "native"
        )["run_attempt"]
        == "2"
    )

    cast("dict[str, object]", retry["qualification"])["native_digest"] = (
        "9" * 64
    )
    _, conflicts = cli._latest_successes(  # pyright: ignore[reportPrivateUsage]
        [*reports, retry], 4
    )
    assert conflicts == ["native"]


@pytest.mark.parametrize("field", ["preparation_manifest_sha256", "expected"])
def test_reference_receipts_reject_manifest_or_expected_digest_drift(
    field: str,
) -> None:
    reports = complete()
    qualification = cast("dict[str, object]", reports[-1]["qualification"])
    if field == "preparation_manifest_sha256":
        qualification[field] = "9" * 64
    else:
        expected = cast(
            "dict[str, object]", qualification["expected_reference_projection"]
        )
        expected["native_digest"] = "9" * 64
    with pytest.raises(ValueError, match="incomplete or inconsistent"):
        aggregate_shards(reports)


@pytest.mark.parametrize(
    "mutation",
    [
        "public-type",
        "public-keys",
        "later-public-type",
        "duplicate-phase",
        "missing-phase",
        "missing-expected",
        "window-rows",
        "window-fields-type",
        "window-fields-total",
    ],
)
def test_aggregate_rejects_additional_identity_and_window_drift(
    mutation: str,
) -> None:
    reports = deepcopy(complete())
    if mutation == "public-type":
        reports[0]["public_objects"] = None
    elif mutation == "public-keys":
        cast("dict[str, object]", reports[0]["public_objects"]).pop("member")
    elif mutation == "later-public-type":
        reports[1]["public_objects"] = None
    elif mutation == "duplicate-phase":
        reports[1] = deepcopy(reports[0])
    elif mutation == "missing-phase":
        reports[1] = deepcopy(reports[-1])
    else:
        qualification = cast("dict[str, object]", reports[-1]["qualification"])
        projection = cast(
            "dict[str, dict[str, object]]", qualification["projections"]
        )["references"]
        if mutation == "missing-expected":
            qualification["expected_reference_projection"] = None
        elif mutation == "window-rows":
            projection["rows"] = 2
            cast(
                "dict[str, object]",
                qualification["expected_reference_projection"],
            )["rows"] = 2
        elif mutation == "window-fields-type":
            projection["native_fields"] = True
            cast(
                "dict[str, object]",
                qualification["expected_reference_projection"],
            )["native_fields"] = True
        else:
            projection["native_fields"] = 4
            cast(
                "dict[str, object]",
                qualification["expected_reference_projection"],
            )["native_fields"] = 4
    with pytest.raises(ValueError, match="incomplete or inconsistent"):
        aggregate_shards(reports)


@pytest.mark.parametrize(
    "reports",
    [None, [], [None] * 8],
)
def test_aggregate_rejects_invalid_containers(reports: object) -> None:
    with pytest.raises(ValueError, match="PBS qualification shards"):
        aggregate_shards(reports)


@pytest.mark.parametrize(
    "case", ["qualification", "projection-set", "projection"]
)
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
def test_reference_aggregate_rejects_window_drift(
    case: str, value: object
) -> None:
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
