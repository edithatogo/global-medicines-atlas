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
- [x] Version the remote-query profile with a predeclared per-observation
  latency ceiling and bind it to the selected versioned matrix workload. The
  matrix schema v2 declares 30-second, 120-second, and 600-second maxima for
  tiny, medium, and large workloads; the remote-query schema v2 identifies
  `remote_query_streaming`, requires its tiny profile, and rejects threshold
  drift or observations above that profile. Review exposed that the initial
  caller-supplied ceiling could exceed the matrix; the 31-second-over-30-second
  regression failed before the binding repair. The focused contract and matrix
  suites pass (42 tests); the full local Test-Goblin profile passes under the
  pinned uv 0.11.29, including 355 gremlin cases, two 184-test stability
  samples, Scalene, and zizmor. Darwin mutation score is 83.83% and advisory;
  Linux CI remains authoritative. PR #1008 merged after all 39 hosted check
  rows passed; the squash merge tree matches the qualified head tree. Real
  engine measurements remain deferred.
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
  controls, and mutation/schema rejection. Review-only matching now keeps the
  heuristic as `raw_score` and exports `confidence: null` with
  `confidence_state=not_calibrated`; thresholds still use the heuristic. This
  closes the score-labeling flaw, not the unresolved calibration requirement.
  A synthetic binary-column test
  verifies that unrecognized schema extensions are rejected before
  serialization. The exporter recursively rejects explicit structured
  `field_policy` labels inside `fields_json` while preserving native values
  that merely use policy-like keys. It does not classify unlabeled text or
  bytes, and it has no rights authority, so the broader rights/content review
  remains open. No live graph or semantic-engine qualification is claimed.
  - [x] Reject non-finite semantic candidate distances. Failing-first
    validation reproduced acceptance of positive infinity; `SemanticHit` now
    uses Pydantic `FiniteFloat` with the existing non-negative bound. Focused
    semantic-retrieval/frontier benchmark tests passed (24), routine checks
    passed, and BasedPyright reported no errors (four existing optional import
    source warnings). The full pinned Test-Goblin run reached 100% with
    6,304 passed and 3 skipped, but one unrelated Hypothesis Bronze Parquet
    reconstruction case exceeded its 30-second timeout under full-suite load;
    that exact case passed alone in 15.19 seconds. Full-profile coverage was
    96.88%. No source, rights, calibration, or production-promotion claim is
    made; the Phase 5 checkpoint remains open. PR #1058 merged as
    `96f82eee3f95c5ae52bbf3af9c51560db6674f01` from exact head
    `77c5239779ea72ece238ee4466ef12c286f25d80` after all 29 required branch
    protection contexts passed, including Codecov patch and Linux/macOS/Windows
    consumers.
  - [x] Reject nested declared field-policy envelopes that carry restricted
    rights or sensitivity labels before graph serialization. Preserve source
    fields that happen to use policy-like keys. Failing-first controls proved
    nested envelopes bypassed the previous check; the focused graph/export/
    parity suite passes 119 tests, and the full pinned Test-Goblin profile
    passes with 96.88% coverage.
    This does not infer privacy content or provide rights clearance; broader
    graph content/rights review remains open. PR #955 merged at
    `410cc61aaaee29cfb86dbc92fb7e655b6bbfaa60` from reviewed head
    `5308e2dd27de3158c25ae9e0c19e3d13fedc01bd`; all 28 required contexts
    passed, including Codecov patch coverage and Linux/macOS/Windows consumers.
    PR #956 reconciled the merge receipt at `5e2d84d65d4cbb28a2e0b8d44d27c058687cdc13`
    after all 28 required contexts passed. PR #957 records that reconciliation
    at `b88632274d2aa0df7ae8f6994870a01799fed0f0` after all 28 required
    contexts passed. PR #958 reconciles that record at
    `c106548ac6ffaf963b3c13b2a0cca08bc6ff23ae` after all 28 required
    contexts passed.
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
  serialization before the guard. A recursive `fields_json` check separately
  rejects explicit field-policy envelopes with those classifications and
  preserves native fields with policy-like values. Neither guard classifies
  unlabeled content, resolves unknown/review-required states, establishes
  licensing, or closes the broader rights/restricted-byte review above.
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
- [x] Run the combined reference JSON, parameterized Cypher, RDF-star, and
  executed NetworkX parity check against both synthetic MBS and PBS Gold graph
  projections. The affected suites pass (22); routine, lint, format, typing,
  and repository checks pass. This closes the portable-projection test gap for
  the two existing Gold families only; live Neo4j/SPARQL execution and the
  broader rights-content review remain open. PR #964 merged from exact head
  `d12243667ccb73bfb54a85cb76b510fc1d3d34c9` at
  `f81fbaf01264e935788724c6ffea1cfceea689f5`; its tree matches the qualified
  head tree, and all 28 distinct required contexts passed.
