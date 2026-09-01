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
    result payload bytes. (`591c011`; 28 focused tests pass with 100% statement
    and branch coverage; 230 affected tests and the routine harness pass.)
- [ ] Phase Verification & Checkpoint: an empty machine can run bounded fixture
  queries from pinned public revisions with no durable local lake.

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

- [ ] Write failing CLI/API tests for MBS services, PBS medicines, evidence
  edges, history, coverage, provenance, dataset identity, pagination, filters,
  errors, and OpenAPI compatibility.
- [ ] Confirm the intended failure before implementation.
- [ ] Implement typed commands and read-only endpoints using shared service
  contracts rather than duplicated query logic.
- [ ] Add deterministic pagination, size limits, rate controls, content
  negotiation, cache headers, and provenance envelopes.
- [ ] Phase Verification & Checkpoint: all result types expose mandatory evidence
  and legacy/current metadata and reject semantic overclaim.

## Phase 3: Historical comparison and atlas (AC-04, AC-05)

- [ ] Write failing temporal/change, missing-period, source-outage, schema-drift,
  responsive, keyboard, focus, contrast, screen-reader, and non-color-only tests.
- [ ] Confirm the intended failure before implementation.
- [ ] Implement side-by-side service/medicine evidence, timelines, change views,
  graph exploration, coverage/freshness, and provenance drill-down.
- [ ] Keep service-benefit, medicine funding, regulatory, formulary, and
  terminology panels visually and semantically distinct.
- [ ] Phase Verification & Checkpoint: representative users can inspect evidence
  and uncertainty without mistaking legacy or missing data for current status.

## Phase 4: Federation and compatibility (AC-06)

- [ ] Write failing canaries for reimbursement-atlas, donor successor links,
  schema/revision drift, missing fields, semantic dimension changes, and
  mutable/unpinned references.
- [ ] Confirm the intended failure before implementation.
- [ ] Publish consumer fixtures and compatibility adapters; update
  reimbursement-atlas to consume GMA/HF contracts rather than duplicate raw
  authority.
- [ ] Verify archived donor READMEs and releases resolve to public successor
  data and documentation without redirecting to local files.
- [ ] Phase Verification & Checkpoint: federation has one authority per contract
  and every consumer is revision-pinned.

## Phase 5: Research exports and qualification (AC-07, AC-08)

- [ ] Write failing determinism, citation, Croissant/RO-Crate, package,
  clean-room, load, concurrency, security, privacy, and release-gate tests.
- [ ] Confirm the intended failure before implementation.
- [ ] Publish deterministic query snapshots and export packages to the public
  data plane with v4 identities and anonymous verification.
- [ ] Run focused, end-to-end, accessibility, OpenAPI, CLI, load, typing,
  coverage, security, provenance, rights, regeneration, and full Test-Goblin
  lanes where supported.
- [ ] Run Conductor review, repair findings, open scoped pull requests, wait for
  hosted checks, merge, and reconcile evidence; stop at public release and
  consequential-interpretation gates.
