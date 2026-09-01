# Plan: federated medicines Platinum products

## Phase 1: Product and remote-query contracts (AC-01, AC-02, AC-03)

- [~] Write failing contract tests for v4 resolution, immutable revision/path,
  manifest verification, remote scan, bounded cache, offline state, result
  metadata, and semantic-dimension separation.
  The first storage-neutral slice covers independently admitted exact contract
  and distribution bindings, immutable location/digest metadata, semantic
  dimension and entity-granularity separation, anonymous verified reads,
  explicit offline cache use, eviction, online failure, and byte/time/cache
  budgets. Full query-result evidence envelopes and scan-engine contracts remain
  pending. (`45d9823`; 18 focused and 162 affected tests pass.)
- [x] Confirm the intended failure before implementation. (`45d9823`;
  collection failed with `ModuleNotFoundError` before the resolver existed.)
- [~] Implement a storage-neutral dataset resolver and remote DuckDB/Polars
  query adapter with explicit capabilities and deterministic fallbacks.
  Exact logical resolution and bounded verified byte reads are implemented in
  `45d9823`; DuckDB/Polars projection and predicate-pushdown adapters remain
  pending and no storage engine has been promoted.
- [~] Add cache receipts, byte/time budgets, expiry/eviction, content
  verification, and stale/unavailable states.
  - [x] Add transient exact-contract cache receipts with last verified origin/time,
    current verified-cache availability, contract expiry, immutable content
    identity, and enforced read/cache-entry/open-result/time budgets. Expiry,
    explicit eviction, corrupt same-size content, insufficient cache capacity,
    online failure, and offline misses remain unavailable and fail closed.
    (`9d147ee`; 22 focused tests pass.) Durable product/query receipts and typed
    higher-level unavailable response envelopes remain pending.
- [ ] Phase Verification & Checkpoint: an empty machine can run bounded fixture
  queries from pinned public revisions with no durable local lake.

### Resolver review fixes

- [x] Apply repository formatting to the resolver contract tests before hosted
  qualification. (`5cfe996`; format check and 18 focused tests pass.)

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