- [x] Execute the fixed parameterized Cypher exporter in an empty, digest-pinned
  Neo4j service using only the existing synthetic MBS/PBS Gold fixtures; read
  every node and directed edge back and require exact canonical payload parity.
  The HTTP contract tests and source-neutral qualification helper pass locally;
  the integration test ran in hosted CI because no local Docker service is
  available. Review found expected endpoint fields could overwrite observed
  Neo4j edge direction; a failing-first regression reproduced the defect, and
  readback now rejects structural-field disagreement. The corrected hosted
  run on PR #1011 head `cbadfd478d80ed45d7e1ff0d6315ef0efa3ef334` passed.
  Neo4j 2026.09.0 reproduced all 4 MBS nodes/2 directed edges and all 10 PBS
  nodes/9 directed edges exactly. The verified checksummed metadata-only
  retain-preview receipt is
  `quality/qualifications/neo4j-synthetic-graph-parity-20261011.json` (SHA-256
  `1da2e161e35f6d4644782b8625ba15ee94d71a664e207f2ba446f23cc7e09231`). No
  sources, source bytes, rights conclusions, or promotion are included. Hosted
  regeneration initially rejected the new job as an unregistered workflow
  change; the exact job inventory is now updated and the regeneration profile
  passes twice in opposite order (184 tests each).
  - [x] Pin the corrected hosted receipt digest and verify its canonical
    checksum, synthetic-only scope, and no-rights-clearance/no-promotion
    declarations in the registered unit suite. Automated review caught that a
    recomputed checksum alone would accept replacement content; the test now
    asserts the qualified SHA-256 `1da2e161e35f6d4644782b8625ba15ee94d71a664e207f2ba446f23cc7e09231`.
    Focused Neo4j unit tests pass (10), with Ruff, format, `ty`, BasedPyright,
    and routine repository checks passing.
- [x] Execute the existing RDF-star preview in digest-pinned Oxigraph 0.4.11
  and compare queried node payloads and directed edge annotations with the
  synthetic MBS/PBS Gold references. Exact hosted parity passed on PR #1014
  head `d45f28d75561a86ff30e12b1f7b492a124fb25c0`; hosted run
  `38148283805` produced the checksummed, metadata-only receipt
  `quality/qualifications/oxigraph-synthetic-graph-parity-20261012.json`
  (SHA-256 `95ecdfdcf3b16efa86065a241b24b0498940ee61c1b1fbb00eefabbfc1f2c746`).
  MBS reproduced 4 nodes/2 directed edges; PBS reproduced 10 nodes/9 directed
  edges. A failing-first hosted run and local HTTP reproduction found that
  Oxigraph 0.5.11 rejects the legacy quoted-triple subject grammar and that
  SPARQL readback uses bare IRIs; both are now handled and tested. This
  retains a qualification of the legacy preview on its pinned engine only. It
  does not qualify current RDF 1.2 compatibility, rights clearance, or
  production promotion.
- [x] Add and execute an RDF 1.2 projection on digest-pinned Oxigraph 0.5.9,
  retaining the RDF-star 0.4.11 receipt as legacy evidence. The projection
  uses `rdf:reifies` with a triple term and explicit source/target properties
  for SPARQL 1.1 readback. Local and hosted exact parity passed on Oxigraph
  0.5.9. The checksummed receipt is
  `quality/qualifications/oxigraph-rdf12-synthetic-graph-parity-20261012.json`
  (file SHA-256 `892e1d89ef45c864c8169eeeb44d7684450ea12d5fb05fecee8c4c03f7ec0004`);
  PR #1014 hosted run `38152116039`, graph job `114507529973`. All required
  checks passed, Codecov patch coverage was 100%, and the RDF 1.2 review
  thread was resolved. PR #1014 merged as `414b6659ad1f0f0a1e4d0b7ced6df59e80b53f9e`.
  This closes current Oxigraph RDF 1.2 engine parity for the synthetic MBS/PBS
  projections only. The phase checkpoint and broader graph rights-content
  review remain open.
