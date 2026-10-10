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
- [x] Phase Verification & Checkpoint: each candidate has an explicit measured
  value or a prerequisite-bound defer/reuse disposition, with a named fallback
  and rollback in `quality/qualifications/frontier-experiment-matrix.json`.
  Remote-query and Xet runs remain deferred until already inventoried public
  Parquet identities satisfy the matrix prerequisites; source expansion is not
  implied.

## Phase 3: Iceberg REST and catalogue federation (AC-03)

- [x] Write REST lifecycle, v3 capability, schema evolution,
  acquisition-binding, branch/tag alias, deletion/rebuild, and core-import
  isolation tests. The actual REST lane's acceptance contract now additionally
  loads the existing synthetic Bronze JSON fixture, appends its typed rows,
  scans them back, and emits a version-2 receipt with row count and acquisition
  identity. PyIceberg remains an optional extra and the core-import test
  verifies it is not loaded by the package's ordinary module import.
- [x] Confirm failure handling with an injected row mutation: the round-trip
  check raises and the disposable table/namespace are cleaned up in `finally`.
- [x] Run the row-bearing experiment against the digest-pinned REST fixture.
  PR #925 merged at `61c9fb85` after all 38 required checks passed. Its hosted
  version-2 receipt verifies the two-row fixture digest and acquisition ID,
  empty and populated snapshots, schema/partition evolution, append/scan
  round-trip, deletion/rebuild, and v3 table creation. The fixture remains
  synthetic and JSON-backed; this does not qualify a public-HF-backed Parquet
  table.
- [x] Register one already-inventoried public-HF-backed Parquet table in an
  isolated catalogue and compare its exact bytes, source lineage, row count,
  and schema with the committed candidate and source-faithful object. The
  hosted run anonymously verified the pinned 100,062-byte MBS services object,
  registered its nested schema using a deterministic Iceberg name mapping,
  scanned all 5,989 rows back, and dropped the disposable table and namespace.
  A metadata-only receipt was uploaded before the temporary runner copy was
  removed. This does not establish source-to-raw content parity, rights,
  production admission/promotion, publication, or source coverage; no source
  was added. A post-review correction places table and namespace cleanup in
  `finally`; focused failure injection confirms cleanup after scan failure and
  parity mismatch. PR #927 merged at `e570b0e6` after all 38 required checks
  passed; exact scanned row-value parity is completed in the follow-up below.
- [x] Compare every Iceberg-scanned value with the same exact pinned Parquet
  object, not only its schema and row count. A failing-first same-row-count
  mutation control reproduced the gap on `e570b0e6`; the implementation now
  uses Arrow table content equality and records a version-2 metadata-only
  receipt flag. Focused tests (65) and Test-Goblin E2E (55) pass locally at
  `8249a8ec`. PR #928 merged as `4ba48aad6cf111b3059845daacb4a8e9d7735655`
  from reviewed head `760e47d265310c9757eefe347d1938beb6ac77a0`; all 38
  protected checks passed, including the exact public Parquet / Iceberg REST
  job and Linux/macOS/Windows consumer lanes. The exact-head hosted v2 receipt
  records all 5,989 rows and 17 columns with `object_content_parity_verified`
  true and contains no source values. Durable receipt:
  `quality/qualifications/public-parquet-iceberg-registration-20261010.json`
  (SHA-256 `717cc62571711564ede23c1ba869fe02a9cce3ee2238382b39a6f4415371c0be`).
  This proves object-to-Iceberg readback only, not source-to-raw parity, rights,
  admission, publication, or source coverage.
- [x] Record version/environment degradation and leave core functional without
  PyIceberg or a live catalogue. PyIceberg remains an optional extra; isolated
  import checks and fail-closed missing-extra tests preserve the Python core.
  The hosted receipt records observed v3 support and missing capabilities.
- [x] Phase Verification & Checkpoint: catalogue metadata is demonstrably
  rebuildable and never becomes evidentiary authority. The hosted fixture drops
  and reconstructs the table from acquisition/digest properties, while the
  receipt expressly makes no production-deployment or universal-compatibility
  claim. PR #927 merged at `e570b0e6` after all 38 required checks passed.
  PR #928 then verified every scanned value against the exact pinned Parquet
  object in a disposable catalogue and passed all 38 protected checks. The
  value-free hosted receipt is committed at
  `quality/qualifications/public-parquet-iceberg-registration-20261010.json`.
  Rights, raw-source parity, production admission, publication, and broader
  source coverage remain separate and unclaimed.

## Phase 4: Attestation and research packages (AC-04)

- [x] Write and pass failing-first Merkle mutation/order/missing-leaf and
  metadata-only RO-Crate completeness controls. Croissant, OpenLineage, and
  optional signature/provenance remain separate candidate surfaces.
- [x] Confirm the intended failure before implementation; add a synthetic
  Bronze-to-Platinum batch-attestation regression to the existing MBS/PBS
  journeys before wiring the Merkle manifest and verification-cost receipt.
  Both MBS and PBS journeys failed first because the batch manifest was absent,
  then passed with the manifest and cost receipt bound into metadata-only
  packages and lineage.
