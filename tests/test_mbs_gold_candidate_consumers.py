from __future__ import annotations

import asyncio
import hashlib
import json
from importlib import import_module
from pathlib import Path
from unittest.mock import Mock

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from test_mbs_gold_graph import (
    _admitted_input,  # ruff: ignore[import-private-name] -- shared fixture
    _admitted_table,  # ruff: ignore[import-private-name] -- shared fixture
)
from test_mbs_gold_scalar_projection import (
    _typed_benefits,  # ruff: ignore[import-private-name] -- shared fixture
)

import global_medicines_atlas.atlas_browser_qualification as browser_qualification
import global_medicines_atlas.mbs_gold_consumer_qualification as consumer_qualification
from global_medicines_atlas.atlas_browser_qualification import (
    _check_page_identity,  # ruff: ignore[import-private-name] -- direct contract test
    _follow_next_link,  # ruff: ignore[import-private-name] -- direct contract test
    _is_expected_main_frame_response,  # ruff: ignore[import-private-name] -- direct response matcher contract
    _read_edge_ids,  # ruff: ignore[import-private-name] -- direct contract test
    _verify_browser_assets,  # ruff: ignore[import-private-name] -- direct contract test
    _verify_loopback_requests,  # ruff: ignore[import-private-name] -- direct contract test
    qualify_candidate_atlas_browser,
)
from global_medicines_atlas.mbs_gold_candidate_export import (
    write_mbs_gold_candidate_edges,
)
from global_medicines_atlas.mbs_gold_consumer_qualification import (
    qualify_consumers,
)
from global_medicines_atlas.mbs_gold_graph import (
    build_mbs_gold_graph_from_admitted_silver,
)
from global_medicines_atlas.mbs_gold_scalar_projection import (
    project_mbs_gold_scalar_candidate,
)
from global_medicines_atlas.receipts import SourceReceipt

ROOT = Path(__file__).resolve().parents[1]


def _candidate_artifact(tmp_path):
    candidate = build_mbs_gold_graph_from_admitted_silver(
        _admitted_table("services", "ItemNum"),
        _admitted_table("benefits", "Benefit100"),
        _admitted_input(),
    )
    edge_path = tmp_path / "candidate.parquet"
    write_mbs_gold_candidate_edges(
        candidate,
        edge_path,
        expected_graph_sha256=candidate.graph_sha256,
    )
    qualification = {
        "graph": {
            "edge_count": len(candidate.edges),
            "graph_sha256": candidate.graph_sha256,
        }
    }
    expected_bindings = {
        "input_admission_sha256": candidate.input_admission_sha256,
        "input_semantic_manifest_sha256": candidate.input_semantic_manifest_sha256,
        "graph_sha256": candidate.graph_sha256,
    }
    return edge_path, qualification, expected_bindings, candidate


def test_candidate_consumer_receipt_traverses_each_surface_without_edge_ids(
    tmp_path,
) -> None:
    edge_path, qualification, expected_bindings, candidate = (
        _candidate_artifact(tmp_path)
    )
    receipt = qualify_consumers(
        edge_path,
        qualification,
        page_size=1,
        expected_bindings=expected_bindings,
        browser_qualifier=qualify_candidate_atlas_browser,
    )

    assert receipt["candidate_only"] is True
    assert receipt["edge_count"] == len(candidate.edges)
    assert receipt["surfaces"] == ["API", "Atlas", "Browser", "CLI"]
    assert receipt["page_offsets"] == [0, 1]
    assert receipt["browser_page_offsets"] == [0, 1]
    assert receipt["surface_edge_id_sha256"] == {
        "API": receipt["surface_edge_id_sha256"]["CLI"],
        "Atlas": receipt["surface_edge_id_sha256"]["CLI"],
        "Browser": receipt["surface_edge_id_sha256"]["CLI"],
        "CLI": receipt["surface_edge_id_sha256"]["CLI"],
    }
    assert receipt["review_state"] == "not_reviewed"
    assert "items" not in receipt
    assert all(
        edge["edge_id"] not in str(receipt)
        for edge in pq.read_table(edge_path).to_pylist()
    )


