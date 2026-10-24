"""Dispatch and aggregate-receipt boundaries for the opt-in URI screen."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml
from scripts import screen_historical_pbs_uri_references as cli

from global_medicines_atlas.pbs_native_uri_screen import (
    URI_SCREEN_SCHEMA_VERSION,
    UriScreenError,
)

COMMIT = "a" * 40


def test_workflow_dispatch_is_separate_and_exact_main_gated():
    workflow_path = (
        Path(__file__).parents[1]
        / ".github/workflows/pbs-historical-qualification.yml"
    )
    workflow = yaml.safe_load(workflow_path.read_text())
    inputs = workflow[True]["workflow_dispatch"]["inputs"]
    assert (
        "native-reference-uri-screen"
        in inputs["qualification_scope"]["options"]
    )
    job = workflow["jobs"]["native-reference-uri-screen"]
    assert job["if"] == (
        "inputs.qualification_scope == 'native-reference-uri-screen'"
    )
    step = next(
        item
        for item in job["steps"]
        if item.get("name") == "Resolve exact source-local URI candidates only"
    )
    assert "test \"${GITHUB_REF}\" = 'refs/heads/main'" in step["run"]
    assert 'test "${GITHUB_SHA}" = "${REQUESTED_COMMIT}"' in step["run"]
    assert "scripts/screen_historical_pbs_uri_references.py" in step["run"]
    assert "screen_historical_pbs_references.py" not in step["run"]


def test_pinned_review_packet_has_46_unreviewed_cases_for_same_member():
    cases, binding = cli.load_review_cases(
        "73d34185fe6ae7fd9a788a68448e20934b38553d42361117faa96cdb07f54f43"
    )
    assert len(cases) == binding["packet_case_count"] == 46
    assert binding["packet_cases_reviewed"] == 0
    assert len(binding["packet_file_sha256"]) == 64
    assert all(len(case["case_id"]) == 64 for case in cases)


def test_review_packet_report_digest_is_verified_before_use(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    packet = json.loads(cli.REVIEW_PACKET.read_text())
    packet["report_sha256"] = "0" * 64
    receipt = tmp_path / "packet.json"
    receipt.write_text(json.dumps(packet))
    monkeypatch.setattr(cli, "REVIEW_PACKET", receipt)
    with pytest.raises(ValueError, match="packet digest differs"):
        cli.load_review_cases(
            "73d34185fe6ae7fd9a788a68448e20934b38553d42361117faa96cdb07f54f43"
        )


def test_script_uses_verified_member_route_and_retains_aggregate_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    archive_digest = "b" * 64
    member_digest = "c" * 64
    source_digest = "d" * 64
    binding = SimpleNamespace(
        archive_payload=SimpleNamespace(sha256=archive_digest, byte_count=12),
        member_path="PBS.xml",
        member_payload=SimpleNamespace(sha256=member_digest, byte_count=8),
    )
    inputs = SimpleNamespace(
        context={"workflow_commit": COMMIT, "run_id": "17", "run_attempt": "1"},
        xml=b"<member/>bytes",
        binding=binding,
        parent=SimpleNamespace(digest=lambda: source_digest),
    )
    calls: list[Any] = []

    def verified(exact_commit: str, *, transport: Any, retry: Any) -> Any:
        calls.append((exact_commit, transport, retry))
        return inputs

    def screen(
        member: bytes,
        *,
        progress: Callable[[str, int, int], None],
        review_cases: list[dict[str, str]],
    ) -> dict[str, Any]:
        assert member is inputs.xml
        assert review_cases == [
            {
                "case_id": "e" * 64,
                "reference_occurrence": "/synthetic/occurrence",
            }
        ]
        progress("pbs-uri-screen-parse", 1, 1)
        return {
            "schema_id": "global-medicines-atlas.pbs-native-uri-screen",
            "schema_version": URI_SCREEN_SCHEMA_VERSION,
            "reference_counts_by_kind": {"xlink_href": 1},
            "outcome_counts_by_kind": {
                "xlink_href": {"same_member_unique_id": 1}
            },
            "outcome_counts_by_qname": {
                "xlink:href": {"same_member_unique_id": 1}
            },
            "uri_values_emitted": False,
            "literal_values_emitted": False,
            "payload_emitted": False,
            "uri_resolution_performed": True,
            "external_targets_fetched": 0,
            "semantic_relationships_qualified": False,
            "precision_claimed": False,
        }

    monkeypatch.setattr(cli, "_verified_inputs", verified)
    monkeypatch.setattr(cli, "screen_pbs_native_uris", screen)
    monkeypatch.setattr(
        cli,
        "load_review_cases",
        lambda _digest: (
            [
                {
                    "case_id": "e" * 64,
                    "reference_occurrence": "/synthetic/occurrence",
                }
            ],
            {"packet_case_count": 1, "packet_cases_reviewed": 0},
        ),
    )
    output = tmp_path / "receipt.json"
    report = cli.run(COMMIT, output)

    assert calls
    assert calls[0][0:2] == (COMMIT, None)
    envelope = json.loads(output.read_text())
    assert envelope["report"] == report
    assert report["status"] == "passed"
    assert report["workflow_commit"] == COMMIT
    assert report["archive_sha256"] == archive_digest
    assert report["member_sha256"] == member_digest
    assert report["source_receipt_sha256"] == source_digest
    assert report["source_receipt_file_sha256"] == cli.RECEIPT.sha256
    assert report["qualification"]["semantic_relationships_qualified"] is False
    assert report["qualification"]["external_targets_fetched"] == 0
    assert report["review_packet_binding"]["packet_case_count"] == 1
    assert report["source_values_emitted"] is False
    assert report["admissions_created"] == report["canaries_performed"] == 0
    assert report["new_sources_added"] == 0
    assert "same_member_unique_id" in output.read_text()
    assert "#target-fragment" not in output.read_text()


def test_existing_receipt_is_not_overwritten(tmp_path: Path):
    output = tmp_path / "receipt.json"
    output.write_text("existing")

    with pytest.raises(SystemExit) as captured:
        cli.main(["--exact-commit", COMMIT, "--output", str(output)])
    assert captured.value.code == 2
    assert output.read_text() == "existing"


@pytest.mark.parametrize(
    ("error", "expected_code"),
    [
        (
            UriScreenError("element-bound", "private synthetic marker"),
            "element-bound",
        ),
        (RuntimeError("private synthetic marker"), None),
    ],
)
def test_failure_receipt_emits_only_allowlisted_scanner_code(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    expected_code: str | None,
):
    inputs = SimpleNamespace(
        context={"workflow_commit": COMMIT, "run_id": "17", "run_attempt": "1"},
        xml=b"<synthetic/>",
        binding=SimpleNamespace(
            archive_payload=SimpleNamespace(sha256="b" * 64, byte_count=1),
            member_path="synthetic.xml",
            member_payload=SimpleNamespace(sha256="c" * 64, byte_count=12),
        ),
        parent=SimpleNamespace(digest=lambda: "d" * 64),
    )

    def verified(*_args: Any, **_kwargs: Any) -> Any:
        return inputs

    def review_cases(
        _digest: str,
    ) -> tuple[list[dict[str, str]], dict[str, Any]]:
        return [], {"packet_case_count": 0, "packet_cases_reviewed": 0}

    monkeypatch.setattr(cli, "_verified_inputs", verified)
    monkeypatch.setattr(cli, "load_review_cases", review_cases)

    def fail(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise error

    monkeypatch.setattr(cli, "screen_pbs_native_uris", fail)
    output = tmp_path / "failure.json"
    report = cli.run(COMMIT, output)

    assert report.get("failure_code") == expected_code
    assert "private synthetic marker" not in output.read_text()
