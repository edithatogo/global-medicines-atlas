# PR 463 governed preview coverage repair

The exact-head CI policy failure at `a5e9c96` identified an unnamed metadata
append job. The job now has an explicit name; offline pedantic Zizmor reports
no findings. NetworkX 3.6.1 is pinned only in the governed test dependency group,
not the core runtime, so CI executes the existing optional graph parity tests.
The experiment matrix lock digests were rebound to this test-only lock change;
historical experiment conclusions have not been requalified.

Focused validation: 91 tests passed across metadata hosted execution, NetworkX
parity, benefits filters/generated-client pagination, and both experiment
matrices. Branch-inclusive coverage is 100% for `federation_metadata_hosted.py`
and `frontier_networkx.py`. New negative controls reject invalid hosted run IDs,
head drift, private/gated baseline snapshots, missing durable acknowledgements,
forged recovery evidence, wrong revisions, and modified graph control fields.
The generated client test traverses a filtered cursor across two API pages.

Command: `uv run --frozen --group test pytest -q tests/test_federation_metadata_hosted.py tests/test_frontier_networkx.py tests/test_platinum_benefits_filters.py tests/test_datahouse_experiment_matrix.py tests/test_frontier_experiment_matrix.py --cov=global_medicines_atlas.frontier_networkx --cov=global_medicines_atlas.federation_metadata_hosted --cov-branch --cov-report=term-missing --cov-fail-under=90.01`.

The final routine profile passed (840 files formatted; Ruff, typing, context,
and ecosystem checks passed). Exact-head
hosted patch coverage remains to be observed after integration and push. This
is local synthetic validation, not publication, engine promotion, source
qualification, or track completion.
