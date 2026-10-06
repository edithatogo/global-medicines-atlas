# Plan: federated medicines Platinum products

## Phase 1: Product and remote-query contracts (AC-01, AC-02, AC-03)

- [x] Write failing contract tests for v4 resolution, immutable revision/path,
  manifest verification, remote scan, bounded cache, offline state, result
  metadata, and semantic-dimension separation.
  The first storage-neutral slice covers independently admitted exact contract
  and distribution bindings, immutable location/digest metadata, semantic
  dimension and entity-granularity separation, anonymous verified reads,
  explicit offline cache use, eviction, online failure, and byte/time/cache
  budgets. DuckDB and Polars now share bounded projection, scalar-filter,
  deterministic-limit, result-digest, exact-evidence-envelope, and semantic
  non-overclaim contracts. (`99b623c`, `57d961b`; the new module and resolver
  pass 47 focused tests with 100% statement and branch coverage.)
- [x] Confirm the intended failure before implementation. (`99b623c`;
  collection failed with `ModuleNotFoundError` before the resolver existed.)
- [x] Implement a storage-neutral dataset resolver and remote DuckDB/Polars
  query adapter with explicit capabilities and deterministic fallbacks.
  Exact logical resolution and bounded verified byte reads are implemented in
  `99b623c`; `57d961b` adds explicit DuckDB and Polars adapters over the
  context-owned verified stream. Both push projection, scalar predicates and
  the deterministic row limit into their Parquet scan while enforcing column,
  filter, row, result-byte and time budgets. DuckDB's named file is transient
  and removed on context exit; no storage engine is promoted as authority.
- [x] Add cache receipts, byte/time budgets, expiry/eviction, content
  verification, and stale/unavailable states.
  - [x] Add transient exact-contract cache receipts with last verified origin/time,
    current verified-cache availability, contract expiry, immutable content
    identity, and enforced read/cache-entry/open-result/time budgets. Expiry,
    explicit eviction, corrupt same-size content, insufficient cache capacity,
    online failure, and offline misses remain unavailable and fail closed.
    (`ce38493`; 22 focused tests pass.)
  - [x] Add deterministic content addresses for exact cache observations,
    successful query plan/result bindings, and typed unavailable envelopes.
    Contract expiry, eviction/cold cache, unknown resources, and verified
    retrieval failure remain distinct; invalid query plans are not relabelled
    as source unavailability. Successful receipts additionally bind the
    independently admitted semantic manifest, and unavailable receipts bind
    the attempted query plan while malformed remote metadata remains typed
    unavailability. (`40d733b`, `a95fe45`; 51 focused tests pass and the query
    and resolver modules retain 100% statement and branch coverage.)
  - [x] Persist cache, successful-query, and unavailable-query receipts as
    bounded atomic content-addressed envelopes. Every read re-verifies the
    envelope and inner receipt digests; expiry, explicit eviction, entry/byte
    eviction, malformed claims, interrupted replacement, and restart readback
    fail closed. The store accepts only receipt types and never source or query
    result payload bytes. Exact canonical inner bytes survive non-ASCII values;
    a bounded root-wide lock serializes multi-instance transactions; and
    unsupported directory sync remains best-effort without bypassing budgets.
    (`b9b5ffe`, `86a56aa`; 37 focused tests pass with 100% statement and branch
    coverage; 239 affected tests and the routine harness pass.)
- [ ] Phase Verification & Checkpoint: an empty machine can run bounded fixture
  queries from pinned public revisions with no durable local lake.
  - [x] Verify one exact, anonymously readable, 24,367-byte MBS Bronze
    projection at immutable revision `75f9f20` with a five-row bounded
    structural query. The public-safe receipt binds the object, metadata,
    schema, row denominator and sample digest without retaining source rows.
    Transport verification is independent of product admission, so the
    receipt records `transport_verified=true`, `product_admitted=false` and
    `checkpoint_complete=false`. The checkpoint remains open until an
    independently admitted v4 product contract and semantic manifest bind a
    published Australian benefits medallion dataset.

### Public-fixture checkpoint review fixes

- [x] Reject clients carrying inherited authorization, cookies, proxy
  authorization, or request/response hooks before any anonymous-preflight
  request is issued. (`4e3df33`, `4627692`; hostile credential and hook
  controls pass.)
