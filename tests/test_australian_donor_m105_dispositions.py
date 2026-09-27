"""Keep the M-105 disposition denominator exact without inferring parity."""

import ast
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = (
    ROOT / "quality/qualifications/australian-donor-m105-dispositions.json"
)
INVENTORY = (
    ROOT / "quality/qualifications/australian-health-donor-inventory.json"
)
DELTA = ROOT / "quality/qualifications/australian-donor-delta.json"
FINAL_DISPOSITIONS = {
    "adopt",
    "adapt",
    "replace-with-equivalent",
    "retain-legacy",
    "supersede",
    "exclude-with-reason",
}


def test_m105_dispositions_cover_exact_pinned_and_later_donors() -> None:
    receipt = json.loads(RECEIPT.read_text())
    inventory = json.loads(INVENTORY.read_text())
    delta = json.loads(DELTA.read_text())
    expected_baseline = {
        (
            repo["repository"],
            repo["commit"],
            item["path"],
            item["git_object_sha1"],
            item["sha256"],
        )
        for repo in inventory["denominator"]["repositories"]
        for item in repo["files"]
    }
    observed_baseline = [
        (
            item["repository"],
            item["commit"],
            item["path"],
            item["git_object_sha1"],
            item["sha256"],
        )
        for item in receipt["baseline"]
    ]
    assert len(observed_baseline) == len(expected_baseline)
    assert set(observed_baseline) == expected_baseline
    expected_delta = {
        (
            review["observation"]["repository"],
            review["observation"]["head"],
            item["path"],
            item["blob"],
        )
        for review in delta["reviews"]
        for item in review["observation"]["files"]
    }
    observed_delta = [
        (
            item["repository"],
            item["commit"],
            item["path"],
            item["git_object_sha1"],
        )
        for item in receipt["post_baseline_delta"]
    ]
    assert len(observed_delta) == len(expected_delta)
    assert set(observed_delta) == expected_delta
    assert all(
        item["disposition"] in FINAL_DISPOSITIONS
        for item in [*receipt["baseline"], *receipt["post_baseline_delta"]]
    )


def test_m105_dispositions_do_not_promote_unproven_behavior() -> None:
    receipt = json.loads(RECEIPT.read_text())
    assert receipt["qualification_state"] == "partial"
    assert (
        sum(
            item["acceptance_state"] == "pending_behavioral_parity"
            for item in receipt["baseline"]
        )
        == 3
    )
    assert (
        sum(
            item["acceptance_state"] == "pending_behavioral_parity"
            for item in receipt["post_baseline_delta"]
        )
        == 2
    )


def test_scraper_ci_supersession_binds_exact_blobs_and_executed_lanes() -> None:
    receipt = json.loads(RECEIPT.read_text())
    expected = {
        "baseline": "6bc00960faaefd159adac31e5a0c16947493b8bd",
        "post_baseline_delta": "6791c2a6c65e0cc2a04f7b2d6f1973291e1ce875",
    }
    for group, blob in expected.items():
        row = next(
            item
            for item in receipt[group]
            if item["repository"] == "edithatogo/aus-health-data-scraper"
            and item["path"] == ".github/workflows/ci.yml"
        )
        assert row["git_object_sha1"] == blob
        assert row["acceptance_state"] == "verified_supersession"
        proof = row["parity_evidence"]
        assert proof["hosted_head"] == (
            "0b006fe7a6fc1738867673ef4ee486668927ff77"
        )
        assert proof["hosted_status"] == "completed/success"
        assert proof["hosted_jobs"] == {
            "Python 3.14 / unit": "success",
            "Python 3.14 / routine": "success",
            "Python 3.14 / strict": "success",
        }
        workflow = yaml.safe_load((ROOT / proof["successor"]).read_text())
        # PyYAML's YAML 1.1 resolver reads GitHub's `on` key as True.
        assert set(workflow[True]) >= {"pull_request", "push"}
        assert "unit" in workflow["jobs"]["tests"]["strategy"]["matrix"]["lane"]
        assert {"routine", "strict"} <= set(
            workflow["jobs"]["quality"]["strategy"]["matrix"]["profile"]
        )
        assert (ROOT / proof["policy_successor"]).is_file()
    harness = (ROOT / "scripts/test_goblin.py").read_text()
    assert '"ruff", "format"' in harness
    assert '"ruff", "check"' in harness
    assert '"pytest"' in harness


