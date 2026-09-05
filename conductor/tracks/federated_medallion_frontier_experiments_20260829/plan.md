# Plan: federated medallion frontier experiments

## Phase 1: Matrix, reuse, and baselines (AC-01, AC-08)

- [x] Write failing matrix-validation tests for prerequisites, exact revisions,
  baselines, thresholds, fallback, rollback, rights, and non-promotion state.
- [x] Confirm the intended failure before implementation. Negative controls
  reject partial identities, unmet and anonymously unverified prerequisites,
  unimported evidence, changed evidence bytes, and malformed workload profiles.
- [x] Import decisions and fixtures from the two archived datahouse experiment
  tracks and mark unchanged hypotheses as reused rather than rerun.
- [x] Define representative tiny, medium, and large public Australian workloads
  plus mutation, corruption, missing-object, and access-failure controls.
- [x] Phase Verification & Checkpoint: no experiment starts without a measured
  question and no existing result is silently discarded.
  The initial matrix contains six bounded families, imports four exact prior
  decision/fixture identities, starts no experiment, adopts no dependency, and
  makes no technology-promotion claim. Exact public objects remain absent until
  revision, path, SHA-256 and anonymous verification evidence are all present.
- [x] Repair independent Phase 1 review findings at `b23eab8`: every experiment
  now requires explicit baseline, threshold, and rights/sensitivity inputs;
  every family has an exact prerequisite-key denominator; the matrix requires
  the exact six approved families; and rows, source bytes, requests, and memory
  all increase strictly across workload profiles. The 64 focused matrix and
  harness tests pass with Ruff and BasedPyright clean.

## Phase 2: Remote query, streaming, and Xet mechanics (AC-02, AC-06)

- [x] Write failing correctness/parity, request-count, byte-amplification,
  memory/cache, cold/warm/concurrent, interruption/resume, offline, digest, and
  identity tests. Rebased implementation `f70123a` supersedes `20e3e9e`: the
  versioned remote-query envelope
  requires the complete four-engine by five-scenario denominator, exact result
  parity, predeclared request/source-byte/memory ceilings, explicit cache and
  latency observations, no-request offline behavior, and exact interrupted
  resume. The paired Xet envelope requires two anonymously verified revisions,
  restored per-object SHA-256 equality, and keeps chunk reuse non-authoritative.
  Nine focused tests provide 100% statement and branch coverage; the combined
  Phase 1/2 contract suite passes 28 tests with Ruff and BasedPyright clean.
  Review fix `22fc22a` registers the new file in the governed unit inventory.
  The resulting local full collection ran 4,268 tests: 4,263 passed, one
  skipped, two existing stable-v1 release tests failed because only uv 0.12.7
  was available instead of pinned 0.11.29, and two existing product tests
  failed their unchanged 250ms local query budget at 348.022ms and 367.446ms.
  No frontier contract failed; hosted Linux lanes remain authoritative.
  Exact-head contract repair `e422380` additionally binds a canonical query
  identity and every observation to it, enforces scanned/returned row and cache
  ceilings, and requires matching interruption/resume byte offsets with at
  least two requests. Thirteen focused tests provide 100% statement and branch
  coverage; Ruff, format, ty and BasedPyright pass.
- [x] Confirm the intended failure before implementation. The new contract test
  failed at collection with `ModuleNotFoundError` before the implementation was
  added; subsequent bounded fixes made custom denominator and anonymous-
  verification failures observable rather than generic field errors.
- [x] Benchmark the portable fallback against a deterministic bounded fixture;
  optional DuckDB, Polars, Arrow, DataFusion, and Xet execution remain explicit
  unavailable candidates until their dependencies and exact public objects are
  observed. The receipt compares operation counts and output digests without
  promoting wall-clock noise or an optional dependency.
- [x] Extend the deterministic receipt with measured DuckDB, Polars, and Arrow
  observations when those optional engines are available; unavailable engines
  remain explicit and fail closed. DataFusion and Xet-aware restore/dedup still
  require exact environments and public objects before measurement.