def test_candidate_scalar_query_canary_preserves_decimal_and_date_engine_parity(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_receipt_path = (
        Path(__file__).resolve().parents[1] / "quality/bronze/receipts/au-mbs/"
        "bbd662119ebebfdf08baf14c0b15c0dd5c93465910fd4f5309f37ecd37a82b8d.json"
    )
    source_receipt = SourceReceipt.model_validate_json(
        source_receipt_path.read_bytes()
    )
    benefits = _typed_benefits("Benefit100", ["10.25", "2.75"], "converted")
    rows = benefits.to_pylist()
    for row, value in zip(rows, ["2025-07-01", "2025-07-15"], strict=True):
        row["BenefitStartDate"] = {
            "native_value": value,
            "native_state": "value",
            "conversion_status": "converted",
            "typed_value": value,
        }
    benefits = pa.Table.from_pylist(rows).replace_schema_metadata(
        benefits.schema.metadata
    )
    graph = build_mbs_gold_graph_from_admitted_silver(
        _admitted_table("services", "ItemNum"),
        benefits,
        _admitted_input(),
    )
    projection = project_mbs_gold_scalar_candidate(graph, source_receipt)
    scalar_path = tmp_path / "candidate-scalar.parquet"
    pq.write_table(projection, scalar_path)
    qualification = {
        "graph": {
            "edge_count": len(graph.edges),
            "graph_sha256": graph.graph_sha256,
            "input_admission_sha256": graph.input_admission_sha256,
            "input_semantic_manifest_sha256": (
                graph.input_semantic_manifest_sha256
            ),
            "source_receipt_sha256": graph.nodes[0].evidence.receipt_sha256,
        },
        "source_identity": {
            "source_sha256": graph.nodes[0].evidence.source_sha256,
            "source_record_count": graph.source_record_count,
            "schema_era": graph.nodes[0].evidence.catalog_version,
        },
    }

    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[1] / "scripts")
    )
    script = import_module(
        "scripts.qualify_australian_mbs_gold_candidate_consumers"
    )
    receipt = script.qualify_candidate_scalar_queries(
        scalar_path, qualification
    )

    assert receipt["candidate_only"] is True
    assert receipt["consumer_admission_performed"] is False
    assert receipt["row_count"] == 2
    assert (
        receipt["parquet_sha256"]
        == hashlib.sha256(scalar_path.read_bytes()).hexdigest()
    )
    assert receipt["query_cases"]["decimal"]["engines"] == [
        "duckdb",
        "polars",
    ]
    assert receipt["query_cases"]["date"]["engines"] == [
        "duckdb",
        "polars",
    ]
    assert receipt["query_cases"]["decimal"]["returned_rows"] == 1
    assert receipt["query_cases"]["date"]["returned_rows"] == 2
    assert receipt["query_cases"]["date"]["returned_rows"] > 0
    assert receipt["query_cases"]["decimal"]["row_limit"] == 1000
    assert "10.25" not in json.dumps(receipt)
    assert "2025-07-01" not in json.dumps(receipt)
    assert "rows" not in receipt

    original_duckdb_adapter = script.DuckDBQueryAdapter
    original_polars_adapter = script.PolarsQueryAdapter

    class EmptyDateAdapter:
        def __init__(self, name, adapter) -> None:
            self.name = name
            self.adapter = adapter

        def execute(self, read, spec):
            if spec.filters[0].column == script.SCALAR_DATE_COLUMN:
                return ()
            return self.adapter.execute(read, spec)

    monkeypatch.setattr(
        script,
        "DuckDBQueryAdapter",
        lambda: EmptyDateAdapter("duckdb", original_duckdb_adapter()),
    )
    monkeypatch.setattr(
        script,
        "PolarsQueryAdapter",
        lambda: EmptyDateAdapter("polars", original_polars_adapter()),
    )
    with pytest.raises(
        ValueError, match="candidate scalar date filter returned no rows"
    ):
        script.qualify_candidate_scalar_queries(scalar_path, qualification)

    forged = pq.read_table(scalar_path)
    metadata = dict(forged.schema.metadata or {})
    metadata[b"graph_sha256"] = b"0" * 64
    pq.write_table(forged.replace_schema_metadata(metadata), scalar_path)
    with pytest.raises(ValueError, match="metadata differs"):
        script.qualify_candidate_scalar_queries(scalar_path, qualification)


