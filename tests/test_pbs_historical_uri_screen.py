"""Dispatch and aggregate-receipt boundaries for the opt-in URI screen."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml
from scripts import screen_historical_pbs_uri_references as cli
from scripts import screen_historical_pbs_xlink_references as xlink_cli
from test_au_pbs_v3 import _zip  # ruff: ignore[import-private-name]
from test_australian_source_contracts import _receipt  # ruff: ignore[import-private-name]
from test_pbs_historical_silver import PATH, SOURCE

from global_medicines_atlas import pbs_xlink_reference_candidates as xlink
from global_medicines_atlas.pbs_member_identity import (
    build_pbs_xml_member_binding,
)
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
        archive=b"archive-bytes",
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


XLINK_NS = (
    b"""xmlns="http://schema.pbs.gov.au/" """
    b'''xmlns:xlink="http://www.w3.org/1999/xlink"'''
)


def _run_xlink(body: bytes, output_path: Path) -> dict[str, Any]:
    member = b"<root " + XLINK_NS + b">" + body + b"</root>"
    archive = _zip([(PATH, member)])
    parent = _receipt(archive, SOURCE)
    binding = build_pbs_xml_member_binding(archive, parent)
    return xlink.export_pbs_xlink_reference_candidates(
        archive, member, parent, binding, output_path
    )


def test_xlink_unique_local_edges_stream_with_digest_and_count(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "edges.jsonl"
    report = _run_xlink(
        b'<code xml:id="target"/><code xlink:href="#target"/>'
        b'<code xlink:href="#target"/>',
        output_path,
    )
    payload = output_path.read_bytes()
    edges = [json.loads(line) for line in payload.splitlines()]
    assert report["candidate_edge_count"] == 2
    assert report["reference_count"] == 2
    assert report["abstention_counts"] == {}
    assert report["resolution_counts"] == {"candidate_unique_same_member_id": 2}
    assert [edge["kind"] for edge in edges] == [
        "source_declared_xlink_link",
        "source_declared_xlink_link",
    ]
    assert (
        edges[0]["source_occurrence_sha256"]
        != edges[1]["source_occurrence_sha256"]
    )
    serialized = json.dumps(report)
    assert '"href"' not in serialized
    assert "#target" not in serialized
    assert report["semantic_relationships_qualified"] is False
    assert report["occurrence_hash_disclosure"] == (
        "deterministic_pseudonymous_correlatable"
    )
    assert report["artifact_finalized"] is True
    assert report["artifact_byte_count"] == len(payload)
    assert report["artifact_sha256"] == hashlib.sha256(payload).hexdigest()


def test_xlink_negative_controls_are_accounted_and_never_exported(
    tmp_path: Path,
) -> None:
    report = _run_xlink(
        b'<code xml:id="dup"/><code xml:id="dup"/>'
        b'<code xlink:href="#dup"/>'
        b'<code xlink:href="#missing"/>'
        b'<code xlink:href="#"/>'
        b'<code xlink:href="#bad%20id"/>'
        b'<code xlink:href="https://example.test/id"/>'
        b'<code xlink:href="relative"/>'
        b'<code xlink:href="##id"/>'
        b'<code xml:base="https://example.test/" xlink:href="#target"/>'
        b'<container xml:base="https://example.test/">'
        b'<code xlink:href="#target"/></container>'
        b'<code xlink:href="#other_member"/>',
        tmp_path / "edges.jsonl",
    )
    assert report["candidate_edge_count"] == 0
    assert report["abstention_counts"] == {
        "duplicate_same_member_xml_id": 1,
        "invalid_ncname_fragment": 1,
        "malformed_or_nonlocal_href": 3,
        "missing_same_member_xml_id": 2,
        "percent_encoded_fragment": 1,
        "xml_base_in_ancestry": 2,
    }
    assert report["external_links_emitted"] == 0
    assert report["artifact_byte_count"] == 0
    assert (tmp_path / "edges.jsonl").read_bytes() == b""


def test_xlink_cross_member_identifier_does_not_resolve(
    tmp_path: Path,
) -> None:
    member = (
        b"<root " + XLINK_NS + b'><code xlink:href="#other_member"/></root>'
    )
    other = b"<root " + XLINK_NS + b'><code xml:id="other_member"/></root>'
    archive = _zip([(PATH, member), ("other.xml", other)])
    parent = _receipt(archive, SOURCE)
    binding = build_pbs_xml_member_binding(archive, parent)
    report = xlink.export_pbs_xlink_reference_candidates(
        archive, member, parent, binding, tmp_path / "edges.jsonl"
    )
    assert report["abstention_counts"] == {"missing_same_member_xml_id": 1}
    assert report["candidate_edge_count"] == 0


@pytest.mark.parametrize(
    ("name", "expected_int"),
    [("_okay.1-" + chr(0x3B1), 1), ("1bad", 0), ("has:colon", 0)],
)
def test_xlink_ncname_validation(name: str, expected_int: int) -> None:
    assert bool(xlink._NCNAME.fullmatch(name)) is bool(expected_int)


def test_xlink_qname_and_occurrence_address_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert xlink._qname(f"{{{xlink.PBS_V3_NAMESPACE}}}code") == "pbs:code"
    assert xlink._qname("{urn:foreign}code") is None
    assert "x-unknown" not in xlink._ALLOWED_PBS_ELEMENTS
    assert xlink._qname(f"{{{xlink.PBS_V3_NAMESPACE}}}not-allowlisted") is None
    monkeypatch.setattr(xlink, "MAX_OCCURRENCE_ADDRESS_BYTES", 3)
    with pytest.raises(ValueError, match="occurrence address exceeds"):
        xlink._address_digest("four")


def test_xlink_long_identifier_and_href_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(xlink, "MAX_LITERAL_BYTES", 3)
    with pytest.raises(ValueError, match="identifier byte limit"):
        _run_xlink(b'<code xml:id="long"/>', tmp_path / "identifier.jsonl")
    with pytest.raises(ValueError, match="reference byte limit"):
        _run_xlink(b'<code xlink:href="#long"/>', tmp_path / "href.jsonl")
    assert not list(tmp_path.iterdir())


def test_xlink_unallowlisted_source_or_target_abstains(
    tmp_path: Path,
) -> None:
    report = _run_xlink(
        b'<code xml:id="target"/><x-unknown xlink:href="#target"/>'
        b'<x-unknown xml:id="unlisted"/><code xlink:href="#unlisted"/>',
        tmp_path / "edges.jsonl",
    )
    assert report["candidate_edge_count"] == 0
    assert report["abstention_counts"] == {"element_qname_not_allowlisted": 2}
    assert (tmp_path / "edges.jsonl").read_bytes() == b""


def test_xlink_element_and_index_storage_limits_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(xlink, "MAX_ELEMENTS", 1)
    with pytest.raises(ValueError, match="element count limit"):
        _run_xlink(b"<code/>", tmp_path / "element-limit.jsonl")
    monkeypatch.setattr(xlink, "MAX_ELEMENTS", 20_000_000)
    monkeypatch.setattr(xlink, "MAX_INDEX_BYTES", 4096)
    member = (
        b"<root "
        + XLINK_NS
        + b">"
        + b"".join(
            f'<code xml:id="identifier-{number}"/>'.encode()
            for number in range(4096)
        )
        + b"</root>"
    )
    with sqlite3.connect(":memory:") as index:
        index.execute(
            "CREATE TABLE identifiers ("
            "literal TEXT PRIMARY KEY, occurrence_count INTEGER NOT NULL, "
            "occurrence_sha256 TEXT NOT NULL, element_qname TEXT)"
        )
        with pytest.raises(ValueError, match="identifier index byte limit"):
            xlink._build_identifier_index(member, index)
    monkeypatch.setattr(xlink, "MAX_INDEX_BYTES", xlink.MIN_INDEX_BYTES - 1)
    with pytest.raises(ValueError, match="minimum supported schema size"):
        _run_xlink(b"<code/>", tmp_path / "index-minimum.jsonl")
    assert not list(tmp_path.iterdir())


def test_xlink_inconsistent_parser_stack_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        xlink,
        "iter_xml_events",
        lambda *_args, **_kwargs: iter([
            ("end", SimpleNamespace(tag="root"), None)
        ]),
    )
    with pytest.raises(ValueError, match="event stack is inconsistent"):
        list(xlink._iter_member_starts(b"<root/>"))


def test_xlink_short_write_removes_incomplete_temporary_artifact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    real_factory = xlink.NamedTemporaryFile

    class ShortWriter:
        def __init__(self, handle: Any) -> None:
            self.handle = handle
            self.name = handle.name

        def __enter__(self) -> ShortWriter:
            return self

        def __exit__(self, *args: Any) -> Any:
            return self.handle.__exit__(*args)

        def write(self, data: bytes) -> int:
            self.handle.write(data[:1])
            return len(data) - 1

        def flush(self) -> None:
            self.handle.flush()

        def fileno(self) -> int:
            return self.handle.fileno()

    monkeypatch.setattr(
        xlink,
        "NamedTemporaryFile",
        lambda **kwargs: ShortWriter(real_factory(**kwargs)),
    )
    with pytest.raises(OSError, match="write was incomplete"):
        _run_xlink(
            b'<code xml:id="target"/><code xlink:href="#target"/>',
            tmp_path / "edges.jsonl",
        )
    assert not list(tmp_path.iterdir())


def test_xlink_two_pass_element_count_mismatch_cleans_temporary_artifact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    resolve = xlink._resolve_and_write

    def mismatched(*args: Any, **kwargs: Any) -> Any:
        result = resolve(*args, **kwargs)
        return (*result[:-1], result[-1] + 1)

    monkeypatch.setattr(xlink, "_resolve_and_write", mismatched)
    with pytest.raises(ValueError, match="pass element counts differ"):
        _run_xlink(
            b'<code xml:id="target"/><code xlink:href="#target"/>',
            tmp_path / "edges.jsonl",
        )
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    ("limit", "message"),
    [
        ("MAX_MEMBER_BYTES", "member exceeds"),
        ("MAX_REFERENCES", "reference limit"),
        ("MAX_IDENTIFIERS", "identifier limit"),
        ("MAX_OUTPUT_EDGES", "output edge limit"),
        ("MAX_OUTPUT_BYTES", "output byte limit"),
    ],
)
def test_xlink_bounds_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    limit: str,
    message: str,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(xlink, limit, 1)
    if limit == "MAX_REFERENCES":
        body = b'<code xlink:href="#one"/><code xlink:href="#two"/>'
    elif limit == "MAX_IDENTIFIERS":
        body = b'<code xml:id="one"/><code xml:id="two"/>'
    elif limit == "MAX_OUTPUT_EDGES":
        body = (
            b'<code xml:id="target"/><code xlink:href="#target"/>'
            b'<code xlink:href="#target"/>'
        )
    else:
        body = b'<code xml:id="target"/><code xlink:href="#target"/>'
    with pytest.raises(ValueError, match=message):
        _run_xlink(body, tmp_path / "edges.jsonl")
    assert not list(tmp_path.iterdir())


def test_xlink_output_failure_preserves_previous_file_and_cleans_temp(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "edges.jsonl"
    output_path.write_bytes(b"previous complete artifact")
    monkeypatch.setattr(xlink, "MAX_OUTPUT_BYTES", 300)
    body = (
        b'<code xml:id="target"/><code xlink:href="#target"/>'
        b'<code xlink:href="#target"/>'
    )
    with pytest.raises(ValueError, match="output byte limit"):
        _run_xlink(body, output_path)
    assert output_path.read_bytes() == b"previous complete artifact"
    assert list(tmp_path.iterdir()) == [output_path]


def test_xlink_input_identity_must_match_exact_member(tmp_path: Path) -> None:
    member = b"<root " + XLINK_NS + b"><code/></root>"
    archive = _zip([(PATH, member)])
    parent = _receipt(archive, SOURCE)
    binding = build_pbs_xml_member_binding(archive, parent)
    with pytest.raises(ValueError, match="member"):
        xlink.export_pbs_xlink_reference_candidates(
            archive, member + b" ", parent, binding, tmp_path / "edges.jsonl"
        )
    assert not list(tmp_path.iterdir())


def test_xlink_workflow_is_exact_main_artifact_only() -> None:
    workflow_path = (
        Path(__file__).parents[1]
        / ".github/workflows/pbs-xlink-candidate-qualification.yml"
    )
    workflow = yaml.safe_load(workflow_path.read_text())
    job = workflow["jobs"]["qualify-xlink-candidates"]
    assert job["if"] == "github.ref == 'refs/heads/main'"
    assert job["permissions"] == {"contents": "read"}
    checkout = next(
        step
        for step in job["steps"]
        if "actions/checkout" in step.get("uses", "")
    )
    assert checkout["with"]["persist-credentials"] is False
    run_step = next(step for step in job["steps"] if step.get("run"))
    assert 'test "${GITHUB_SHA}" = "${REQUESTED_COMMIT}"' in run_step["run"]
    assert (
        "scripts/screen_historical_pbs_xlink_references.py" in run_step["run"]
    )
    retained = [
        step
        for step in job["steps"]
        if step.get("uses", "").startswith("actions/upload-artifact")
    ]
    assert len(retained) == 2
    assert retained[0]["if"] == "always()"
    assert retained[1]["if"] == "success()"
    assert all(step["with"]["retention-days"] == 30 for step in retained)
    assert "issues: write" not in str(workflow)


def test_xlink_screen_binds_candidate_to_same_verified_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = SimpleNamespace(
        archive_payload=SimpleNamespace(sha256="b" * 64, byte_count=12),
        member_path="PBS.xml",
        member_payload=SimpleNamespace(sha256="c" * 64, byte_count=8),
    )
    inputs = SimpleNamespace(
        context={"workflow_commit": COMMIT, "run_id": "17", "run_attempt": "1"},
        archive=b"archive-bytes",
        xml=b"<member/>bytes",
        binding=binding,
        parent=SimpleNamespace(digest=lambda: "d" * 64),
    )
    calls: list[Any] = []

    def verified(exact_commit: str, *, transport: Any, retry: Any) -> Any:
        calls.append((exact_commit, transport, retry))
        return inputs

    def export(
        archive: bytes,
        member: bytes,
        parent: Any,
        member_binding: Any,
        destination: Path,
    ) -> dict[str, Any]:
        assert archive is inputs.archive
        assert member is inputs.xml
        assert parent is inputs.parent
        assert member_binding is binding
        destination.write_bytes(b"candidate-jsonl\n")
        return {
            "qualification": "candidate",
            "semantic_relationships_qualified": False,
            "candidate_edge_count": 1,
            "artifact_byte_count": 16,
            "artifact_sha256": "f" * 64,
        }

    monkeypatch.setattr(xlink_cli, "_verified_inputs", verified)
    monkeypatch.setattr(
        xlink_cli, "export_pbs_xlink_reference_candidates", export
    )
    receipt_path = tmp_path / "receipt.json"
    xlink_output = tmp_path / "candidates.jsonl"
    report = xlink_cli.run(COMMIT, receipt_path, xlink_output)

    assert calls
    assert calls[0][0:2] == (COMMIT, None)
    envelope = json.loads(receipt_path.read_text())
    assert envelope["report"] == report
    assert report["status"] == "passed"
    assert report["source_receipt_sha256"] == "d" * 64
    assert report["member_sha256"] == "c" * 64
    assert report["candidate_artifact"]["candidate_edge_count"] == 1
    assert report["semantic_relationships_qualified"] is False
    assert report["admissions_created"] == report["canaries_performed"] == 0
    assert report["publication_performed"] is False
    assert report["new_sources_added"] == 0
    assert xlink_output.read_bytes() == b"candidate-jsonl\n"
