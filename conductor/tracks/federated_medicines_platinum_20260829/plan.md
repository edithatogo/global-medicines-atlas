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
- [x] Phase Verification & Checkpoint: all result types expose mandatory evidence
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
  - [x] Render bound evidence context in Atlas comparison cards and coverage
    rows. A red accessibility test confirmed those fields were absent from the
    rendered result. The UI now shows schema era, comparison cohort, entity
    granularity, and review state; missing values are explicitly “Not
    reported” or “Unknown.” Focused accessibility/browser tests passed (5),
    and the governed E2E lane passed (27). The full profile passed with 5,904
    tests, one optional PyIceberg skip, and 96.82% coverage; mutation examined
    2,250 cases (1,879 killed, 364 survived, five suspicious, two unmutated),
    Gremlins passed 322 tests (892 zapped, 100 survived, no errors), both
    randomized orders passed 184 tests, and profiling/security passed. This
    displays the current context contract but does not populate missing source
    metadata or close the broader checkpoint.
  - [x] Preserve the left and right subjects' evidence contexts on each
    comparison-validity result. Contexts flow from the compared conclusions
    through the v1 API; absent metadata remains explicitly unknown per side.
    The versioned validity schema and additive OpenAPI snapshot are updated,
    and the consumer compatibility baseline remains unchanged. Synthetic
    query/API controls verify that distinct contexts are not collapsed. An
    asymmetric-context regression preserved each side's independent unknown
    fallback after hosted mutation initially found a small survivor-score
    regression. PR #824 merged as `c98ab6b0` after all 39 hosted checks passed;
    Linux mutation killed 1,889/2,256 (83.7323%), above the immutable baseline.
    The broader checkpoint and production source qualification remain open.
  - [x] Give the additive v2 comparison endpoint explicit pairwise validity
    and report whether pagination makes that validity set complete. The v2
    envelope currently returns cross-jurisdiction conclusions without a
    validity result; no evidence-backed compatibility dimensions are
    populated, so the safe outcome must remain insufficient evidence. The
    intended-red service test confirmed `validity_completeness` was absent.
    Runtime validity now binds each pair to both subject contexts, enforces
    complete pair coverage for non-paginated results, and identifies paged
    outputs as partial. PR #825 merged as `caf05e700e3d77d2076837de6498a36cb5c3d7ac`
    after all 39 hosted checks passed; Codecov reported 100.00% patch coverage
    against the 90.01% target, and the full hosted profile passed 5,931 tests
    with one optional skip at 96.80% coverage. The focused source-neutral result
    surface matrix subsequently passed 224 tests; `test_goblin.py routine`
    passed. A deliberately forged BenefitsPage in its fail-closed regression
    emits a Pydantic serializer warning before revalidation rejects it; it does
    not bypass the transport boundary. This completes the v2 pairwise validity
    subtask only. The broader all-result-types checkpoint, production source
    qualification, source coverage, representative-user acceptance, WCAG
    conformance, and release gates remain open.
  - [x] Add one regression matrix across evidence and non-evidence product
    outputs. Assertion and coverage rows require explicit evidence context and
    valid-time clocks; v1/v2 response envelopes preserve version, paging, and
    comparison-validity metadata; identity and benefits results preserve exact
    admitted-object lineage and explicit not-declared states; historical pages
    preserve per-snapshot source revision, paths, digests, era, cohort, and
    observed time; Gold edges remain a schema-versioned synthetic structural
    projection; discovery explicitly denies equivalence; health/errors remain
    operational envelopes without product conclusions. Existing fail-closed
    validator tests cover unsupported status, missing evidence, pagination,
    incomplete history, and edge qualification. The new cross-surface guard
    runs in Test-Goblin and the dependency-upgrade contract lane. The affected
    suite passed 201 tests, and routine checks passed. This closes the bounded
    result-contract checkpoint only; it does not establish populated source
    context, source coverage, production qualification, representative-user
    acceptance, WCAG conformance, or release readiness.

  - [x] Connect the exact reconciled synthetic PBS Gold edge object to the
    resolver-backed V2 dataset-identity API. The response preserves its pinned
    revision, path, object digest, `source_structure` dimension and
    `evidence_edge` granularity while keeping coverage undeclared, comparison
    unevaluated, and rows unqueried. The identity-only request performs no
    object read; anonymous transport remains mocked. Two governed medallion
    E2E tests pass. PR #841 merged as `24ef28a7555cc3746d5fb8cdad79c548998f6780`
    after all 36 hosted checks passed. This proves synthetic API wiring only
    and does not qualify a production source or close the broader Phase 2
    checkpoint.

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
- [x] Give keyboard focus a dedicated indicator color and assert at least 3:1
  contrast against the configured Atlas paper and wash surfaces (7.788:1 and
  7.149:1 for the current palette). A red test first failed because the
  dedicated token was absent. This is automated color-contrast evidence for
  those surfaces only; it does not establish full WCAG conformance.