def test_reviewed_candidate_canary_binds_the_exact_maintainer_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    script = import_module(
        "scripts.qualify_australian_mbs_gold_candidate_consumers"
    )
    qualification = json.loads(
        (ROOT / script.QUALIFICATION_PATH).read_text(encoding="utf-8")
    )
    review = json.loads(
        (ROOT / script.EDGE_REVIEW_DISPOSITION_PATH).read_text(encoding="utf-8")
    )

    binding = script.reviewed_candidate_relationship_binding(
        qualification,
        review,
        review_file_sha256=script.EXPECTED_EDGE_REVIEW_FILE_SHA256,
    )

    assert binding["state"] == "reviewed_candidate_only"
    assert binding["edge_count"] == 5989
    assert binding["edge_id_sha256"] == script.EXPECTED_REVIEWED_EDGE_ID_SHA256
    assert binding["m110_overall_accepted"] is False
    assert binding["m112_federation_accepted"] is False

    altered_review = {**review, "decision": "accept all semantic matches"}
    with pytest.raises(ValueError, match="review disposition"):
        script.reviewed_candidate_relationship_binding(
            qualification,
            altered_review,
            review_file_sha256=script.EXPECTED_EDGE_REVIEW_FILE_SHA256,
        )


def test_reviewed_candidate_canary_rejects_consumer_surface_drift() -> None:
    script = import_module(
        "scripts.qualify_australian_mbs_gold_candidate_consumers"
    )
    receipt = {
        "surface_edge_id_sha256": dict.fromkeys(
            ("API", "Atlas", "Browser", "CLI"), "a" * 64
        )
    }
    binding = {"edge_count": 5989, "edge_id_sha256": "a" * 64}

    canary = script.qualify_reviewed_candidate_canaries(receipt, binding)
    assert canary["status"] == "passed"
    assert canary["surface_canary_count"] == 4
    assert canary["review_state"] == "reviewed_candidate"
    assert canary["m110_overall_accepted"] is False

    receipt["surface_edge_id_sha256"]["Browser"] = "b" * 64
    with pytest.raises(ValueError, match="reviewed edge set"):
        script.qualify_reviewed_candidate_canaries(receipt, binding)


def test_candidate_v4_lineage_binds_exact_six_source_faithful_tables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[1] / "scripts")
    )
    script = import_module(
        "scripts.qualify_australian_mbs_gold_candidate_consumers"
    )
    admission = script._read_json(script.ROOT / script.ADMISSION_PATH)
    semantic = script._read_json(script.ROOT / script.SEMANTIC_PATH)
    authorization = script._read_json(
        script.ROOT / script.V4_USE_AUTHORIZATION_PATH
    )
    manifest = script._read_json(script.ROOT / script.MBS_V4_MANIFEST_PATH)
    qualification = script._read_json(
        script.ROOT / script.MBS_V4_QUALIFICATION_PATH
    )["qualification"]
    source_report = script._read_json(
        script.ROOT / script.SOURCE_CANDIDATE_REPORT_PATH
    )

    binding = script.candidate_v4_lineage_binding(
        admission,
        semantic,
        authorization,
        manifest,
        qualification,
        source_report,
    )

    assert binding["candidate_only"] is True
    assert binding["status"] == (
        "verified_candidate_source_faithful_silver_lineage"
    )
    tables = binding["tables"]
    assert isinstance(tables, list)
    assert [table["name"] for table in tables] == [
        "benefits",
        "caps",
        "descriptions",
        "fees",
        "hierarchy",
        "services",
    ]
    assert all(table["row_count"] == 5989 for table in tables)
    boundaries = binding["boundaries"]
    assert isinstance(boundaries, dict)
    assert boundaries["production_admission_or_promotion"] is False
    assert boundaries["new_rights_or_licensing_conclusion"] is False
    assert boundaries["m112_federation_acceptance"] is False
    assert "native_value" not in str(binding)

    changed_admission = json.loads(json.dumps(admission))
    changed_admission["tables"][0]["path"] = "silver/forged.parquet"
    with pytest.raises(ValueError, match="table identity differs"):
        script.candidate_v4_lineage_binding(
            changed_admission,
            semantic,
            authorization,
            manifest,
            qualification,
            source_report,
        )

    duplicate_semantic = json.loads(json.dumps(semantic))
    conflicting = json.loads(json.dumps(duplicate_semantic["tables"][0]))
    conflicting["sha256"] = "0" * 64
    duplicate_semantic["tables"][-1] = conflicting
    with pytest.raises(ValueError, match="duplicate table identities"):
        script.candidate_v4_lineage_binding(
            admission,
            duplicate_semantic,
            authorization,
            manifest,
            qualification,
            source_report,
        )


