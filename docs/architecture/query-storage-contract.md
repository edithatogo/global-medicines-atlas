# Query and storage contract

The read-only product query service uses DuckDB keyset pagination. Coverage,
evidence and comparison candidate keys are filtered after the signed cursor in
SQL, sorted by stable non-null composite keys and fetched with `LIMIT n+1`.
Only the requested page's comparison keys are selected. For each selected key,
DuckDB computes conflict and row-count aggregates over the complete matching
assertion set, but materialises at most 32 deterministic provenance rows.
Comparison uncertainty states when this provenance sample is incomplete and
directs consumers to the separately paginated evidence endpoint. Coverage
selection materialises one most-specific observation per comparison key.
Consequently memory use is bounded by the page limit rather than by duplicate
or conflicting source-row cardinality.

The stable keys are:

- comparisons: `(jurisdiction, dimension, concept_id)`;
- coverage: `(jurisdiction, dimension, normalized_status, assertion_status)`;
- evidence: `(jurisdiction, kind, assertion_id)`.

The normalized coverage status is the public `ProductState` value and the raw
source status is the deterministic tie-breaker. Cursors encode both exact SQL
values, so multiple source-native statuses that normalize to `unknown` cannot
be skipped or duplicated. All key columns are required to be non-null strings
by the canonical database contract, so cursor ordering has no implicit
null-ordering ambiguity.

At service startup, required columns and key-column types are validated. A
SHA-256 schema identity is computed from the ordered DuckDB table, column, type
and ordinal-position metadata. The identity supports compatibility evidence;
it does not make a DuckDB file authoritative or replace the governed Arrow and
Parquet schema versions.

`query_plan_evidence()` produces an `EXPLAIN` receipt for comparison, coverage,
and evidence-page SQL. Each receipt includes the schema identity, SQL digest,
parameter count, measured planning duration, requested limit, `n+1` fetch
limit, and whether a keyset predicate was applied. It does not invent rows
scanned, peak memory, or index-selection measurements that plain `EXPLAIN`
does not provide. DuckDB query plans can change between compatible engine
releases, so the plan is review and benchmark evidence rather than a
byte-stable public API. No physical secondary index is claimed: the current
bounded local workload and DuckDB's columnar execution do not yet justify one
without representative-scale measurements.

The current CLI export formats are JSON and JSONL and already traverse bounded
query pages. There is no Arrow export surface in this service, so this slice
does not introduce a parallel Arrow API. A future Arrow export must stream
bounded `RecordBatch` objects from DuckDB and retain the same signed-resume
cursor and hard row limits.