def test_scraper_processor_supersession_maps_every_donor_function() -> None:
    receipt = json.loads(RECEIPT.read_text())
    inventory = json.loads(INVENTORY.read_text())
    donor = next(
        repo
        for repo in inventory["denominator"]["repositories"]
        if repo["repository"] == "edithatogo/aus-health-data-scraper"
    )
    donor_functions = {
        item["path"]: set(item["functions"])
        for item in donor["files"]
        if item["path"] in {"src/processor.py", "tests/test_processor.py"}
    }
    # Exact later blobs: the processor narrows its HTML exception handler;
    # the processor test only reorders imports.
    later_blobs = {
        "src/processor.py": (
            "e7cae9b5585a825a197b6c9b850d918a71cfb105",
            {"process_mbs_xml", "process_html_file", "combine_and_save_data"},
        ),
        "tests/test_processor.py": (
            "d016d0d1484aa1fe3adc6a8cf85965bc111d06d7",
            {
                "temp_data_dirs",
                "test_process_mbs_xml",
                "test_combine_and_save_data",
            },
        ),
    }
    for group in ("baseline", "post_baseline_delta"):
        for row in receipt[group]:
            if (
                row["repository"] != donor["repository"]
                or row["path"] not in donor_functions
            ):
                continue
            expected_functions = donor_functions[row["path"]]
            if group == "post_baseline_delta":
                expected_blob, expected_functions = later_blobs[row["path"]]
                assert row["git_object_sha1"] == expected_blob
            assert row["acceptance_state"] == "verified_supersession"
            proof = row["parity_evidence"]
            assert set(proof["function_dispositions"]) == expected_functions
            for function in proof["function_dispositions"].values():
                refs = function.get(
                    "behavior_tests", [function.get("behavior_test")]
                )
                for ref in refs:
                    test_path, test_name = ref.split("::", 1)
                    tree = ast.parse((ROOT / test_path).read_text())
                    assert test_name in {
                        node.name
                        for node in ast.walk(tree)
                        if isinstance(node, ast.FunctionDef)
                    }
    assert receipt["qualification_state"] == "partial"


def test_mbs_parser_replacement_binds_exact_pre_archive_qualification() -> None:
    receipt = json.loads(RECEIPT.read_text())
    row = next(
        item
        for item in receipt["baseline"]
        if item["repository"] == "edithatogo/aus_mbs_pbs_graph"
        and item["path"] == "scripts/parsing/parse_mbs_xml.py"
    )
    assert row["disposition"] == "replace-with-equivalent"
    assert row["acceptance_state"] == "verified_replacement"
    proof = row["parity_evidence"]
    ledger = [
        json.loads(line)
        for line in (ROOT / proof["ledger"]).read_text().splitlines()
    ]
    source = next(
        item
        for item in ledger
        if item.get("kind") == proof["source_qualification_record_kind"]
    )
    streamed = next(
        item
        for item in ledger
        if item.get("kind") == proof["streamed_qualification_record_kind"]
        and item.get("phase") == proof["streamed_qualification_phase"]
    )
    assert source["source"]["repository"] == row["repository"]
    assert source["source"]["commit"] == row["commit"]
    assert (
        source["source"]["sha256"]
        == streamed["exact_streamed_qualification"]["mbs_xml"]["sha256"]
    )
    assert source["observation"]["records"] == 5989
    assert source["observation"]["distinct_native_fields"] == 40
    assert (
        streamed["exact_streamed_qualification"]["mbs_xml"]["records"] == 5989
    )
    scraper_archive = json.loads(
        (
            ROOT / "quality/qualifications/scraper-archival-20260906.json"
        ).read_text()
    )
    graph_archive = json.loads(
        (
            ROOT / "quality/qualifications/graph-archival-20260906.json"
        ).read_text()
    )
    assert streamed["recorded_at"] < scraper_archive["archival"]["updated_at"]
    assert streamed["recorded_at"] < graph_archive["updated_at"]
    assert (ROOT / proof["source_qualifier"].split("::", 1)[0]).is_file()
    assert (ROOT / proof["behavior_tests"]).is_file()