- [x] Query the RDF 1.2 `rdf:reifies` triple terms in Oxigraph with a SPARQL 1.2
  triple-term pattern and compare the reified source/target against every
  directed synthetic Gold edge. The initial test collection failed because no
  reification-semantic verifier existed; a negative control rejects reversed
  endpoints. The pinned Oxigraph 0.5.9 hosted job passed on PR #1016 code commit
  `b480c85918ef53b24a93a93330f9063d5f894878`; artifact `11708066289` verifies
  all 2 MBS and 9 PBS directed reifications. The committed metadata-only
  receipt is `quality/qualifications/oxigraph-rdf12-reification-semantic-parity-20261012.json`
  (SHA-256 `047d665c960ff8e4ffb0e2d551543a8cd3cdbdcf4224e7705ca4f9702e2fda65`).
  All 29 required status contexts and the Codecov patch check passed on final
  head `3b117acbc02305c97cacaac5fbdef7e6991ef5ad`; PR #1016 merged at
  `2da8b2382a419634cc8d92242a1553952d5211f9` on 2026-10-11. The merge
  receipt is reconciled in the evidence ledger.
  This closes RDF 1.2 reification-term parity for synthetic MBS/PBS only; it
  does not resolve rights, source coverage, confidence calibration, or
  production authority.
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
- [x] Add content screening to the portable, RDF-star, and RDF 1.2 graph
  exporters before serialization. It rejects synthetic sensitive-field-name
  and email-like canaries plus exact caller-supplied SHA-256 canaries, bounds
  inputs, rejects ambiguous JSON, and records no matched values. MBS and PBS
  integration controls pass. A clean result is not exhaustive inspection,
  restricted-terminology detection, or rights clearance.
- [x] Add a case-disjoint, sample-gated Platt calibration evaluator with
  dataset digests and held-out Brier/ECE. A generated synthetic mechanics
  control passed with 400 calibration and 400 disjoint holdout cases
  (Brier 0.1911; ten-bin ECE 0.0149). This validates the fitting path only;
  it is explicitly not a calibration result for the retrieval method.
- [x] Screen the exact July 2025 MBS Gold candidate relationship cohort for
  candidate eligibility independently of engine parity. The value-free graph
  qualification binds 5,989 source-explicit `source_record_has_benefit` edges;
  all 5,989 satisfy the same-source-record, non-inferred screen and zero are
  excluded. The screen does not set review state, establish semantic or
  clinical equivalence, clear rights, admit the graph, or authorize release.
  The expanded qualification is versioned as receipt/schema v2; the existing
  v1 schema and receipt remain unchanged and valid.
- [~] Calibrate the actual synthetic candidate retrieval method. A generated
  400-case calibration partition and disjoint 400-case holdout were scored by
  the actual matcher, with 200 positive and 200 negative cases per partition.
  The fit is `measured_synthetic_only` but performs poorly on holdout
  (Brier 0.2108; ten-bin ECE 0.2068); confidence remains un-emitted. This
  experiment replaces the fake score-curve control as method evidence, but it
  does not establish representative source performance or adequate calibration.
  Keep this lane open; do not infer clinical or source performance from the
  generated cases.
- [ ] Phase Verification & Checkpoint: all engines reproduce portable Gold
  semantics and no model/index is an authority. Hosted synthetic exact parity
  is now evidenced for Neo4j 2026.09.0 and Oxigraph 0.5.9 RDF 1.2, including
  RDF 1.2 reification source/target semantics; the local `tests/test_frontier_*.py`
  suite and new relationship-screen/matcher-calibration tests pass 231 tests
  with two expected skips because local Neo4j and
  Oxigraph services are not configured. These results cover the existing
  synthetic MBS/PBS projections only. Bounded canary screening now runs before
  export, and candidate relationship eligibility is screened separately.
  Exhaustive/source-specific restricted-content screening and representative
  candidate-model calibration remain unresolved, so the phase
  checkpoint stays open. No source expansion, rights clearance,
  source-coverage claim, or production authority is implied.

## Phase 6: Threat, cost, and disposition review (AC-07, AC-08)