- [x] Apply the remaining shared deadline to each metadata, redirect, and
  payload request rather than inheriting an unrelated client timeout.
  (`4e3df33`; latency reduces every later request budget.)
- [x] Reject boolean, non-numeric, NaN, and infinite timeout values before
  constructing the shared preflight deadline. (`4627692`; boundedness remains
  an input invariant.)
- [x] Bind the UTC observation timestamp into receipt version 1.1, regenerate
  the bounded live receipt anonymously, and verify its committed content
  address. (`4e3df33`; 35 focused tests pass with 100% statement and branch
  coverage.)
- [x] Scope the advisory free-threaded canary concurrency key to its workflow
  and ref so activity on another branch cannot cancel the exact-head run.
  (Hosted isolation regression passes; exact-head checks pending.)
- [x] Reject default client query parameters and caller-managed automatic
  redirects before transport, and consume response bodies through an
  absolute-deadline bridge so a stalled chunk cannot extend the shared wall
  deadline. (45 hostile focused tests; 100% statement and branch coverage.)

### Resolver review fixes

- [x] Apply repository formatting to the resolver contract tests before hosted
  qualification. (`f4f0864`; format check and 18 focused tests pass.)
- [x] Bind product semantic dimension and entity granularity to an independently
  admitted, byte-digested, exact-key semantic manifest rather than trusting
  caller labels. Reject unadmitted, duplicate-key, extra-field, aliased, or
  contract-mismatched manifests. (`7cc1693`; hosted P1 review correction.)
- [x] Advertise offline-cache capability only when the v4 contract permits
  exact-digest offline use, configured cache capacity can retain the object,
  the contract cache budget permits it, and expiry is still future. (`7cc1693`;
  hosted P2 review correction; 26 focused tests pass.)

### Query-adapter review fixes

- [x] Register the Platinum query contract suite in the governed unit lane so
  inventory validation and every full Test-Goblin execution include it.
  (`25cf0d0`; the routine harness passes.)

## Phase 2: CLI and API (AC-01, AC-02, AC-04)

- [x] Reduce duplicate comparison cohort work while preserving request-local
  validity, bounded provenance and executed SQL pagination. The shared service
  now issues three rather than four comparison statements and binds repeated
  scope/time values once per statement. Query/API regressions pass. The initial
  paired 20-sample fixture comparison measured p95 441.374 ms before and
  331.128 ms after; a later qualification on the merged implementation passes
  the unchanged 250 ms budget. See the current-host receipt below.
- [x] Define the strict shared dataset-identity response envelope over an
  already-admitted resolver resource. It preserves the exact public revision,
  object/contract/semantic digests, semantic dimension, entity granularity,
  jurisdiction, cohort, times and closed capabilities while declaring
  fail-closed coverage/comparison states and that no rows were queried. Every
  claim-bearing state is required. This contract performs no discovery,
  admission, publication or I/O.
- [x] Add the first resolver-backed read-only API slice at
  `/api/v1/datasets/{resource_id}`. The injected shared identity service maps
  admitted resources to explicit jurisdictions without opening bytes; unknown
  resources return a detail-free typed 404 and an unconfigured service returns
  a typed retryable 503. GET/HEAD, cache policy and OpenAPI responses are
  bounded independently of later query endpoints; the semantic OpenAPI
  snapshot and generated read-only client include the new operation.
- [x] Add the bounded Australian benefits shared query service and GET API.
  The service consumes admitted MBS/PBS identities and verified Parquet through
  the existing Polars adapter. Pages preserve semantic dimension, granularity,
  revision, cohort and source evidence, with separate page/window digests and
  signed cursors bound to resource, query, result and page size. A maximum
  1,000-row scan window is explicit: exhausting the window never establishes
  source completeness. Offline misses return typed unavailability. Clean-wheel
  API imports defer the optional federation runtime. This local slice does not
  complete CLI wiring, filters, general edges/history/coverage or qualification.
- [x] Add a benefits CLI adapter over the shared query service with a separate
  operator-controlled trust configuration. Verify candidate contract/semantic
  changes cannot self-admit, bound metadata files and paths, preserve JSON
  provenance and explicit unavailable exit status. This does not establish
  production admission or complete filters/history/edge/coverage surfaces.