- [x] Keep service-benefit, medicine funding, regulatory, formulary, and
  terminology panels visually and semantically distinct. The source-backed
  Atlas V2 factory renders all five requested dimensions as distinct
  assertion-backed, coverage-backed, or explicit-unknown cards, with missing
  coverage never represented as a negative status (PR #521, merged
  `3ea526b32cdc937cf416f8abebd8c59170dd1eb4`; evidence recorded in PR #522).
- [ ] Phase Verification & Checkpoint: representative users can inspect evidence
  and uncertainty without mistaking legacy or missing data for current status.
  - [x] Add a federated Atlas view that queries already-admitted benefit
    evidence from its pinned resolver identity, preserves evidence provenance,
    and keeps service-benefit edges separate from medicine funding and
    regulatory conclusions. Mount it through the source-backed Atlas factory
    and link it from the home page when configured. Exercise the rendered view
    in the synthetic Bronze-to-Platinum E2E path. PR #848 merged as
    `075ea0920fd950e54975d941c45ac38b66bed25f` after all 38 hosted checks passed,
    including all 28 required branch-protection contexts and 100% Codecov patch
    coverage. Representative-user acceptance remains open at the parent
    checkpoint.
  - [x] Expose existing PBS `source_structure` Gold edges through a separate
    pinned Atlas view with v2 identity, an anonymous bounded query, verified
    cache reuse, and explicit non-equivalence wording. Track issue #850; no
    source acquisition, admission, or publication is part of this task. The
    view renders the full evidence identity and retains it with the bounded
    receipt on unavailable reads. Focused Atlas/medallion checks (11) and the
    routine harness pass; exact-head PR #851 passed all 38 checks, including
    Codecov, then merged as `77dea5a4` on 2026-10-07. This closes only the
    synthetic source-structure Atlas integration, not representative-user
    acceptance or the broader Phase 3 checkpoint.
  - [x] Render the existing bounded historical-change service in an opt-in
    Atlas timeline, preserving source identity, attribution failures, and
    unknown absence semantics. The synthetic Bronze snapshot pair passes
    through API, CLI, and Atlas; no sources or acquisition paths were added.
    Focused Atlas/medallion (9) and governed E2E (32) checks plus routine
    checks pass. Hosted exact-head PR #862 passed all 38 checks and 100% of
    patch coverage, then merged as `fb949d5d` on 2026-10-09. The local full
    profile was attempted with Python 3.14.6; the first run lacked pinned uv
    0.11.29, and a pinned-toolchain retry passed 5,983 tests with one optional
    PyIceberg skip before exhausting host disk space during coverage output.
    The two toolchain-sensitive stable-v1 tests pass when run with uv 0.11.29.
    No local full-profile pass is claimed. No additional source was added.
  - [x] Add a Chromium-backed synthetic browser check for the historical Atlas
    route, exercising skip-link navigation, keyboard access to the snapshot
    table, snapshot identity, and before/after native values/states. The focused
    browser tests (2), governed E2E lane (33), routine, Ruff, ty, and BasedPyright
    passed locally. Review tightened the browser assertions so each labelled
    table row is bound to its expected revision and path. PR #864 merged as
    `ba47289513a1f6da2a831d8ca12769886c0687b5` after all 37 hosted checks passed,
    including Codecov patch coverage and Linux/macOS/Windows consumers.
    Representative-user acceptance and full WCAG conformance remain open.
  - [x] Drive the browser from the Atlas home page through the history link and
    load the stylesheet and autocomplete script through the application's ASGI
    routes. Playwright fulfills each browser request with the synthetic ASGI
    test client; this verifies route-to-render wiring without claiming a
    deployed-server run. Review requires successful (200) stylesheet and script
    responses, a computed stylesheet effect, and observable autocomplete status
    after script execution. The focused browser tests (2), combined history and
    medallion E2E tests (4), Ruff, `ty`, routine harness, and diff checks pass.
    PR #866 merged as `f9c851df335e6f7051dd4673b15dd73946ad6d5e` after all 37
    hosted checks passed, including Codecov patch coverage and
    Linux/macOS/Windows consumers.
  - [x] Keep federated benefits and source-structure interpretation copy
    accurate for currently identified resources whose v4 identity declares the
    `current` cohort. Synthetic route regressions assert that those views do
    not call the resource fixture-only or synthetic while preserving explicit
    undeclared-coverage and non-equivalence limits. Focused Atlas, medallion,
    browser, accessibility, routine, and full Test-Goblin checks passed with
    pinned uv 0.11.29: 5,998 passed, one optional PyIceberg skip, 96.88%
    coverage; 332 gremlin checks passed. Local Darwin mutation observations
    are advisory and Linux CI remains authoritative. This copy correction does
    not establish source coverage or production qualification.
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
  - [x] Verify the focus-indicator contract and run the full local profile on
    the rebased head: the five focused accessibility/browser tests passed;
    pytest passed 5,904 tests with one optional PyIceberg skip and 96.81%
    coverage; mutation analyzed 2,250 cases (1,879 killed, 364 survived, five
    suspicious, two unmutated, zero timeouts); Gremlins passed 322 tests,
    zapped 864 classified mutations (87%), and reported 125 survivors and one
    error; both randomized orders passed 184 tests; Scalene qualification
    passed; offline zizmor found no issues, and pip-audit found no known
    vulnerabilities (the unpublished local package was skipped). The full
    harness exited 0. These automated checks do not establish WCAG conformance
    or representative-user acceptance.
  - [x] Drive a Chromium browser from Atlas home into the existing federated
    benefits and source-structure views, load their application assets through
    the synthetic ASGI client, and submit bounded queries. The journey exposed
    that a blank optional benefits filter was passed as invalid JSON and
    returned HTTP 422; normalize only the blank value to no filter, preserving
    strict parsing for non-empty input. Five focused browser/route tests, the
    routine harness, Ruff, `ty`, and repository BasedPyright pass. Full
    Test-Goblin with pinned uv 0.11.29 also passed locally. PR #873 merged as
    `f496daa20a3ff63640340198e73287ca0305547e` after all 38 hosted checks,
    including Codecov and protected contexts, passed. This proves a synthetic
    browser-to-ASGI path only;
    it adds no source and does not establish source coverage, deployment,
    WCAG conformance, or representative-user acceptance. Automated review
    caught a receipt timestamp later than its introducing commit; an appended
    evidence correction now records the commit timestamp as the first durable
    verifiable time.
  - [x] Cover federated browser error recovery for an unknown resource and a
    malformed non-empty benefits filter. The browser observes the expected
    404/422 responses, accessible alert messages, and preserved invalid input;
    the already-verified ASGI fixture exercises both route outcomes. Review
    tightened the retained-input assertion to compare the complete submitted
    string. Six focused module tests and Ruff passed after correction;
    repository typing passed before the assertion-only change, and routine was
    rerun after it during merge-receipt reconciliation. PR #875 merged as
    `0f80a02d4ac3e0440250c2bd486ac915bd758938`
    after all 37 hosted check runs passed, including Codecov, protected
    contexts, and Linux/macOS/Windows consumers. This is test-only synthetic
    evidence; it adds no source or runtime behavior and does not establish
    representative-user acceptance or WCAG conformance.
  - [x] Exercise an offline verified-cache miss through the federated benefits
    Atlas in Chromium. The typed unavailable result must render as an accessible
    status with actionable cache guidance, without an evidence table or a
    negative-coverage implication. The regression exposed the internal reason
    code being shown directly; review also caught that an expired cached copy
    can be refreshed online. Both missing-cache and expired-cache messages now
    offer that recovery. The eight-test focused module and full pinned
    Test-Goblin profile pass; this synthetic fixture change adds no source,
    acquisition, publication, source-coverage claim, or production admission.
    Representative-user acceptance and WCAG conformance remain open.
  - [x] Exercise the online `verified_resource_unavailable` result in Chromium
    in addition to offline cache-miss and expired-cache states. The status copy
    is actionable, no table is rendered, and the browser path does not turn a
    failed read into a negative claim. The focused module passes nine tests;
    repository routine, formatting, and diff checks pass. This is a test-only
    synthetic follow-up to the current full-profile evidence. PR #878 merged
    as `bba01ac4277f7f897a048720a175188fb71bc213` after all 37 exact-head hosted
    checks passed, including protected contexts, Codecov, and all three
    consumer platforms. No source coverage, admission, or publication claim was
    added.
  - [x] Exercise missing-cache, expired-cache, and online verified-read
    unavailability for source-structure evidence in Chromium. The page provides
    readable recovery guidance, preserves exact identity and query receipt,
    announces an accessible status, shows no evidence rows, and rejects an
    accidental offline flag in the online fixture. The affected browser,
    API, and medallion set passes 23 tests; full pinned Test-Goblin passed with
    6,006 tests, one optional PyIceberg skip, and 96.87% coverage. PR #879
    merged as `2834ed10f5615244cd28f559859c4b36314e877e` after all 39 hosted
    checks passed, including protected contexts, Codecov, and all consumer
    platforms. This synthetic fixture adds no source or admission.
  - [x] Exercise unknown source-structure resources and invalid bounded columns
    through the Chromium form. Assert accessible 404/422 errors and exact
    retention of both submitted fields after each response, with no stale
    evidence table rendered. The focused browser module passes 13 tests; the adjacent Atlas, structure API, and medallion
    suite passes 24 tests, plus routine, lint, format, and diff checks. PR #880
    merged as `0a9f1e85a2bf30784802655e604dce8bd1c06e26` after all 28 required
    branch-protection contexts passed. Thirty-seven of 38 check runs passed;
    the optional Delta table-format check was still queued at reconciliation.
    This is test-only synthetic evidence.
  - [x] Use a generic accessible message for unrecognized source-structure
    failure reasons so future internal codes are not exposed to users. Synthetic
    Chromium cases confirm the reason is absent from rendered text and the
    unavailable receipt JSON is hidden while its digest and retained status
    remain visible; no evidence rows appear. The adjacent Atlas, structure API,
    and medallion suite passes 25 tests. Pinned Test-Goblin passes 6,010 tests,
    one optional PyIceberg skip, and 96.88% coverage; Gremlins reports 332
    passed, both randomized runs pass 184 tests, and offline zizmor reports no
    findings. PR #882 merged as `8b68bf9cd2431b39d9e03cb35938f06e5463e50d`
    after all 28 required branch-protection contexts and all 38 exact-head check
    runs passed, including Codecov and Linux/macOS/Windows consumers.
  - [x] Verify keyboard recovery after source-structure 404 and 422 errors.
    Activate the source-structure link by Enter, then use the skip link and
    verify the sequential tab order through both text fields, row limit, cache
    checkbox, and submit button. Keyboard text entry corrects the retained query
    and resubmits successfully for both errors. The adjacent Atlas, structure
    API, and medallion suite passes 27 tests; Ruff, format, routine, and diff
    checks pass. This synthetic test-only follow-up adds no sources and relies
    on the preceding pinned full-profile result. Linux CI caught and prompted
    the platform-aware ControlOrMeta+A correction. PR #883 merged as
    `d1147ba2ca44e000f14cae71a00ffd756a40e67d` after all 28 required
    branch-protection contexts and all 37 exact-head check runs passed,
    including Codecov and Linux/macOS/Windows consumers. Hosted checks for this
    404/422 expansion remain pending.

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
- [x] Preserve all contract authority, object-size, source representation,
  schema-era, cohort, and temporal identity fields in GMA consumer bindings;
  reject malformed source/verification sections with a bounded error. The
  intended-red regressions show these fields are currently dropped and malformed
  JSON object sections can escape as `AttributeError`. Green: 27 focused tests
  with 100% statement and branch coverage, Ruff, ty, routine, and full
  Test-Goblin passed with pinned uv 0.11.29 on Darwin/Python 3.14.6. PR #828
  merged at `8801c8c2` after 38 hosted checks passed, including 100% Codecov
  patch coverage. Synthetic v4 fixtures only; no source reads, acquisition,
  admission, or publication.
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
- [x] Run focused, end-to-end, accessibility, OpenAPI, CLI, load, typing,
  coverage, security, provenance, rights, regeneration, and full Test-Goblin
  lanes where supported. Exact-head PR #866 passed all 37 hosted check runs,
  including the full Test-Goblin coverage, mutation, Gremlins, security,
  regeneration, browser E2E, Codecov, and Linux/macOS/Windows consumer lanes.
  This closes automated test execution only. It does not qualify production
  source coverage, settle licensing or rights, establish full WCAG conformance
  or representative-user acceptance, or authorize publication or release.
  - [x] Carry the existing synthetic MBS Gold edges through the public edge
    API and CLI, and compare their bounded structural evidence readbacks.
    The existing Bronze-to-Platinum MBS fixture now verifies exact API/CLI
    page equality, candidate-only qualification, row count, and source
    identity. Both medallion E2E cases pass locally. PR #855 merged as
    `7f27ae4b6c2eed9ec9067b4e12b09b119b6b5330` after all 38 hosted checks,
    including Codecov patch coverage and Linux/macOS/Windows consumers, passed.
  - [x] Compare a synthetic historical MBS snapshot pair through the bounded
    history API and `gma history`, preserving explicit change and unknown
    absence semantics without inferring cessation. Both source snapshots now
    come from landed XML parsed through MBS Silver. The end-to-end comparison
    covers a changed description and a left-only native row; both surfaces
    agree and absence remains `unknown`. The affected E2E tests (2), routine
    checks, Ruff, formatting, and diff validation pass locally. PR #856 merged
    as `6484d045ed15f15a5c1004adca3528f2335540ca` after all 37 hosted checks,
    including Codecov patch coverage and Linux/macOS/Windows consumers, passed.
  - [x] Extend the synthetic Bronze-to-Platinum end-to-end qualification to
    query remotely, reproduce from its verified offline cache, prove explicit
    unavailability after eviction, and refetch the same result. The synthetic
    contract expiry is bound beyond the fixed qualification clock. PR #834
    merged as `59b75c9b6445bdb247a20ec7db2a8d5a48e650b9` after all 38 hosted
    checks, including Codecov and Linux/macOS/Windows consumers, passed. No
    source data or publication is involved.
  - [x] Carry the synthetic MBS Gold edge through the bounded `BenefitsService`
    and read-only `/api/v1/benefits/{resource_id}` endpoint. Verify anonymous
    metadata and exact-object reads use the reconciled revision and path, the
    response preserves the exact Gold digest and source/evidence-edge identity,
    and coverage/comparison remain `not_declared`/`not_evaluated`. The two
    medallion tests and governed 31-test E2E lane pass; no source bytes or
    production admission are involved. PR #846 merged as
    `292b9719147796866cf059b3576f928ff9ed0eb8` after 38 hosted checks passed.
    This is synthetic API integration only.
  - [x] Exercise the same synthetic MBS Gold edge through `gma benefits` and
    compare rows, identity, page/window digests, and conservative coverage and
    comparison states with the API response. Focused medallion tests (2), the
    governed E2E lane (31), routine checks, Ruff, `ty`, and BasedPyright pass;
    the four existing optional `huggingface_hub` source warnings remain.
    No source acquisition, production admission, or publication is involved.
  - [x] Add `gma source-structure` for the existing synthetic PBS Gold edge;
    compare its identity and bounded rows/result digests against the resolver
    query in the governed E2E test. The final focused suite passes 43 tests;
    the governed integration and clean-clone probes pass. The local full
    profile's pytest phase passed; one performance test exceeded budget under
    full-profile load and passed on isolated rerun. Exact-head hosted
    performance, coverage, integration, mutation, gremlins, security, and all
    platform consumer checks passed. PR #853 merged as
    `b377938b78eb8108868fd240bcf68054b6c18b4b` after 29 required check runs
    passed. No new source, acquisition, admission, coverage claim, or
    publication is involved.
  - [x] Close the Codecov patch gap for this CLI by covering typed unknown
    resource, invalid request, and I/O error responses. The final exact-head
    Codecov patch check passes at 100%.
  - [x] Load the configured resolver before importing optional federation
    query modules so a base installation receives the existing typed
    `SERVICE_UNAVAILABLE` response. Configuration and query error controls
    pass in the focused suite and the hosted exact-head CI.
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

### PBS source-structure Platinum integration (2026-10-07)

- [x] Admit `source_structure` as its own internal Platinum semantic value;
  preserve source-structure edges without funding, formulary, regulatory, or
  terminology promotion.
- [x] Keep the established v1 dataset-identity enum unchanged and expose the
  expanded source-structure identity through the isolated v2 dataset route.
- [x] Verify synthetic PBS bytes from Bronze B1 receipt through Silver fields,
  Gold containment edges, Platinum verified query/cache recovery, research
  export, and non-publishable v4 producer-inventory reconciliation.
- [x] Complete exact-head protected hosted checks, merge, and append the hosted
  merge receipt. This remains a fixture-only qualification and makes no claim
  about populated public sources, source coverage, deployment, or release.

### Bronze acquisition-metadata projection federated E2E (2026-10-09)

- [x] Carry the actual landed B1 acquisition-manifest Parquet projection
  through v4 distribution reconciliation, remote read, verified cache,
  eviction, and refetch. Keep the receipt-bound B2 bytes local, and verify the
  existing distribution gate rejects raw B2 as a derived projection. Use only
  the existing synthetic MBS/PBS fixtures; no additional source, source claim,
  or public mutation. PR #858 merged as `8cc48eac` after all 37 hosted checks
  passed. The review follow-up inspects decoded Parquet columns and Arrow / file
  metadata for B2 payload and workstation-path sentinels; negative controls
  inject both sentinels into values and metadata and confirm rejection. The
  review-control follow-up merged as PR #860 (`9d600070`) after all 37 hosted
  checks passed. No source acquisition,
  production admission, coverage claim, public publication, or release.