def test_mbs_downloader_adaptation_binds_legacy_and_hosted_receipts() -> None:
    receipt = json.loads(RECEIPT.read_text())
    row = next(
        item
        for item in receipt["baseline"]
        if item["repository"] == "edithatogo/aus_mbs_pbs_graph"
        and item["path"] == "scripts/parsing/download_mbs.py"
    )
    assert row["disposition"] == "adapt"
    assert row["acceptance_state"] == "verified_adaptation"
    proof = row["parity_evidence"]
    inventory = json.loads(INVENTORY.read_text())
    donor_file = next(
        item
        for repo in inventory["denominator"]["repositories"]
        if repo["repository"] == row["repository"]
        for item in repo["files"]
        if item["path"] == row["path"]
    )
    functions = proof["function_dispositions"]
    assert set(functions) == set(donor_file["functions"])
    assert functions["download_file"]["disposition"] == "adapt"
    assert functions["get_filename_from_url"]["disposition"] == "supersede"
    for item in functions.values():
        module, test_name = item["behavior_test"].split("::", 1)
        assert (ROOT / module).is_file()
        assert test_name.startswith("test_")
    legacy = json.loads((ROOT / proof["legacy_public_receipt"]).read_text())
    raw = next(
        item for item in legacy["raw_payloads"] if item["source_id"] == "au-mbs"
    )
    assert legacy["donor_commits"][row["repository"]] == row["commit"]
    assert legacy["publication_performed_by_github_actions"] is True
    assert legacy["anonymous_clean_room_restore"] is True
    assert legacy["public"] is True
    assert legacy["gated"] is False
    assert raw["sha256"] == (
        "db873768c5795222455033e2bad28586f19bbf2a10c7d58f06a0671d9111a556"
    )
    contract = json.loads(
        (ROOT / proof["current_release_contract"]).read_text()
    )
    assert contract["source_id"] == "au-mbs"
    assert contract["dataset"] == legacy["dataset"]
    assert contract["publication_authorized"] is True
    assert contract["source_url"].endswith("/MBS-XML-20260801.XML")
    ledger = [
        json.loads(line)
        for line in (ROOT / proof["ledger"]).read_text().splitlines()
    ]
    hosted = next(
        item
        for item in ledger
        if item.get("kind") == proof["hosted_qualification_record_kind"]
    )
    assert hosted["dataset"] == legacy["dataset"]
    assert hosted["parent_revision"] == legacy["immutable_revision"]
    assert hosted["workflow_conclusion"] == "success"
    assert hosted["raw_bytes"] > 0
    assert len(hosted["raw_sha256"]) == 64
    assert hosted["anonymous_digest_verification"] == "passed"
    assert hosted["temporary_source_bytes_removed"] is True
    assert (
        hosted["recorded_at"]
        < json.loads(
            (
                ROOT / "quality/qualifications/scraper-archival-20260906.json"
            ).read_text()
        )["archival"]["updated_at"]
    )
    assert (ROOT / proof["replacement"].split("::", 1)[0]).is_file()
    assert all((ROOT / path).is_file() for path in proof["behavior_tests"])