- [~] Run focused, parity, benchmark, property, mutation, security, dependency,
  typing, provenance, rights, full Test-Goblin where supported, and hosted lanes.
  The synthetic benchmark has full local and 38/38 hosted evidence. The hosted
  graph lanes now verify exact synthetic MBS/PBS parity on Neo4j 2026.09.0 and
  Oxigraph 0.5.9 RDF 1.2, including reification direction; the local Frontier
  module suite and relationship/calibration receipts pass 231 tests with two
  expected service-absent skips;
  routine, Ruff, `ty`, and BasedPyright pass. The local full Test-Goblin run
  completed with 6,911 passed, 3 skipped, 4 failed, and 96.89% coverage. Two
  clean-clone reproducibility failures passed in isolation after exposing the
  required uv 0.11.29. One Chromium test passed in isolation; the PBS Chromium
  test still timed out in isolation, and the second browser timeout occurred
  under full-suite load. These failures remain distinct from the Frontier
  focused pass; hosted protected checks are still required.
  Bounded content-pattern and candidate relationship screening pass. Generated
  matcher cases yield poor holdout calibration metrics and no confidence
  output; representative matcher calibration and actual restricted-content
  clearance remain open. This is not public-graph qualification or production
  promotion.
- [x] Record free-tier/resource use, threat model, supply-chain impact,
  operational burden, fallback, rollback, and withdrawal behavior.
- [x] Review the current experiment matrix and evidence, record bounded
  security/rights/operational dispositions in
  `quality/qualifications/frontier-experiment-disposition-20261011.json`, and
  classify every matrix row. No preview passed its production-promotion gate.
- [x] Do not promote dependencies or production authority in this track; open a
  separate ADR/implementation track for any candidate that passes.

## 2026-10-18 synthetic candidate fixture identity correction

- [x] Align the governed multilingual identifier-positive case with its
  existing rationale by giving the synthetic source the same UNII already
  declared for its relevant target. A failing-first benchmark regression
  reproduced the missing candidate. The regenerated deterministic receipt
  reports 2/4 relevant cases retrieved (previously 1/4); both negative cases
  still produce candidates, and confidence calibration remains unevaluated.
  The old 2026-10-11 receipt is retained as historical evidence. The new
  receipt is `quality/benchmarks/frontier-candidate-benchmark-20261018.json`
  (SHA-256
  `8c2faa37fcd2c576a633f85925c3929b6ebc117024fed3df0340a16412a4a601`).
  Focused tests pass (7), the broader matching suite passes (113), the routine
  harness passes, and Ruff, `ty`, and BasedPyright pass. The derived Bronze
  receipt-cohort input digest was regenerated and its focused tests pass (13);
  cohort counts did not change. No source, model, production behavior, rights
  conclusion, or authority state changed.

## 2026-10-21 exact MBS Silver candidate content-pattern screen

- [x] Apply the existing value-redacting scanner to all six exact July 2025
  MBS v4 candidate Parquet objects at pinned public revision
  `42d73b6facac016f14a335d36d83f1a3b630add8`. Verify each object against its
  manifest size and digest, then screen all 35,934 rows in memory. The bounded
  sensitive-field, email-like-value, and exact-digest detectors found no
  patterns. Receipt:
  `quality/qualifications/australian-mbs-v4-bounded-content-screen-20261021.json`
  (SHA-256 `83ae8b29ad197495c6cb929165bf2560eaaf22f13ffbb8c7410f8a26ce2d6e5e`).
- [x] Complete and reconcile the bounded content screen for the six MBS v4
  candidate tables and six PBS utilisation objects. The exact-scope disposition
  classifies every observed pattern, including ATC-shaped values, numeric
  fields, terminology markers, sensitive-looking headers, UMLS-CUI patterns,
  and email-like patterns. It records the maintainer's exact-scope rights
  attestations without independently reviewing their instruments.
- [ ] Keep broader screening and vocabulary membership open: configured
  detectors are not exhaustive, the retained inventory has no authoritative
  ATC dictionary, and workbook narrative-token semantics are unresolved. No
  additional source is introduced to close these gaps.
- [ ] Keep actual matcher calibration open. Existing case-disjoint 400-case
  partitions were generated from invented names and calibration remains poor
  on holdout (Brier 0.2108; ten-bin ECE 0.2068). Representative
  human-adjudicated held-out source labels remain absent; no confidence or
  production threshold is emitted.


## 2026-10-21 PBS utilisation field-header resolution

- [x] Resolve field labels for three exact, already-screened PBS CSV objects at
  revision `9f1d53cd50eea251b326da42a96f3ac72ebce97a`. Numeric-shaped values in
  both DOS files occur in `MONTH_OF_SUPPLY`, `PRESCRIPTIONS`, contribution,
  cost, and markup fields; the ATC-shaped values in the item-drug map occur in
  `ATC5_Code`. No CSV record values were emitted. Receipt:
  `quality/qualifications/australian-pbs-utilisation-pattern-field-header-map-20261021.json`
  (SHA-256 `1e6c2e254af3704ab422cfc4a495648441dae9a533907bca4097cfab15cb33a4`).