def test_qualification_script_emits_browser_bound_aggregate_receipt(
    tmp_path, monkeypatch, capsys
) -> None:
    edge_path, qualification, expected_bindings, candidate = (
        _candidate_artifact(tmp_path)
    )
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[1] / "scripts")
    )
    script = import_module(
        "scripts.qualify_australian_mbs_gold_candidate_consumers"
    )
    candidate_ids = sorted(
        pq.read_table(edge_path).column("edge_id").to_pylist()
    )
    monkeypatch.setattr(
        script,
        "qualify_candidate_atlas_browser",
        lambda *_args: (
            candidate_ids,
            list(range(0, len(candidate_ids), 1000)),
        ),
    )
    read_json = script._read_json
    sha256 = script._sha256
    monkeypatch.setattr(
        script,
        "_read_json",
        lambda path: (
            qualification
            if path == script.QUALIFICATION_PATH
            else read_json(path)
        ),
    )
    monkeypatch.setattr(
        script,
        "_sha256",
        lambda path: (
            expected_bindings["input_admission_sha256"]
            if path == script.ROOT / script.ADMISSION_PATH
            else expected_bindings["input_semantic_manifest_sha256"]
            if path == script.ROOT / script.SEMANTIC_PATH
            else sha256(path)
        ),
    )
    output = tmp_path / "consumer-qualification.json"
    scalar_path = tmp_path / "candidate-scalar.parquet"
    scalar_path.write_bytes(b"candidate scalar placeholder")
    monkeypatch.setattr(
        script,
        "qualify_candidate_scalar_queries",
        lambda *_args: {
            "candidate_only": True,
            "consumer_admission_performed": False,
            "row_count": 1,
            "query_cases": {},
        },
    )
    monkeypatch.setattr(
        script,
        "reviewed_candidate_relationship_binding",
        lambda *_args, **_kwargs: {
            "edge_count": len(candidate_ids),
            "edge_id_sha256": hashlib.sha256(
                ("\n".join(candidate_ids) + "\n").encode()
            ).hexdigest(),
            "state": "reviewed_candidate_only",
        },
    )

    assert (
        script.main([
            "--edge-file",
            str(edge_path),
            "--scalar-file",
            str(scalar_path),
            "--output",
            str(output),
            "--workflow-commit",
            "a" * 40,
            "--workflow-repository",
            "edithatogo/global-medicines-atlas",
            "--workflow-run-id",
            "123456",
            "--workflow-run-attempt",
            "2",
        ])
        == 0
    )
    receipt = json.loads(output.read_text(encoding="utf-8"))
    assert receipt["surfaces"] == ["API", "Atlas", "Browser", "CLI"]
    assert receipt["reviewed_candidate_consumer_canary"]["status"] == "passed"
    assert (
        receipt["reviewed_candidate_consumer_canary"]["surface_canary_count"]
        == 4
    )
    assert receipt["hosted_workflow"] == {
        "repository": "edithatogo/global-medicines-atlas",
        "workflow": script.WORKFLOW_PATH,
        "commit": "a" * 40,
        "run_id": 123456,
        "run_attempt": 2,
        "run_url": (
            "https://github.com/edithatogo/global-medicines-atlas/"
            "actions/runs/123456"
        ),
    }
    assert receipt["edge_count"] == len(candidate.edges)
    assert (
        receipt["candidate_v4_use_authorization"]["authorized_object_count"]
        == 6
    )
    assert receipt["candidate_v4_use_authorization"]["candidate_only"] is True
    source_lineage = receipt["candidate_v4_source_lineage"]
    assert isinstance(source_lineage, dict)
    assert source_lineage["candidate_only"] is True
    assert receipt["candidate_scalar_query_canary"]["candidate_only"] is True
    assert len(source_lineage["tables"]) == 6
    assert source_lineage["source"]["source_receipt_sha256"] == (
        "c8c3e3baeee4c08dba1a944c19652ec184d90de850968fc4d6a124747d994e03"
    )
    assert "items" not in receipt
    assert all(
        edge["edge_id"] not in str(receipt)
        for edge in pq.read_table(edge_path).to_pylist()
    )
    assert json.loads(capsys.readouterr().out) == receipt


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("commit", "not-a-commit"),
        ("repository", "someone/else"),
        ("run_id", "0"),
        ("run_id", "1x"),
        ("run_attempt", "0"),
        ("run_attempt", "1x"),
    ],
)
def test_hosted_workflow_binding_rejects_untrusted_identity(
    field: str, value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[1] / "scripts")
    )
    script = import_module(
        "scripts.qualify_australian_mbs_gold_candidate_consumers"
    )
    values = {
        "commit": "a" * 40,
        "repository": "edithatogo/global-medicines-atlas",
        "run_id": "123",
        "run_attempt": "1",
    }
    values[field] = value
    with pytest.raises(ValueError, match="hosted qualification"):
        script.hosted_workflow_binding(**values)


