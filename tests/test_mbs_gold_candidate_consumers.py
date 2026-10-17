from __future__ import annotations

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from test_mbs_gold_graph import (
    _admitted_input,  # ruff: ignore[import-private-name] -- shared fixture
    _admitted_table,  # ruff: ignore[import-private-name] -- shared fixture
)

import global_medicines_atlas.mbs_gold_consumer_qualification as consumer_qualification
from global_medicines_atlas.mbs_gold_candidate_export import (
    write_mbs_gold_candidate_edges,
)
from global_medicines_atlas.mbs_gold_consumer_qualification import (
    qualify_consumers,
)
from global_medicines_atlas.mbs_gold_graph import (
    build_mbs_gold_graph_from_admitted_silver,
)


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
    )

    assert receipt["candidate_only"] is True
    assert receipt["edge_count"] == len(candidate.edges)
    assert receipt["surfaces"] == ["API", "Atlas", "CLI"]
    assert receipt["page_offsets"] == [0, 1]
    assert receipt["surface_edge_id_sha256"] == {
        "API": receipt["surface_edge_id_sha256"]["CLI"],
        "Atlas": receipt["surface_edge_id_sha256"]["CLI"],
        "CLI": receipt["surface_edge_id_sha256"]["CLI"],
    }
    assert receipt["review_state"] == "not_reviewed"
    assert "items" not in receipt
    assert all(
        edge["edge_id"] not in str(receipt)
        for edge in pq.read_table(edge_path).to_pylist()
    )


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
