"""Execute synthetic MBS/PBS Gold graph exports in an isolated Neo4j."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from test_mbs_gold_graph import graph as mbs_graph
from test_pbs_gold_graph import graph as pbs_graph
from test_support.frontier_neo4j import qualify_graph_exports

from global_medicines_atlas.frontier_graph_export import export_gold_tables
from global_medicines_atlas.mbs_gold_graph import project_mbs_gold_graph_arrow
from global_medicines_atlas.pbs_gold_graph import project_pbs_gold_graph_arrow


def test_neo4j_executes_exact_synthetic_mbs_pbs_projections() -> (  # ruff: ignore[too-many-locals] - test coordinates two synthetic graphs and receipt verification
    None
):
    endpoint = os.environ.get("NEO4J_HTTP_URL")
    if not endpoint:
        pytest.skip("Neo4j service is not configured")

    mbs = mbs_graph()
    pbs = pbs_graph()
    assert mbs.qualification == "synthetic_silver_candidate_only"
    assert pbs.qualification == "synthetic_silver_candidate_only"
    mbs_nodes, mbs_edges = project_mbs_gold_graph_arrow(mbs)
    pbs_nodes, pbs_edges = project_pbs_gold_graph_arrow(pbs)
    receipt = qualify_graph_exports(
        endpoint,
        {
            "mbs": export_gold_tables(mbs_nodes, mbs_edges),
            "pbs": export_gold_tables(pbs_nodes, pbs_edges),
        },
    )

    cases_object = receipt["cases"]
    assert isinstance(cases_object, dict)
    cases = cast("dict[str, object]", cases_object)
    assert set(cases) == {"mbs", "pbs"}
    for family in ("mbs", "pbs"):
        case_object = cases[family]
        assert isinstance(case_object, dict)
        case = cast("dict[str, object]", case_object)
        assert case.get("exact_payload_and_direction_parity") is True
    assert receipt["disposition"] == "retain-preview"
    assert receipt["source_scope"] == "synthetic-mbs-pbs-only"
    assert receipt["source_payloads_accessed"] is False
    assert receipt["rights_clearance_claimed"] is False
    assert receipt["production_authority_promoted"] is False

    output = os.environ.get("NEO4J_QUALIFICATION_RECEIPT")
    if output:
        document = {
            **receipt,
            "recorded_at": datetime.now(UTC).isoformat(),
        }
        canonical = json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        document["receipt_sha256"] = hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest()
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(document, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