- [x] Record deterministic profiling evidence and reject optimizations that weaken immutable
  identities, bounded resource behavior, or Python 3.14 completeness.
- [ ] Phase Verification & Checkpoint: each candidate has measured value and an
  exact fallback/rollback disposition.

## Phase 3: Iceberg REST and catalogue federation (AC-03)

- [ ] Write failing REST lifecycle, v3 capability, schema evolution,
  acquisition-binding, branch/tag alias, deletion/rebuild, and core-import
  isolation tests.
- [ ] Confirm the intended failure before implementation.
- [ ] Register disposable public-HF-backed Parquet tables in an isolated
  catalogue and compare observed behavior with prior bounded evidence.
- [ ] Record version/environment degradation and leave core functional without
  PyIceberg or a live catalogue.
- [ ] Phase Verification & Checkpoint: catalogue metadata is demonstrably
  rebuildable and never becomes evidentiary authority.

## Phase 4: Attestation and research packages (AC-04)

- [x] Write and pass failing-first Merkle mutation/order/missing-leaf and
  metadata-only RO-Crate completeness controls. Croissant, OpenLineage, and
  optional signature/provenance remain separate candidate surfaces.
- [ ] Confirm the intended failure before implementation.
- [ ] Generate cross-dataset batch roots, research packages, and federation
  lineage over exact public revisions.
- [ ] Measure verification cost and retain per-object SHA-256 as the base
  evidence even when batch proofs pass.
- [ ] Phase Verification & Checkpoint: additive attestations improve
  verification without creating circular trust or hiding object-level failures.

## Phase 5: Graph and semantic projections (AC-05)

- [x] Implement a bounded offline reference JSON and parameterized Cypher
  exporter from the existing MBS/PBS portable Gold tables. Preserve every
  field, null, evidence/control JSON and edge direction; reject schema drift,
  duplicate identities and dangling endpoints. Local round-trip tests cover
  hostile native text and deterministic ordering. This is export behavior,
  not live Neo4j query parity, NetworkX/RDF-star coverage or public-data
  qualification; those broader tasks below remain open.

- [ ] Write failing deterministic graph, engine-parity, query-semantic,
  confidence/calibration, negative-control, review, rights, and restricted-byte
  tests.
- [x] Execute the optional NetworkX directed multigraph projection against the
  same portable Gold tables and independently compare every node's ancestors,
  descendants and directed degrees with Python table traversal. Preserve
  parallel edges, self loops, isolated nodes and all candidate/null/control
  fields. NetworkX 3.6.1 was already available locally; no core dependency was
  added. This bounded synthetic experiment does not qualify Neo4j/RDF-star,
  live public graphs, retrieval calibration or production promotion.
- [ ] Confirm the intended failure before implementation.
- [x] Produce deterministic NetworkX reference, parameterized Cypher, and
  RDF-star preview projections from the same Gold node/edge tables. Local
  verification passed; live engine parity, public graphs, and promotion remain
  open.
- [ ] Benchmark lexical, ontology-assisted, LanceDB embedding/NLP, and any
  justified Tantivy/Qdrant candidates; preserve explicit candidate status.
- [ ] Phase Verification & Checkpoint: all engines reproduce portable Gold
  semantics and no model/index is an authority.

## Phase 6: Threat, cost, and disposition review (AC-07, AC-08)

- [ ] Run focused, parity, benchmark, property, mutation, security, dependency,
  typing, provenance, rights, full Test-Goblin where supported, and hosted lanes.
- [ ] Record free-tier/resource use, threat model, supply-chain impact,
  operational burden, fallback, rollback, and withdrawal behavior.
- [ ] Run Conductor review, repair findings, publish decision evidence, and
  classify each row as promote-candidate, retain-preview, defer, or reject.
- [ ] Do not promote dependencies or production authority in this track; open a
  separate ADR/implementation track for any candidate that passes.