- [x] Write CLI/API contract tests for MBS services, PBS medicines, evidence
  edges, history, coverage, provenance, dataset identity, pagination, filters,
  errors, and OpenAPI compatibility. The repository retains the resulting
  focused contract suites; pre-implementation red output is only recorded
  where it was actually observed.
- [x] Add bounded scalar benefits predicates to the shared service, GET API
  and CLI, preserving filter types and existing query-engine semantics. Bind
  predicates to query evidence and signed cursors; reject malformed copied
  models, unknown filter keys/columns, duplicate JSON keys and nonfinite or
  oversized values. Regenerate the semantic OpenAPI snapshot and read-only
  client. Missing optional jsonschema now reports installation guidance for
  `global-medicines-atlas[federation]`; unrelated import failures propagate.
  This slice does not close history, edge, coverage or production admission.
- [x] Confirm the intended failure before implementation. The Phase 2
  checkpoint validator initially rejected the actual dataset-identity envelope
  because confidence, uncertainty and review states were absent; a collection
  response constructed without the typed tuple boundary also fails closed.
- [x] Implement typed commands and read-only endpoints using shared service
  contracts rather than duplicated query logic. Dataset identity and benefits
  API/CLI slices, plus bounded history, structural evidence-edge, and explicit
  coverage API/CLI surfaces are implemented. Their focused contract suite
  passed 186 tests on 2026-09-14; the remaining Phase 2 checkpoint is a
  broader qualification task.
- [x] Add deterministic pagination, size limits, rate controls, content
  negotiation, cache headers, and provenance envelopes. Benefits pagination,
  serialized-page bounds, fixed-window rate controls, transport observations,
  cache policy and evidence-bearing responses are locally verified.
- [x] Complete the documented content-negotiation follow-up for both API
  versions: accept JSON-compatible media ranges with correct quality handling,
  reject requests that explicitly cannot accept JSON, and document the 406
  response while keeping documentation UI routes available. Before the shared
  middleware, six v1/v2 rejection cases incorrectly returned 200. The final API
  suites pass (93 tests); the shared negotiation helper has 100% statement and
  branch coverage. JSON quality/specificity controls and v1/v2 docs and OpenAPI
  checks pass. The semantic snapshot and generated client were refreshed. Full
  Test-Goblin reported 5,566 passed, one optional skip, and
  three failures: the expected stale snapshot plus two clean-clone release
  probes using the host's wrong uv version. The snapshot check and both probes
  passed when rerun after correction with pinned uv 0.11.29. Routine, context,
  ecosystem, typing, format, and diff checks pass; hosted qualification remains
  pending.
- [ ] Phase Verification & Checkpoint: all result types expose mandatory evidence
  and legacy/current metadata and reject semantic overclaim.
  - [x] Reject v1/v2 assertion rows that combine `unknown` or `not_covered`
    states with a source status code; conclusion models already enforced the
    same distinction. Red tests reproduced the contract gap. This closes that
    semantic-overclaim case only; the broader result-metadata checkpoint stays
    open.
  - [x] Add an explicit `EvidenceContext` to v1 and v2 conclusions and evidence
    rows, and v1 coverage rows. When the query tables do not carry an
    independently bound schema era, comparison cohort, granularity, or review
    record, JSON now reports `null`/`unknown`/`not_reported` instead of omitting
    the metadata. The model cannot assert a reviewed state until a review record
    is supplied. Focused query/API/OpenAPI checks pass and the schema remains
    semantically compatible. This does not populate missing lineage or close
    the checkpoint for every product result surface. The broader local full
    profile passed its pytest lane at 96.81% coverage; its Darwin mutation stage
    hit a native segmentation fault, while standalone mutation (2,250 cases),
    Gremlins (320 tests), regeneration (both 184-test orders), profiling, and
    security lanes passed. Linux hosted mutation remains authoritative.

## Phase 3: Historical comparison and atlas (AC-04, AC-05)

