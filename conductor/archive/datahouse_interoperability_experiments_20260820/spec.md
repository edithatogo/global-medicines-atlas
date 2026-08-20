# Specification: Evaluate optional datahouse interoperability and versioning technologies

## Overview

Evaluate six optional datahouse capabilities against the existing governed
Bronze contracts: an actual Iceberg REST catalogue, Iceberg v3, DuckLake,
lakeFS or an equivalent object-versioning workflow, cryptographic batch
attestation, and Delta Lake/Hudi for future high-update sources.

These are evidence-producing experiments. They do not block Bronze completion,
promote a dependency, authorize production deployment, or replace immutable
payloads and append-only receipts as evidentiary truth.

## Authoritative inputs

- `conductor/requirements.md`, continuing requirements C-007 through C-010.
- `conductor/design.md`, Datahouse and Medallion boundaries.
- `conductor/roadmap.md`, Non-blocking datahouse experiments.
- `conductor/tech-stack.md`, Python 3.14 fallback and dependency doctrine.
- `conductor/tracks/bronze_medallion_completion_20260819/spec.md`, Bronze
  evidentiary, catalogue, durable-storage, and sensitivity contracts.
- `src/global_medicines_atlas/iceberg_ready.py`, rebuildable Iceberg-ready
  table identities and REST request projections.
- `src/global_medicines_atlas/bronze_storage.py`, durable-storage policy and
  append-only storage receipts.
- `pyproject.toml`, `uv.lock`, `pylock.toml`, `pixi.toml`, and `pixi.lock`, at
  the track initialization revision.

Official specifications and implementation documentation must be pinned by
version or commit in each experiment receipt before a conformance claim is
made. Derived documentation does not override those specifications.

## Functional requirements

### Shared experiment contract

- Run every comparison against the same governed synthetic or redistributable
  Parquet fixtures and acquisition/snapshot bindings.
- Record runtime, dependency lock, protocol/specification version, feature
  flags, test vector digest, outcome, limitations, and rollback procedure.
- Distinguish supported, unsupported, degraded, failed, and not-run outcomes.
- Keep optional experiment dependencies outside the Python 3.14 core install.
- Preserve payload/receipt truth, source-faithful Parquet portability, and
  rebuildable catalogue metadata in every experiment.

### Iceberg REST interoperability

- Exercise namespace and table creation, load, commit, snapshot lookup, schema
  evolution, partition-spec evolution, and teardown against at least one
  disposable implementation of the Iceberg REST catalogue protocol.
- Prove that catalogue loss can be recovered from repository-governed Parquet,
  table specifications, and acquisition/snapshot bindings.
- Record server identity and protocol deviations without claiming universal
  Iceberg interoperability from one implementation.

### Iceberg v3 capability testing

- Detect and exercise only capabilities advertised by the pinned Iceberg v3
  specification and selected implementation.
- Record capability-by-capability support and graceful fallback to the existing
  v2-compatible table contract.
- Reject silent version downgrade or mutation of evidentiary identities.

### DuckLake comparison

- Compare DuckLake with the Iceberg-ready baseline using identical inputs and
  measured catalogue, transaction, portability, recovery, and operational
  criteria.
- Keep DuckDB as the embedded analytical engine without making a DuckLake file
  or catalogue the sole authoritative copy.

### Object-versioning workflow

- Evaluate lakeFS or a documented equivalent only after a deployed durable
  object-store policy and non-secret test environment are evidenced.
- Exercise commit, branch, merge/conflict, rollback, retention, and independent
  restore behavior.
- Treat workflow history as complementary to provider versioning, Object Lock
  or WORM, replication, checksum inventory, and restore receipts.

### Cryptographic batch attestation

- Build deterministic batch manifests over existing per-object content IDs and
  SHA-256 digests.
- Exercise inclusion, absence, order independence where specified, tamper
  detection, reproducible root generation, and incremental update behavior.
- Keep the per-object receipt authoritative; a batch or Merkle root is additive
  evidence rather than a replacement.

### Delta Lake and Hudi comparison

- Begin executable comparison only after a governed benchmark demonstrates a
  high-update workload and explicit transaction requirements.
- Compare Delta Lake and Hudi with the same workload and Iceberg-ready baseline
  for update/delete semantics, concurrency, recovery, portability, maintenance,
  and Python 3.14 compatibility.
- Record `not_run_prerequisite_unmet` when workload evidence is absent; do not
  add speculative production dependencies.

## Acceptance criteria

- AC-01: A versioned, schema-validated experiment matrix covers all six
  requested capabilities and preserves explicit not-run states.
- AC-02: An actual disposable Iceberg REST catalogue passes the defined
  lifecycle test or produces a reproducible failure receipt.
- AC-03: Iceberg v3 results are capability-specific, version-pinned, and prove
  graceful fallback without changing Bronze identity.
- AC-04: DuckLake results use identical governed inputs and publish comparable
  correctness, recovery, portability, performance, and operational measures.
- AC-05: Object-versioning results are absent until the durable-storage entry
  condition is evidenced, then remain additive to storage receipts.
- AC-06: Batch-attestation vectors deterministically detect tampering while
  preserving per-object SHA-256 authority.
- AC-07: Delta/Hudi execution is gated by measured high-update demand and uses
  identical workload semantics; otherwise both remain explicitly not run.
- AC-08: Core installation and existing Bronze reconstruction tests pass with
  every experiment dependency absent.
- AC-09: Each phase ends with focused tests, broader affected validation,
  dependency and security review, a reproducible receipt, and automated review.
- AC-10: The final disposition may recommend adoption, continued experiment,
  rejection, or supersession, but cannot promote or deploy a technology without
  a separately approved decision.

## Non-functional constraints

- Python 3.14 remains the complete fallback.
- Experiments use bounded, disposable, non-production resources.
- No credentials, restricted source bytes, or sensitive payloads enter logs,
  fixtures, receipts, or Git history.
- Tests use synthetic or expressly redistributable inputs.
- Regulatory, funding, formulary, terminology, rights, sensitivity, and
  publication states remain independent.
- Missing experiment evidence is not positive or negative product evidence.

## External gates

- Credentials or hosted infrastructure for a non-local catalogue or object
  store require explicit maintainer authority.
- Production deployment, provider selection, expenditure, dependency
  promotion, or migration requires a separate approved track or decision.
- The lakeFS-equivalent phase waits for deployed durable-storage evidence.
- The Delta/Hudi executable phase waits for measured high-update workload
  evidence.
- External publication of benchmark data or receipts remains separately gated.

## Out of scope

- Changing the Bronze maturity or completion gate.
- Replacing immutable payloads, acquisition receipts, admission events, or
  transformation receipts with catalogue metadata.
- Production migration, availability claims, RPO/RTO qualification, or public
  dataset publication.
- Graph, vector, OMOP, cross-source semantic normalization, and Rust
  terminology implementation.
- Selecting a permanent vendor or managed service.