- [x] Resolve the prior exact header digest `20f9f06f…e524ad` in the existing
  July 2021–June 2026 summary workbook. It identifies `ATC5_CODE` in five
  annual sheets carrying 1,304,100 ATC-shaped strings; no data values were
  emitted. Receipt:
  `quality/qualifications/australian-pbs-utilisation-summary-workbook-header-resolution-20261021.json`
  (SHA-256 `f717d2bda385a1dc7080b3493de9430998172146c03b5f8252f21e6f61ae71dd`).
- [ ] Map marker-bearing fields in the two expenditure workbooks and finish
  restricted-content classification. These header mappings identify candidate
  fields only; they do not establish vocabulary membership or clear rights. The
  exact six-object user attestation covers all file contents, including
  vocabulary, while its instrument remains independently unreviewed.
- [ ] Calibrate the actual matcher on representative, reviewed source labels.
  Existing 400/400 generated partitions remain poor synthetic-only evidence;
  no real-source threshold or confidence is selected.


## 2026-10-21 PBS expenditure workbook marker context

- [x] Join the previously counted explicit-terminology marker locations in the
  two exact PBS expenditure workbooks to their official sheet titles. The
  value-free mapping resolves marker locations across 7 of 41 sheets in the
  2023–24 workbook and 8 of 47 sheets in the 2024–25 workbook, including named
  tables and figure inputs. Receipt:
  `quality/qualifications/australian-pbs-expenditure-terminology-marker-sheet-map-20261021.json`
  (SHA-256 `baba4bee9a172e4bc4a57fb068ddedb175a7c9df8b75be2aa661a8cbc7bbf01d`).
- [ ] Interpret marker-bearing cell content and classify the identified fields
  against a bounded terminology contract. Sheet context alone is not header or
  content review; no rights or restricted-terminology clearance follows.


## 2026-10-21 exact PBS six-object privacy-pattern screen

- [x] Scan the exact six already-authorized PBS utilisation files at revision
  `9f1d53cd50eea251b326da42a96f3ac72ebce97a` after checking every pinned byte
  count and SHA-256. Across 191,047,619 bytes, the bounded scanner found zero
  email-shaped cell values. The two DOS CSVs each had three sensitive-looking
  headers; a separate exact-header read resolves them to `PATIENT_CAT`,
  `PATIENT_CONTRIB`, and `PATIENT_NET_CONTRIB`, aggregate category/contribution
  measures. Workbook strings contain bounded patient/person token occurrences
  in narrative cells, not classified individual records. The value-free scan
  and context receipt are
  `quality/qualifications/australian-pbs-utilisation-private-pattern-screen-20261021.json`
  (SHA-256 `43c1c2a80adb86bb215dbd2340645fee1ce20d4c17a2a0545c9134c2d4c86f33`) and
  `quality/qualifications/australian-pbs-dos-sensitive-header-context-20261021.json`
  (SHA-256 `a5046bae17eb24a63e286f0c083ca0a2269c997bc2918b7fe3bf97324ee40654`).
- [ ] Complete source-specific restricted-content classification for workbook
  narrative and terminology fields. This detector is bounded, had no exact
  restricted-value digest denylist, and is not an exhaustive privacy or
  licensing clearance. The user attestation remains the rights assertion; the
  instrument was not independently reviewed. No admission, canary, or public
  release followed.


## 2026-10-21 actual-matcher label availability audit

- [x] Reconcile current retained real-source inputs with the matcher's scope.
  The Bronze receipt inventory contains 18 source receipts across
  only these Australian source IDs: `au-data-gov-mbs-demographics|AUS, au-data-gov-mbs-group|AUS, au-mbs-p7-legacy-workbook|AUS, au-mbs|AUS`.
  `src/global_medicines_atlas/matching.py` skips candidates when source and
  target jurisdictions match, while all cross-jurisdiction medicine examples
  in the repository are `synthetic_fixture_only`. The maintainer-reviewed
  5,989-edge MBS set is exact same-record service/benefit provenance, not
  cross-jurisdiction medicine identity ground truth. Audit:
  `quality/qualifications/frontier-real-matcher-label-availability-20261021.json`
  (SHA-256 `6683d10d46b4878747f227ccd6db3033c3338422199889b036f3ef55ca0da868`).
- [ ] Actual matcher calibration needs representative reviewed cross-jurisdiction
  medicine labels. The current source scope cannot supply them; no threshold or
  confidence is calibrated. Keep the calibration requirement open while
  respecting the no-new-sources constraint.