- [x] Write temporal/change, missing-period, source-outage, schema-drift,
  responsive, keyboard, focus, contrast, screen-reader, and non-color-only tests.
  The focused Phase 3 suite now directly exercises absent-left/right periods,
  both-source outages, incomplete snapshots, and schema-era drift alongside
  the established accessible Atlas checks. (`81 passed`, 2026-09-14.)
- [ ] Confirm the intended failure before implementation.
- [x] Implement repository-owned historical comparison and coverage envelopes
  for side-by-side evidence, timelines, change views, coverage/freshness, and
  provenance drill-down. Synthetic validation passes; interactive atlas,
  accessibility, and live-source qualification remain open.
- [x] Keep service-benefit, medicine funding, regulatory, formulary, and
  terminology panels visually and semantically distinct. The source-backed
  Atlas V2 factory renders all five requested dimensions as distinct
  assertion-backed, coverage-backed, or explicit-unknown cards, with missing
  coverage never represented as a negative status (PR #521, merged
  `3ea526b32cdc937cf416f8abebd8c59170dd1eb4`; evidence recorded in PR #522).
- [ ] Phase Verification & Checkpoint: representative users can inspect evidence
  and uncertainty without mistaking legacy or missing data for current status.
  - [x] Add a Chromium-backed synthetic browser E2E check for keyboard medicine
    selection, live status and active-descendant announcements, skip-link focus,
    unknown-state wording, and keyboard disclosure of source evidence. Register
    it in the governed E2E lane and install the pinned Playwright browser in
    both the E2E and full coverage CI jobs.
    The first browser readback exposed an invalid synthetic fixture that paired
    unavailable evidence with provenance; the fixture now models available but
    non-decisive evidence. This verifies interaction behavior, not WCAG
    conformance or representative-user acceptance. The test owns and closes
    its synchronous browser lifecycle instead of using the pytest Playwright
    session fixture, which interfered with unrelated asyncio-based tests in
    the full-suite run.

## Phase 4: Federation and compatibility (AC-06)

- [x] Write and execute synthetic canaries for reimbursement-atlas, donor successor links,
  schema/revision drift, missing fields, semantic dimension changes, and
  mutable/unpinned references.
- [ ] Confirm the intended failure before implementation.
- [x] Publish consumer fixtures and compatibility adapters; update
  reimbursement-atlas to consume GMA/HF contracts rather than duplicate raw
  authority. The protected external PR [reimbursement-atlas#816](https://github.com/edithatogo/reimbursement-atlas/pull/816)
  merged at `a93516ed416118bc51c1db2b71ab540fa4d0fe52` after all required
  hosted checks passed. It consumes an explicitly revision-pinned, digested
  GMA contract identity and rejects malformed contract sections without
  republishing raw authority.
- [~] Verify archived donor READMEs and releases resolve to public successor
  data and documentation without redirecting to local files. Current anonymous
  readback confirms both README-to-`SUCCESSOR.md` links and GMA documentation
  links resolve, but the archived notices falsely say the repositories are
  unarchived and point to historical dataset revisions; the scraper `v0.1`
  tag predates successor links. No GitHub Releases exist. The readback is
  `quality/qualifications/australian-donor-successor-link-readback-20261004.json`.
  Updating archived public content remains a maintainer authorization gate.
- [ ] Phase Verification & Checkpoint: federation has one authority per contract
  and every consumer is revision-pinned.

### Successor-link current-state reconciliation (2026-10-04)

- [x] Read back both archived GitHub repositories, their README/SUCCESSOR.md
  blobs, GitHub Release collections and tags, plus anonymous current MBS/PBS
  successor dataset metadata. Record the exact observations in
  `quality/qualifications/australian-donor-successor-link-readback-20261004.json`.
- [x] Apply the maintainer's 2026-10-04 direction to keep both donor
  repositories archived and defer public notice updates. The copy-ready draft
  remains local; neither repository, tag, release nor dataset was changed.
  See `docs/migrations/australian-donor-successors.md`.
- [~] Keep donor compatibility acceptance open: both external notices still
  falsely say the repositories are unarchived and only name historical
  successor dataset revisions. The scraper `v0.1` tag predates successor
  documentation; neither repository has GitHub Release objects. The accepted
  deferral is not authorization to alter those public artifacts and does not
  satisfy this acceptance task.

## Phase 5: Research exports and qualification (AC-07, AC-08)

- [~] Write failing determinism, citation, Croissant/RO-Crate, package,
  clean-room, load, concurrency, security, privacy, and release-gate tests.
  - [x] Confirmed and fixed query-manifest instability when callers mutate a
    nested query mapping after manifest construction.
  - [x] Add a governed synthetic Bronze-to-Silver-to-Gold-to-Platinum query
  path to the e2e harness; candidate-only Gold and mocked remote reads remain
    explicit. The fixture asserts structural Bronze acceptance independently
    from unknown rights and a false live-source gate (`43aefbf5`; PR #807
    merged as `3ad69e18`, 38 protected checks passed).
- [x] Confirm the intended failure before implementation: the new
  `canonical_result_bytes` contract test initially failed to import that
  missing API.
  - [x] The metadata-only package composition test failed collection because
    the bundle module did not exist.
- [x] Compose the local metadata-only research export package from the existing
  manifest, RO-Crate, Croissant, and lineage contracts.
  - [x] Compose and validate manifest, RO-Crate, Croissant, and lineage
    metadata into a deterministic offline package with no embedded rows.
  - [x] Verify a saved package in a clean-room reader using only its archive;
    reject duplicate JSON members and unexpected ZIP members. Focused tests,
    malformed ZIP/JSON/RO-Crate negative controls, 100% statement and branch
    coverage, 32 targeted end-to-end and regression tests, format/lint, `ty`,
    BasedPyright, routine harness, context, and ecosystem validation passed
    on 2026-10-06.
  - [x] Merge the verifier after all 39 hosted checks passed, including
    Codecov patch coverage, cross-platform consumer tests, and the full
    protected Test-Goblin lanes (`f5df2e42`; PR #810).
  - [x] Bind the bounded synthetic Platinum query's order-stable result bytes
    to its snapshot digest, query receipt, source lineage, and saved package.
    Read the ZIP back through the clean-room verifier and confirm query rows are
    absent (`3a3d3b43`; 45 focused tests, 100% statement and branch coverage for
    both export modules, and the registered E2E lane passes 26 tests). PR #812
    merged as `244dc212` after all 39 protected checks passed.
- [ ] Publish deterministic query snapshots and export packages to the public
  data plane with v4 identities and anonymous verification.
- [~] Run focused, end-to-end, accessibility, OpenAPI, CLI, load, typing,
  coverage, security, provenance, rights, regeneration, and full Test-Goblin
  lanes where supported.
  - [x] Run all local full-profile components on 2026-10-06 with the pinned
    temporary `uv 0.11.29`: full pytest passes with one optional PyIceberg skip
    and 96.81% coverage; mutation analyzes 2,250 mutants; gremlins passes 317
    tests (861 zapped, 87%); Scalene profiling and the security audit pass.
    The first umbrella run exposed the missing pinned uv and optional Scalene
    group; the pinned clean-clone probes pass, and profiling/security were
    rerun explicitly after installing the declared profiling group. The
    broader product qualification remains open for hosted and external gates.
- [x] Run Conductor review, repair findings, open scoped pull requests, wait for
  hosted checks, merge, and reconcile evidence; stop at public release and
  consequential-interpretation gates.
  - [x] Self-review the result-bytes diff against the Platinum plan, product
    guidelines, and Python style guide; no correctness, provenance, privacy, or
    maintainability findings remain (`3a3d3b43`).
  - [x] Merge the scoped implementation after all 39 protected checks passed;
    reconcile exact PR head, merge commit, and hosted state in append-only
    evidence (PR #812).

### Current-host product performance requalification (2026-10-06)

- [x] Re-run the governed synthetic product qualification on merged
  implementation `8ccefeeb070ca2b2443b920891819972880705a851ae42aa62bc6931bf4a5eba`.
  The durable comparison p95 is 144.987 ms against the unchanged 250 ms budget;
  bounded single-page export traversal is 305.613 ms against 1,000 ms. The
  resulting release evidence is `fixture_qualified`, with clean-start,
  live-deployment, accessibility-conformance, and production-data gates still
  unverified. The value-file receipts and aggregate are in
  `quality/qualifications/platinum-product-performance-20261006/`.