def test_candidate_consumer_rejects_surfaces_agreeing_on_wrong_edge_ids(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    edge_path, qualification, expected_bindings, _candidate = (
        _candidate_artifact(tmp_path)
    )
    authoritative_ids = sorted(
        edge["edge_id"] for edge in pq.read_table(edge_path).to_pylist()
    )
    last = authoritative_ids[-1]
    replacement = last[:-1] + ("0" if last[-1] != "0" else "1")
    wrong_ids = [*authoritative_ids[:-1], replacement]
    monkeypatch.setattr(
        consumer_qualification, "_api_ids", lambda *_args: wrong_ids
    )
    monkeypatch.setattr(
        consumer_qualification, "_cli_ids", lambda *_args: wrong_ids
    )
    monkeypatch.setattr(
        consumer_qualification,
        "_atlas_ids",
        lambda *_args: (wrong_ids, [0, 1]),
    )

    with pytest.raises(ValueError, match="authoritative candidate edges"):
        qualify_consumers(
            edge_path,
            qualification,
            page_size=1,
            expected_bindings=expected_bindings,
        )


def test_candidate_consumer_rejects_browser_page_offset_drift(tmp_path) -> None:
    edge_path, qualification, expected_bindings, _candidate = (
        _candidate_artifact(tmp_path)
    )
    ids = sorted(pq.read_table(edge_path).column("edge_id").to_pylist())
    with pytest.raises(ValueError, match="page offsets differ"):
        qualify_consumers(
            edge_path,
            qualification,
            page_size=1,
            expected_bindings=expected_bindings,
            browser_qualifier=lambda *_args: (ids, [0]),
        )


def _valid_payload(bindings, *, offset=0, edge_count=1, items=None):
    return {
        "qualification": "admitted_real_silver_candidate_only",
        "admission_bindings": dict(bindings),
        "total": edge_count,
        "offset": offset,
        "items": items
        if items is not None
        else [
            {
                "edge_id": "mbs-gold-edge:" + "a" * 64,
                "controls": {"review_state": "not_reviewed"},
            }
        ],
        "has_more": offset + 1 < edge_count,
    }


class _BrowserLocator:
    def __init__(self, *, count=1, text="", rows=None, href=None):
        self._count = count
        self._text = text
        self._rows = rows or []
        self._href = href
        self.clicked = False

    def count(self):
        return self._count

    def inner_text(self):
        return self._text

    def evaluate_all(self, _script):
        return self._rows

    def get_attribute(self, _name):
        return self._href

    def click(self):
        self.clicked = True


class _BrowserPage:
    def __init__(self, *, url, locator):
        self.url = url
        self._locator = locator

    def locator(self, _selector):
        return self._locator

    def get_by_role(self, _role, name=None):
        if name is not None and "candidate edges" in str(name):
            return self._locator
        return self._locator


@pytest.mark.parametrize(
    ("url", "count", "message"),
    [
        ("http://127.0.0.1/gold/edges?kind=k&limit=1&offset=1", 1, "skipped"),
        (
            "http://127.0.0.1/gold/edges?kind=wrong&limit=1&offset=0",
            1,
            "filters",
        ),
        (
            "http://127.0.0.1/gold/edges?kind=k&limit=1&offset=0",
            0,
            "full edge count",
        ),
    ],
)
def test_browser_page_identity_rejects_changed_or_missing_state(
    url, count, message
) -> None:
    page = _BrowserPage(url=url, locator=_BrowserLocator(count=count))
    with pytest.raises(ValueError, match=message):
        _check_page_identity(
            page, edge_count=1, offset=0, kind="k", page_size=1
        )


@pytest.mark.parametrize(
    ("body", "rows", "message", "error"),
    [
        (
            "",
            [
                {
                    "Edge identifier": "mbs-gold-edge:" + "a" * 64,
                    "Review state": "not_reviewed",
                }
            ],
            "binding",
            ValueError,
        ),
        ("binding", [], "page size", ValueError),
        ("binding", [None], "invalid edge row", TypeError),
        (
            "binding",
            [{"Edge identifier": "bad", "Review state": "not_reviewed"}],
            "edge identity",
            ValueError,
        ),
        (
            "binding",
            [
                {
                    "Edge identifier": "mbs-gold-edge:" + "a" * 64,
                    "Review state": "reviewed",
                }
            ],
            "review state",
            ValueError,
        ),
    ],
)
def test_browser_edge_rows_reject_malformed_or_reviewed_data(
    body, rows, message, error
) -> None:
    page = _BrowserPage(
        url="http://127.0.0.1/gold/edges?kind=k&limit=1&offset=0",
        locator=_BrowserLocator(text=body, rows=rows),
    )
    with pytest.raises(error, match=message):
        _read_edge_ids(
            page,
            edge_count=1,
            offset=0,
            page_size=1,
            bindings={"graph_sha256": "binding"},
        )


@pytest.mark.parametrize(
    ("href", "has_more", "offset", "message"),
    [
        ("/gold/edges?kind=k&limit=1&offset=1", False, 1, "extra continuation"),
        (None, True, 1, "next-page link"),
        (
            "/gold/edges?kind=other&limit=1&offset=1",
            True,
            1,
            "changed its filters",
        ),
        ("/gold/edges?kind=k&limit=1&offset=2", True, 1, "skipped a page"),
    ],
)
def test_browser_continuation_rejects_invalid_targets(
    href, has_more, offset, message
) -> None:
    link_count = 1 if href is not None or not has_more else 0
    page = _BrowserPage(
        url="http://127.0.0.1/gold/edges?kind=k&limit=1&offset=0",
        locator=_BrowserLocator(count=link_count, href=href),
    )
    with pytest.raises(ValueError, match=message):
        _follow_next_link(
            page,
            has_more=has_more,
            kind="k",
            page_size=1,
            next_offset=offset,
        )


def test_browser_continuation_requires_a_link_target() -> None:
    page = _BrowserPage(
        url="http://127.0.0.1/gold/edges?kind=k&limit=1&offset=0",
        locator=_BrowserLocator(count=1),
    )
    with pytest.raises(ValueError, match="no target"):
        _follow_next_link(
            page,
            has_more=True,
            kind="k",
            page_size=1,
            next_offset=1,
        )


@pytest.mark.parametrize(
    ("navigation", "main_frame", "response_url", "expected"),
    [
        (True, True, "http://atlas/gold/edges?offset=1", True),
        (False, True, "http://atlas/gold/edges?offset=1", False),
        (True, False, "http://atlas/gold/edges?offset=1", False),
        (True, True, "http://atlas/gold/edges?offset=2", False),
    ],
)
def test_continuation_response_must_match_main_frame_and_exact_url(
    navigation, main_frame, response_url, expected
) -> None:
    page = Mock()
    page.main_frame = object()
    request = Mock()
    request.is_navigation_request.return_value = navigation
    request.frame = page.main_frame if main_frame else object()
    response = Mock()
    response.request = request
    response.url = response_url

    assert (
        _is_expected_main_frame_response(
            response,
            page,
            "http://atlas/gold/edges?offset=1",
        )
        is expected
    )


def test_browser_asset_and_request_scope_checks_fail_closed() -> None:
    with pytest.raises(ValueError, match="stylesheet"):
        _verify_browser_assets({})
    with pytest.raises(ValueError, match="stylesheet"):
        _verify_browser_assets({"/static/atlas.css": 404})
    _verify_browser_assets({"/static/atlas.css": 200})
    with pytest.raises(ValueError, match="left the loopback"):
        _verify_loopback_requests(
            {"127.0.0.1:8000", "example.test"}, "127.0.0.1:8000"
        )
    _verify_loopback_requests({"127.0.0.1:8000"}, "127.0.0.1:8000")


def test_browser_waits_for_delayed_stylesheet_before_qualifying(
    tmp_path, monkeypatch
) -> None:
    edge_path, _qualification, bindings, _candidate = _candidate_artifact(
        tmp_path
    )
    edges = pq.read_table(edge_path)
    create_app = browser_qualification.create_atlas_app

    def app_with_delayed_stylesheet(*args, **kwargs):
        app = create_app(*args, **kwargs)

        @app.middleware("http")
        async def delay_stylesheet(request, call_next):
            if request.url.path == "/static/atlas.css":
                await asyncio.sleep(0.2)
            return await call_next(request)

        return app

    monkeypatch.setattr(
        browser_qualification, "create_atlas_app", app_with_delayed_stylesheet
    )
    edge_ids, offsets = qualify_candidate_atlas_browser(
        edges,
        edges.column("kind")[0].as_py(),
        edges.num_rows,
        bindings,
        1,
    )

    assert len(edge_ids) == edges.num_rows
    assert offsets == [0, 1]


def test_browser_rejects_a_non_success_loopback_response(
    tmp_path, monkeypatch
) -> None:
    edge_path, _qualification, bindings, _candidate = _candidate_artifact(
        tmp_path
    )
    edges = pq.read_table(edge_path)

    async def not_found_app(_scope, _receive, send):
        await send({
            "type": "http.response.start",
            "status": 404,
            "headers": [],
        })
        await send({"type": "http.response.body", "body": b"not found"})

    monkeypatch.setattr(
        browser_qualification,
        "create_atlas_app",
        lambda *_args, **_kwargs: not_found_app,
    )
    with pytest.raises(ValueError, match="page was not served"):
        qualify_candidate_atlas_browser(
            edges,
            edges.column("kind")[0].as_py(),
            edges.num_rows,
            bindings,
            1,
        )


def test_browser_rejects_failed_continuation_with_valid_candidate_markup(
    tmp_path, monkeypatch
) -> None:
    edge_path, _qualification, bindings, _candidate = _candidate_artifact(
        tmp_path
    )
    edges = pq.read_table(edge_path)
    create_app = browser_qualification.create_atlas_app

    def app_with_failed_second_page(*args, **kwargs):
        app = create_app(*args, **kwargs)

        @app.middleware("http")
        async def mark_second_page_unavailable(request, call_next):
            response = await call_next(request)
            if (
                request.url.path == "/gold/edges"
                and request.query_params.get("offset") == "1"
            ):
                response.status_code = 503
            return response

        return app

    monkeypatch.setattr(
        browser_qualification, "create_atlas_app", app_with_failed_second_page
    )
    with pytest.raises(ValueError, match="continuation response status"):
        qualify_candidate_atlas_browser(
            edges,
            edges.column("kind")[0].as_py(),
            edges.num_rows,
            bindings,
            1,
        )


def test_mapping_and_binding_validation_fail_closed(tmp_path) -> None:
    edge_path, qualification, expected, _candidate = _candidate_artifact(
        tmp_path
    )
    edges = pq.read_table(edge_path)
    with pytest.raises(TypeError, match="qualification graph"):
        consumer_qualification._bindings(edges, {"graph": None}, expected)
    with pytest.raises(ValueError, match="graph digest"):
        consumer_qualification._bindings(
            edges, {"graph": {"graph_sha256": "0" * 64}}, expected
        )
    with pytest.raises(ValueError, match="expected inputs"):
        consumer_qualification._bindings(
            edges, qualification, {**expected, "graph_sha256": "0" * 64}
        )
    metadata = dict(edges.schema.metadata or {})
    metadata[b"input_admission_sha256"] = b"bad"
    malformed = edges.replace_schema_metadata(metadata)
    with pytest.raises(ValueError, match="binding is malformed"):
        consumer_qualification._bindings(malformed, qualification, None)
    metadata = dict(edges.schema.metadata or {})
    metadata[b"qualification"] = b"not-qualified"
    wrong_qualification = edges.replace_schema_metadata(metadata)
    with pytest.raises(ValueError, match="not the admitted real candidate"):
        consumer_qualification._bindings(
            wrong_qualification, qualification, None
        )


@pytest.mark.parametrize(
    ("change", "error", "message"),
    [
        (
            lambda p: p.update(qualification="synthetic"),
            ValueError,
            "qualification",
        ),
        (lambda p: p.update(admission_bindings={}), ValueError, "bindings"),
        (lambda p: p.update(total=99), ValueError, "total or offset"),
        (lambda p: p.update(offset=99), ValueError, "total or offset"),
        (lambda p: p.update(items=None), TypeError, "edge page"),
        (lambda p: p.update(items=[None]), TypeError, "edge row"),
        (lambda p: p["items"][0].update(edge_id="bad"), ValueError, "identity"),
        (
            lambda p: p["items"][0].update(review_state="reviewed"),
            ValueError,
            "review state",
        ),
        (
            lambda p: p["items"][0].update(
                controls={"review_state": "reviewed"}
            ),
            ValueError,
            "review state",
        ),
        (lambda p: p.update(has_more=True), ValueError, "continuation"),
    ],
)
def test_consumer_page_payload_rejections(change, error, message) -> None:
    bindings = {"graph_sha256": "0" * 64}
    payload = _valid_payload(bindings)
    change(payload)
    with pytest.raises(error, match=message):
        consumer_qualification._page_ids(
            payload, offset=0, edge_count=1, bindings=bindings, page_size=1
        )


def test_consumer_page_payload_accepts_explicit_review_state() -> None:
    bindings = {"graph_sha256": "0" * 64}
    payload = _valid_payload(bindings)
    payload["items"][0]["controls"] = {}
    payload["items"][0]["review_state"] = "not_reviewed"
    assert consumer_qualification._page_ids(
        payload, offset=0, edge_count=1, bindings=bindings, page_size=1
    ) == ["mbs-gold-edge:" + "a" * 64]


def test_api_and_cli_consumer_refusals_are_rejected(
    tmp_path, monkeypatch
) -> None:
    edge_path, _qualification, bindings, _candidate = _candidate_artifact(
        tmp_path
    )

    class RefusedResponse:
        status_code = 400
        text = ""

        def json(self):
            return {}

    class RefusedClient:
        def __init__(self, _app):
            pass

        def get(self, *_args, **_kwargs):
            return RefusedResponse()

    monkeypatch.setattr(consumer_qualification, "TestClient", RefusedClient)
    with pytest.raises(ValueError, match="API consumer rejected"):
        consumer_qualification._api_ids(
            pq.read_table(edge_path), "kind", 1, bindings, 1
        )

    class RefusedRunner:
        def invoke(self, *_args, **_kwargs):
            return type("Result", (), {"exit_code": 2, "stdout": ""})()

    monkeypatch.setattr(consumer_qualification, "CliRunner", RefusedRunner)
    with pytest.raises(ValueError, match="CLI consumer rejected"):
        consumer_qualification._cli_ids(edge_path, "kind", 1, bindings, 1)


def _atlas_html(
    bindings,
    *,
    next_href=None,
    edge_id="mbs-gold-edge:" + "a" * 64,
    review="not_reviewed",
    total=1,
    include_id=True,
):
    edge = (
        f"<dl><dt>Edge identifier</dt><dd><code>{edge_id}</code></dd>"
        f"<dt>Review state</dt><dd>{review}</dd></dl>"
        if include_id
        else ""
    )
    binding_text = " ".join(bindings.values())
    link = f'<a href="{next_href}">Next page</a>' if next_href else ""
    return f"{edge}<p>{binding_text}</p><p>{total} candidate edge</p>{link}"


@pytest.mark.parametrize(
    ("html", "status", "message", "count", "page_size"),
    [
        (_atlas_html({"x": "x"}, total=2), 200, "next-page link", 2, 1),
        (
            _atlas_html(
                {"x": "x"},
                next_href="/gold/edges?kind=other&limit=1&offset=1",
                total=2,
            ),
            200,
            "preserve its filter",
            2,
            1,
        ),
        (
            _atlas_html(
                {"x": "x"},
                next_href="/gold/edges?kind=k&limit=1&offset=2",
                total=2,
            ),
            200,
            "skipped or repeated",
            2,
            1,
        ),
        (_atlas_html({"x": "x"}), 400, "Atlas consumer rejected", 1, 1),
        (
            _atlas_html({"x": "x"}, include_id=False),
            200,
            "unexpected page size",
            1,
            1,
        ),
        (
            _atlas_html({"x": "x"}, review="reviewed"),
            200,
            "changed review state",
            1,
            1,
        ),
        (_atlas_html({}, total=1), 200, "identity binding", 1, 1),
        (
            _atlas_html({"x": "x"}, total=5),
            200,
            "full matching edge count",
            1,
            1,
        ),
        (
            _atlas_html(
                {"x": "x"}, next_href="/gold/edges?kind=k&limit=1&offset=1"
            ),
            200,
            "unexpected continuation",
            1,
            1,
        ),
    ],
)
def test_atlas_rendered_page_rejections(
    monkeypatch, html, status, message, count, page_size
) -> None:
    class Response:
        status_code = status
        text = html

    class Client:
        def __init__(self, _app):
            pass

        def get(self, _url):
            return Response()

    monkeypatch.setattr(consumer_qualification, "TestClient", Client)
    with pytest.raises(ValueError, match=message):
        consumer_qualification._atlas_ids(
            pa.table({"kind": ["k"]}), "k", count, {"x": "x"}, page_size
        )


@pytest.mark.parametrize("page_size", [0, -1, 1001])
def test_qualification_rejects_invalid_page_size(tmp_path, page_size) -> None:
    edge_path, qualification, _bindings, _candidate = _candidate_artifact(
        tmp_path
    )
    with pytest.raises(ValueError, match="page size"):
        qualify_consumers(edge_path, qualification, page_size=page_size)


@pytest.mark.parametrize("edge_count", [True, 99, "2"])
def test_qualification_rejects_invalid_edge_count(tmp_path, edge_count) -> None:
    edge_path, qualification, _bindings, _candidate = _candidate_artifact(
        tmp_path
    )
    qualification["graph"]["edge_count"] = edge_count
    with pytest.raises(ValueError, match="edge count"):
        qualify_consumers(edge_path, qualification)