def test_pbs_donor_functions_bind_successors_and_pre_archive_publication() -> (  # ruff: ignore[too-many-locals] - one receipt binds three donor files and four functions
    None
):
    receipt = json.loads(RECEIPT.read_text())
    inventory = json.loads(INVENTORY.read_text())
    paths = {
        "scripts/parsing/download_pbs.py",
        "scripts/parsing/parse_pbs_xml.py",
        "scripts/utils/identify_pbs_tags.py",
    }
    rows = {
        item["path"]: item
        for item in receipt["baseline"]
        if item["repository"] == "edithatogo/aus_mbs_pbs_graph"
        and item["path"] in paths
    }
    donor = next(
        item
        for item in inventory["denominator"]["repositories"]
        if item["repository"] == "edithatogo/aus_mbs_pbs_graph"
    )
    assert set(rows) == paths
    ledger = [
        json.loads(line)
        for line in (
            ROOT
            / "conductor/tracks/australian_health_source_consolidation_20260829/evidence.jsonl"
        )
        .read_text()
        .splitlines()
    ]
    hosted = next(
        item
        for item in ledger
        if item.get("kind") == "hosted_publication_receipt"
        and item.get("phase") == "governed_pbs_v3"
    )
    assert hosted["status"] == "passed_public_anonymously_verified"
    assert hosted["dataset"] == "edithatogo/australian-pbs-source-archive"
    assert hosted["revision"] == "31ec854ef9fc82f30a0dbe743fdf50a2e5bd24a7"
    assert hosted["visibility"] == {"public": True, "gated": False}
    assert hosted["verification"]["anonymous_digest_verification"] == "passed"
    assert "exact source ZIP" in hosted["products"]
    assert "exact source XML member" in hosted["products"]
    assert (
        hosted["source"]["archive_sha256"] != hosted["source"]["member_sha256"]
    )
    graph_archive = json.loads(
        (
            ROOT / "quality/qualifications/graph-archival-20260906.json"
        ).read_text()
    )
    assert hosted["recorded_at"] < graph_archive["updated_at"]

    for donor_file in donor["files"]:
        if donor_file["path"] not in paths:
            continue
        row = rows[donor_file["path"]]
        assert row["commit"] == donor["commit"]
        assert row["git_object_sha1"] == donor_file["git_object_sha1"]
        assert row["acceptance_state"].startswith("verified_")
        proof = row["parity_evidence"]
        assert proof["hosted_qualification_record_kind"] == hosted["kind"]
        successor_path, _, successor_name = proof["successor"].partition("::")
        assert (ROOT / successor_path).is_file()
        if successor_name:
            successor_tree = ast.parse((ROOT / successor_path).read_text())
            assert successor_name in {
                item.name
                for item in ast.walk(successor_tree)
                if isinstance(item, ast.FunctionDef)
            }
        if donor_file["path"] == "scripts/utils/identify_pbs_tags.py":
            assert proof["successor"] == "scripts/inspect_pbs_v3.py::main"
            assert set(proof["implementation_components"]) == {
                "scripts/inspect_pbs_v3.py",
                "src/global_medicines_atlas/adapters/au_pbs.py",
            }
        assert (ROOT / proof["publication_tests"]).is_file()
        assert set(proof["function_dispositions"]) == set(
            donor_file["functions"]
        )
        for function in proof["function_dispositions"].values():
            assert function["disposition"] in FINAL_DISPOSITIONS
            test_refs = function.get(
                "behavior_tests", [function.get("behavior_test")]
            )
            assert test_refs
            assert all(isinstance(ref, str) for ref in test_refs)
            for ref in test_refs:
                test_path, name = ref.split("::", 1)
                source = (ROOT / test_path).read_text()
                declarations = {
                    item.name
                    for item in ast.walk(ast.parse(source))
                    if isinstance(item, ast.FunctionDef)
                }
                assert name in declarations
    assert (
        next(
            item
            for item in donor["files"]
            if item["path"] == "scripts/parsing/parse_pbs_xml.py"
        )["implementation_state"]
        == "invalid_syntax"
    )