- [x] Generate cross-dataset batch roots, research packages, and federation
  lineage over exact public revisions. Synthetic per-dataset end-to-end
  integration now passes for the existing MBS/PBS journeys (PR #920); a
  synthetic cross-dataset package now binds distinct source revisions under
  one export revision. PR #921 merged after all 38 protected checks passed,
  including 92.30% Codecov patch coverage. Manifest binding now checks each
  lineage input's source dataset identity, path, revision, and digest. Exact
  existing MBS/PBS public revisions now pass through the metadata-only
  cross-dataset package verifier. This is immutable identity binding, not a
  source-content join or source-coverage qualification; those remain open and
  are deferred from this source-neutral completion effort.
  PR #923 then merged with all 38 protected checks passing, correcting the
  batch-leaf identity and hosted-check attribution review findings. Its
  manifest schema v2 includes dataset and revision in leaf hashes. This
  follow-up versions the required-identity contract as schema v3 and binds the
  exact existing public MBS/PBS revisions into their leaves; payload bytes and
  source-content parity remain out of scope.
- [x] Measure deterministic verification work and retain per-object SHA-256
  as the base evidence even when batch proofs pass. For two existing immutable
  source objects plus one synthetic result leaf, the bound receipt requires
  three object-digest checks, three Merkle leaf hashes, and three pair hashes;
  all three SHA-256 values remain explicit leaves. This is a reproducible work
  count, not payload re-download or wall-clock performance evidence.
- [x] Phase Verification & Checkpoint: additive attestations improve
  verification without creating circular trust or hiding object-level failures.
  PRs #920–#924 retain per-object SHA-256 leaves alongside Merkle proofs; exact
  source dataset/revision identities participate in hashes and mutation
  controls. Existing MBS/PBS identity packages remain metadata-only, with source
  content parity and coverage explicitly deferred.

## Phase 5: Graph and semantic projections (AC-05)

- [x] Implement a bounded offline reference JSON and parameterized Cypher
  exporter from the existing MBS/PBS portable Gold tables. Preserve every
  field, null, evidence/control JSON and edge direction; reject schema drift,
  duplicate identities and dangling endpoints. Local round-trip tests cover
  hostile native text and deterministic ordering. This is export behavior,
  not live Neo4j query parity, NetworkX/RDF-star coverage or public-data
  qualification; those broader tasks below remain open.

- [~] Write failing deterministic graph, engine-parity, query-semantic,
  confidence/calibration, negative-control, review, rights, and restricted-byte
  tests. Existing MBS/PBS portable-table, NetworkX, and preview parity suites
  cover stable ordering, directed queries, null confidence, explicit candidate
  controls, and mutation/schema rejection. A synthetic binary-column test
  verifies that unrecognized schema extensions are rejected before
  serialization. This does not screen restricted content inside an allowed
  `fields_json` value; the export contract has no rights authority, so the
  rights/restricted-content portion remains open. No live graph or
  semantic-engine qualification is claimed.
  - [x] Reject nested declared field-policy envelopes that carry restricted
    rights or sensitivity labels before graph serialization. Preserve source
    fields that happen to use policy-like keys. Failing-first controls proved
    nested envelopes bypassed the previous check; the focused graph/export/
    parity suite passes 119 tests, and the full pinned Test-Goblin profile
    passes with 96.88% coverage.
    This does not infer privacy content or provide rights clearance; broader
    graph content/rights review remains open.
- [x] Validate the canonical graph envelope inside the engine-free parity
  boundary independently of the exporter. Failing-first controls reproduced
  acceptance of duplicate node/edge identities, blank identities, and a
  dangling endpoint when all preview representations agreed; the validator
  now rejects those cases and non-deterministic row order. Synthetic only;
  this does not execute Neo4j/SPARQL, screen unlabeled restricted content,
  calibrate candidate confidence, or grant rights/promotion. The broader
  graph export/parity/NetworkX/MBS/PBS suite passed (108); the pinned full
  Test-Goblin profile passed, including both 184-test randomized-order runs,
  Gremlins (355 passed), profiling, security workflow, and dependency audit.
  PR #949 merged the shape-validation change at
  `5f8f34e59c3598a94d73ac76d3eed40bc364ec62` from exact head
  `d733a4b2f578b0d808a20ebae0e576f47251811b`; all 28 distinct required
  contexts passed (29 required-check rows list CodeQL twice), including Codecov
  patch coverage and Linux/macOS/Windows consumers.
- [x] Propagate receipt rights and sensitivity metadata into MBS/PBS graph
  node evidence and reject graph previews when node/edge metadata explicitly
  classifies rights or content as restricted/prohibited or personal data as
  possible/present. Failing-first tests confirmed those classifications reached
  serialization before the guard. This metadata-only screen does not inspect
  `fields_json`, resolve unknown/review-required states, establish licensing,
  or close the broader rights/restricted-byte review above.
  Verification: focused/affected graph suite 83 passed; the pinned full
  Test-Goblin profile completed with 6,102 passed and 1 optional PyIceberg
  skip, 97.92% line coverage, 353 Gremlins targets passed, both randomized-order
  runs passed, and the package/CLI/API probes passed. BasedPyright and routine
  repository/rights checks passed. Hosted CI passed 39/39 checks on PR #937;
  merge commit `1ca89a37`.
  Review follow-up preserves valid root-only PBS graphs with zero edges while
  still checking every node's policy metadata; a synthetic root-only fixture
  passes both candidate validation and graph export.
- [x] Encode untrusted graph identifiers as valid ASCII RDF IRI references in
  both preview export and parity validation. Failing-first controls reproduced
  invalid RDF IRIs for spaces, slashes, Unicode, percent/query/fragment
  characters, angle brackets, and backslashes. The shared encoder preserves
  original identifiers in payloads; this closes only that source-neutral
  serialization gap and does not close the broader graph review task above.
- [x] Execute the optional NetworkX directed multigraph projection against the
  same portable Gold tables and independently compare every node's ancestors,
  descendants and directed degrees with Python table traversal. Preserve
  parallel edges, self loops, isolated nodes and all candidate/null/control
  fields. NetworkX 3.6.1 was already available locally; no core dependency was
  added. This bounded synthetic experiment does not qualify Neo4j/RDF-star,
  live public graphs, retrieval calibration or production promotion.
- [ ] Confirm the intended failure before implementation.
- [x] Produce NetworkX reference, Cypher/Neo4j, and RDF-star projections
  (deterministic parameterized Cypher and
  RDF-star preview projections from the same Gold node/edge tables. Local
  verification passed; live engine parity, public graphs, and promotion remain
  open.
- [x] Reject duplicate object keys in reference and Cypher-parameter JSON
  envelopes before semantic parity checks. Failing-first controls reproduced
  last-key-wins acceptance in both inputs; the shared parser now rejects the
  ambiguity while preserving the existing envelope contract. This closes a
  source-neutral preview integrity gap only; live engine parity and broader
  graph qualification remain open.
- [x] Reject portable graph field envelopes whose explicit `field_policy`
  declares restricted/prohibited rights, sensitive/restricted data, possible/
  present personal data, or prohibited publication. Failing-first synthetic
  tests cover MBS and PBS node projections. Unknown and review-required field
  declarations remain preserved, and fields without policy envelopes remain
  unchanged. This is a declared-metadata guard only; it does not inspect
  unlabeled content, establish rights, or close the restricted-content review.
  The focused graph export/parity/NetworkX suite passes 71 tests, and the
  routine harness passes. The pinned full profile passes 6,154 tests at 96.94%
  coverage and all local lanes. PR #945 merged as
  `6bac5fe1605fbf27f8df02717d0063d27718058b` from reviewed head
  `4329a3a01faa2ed0a55a4d51cea4385ac3911cc4`; all 39 hosted checks passed,
  including Codecov patch coverage.
- [x] Benchmark lexical, ontology-assisted, LanceDB embedding/NLP, and any
  justified Tantivy/Qdrant candidates; preserve explicit candidate status.
  The deterministic receipt over six existing synthetic matching cases
  measured identifier-first lexical recall@5 at 0.25 (one of four relevant
  cases retrieved), negative-candidate rate at 1.0 (both negative controls
  surfaced candidates), and abstention at 0.5. Confidence calibration remains
  unevaluated because candidate scores are not calibrated confidence.
  Ontology-assisted and LanceDB embedding/NLP are explicitly unavailable
  without governed synthetic relationship and pinned embedding fixtures;
  Tantivy and Qdrant are not justified by these bounded pools. No source or
  dependency was added, and no candidate is promoted or authoritative.
  Automated review caught that the hashed lexical threshold was not passed to
  candidate generation. The benchmark now uses one shared threshold constant
  for execution and query identity; a regression test checks both bindings.
- [ ] Phase Verification & Checkpoint: all engines reproduce portable Gold
  semantics and no model/index is an authority.

## Phase 6: Threat, cost, and disposition review (AC-07, AC-08)

- [~] Run focused, parity, benchmark, property, mutation, security, dependency,
  typing, provenance, rights, full Test-Goblin where supported, and hosted lanes.
  The synthetic benchmark has full local and 38/38 hosted evidence; broader
  graph rights-content screening and live-engine parity remain open.
- [x] Record free-tier/resource use, threat model, supply-chain impact,
  operational burden, fallback, rollback, and withdrawal behavior.
- [x] Review the current experiment matrix and evidence, record bounded
  security/rights/operational dispositions in
  `quality/qualifications/frontier-experiment-disposition-20261011.json`, and
  classify every matrix row. No preview passed its production-promotion gate.
- [x] Do not promote dependencies or production authority in this track; open a
  separate ADR/implementation track for any candidate that passes.
