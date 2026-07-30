# Query and storage contract

The read-only product query service uses DuckDB keyset pagination. Coverage,
evidence and comparison candidate keys are filtered after the signed cursor in
SQL, sorted by stable non-null composite keys and fetched with `LIMIT n+1`.
Only the requested page's comparison assertions and coverage observations are
then materialised. This preserves the existing response and cursor contracts
without offset scans.

The stable keys are:

- comparisons: `(jurisdiction, dimension, concept_id)`;
- coverage: `(jurisdiction, dimension, assertion_status)`;
- evidence: `(jurisdiction, kind, assertion_id)`.

All key columns are required to be non-null strings by the canonical database
contract, so cursor ordering has no implicit null-ordering ambiguity. Nullable
coverage specificity is ordered separately with `medicine_concept_id NULLS
LAST` after the page key has been selected.

At service startup, required columns and key-column types are validated. A
SHA-256 schema identity is computed from the ordered DuckDB table, column, type
and ordinal-position metadata. The identity supports compatibility evidence;
it does not make a DuckDB file authoritative or replace the governed Arrow and
Parquet schema versions.

`query_plan_evidence()` produces an `EXPLAIN` receipt for evidence-page SQL,
including the schema identity, requested limit, `n+1` fetch limit and whether a
keyset predicate was applied. DuckDB query plans can change between compatible
engine releases, so the plan is evidence for review and benchmarking rather
than a byte-stable public API. No physical secondary index is claimed: the
current bounded local workload and DuckDB's columnar execution do not yet
justify one without representative-scale measurements.

The current CLI export formats are JSON and JSONL and already traverse bounded
query pages. There is no Arrow export surface in this service, so this slice
does not introduce a parallel Arrow API. A future Arrow export must stream
bounded `RecordBatch` objects from DuckDB and retain the same signed-resume
cursor and hard row limits.
