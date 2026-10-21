# Plan: public Hugging Face federated data plane

## Phase 1: Freeze and remediate the current estate (AC-01, AC-02, AC-08)

- [x] Add regression tests for complete estate enumeration, exact revision and
  manifest allowlists, public/non-gated state, and anonymous restoration.
  Direct public dataset/collection scan tests now cover complete-list bounds,
  duplicate and malformed identities, exact immutable revisions, visibility,
  member-note preservation, deterministic order, and credential-free reads.
  `tests/test_hf_estate_visibility_workflow.py` retains exact manifest,
  anonymous restoration, and visibility containment checks. See the
  2026-10-01 estate scan test evidence record.
- [x] Record that the original Phase 1 intended-failure output was not retained
  and is irrecoverable; do not fabricate it from later green tests. The
  source-metadata slice retains its own reproducible collection failure and
  digest-bound negative controls in
  `quality/qualifications/hf-source-metadata-negative-controls-20260902.json`.
- [x] Generate a public-safe estate registry snapshot without credentials or
  restricted contents. (`f5d10ed`, permission hardening `31f2458`;
  93 entries from stable owner-filtered scans, six private identities redacted;
  local metadata observation only, not publication of the registry dataset.)
- [x] Add an exact-revision GitHub Actions workflow for the legacy composite;
  require the default head to equal the authorized revision, verify its
  manifest and sibling set against the public baseline, and persist a rollback
  intent on issue #340 before any visibility change.
- [x] Make the exact legacy composite public in the hosted workflow, download
  every manifest object anonymously, verify all 42 SHA-256 digests, and persist
  the receipt durably on issue #340 as well as a bounded Actions artifact.
- [x] Restore privacy from a separate cleanup job after failed or cancelled
  dispatches, and run an hourly watchdog that contains public visibility when
  no trusted exact success receipt exists or the dataset head has drifted.
- [x] Keep licensed ontology, rare-burden, unrelated Space, and empty collection
  states unchanged and record why.
- [x] Phase Verification & Checkpoint: one eligible legacy dataset is public and
  anonymously recoverable; no other private state was broadened.

## Phase 2: Contract v4 and public dataset topology (AC-03, AC-04, AC-09)

- [x] Write failing JSON Schema and semantic tests for all mandatory v4
  authority, location, digest, visibility, verification, rights, collection,
  replica, schema-era, comparison, lineage, and cache fields. (`6055379`)
- [x] Confirm the intended failure before implementation. (`6055379`;
  missing module, then three trailing-newline identity regressions)
- [x] Commit immutable v4 schema, valid/invalid fixtures, documentation, and
  cross-repository conformance canaries.
  Schema, offline semantic validation and portable canary fixtures implemented
  in `6055379`; 54 focused tests pass with 100% semantic-module branch coverage.
  reimbursement-atlas PR #816 merged at
  `a93516ed416118bc51c1db2b71ab540fa4d0fe52`; its binding requires the GMA
  producer, immutable revision, and content digest. The current GMA contract,
  compatibility-canary, and consumer suites pass (99 tests). This verifies
  one pinned consumer and synthetic canaries; live receipt emission and
  production admission remain open as separate qualification gates.
  This independent Phase 2 contract slice does not close the remaining Phase 1
  complete-estate inventory tasks.
- [x] Approve the stable `edithatogo/australian-mbs-source-archive` name and
  implement its create-private, publish, and anonymous-verification transaction
  entirely in GitHub Actions. The exact revision is public, non-gated, and
  anonymously digest verified. (`4d1dae4`, run `33244323861`)
- [x] Create the exact approved PBS source dataset from GitHub Actions.
  Run `33290449753`, public revision `31ec854ef9fc82f30a0dbe743fdf50a2e5bd24a7`;
  issue #340 receipt `5466488482` verifies ZIP/XML digests and hosted cleanup.
  Anonymous metadata recheck on 2026-08-31 confirms public/non-gated identity.
- [ ] Create the Australian benefits medallion dataset from GitHub Actions
  once its non-empty, independently admitted producer manifest exists.
- [x] Require source-specific data cards, Croissant, citations, provenance,
  coverage, rights/permission, withdrawal/correction, and version histories.
  The offline MBS/PBS contract, valid/invalid fixtures, and intended-red receipt
  are implemented. PBS metadata was appended and anonymously verified at
  revision `48fd7345fb09277bb5b85644dba72804633a2abb` (run
  `36520821504`; issue #340 comment `5883538920`). MBS metadata was appended
  and anonymously verified at revision
  `243f9ff5498816af6e4d9ae4db60528728f01834` (run `36532129354`; issue #340
  comments `5885053897`, `5885054280`, and `5885067299`). The MBS document
  retains source release `75f9f20a36ddb829dfe0ca88660664570782be02`, with
  exact CAS parent `ba82cd1d0f9b0f28514df431b8da3a6c207d76fa`; its 2,900-byte
  object SHA-256 is
  `1067278e06e40edc15994dedc9789f5130aea4727c9dcf3be276f475743e896e`.
  The hosted verifier preserved and anonymously rehashed all 49 baseline
  objects; the archive remains public and non-gated. See
  `docs/qualification/source-metadata-append.md` for both hosted receipts.
- [ ] Phase Verification & Checkpoint: datasets exist publicly but contain only
  exact approved manifests; empty repositories are not claimed as data.

## Review Fixes: v4 federation foundation

- [x] Reject B0 projections, blank or padded mandatory text, null independent
  replica RPO/RTO, and case/whitespace aliases of the same recovery domain.
  (`7ac4ada`; nine intended regression failures before correction)
- [x] Requalify the corrected contract through focused tests and exact-head
  hosted checks; retain partial local full-suite evidence separately.
  (`0e2a818`, PR #369; reviewed `648d32b`, all 38 checks passed; 62 focused tests)

## Phase 3: Publish the donor and continuing raw corpus (AC-03, AC-06)

- [x] Write failing hosted-workflow tests for exact donor digests, duplicate or
  missing files, path traversal, private/gated output, local upload attempts,
  partial uploads, anonymous digest mismatch, and premature cleanup. The first
  slice covers exact payloads, Actions-only transport, public/non-gated state,
  anonymous digests, and privacy containment; archive hardening remains open.
- [x] Confirm the intended failure before implementation.
- [x] Implement hosted publication of the July 2025 MBS XML and July 2024 P7
  workbook as separate exact B2 objects with provenance, authorization, and
  manifest material. (`4d1dae4`, run `33244323861`)
- [ ] Publish continuing MBS/PBS exact source manifests only after acquisition,
  admission, authorization, and source-version gates pass.
  Exact August 2026 MBS release is now public at `75f9f20a36ddb829dfe0ca88660664570782be02`
  (run `33296983154`), alongside the previously verified April 2026 PBS archive.
  This does not authorize future unenumerated releases or complete v4 emission.
- [x] Retain the two donor Git ancestry bundles, source bytes, licences, and
  donor inventory; never replace the XML/XLSX raw objects with Parquet.
- [ ] Retain continuing archive/container bytes as well as member manifests;
  never replace
  an XML/ZIP/XLSX raw object with Parquet.
- [x] Remove the hosted temporary source-byte workspace only after token-free
  clean-room verification succeeds and its cleanup receipt is durable. (run
  `33244323861`)
- [x] Phase Verification & Checkpoint: every approved donor raw object and both
  complete histories are public, non-gated, and token-free digest verified;
  no durable workstation-only copy is required. (`4d1dae4`)

## Phase 4: Publish derived medallion products (AC-04, AC-06)

- [x] Implement an offline v4 referenced-receipt byte-closure checker. Validate
  the existing contract, enumerate every named receipt role, require exact
  caller-supplied bytes and SHA-256 agreement, and bound count and byte sizes.
  Reject missing/extra/conflicting references; allow one exact object to serve
  multiple explicit roles. Return immutable role/digest inventory only: this
  is neither independent authority nor admission, publication or qualification.
  Test hostile copied inputs, metadata-only output, role coverage and no I/O.
  Implemented `84c844a` (agent `294b506`): 22 new and 156 broader tests pass,
  full module coverage; duplicate JSON-key regression failed before repair.
  Root integrated all three evidence slices: 414 tests pass, 100% statement
  and branch coverage for the three affected modules before the review fix.
  Review correction `6bb351b` (agent `3e797a2`) adds structural bounds before
  schema uniqueness validation: 256 container entries/references, 8,192 nodes,
  depth 32. Four oversized/malformed-reference regressions failed before repair;
  210 integrated tests and 28 independent review tests pass, 99.08% closure
  coverage. PR #403 merged as `44a603d` after all 38 hosted checks passed;
  reviewed/merged trees match. Actual admission remains separately pending.
- [~] Add independently trusted typed admission adapters after byte closure;
  validate subject/layer/lineage and authorization rather than treating
  self-consistent or digest-matched receipts as authority. Existing public
  archives must not be retroactively labelled v4-admitted.
  Offline exact-profile adapter implemented with immutable admission records;
  actual producer trust profiles and live archive admission remain pending and
  require complete v4 evidence rather than retroactive relabelling.
  - [x] Preserve the complete contract authority, exact object byte count,
    source representation/era/cohort, and temporal identity in independently
    profiled admission records. Twenty-three focused admission tests pass with
    100% statement and branch coverage; all 380 federation tests and full local
    Test-Goblin pass on pinned uv 0.11.29. Synthetic fixture only. Independently
    configured production profiles and live archive admission remain pending;
    this change does not alter the publication/rights boundary. PR #830 merged
    as `f70b2419864ef2db1cc740006f9e3e4aa04a5675` on 2026-10-06 after all 39
    hosted checks passed, including Codecov; see the append-only merge receipt.

- [x] Write failing tests that map every produced Bronze/Silver/Gold/Platinum
  object to one public destination and reject mutable/unpinned references.
  (`620aaf7`; synthetic caller-owned denominator, 32 cases, all four layers.)
- [x] Confirm the intended failure before implementation. (`620aaf7`;
  test collection failed because the distribution module did not exist.)
- [~] Qualify offline distribution-inventory reconciliation and integrate the
  complete producer denominator. (`620aaf7`; 123 focused federation tests pass,
  new module 100% coverage; full harness and hosted qualification pending.
  Receipt admission and live producer integration remain open.)
  - [x] Strictly load the bounded synthetic-only producer inventory and
    reconcile every Bronze/Silver/Gold/Platinum row against a matching pinned
    v4 contract; reject a partial object or contract denominator. Local E2E
    uses no network or source bytes, and the inventory is explicitly
    non-publishable. Full hosted qualification and real producer integration
    remain open.
  - [x] Integrate actual synthetic Bronze B1 receipt metadata, Silver Parquet,
    Gold node/edge Parquet, and Platinum research-package bytes with the strict
    non-publishable producer inventory loader and v4 distribution reconciler.
    Every emitted object is matched to its immutable destination, path, digest,
    byte count, source/acquisition identity, layer, and Bronze stratum. PR #836
    merged as `08a08a0f8662fefe8cc473272f6cbe2e2252ba68` after all 38 hosted
    checks passed. This is synthetic qualification only; it does not publish,
    admit real data, or close the live producer integration gate.
  - [x] Read every exact reconciled synthetic B1, Silver, Gold, and Platinum
    object through the typed-admission federated reader; prove anonymous
    remote verification, exact offline cache replay, fail-closed cache
    eviction, and remote refetch preserve each object's digest and byte count.
    Keep B2 raw payloads in the separate source-archive denominator. Code
    `eceae48`; 136 affected federation/E2E tests and 31 governed E2E tests pass;
    routine and typing gates pass. Mock transport only; no live admission or
    publication. PR #840 merged as `71d567f6e4a0346702a38000e9381f96438c97c2`
    after all 37 hosted checks passed. See the append-only evidence entry.
  - [x] Add byte-closed synthetic receipt evidence and caller-owned exact
    admission profiles to the same actual-output journey before reader setup.
    The B1, Silver, Gold nodes/edges, and Platinum export are independently
    checked for contract digest, authority, path, object digest/size, source and
    acquisition, layer/cohort, and receipt roles. Changed contract bytes and a
    forged expected path are rejected. The resulting records drive the
    FederatedReader and PBS identity/Atlas path. No source coverage, rights
    clearance, live admission, or publication is established. PR #972 merged
    as `1b5c38ed00d549b2b994a9898b9868b2482f0575` from exact head
    `44c107bb707458d98d73a9f260fbb457b8328d81`; the merge tree matches the
    qualified head. All 28 distinct required contexts and Codecov patch passed.
- [x] Reject duplicate JSON member names consistently at v4 distribution,
  admission, reader, receipt-closure, and consumer boundaries. Three synthetic
  regressions failed before the shared strict parser; 436 affected federation
  and Platinum tests pass. The new parser has 100% statement and branch
  coverage; Ruff, `ty`, and BasedPyright pass. The full Test-Goblin profile
  reports 5,867 passed, 2 existing clean-clone reproducibility failures caused
  by local `uv 0.12.23` versus the CI-pinned `0.11.29`, 1 optional PyIceberg
  skip, and 96.80% coverage. No source bytes, network reads, admission, or
  publication were involved. This does not close distribution integration.
  See `quality/qualifications/federation-v4-strict-json-observation-20261006.json`.
- [ ] Publish source-faithful Parquet, typed tables, graph edge/node tables,
  products, coverage, lineage, and promotions with v4 identities.
- [x] Implement remote-first readers with bounded cache and offline behavior;
  verify local cache eviction cannot change content identity.
  The complete synthetic B1/Silver/Gold/Platinum journey verifies anonymous
  remote reads against exact digest and byte count, exact offline cache replay,
  fail-closed behavior after eviction without a request, and remote refetch with
  unchanged digest and byte count. The existing MBS and PBS synthetic fixtures
  were rerun locally (2 passed; one existing Starlette/httpx deprecation
  warning). The broader journey records 136 affected tests and 31 governed E2E
  tests passing; PR #840 merged at
  `71d567f6e4a0346702a38000e9381f96438c97c2` after all 37 hosted checks passed.
  No new sources, production source bytes, live admission, or publication were
  involved. See the append-only reconciliation evidence entry. Live producer
  admission and publication remain separate open tasks.
- [ ] Phase Verification & Checkpoint: exact remote revisions reproduce all
  products and local storage is demonstrably transient.

### M-108 live Australian product reconciliation (2026-10-05)

- [x] Inventory the anonymous public Australian dataset heads, accepted Bronze
  projection executions, and public MBS Silver v4 candidate. Bind current
  paths, byte counts, digests, source rights receipts, v4 identity/admission,
  data-card, and readback evidence in
  `docs/qualification/australian-m108-derived-products.md` and
  `quality/qualifications/australian-m108-derived-products-20261005.json`.
- [~] Keep M-108 blocked: Bronze parser acceptance is not typed federation-v4
  admission; the July 2025 MBS Silver v4 package remains candidate-only and
  lacks a product-specific card, output-specific v4 rights admission, and
  independent-replica evidence. Do not publish or relabel these products
  until their exact per-product gates are satisfied.
- [ ] Publish newly admitted products through their authorized protected-main
  workflow, anonymously restore and digest-check every object, and persist
  readback receipts before removing hosted temporary bytes.

### M-108 exact-current-head metadata refresh (2026-10-17)

- [x] Reconcile the current anonymous public heads and refresh the M-108
  product inventory. The current MBS archive has three distinct accepted
  August acquisition records for one source content ID; the third acquisition
  was missing from the 2026-10-05 inventory. Record the separate public MBS
  projection whose manifest has no admission state and whose prefix has no
  admission sidecar, without counting it as accepted. See
  `docs/qualification/australian-m108-derived-products-20261017.md` and
  `quality/qualifications/australian-m108-derived-products-20261017.json`.
- [~] Keep M-108 blocked: all four accepted Bronze projections and the public
  MBS Silver candidate still lack a complete output-specific rights and typed
  federation-v4 admission bundle, product-specific card, and independent
  replica evidence. The unadmitted MBS prefix also needs an explicit
  disposition. No publication, visibility change, or admission was performed.

### M-108 MBS archive head refresh after M-107 publication (2026-10-17)

- [x] Reconcile the MBS root manifest at the exact revision produced by hosted
  M-107 run `38993834387`. Anonymous manifest readback at revision
  `52ad5c31cfe101c487a4c7a9c382540642e6110a` (SHA-256
  `9f9dbe6f5ccf3a6119177bbcbb5d942ce9e9db5ea35d2142c7696a3139cab796`)
  contains 40 entries. Full comparison with prior revision
  `3d2d528439bddf6f42e8e700c88917f0960a9f38` finds 12 additions, no changed
  existing rows, and no removals: four monthly schedule XML payloads, two
  November 2025 Basic Service Description payloads, and their six B1 receipt
  sidecars. Per-object metadata and the prior observation are retained in
  `quality/qualifications/australian-m108-derived-products-20261017.json`;
  the hosted anonymous digest and cleanup receipt remains the raw-byte proof.
  No raw or Parquet payload was fetched for this refresh.
- [~] M-108 remains blocked. The additive Bronze archive change does not alter
  the four accepted Bronze product admissions or the MBS Silver candidate;
  output-specific derived rights, typed federation-v4 admission, product
  cards, independent replica evidence, and disposition of the unadmitted MBS
  projection remain unresolved.

### M-108 exact MBS archive refresh after collision-page append (2026-10-17)

- [x] Refresh only the MBS source archive's current metadata references in the
  2026-10-17 M-108 inventory after the final M-107 append. Current revision
  `da83cad9116e2f9a5b927be7b080e9a5e5ea6998` has a 212-object root manifest
  with SHA-256
  `68e6bb97ee43117b860ff1c57e625a00075c734e933d08b3cd67de673432d055`.
  Compared with the preserved prior current observation at `52ad5c31` (40
  objects), this adds 172 manifest entries without changing or removing prior
  entries. The MBS Silver candidate's nine-file tree remains visible in the
  exact current dataset tree metadata. The derivative publication revision,
  candidate manifest digest, output digests, admission, and rights findings
  are unchanged. No raw source or Parquet bytes were read.
- [~] M-108 remains blocked by output-specific derived rights, typed
  federation-v4 admission, product cards, independent replica evidence, and
  disposition of the unadmitted MBS projection.

## Review fixes: runtime reader

- [x] Admit the exact observed `us.aws.cdn.hf.co` delivery host, with signed
  redirect/no-auth/no-cookie canaries, hostile lookalike negatives and the
  same DNS-bound destination policy. `96fcb40` (agent original `4534d21`):
  two intended red regressions; 134 federation tests pass, reader coverage
  100%; 39 source-acquisition safety tests pass. PR #401 delivered at reviewed
  `f0799c4`, merged `2543720`, 38 successful checks and matching trees.
  This does not admit caller-supplied v4 receipts or publish derived data.

- [x] Reject writes through verified result streams without breaking seek/read
  or active-result lifetime. (`2787188`; intended writable-stream regression
  failed first, then 90 focused tests passed with reader 100% branch coverage.)
- [x] Qualify the corrected reader through exact-head hosted checks and retain
  local full-harness limitations separately. (`5d4f382`, PR #375; reviewed
  `96ac770`, all 38 checks passed; exact reviewed/merge trees match.)
- [x] Require installed date/date-time/URI validators and bind generated lock
  receipts to the optional-extra change. (`637ab07`; isolated missing-format
  observation and guard regression failed first; 91 reader/contract tests and
  39 receipt/matrix tests pass, reader 100% branch coverage.)
- [x] Wire exact-profile `AdmissionRecord` identities through the Platinum
  resolver and bounded reader; compare the complete authority, source, temporal
  and object identity before remote or cache I/O. The operator trust document
  now carries the record under configuration version 1.1. Synthetic regression
  rejects a digest-matched substituted path before any request. Focused reader,
  admission, resolver, API, configuration and medallion E2E tests pass (168);
  routine and strict production typing pass. A first combined Darwin
  Test-Goblin attempt encountered a native subprocess segmentation fault in
  the mutation lane; the ordinary product-performance test and isolated
  gremlin lane passed, then a clean full retry passed. It records 97.91% line /
  93.22% branch coverage, 1,885 killed / 364 survived / 5 suspicious / 2
  untested mutations, 324 gremlins passed with one warning, randomized suites
  184/184 each, package, regeneration, Scalene and security lanes passed.
  Linux remains authoritative for mutation. This connects the offline trust
  result to the consumer read boundary; configured production profiles, live
  archive admission and public product publication remain open. PR #832 merged
  as `ed38571146de342db5f243ea435e6b331ad57112` after all 39 hosted checks
  passed; the exact receipt is in the append-only evidence log.

- [x] Reject boolean and nonnumeric timeout budgets at reader construction.
  Failing-first cases reproduced acceptance of `True` and raw `TypeError` for
  string/`None` values; all invalid budgets now fail with the documented
  `ValueError`. The focused reader/admission/contract suites pass (129 tests).
  The pinned full Test-Goblin profile passes with 6,105 tests, one optional
  PyIceberg skip, 97.92% line coverage and 93.27% branch coverage; 1,960/2,338
  mutations killed (367 survived, 4 timed out, 5 suspicious, 2 untested), 353
  Gremlins passed, both randomized 184-test runs passed, and package/API/CLI,
  routine, typing, security, and regeneration checks passed. Darwin mutation is
  advisory; Linux hosted mutation remains authoritative. Synthetic contracts
  only; no source reads, admission, publication, licensing conclusion, or
  source-coverage claim. PR #939 merged as
  `6c785f6fed362d9f45a2de57a7b77aa071938206` from exact head
  `5f7617e6025cd04e720f3d1626736b6f3b9bc4a2` after all 39 hosted checks
  passed, including Codecov patch and Linux/macOS/Windows consumer lanes.
- [x] Reject integer timeout budgets too large for Python's finite-float check.
  The failing-first `10**1000` case reproduced raw `OverflowError`; it now
  follows the same typed `ValueError` path as other invalid budgets. Reader,
  admission and contract tests pass (130). The pinned full profile passes with
  6,106 tests, one optional PyIceberg skip, 97.92% line and 93.27% branch
  coverage; 1,960/2,338 mutations killed (367 survived, 4 timed out, 5
  suspicious, 2 untested), 353 Gremlins passed and both randomized 184-test
  runs passed. Package/API/CLI, typing, security and regeneration pass. Darwin
  mutation is advisory; Linux hosted mutation is authoritative. Synthetic
  contract only; no source bytes, admission, publication, rights conclusion or
  coverage claim. PR #941 merged as `b402191d55ea99bf51562d4a216e0c2053919268`
  from exact head `73e4f54931f01a167204fa399618ff05585ac978` after all 39
  hosted checks passed; the merge tree matches the qualified head.

### Source-metadata review fixes

- [x] Replace placeholder MBS/PBS payload, B1 receipt, retrieval, and Hub
  revision identities with the exact anonymously verified archive identities.
  (`54cea68`; both valid fixtures now describe the observed public revisions.)
- [x] Bind each permission reference and review date to its source-specific
  authorization evidence and reject jointly mutated revision aliases.
  (`54cea68`; 59 focused and 172 affected tests pass; no Hub mutation or new
  rights conclusion.) PR #427 merged as `9ea3b0d` from reviewed head
  `c4ef596` after all 38 hosted checks passed and all review threads resolved.

- [x] Close expired cache spools on open and occupancy inspection. (`9f2b929`;
  automated P2 review; regression failed first, then 91 tests and 100% coverage.)
- [x] Declare format plugins in the CI test group as well as the optional runtime
  extra. (`66561b2`; exact unit-job failure reproduced in isolated test group;
  corrected locked isolated reader/contract/receipt/matrix suite: 130 passed.)

## Phase 5: Collections, estate registry, and recovery (AC-05, AC-07)

### Distribution review correction

- [x] Preserve Bronze stratum in the producer-to-contract identity comparison.
  (`ac31ecb`; P1 regression accepted substituted B1/B2 before correction;
  124 focused federation tests passed, new module 100% branch coverage.)
- [x] Requalify the corrected distribution inventory through exact-head hosted
  checks. PR #377 merged as `eaac37c` after all 38 checks passed on `63afa0b`.
  Prior local full run: 3052 passed, 3 failed, 1 skipped, 96.60%; two
  pinned Python mismatch failures and a product-runner failure whose isolated
  rerun passed. No full exact-corrected-head pass is claimed.

### Discovery and recovery

- [x] Write failing reconciliation tests for collection visibility, item
  membership, notes, revisions, estate-registry identity, and stale entries.
  (`1aefa79`; 24 synthetic offline cases bind a complete caller-owned scoped
  denominator without reading or mutating Hub state.)
- [x] Confirm the intended failure before implementation. (`1aefa79`;
  collection failed with `ModuleNotFoundError` before the pure reconciler was
  added.)
- [x] Implement pure collection/registry reconciliation with exact public
  visibility, immutable dataset revisions, notes, member bijections, registry
  identity, cross-membership, and stale-entry rejection. (`1aefa79`; 215
  affected federation/estate tests pass; Ruff and BasedPyright pass.) This is
  metadata consistency only, not live observation, publication, admission,
  rights authority, or a collection mutation.

### Collection reconciliation review fixes

- [x] Bound caller-supplied collection counts, member counts, and public text
  before denominator reconciliation. (`fc449e5`; one structural hostile-input
  regression, 25 focused tests pass.)
- [x] Apply repository formatting after the exact hosted routine lane identified
  the two unformatted collection files. (`737e93f`; format check and 25 focused
  tests pass; no quality gate or behavior changed.)
- [x] Require every collection member to declare the `dataset` resource type;
  reject model/Space aliases that reuse the same owner/name identity. (`8015cd4`;
  hosted P2 review correction.)
- [x] Bound estate-registry entries and each entry's collection-membership tuple
  before dictionary/set allocation or iteration. (`8015cd4`; hosted P2 review
  correction; 26 focused and 141 affected tests pass.)

- [x] Reobserve live collections and the owner dataset estate on 2026-09-30.
  `Policy AUS` remains private and empty. The public HEOR collection has four
  dataset members, including the MBS/PBS source archives, reimbursement-atlas,
  and a separate New Zealand health-funding dataset. The authenticated owner
  snapshot contains 81 datasets; the public registry contains 52 entries and
  omits 26 current public and 3 current private datasets. See the Australian
  M-112 scope assessment and owner snapshot in the dependent track receipts.
- [x] Refresh the public registry comparison through anonymous stable Hub API
  scans on 2026-10-01. The live public denominator is 76 datasets and eight
  collections. The pinned public catalog has 52 rows (47 public, three gated,
  two private); 26 live public datasets are absent, two catalog access states
  conflict with live visibility/gating, and one public catalog row has no
  matching live public dataset. The unmatched row is preserved for owner review;
  private registry identities are excluded from this observation. Conservative
  placeholder entries for the 26 missing public datasets record unknown family,
  role, source and rights rather than inventing claims; all 26 validate against
  the schema pinned to the observed registry revision. This is preparation only;
  catalog publication and collection mutation remain behind explicit approval.
  See `quality/qualifications/hf-public-registry-gap-20261001.json` and
  `scripts/qualify_hf_public_registry_gap.py`.
- [x] Verify the public metadata reader rejects redirects away from the
  official HTTPS Hub host and responses larger than its 8 MiB bound. Both
  focused regressions pass; BasedPyright, Ruff, and the 61-test affected set
  pass locally. Test-only PR #679 passed all 37 protected checks and merged at
  `9647d2878e0c5ebe101bb01437209e40eaea3080`; the publisher workflow's
  publish step was skipped. No Hub state or source payload was changed.
- [x] Reconcile the post-merge evidence for PR #678 and PR #679 on main.
  PR #680 merged as `3044a3340179820055e279ab58eaa5e87507ee91` after all 37
  hosted checks passed; its exact-head changes record the two prior merge
  receipts and their passing check totals. The PR was documentation/evidence
  only; no Hub state or source payload changed. This entry records PR #680's
  own exact merge receipt.
- [x] Apply the approved public registry and HEOR source-note changes, then
  verify the complete public state anonymously. The maintainer approved the
  exact 146-character Policy AUS description and full caveat in all five
  member notes on 2026-10-01. After PR #691 merged as
  `aaa181938f8cf7b4f9ef790fc93ac86b41988e1a`, hosted run
  `36816927372` applied the registry and collection metadata and produced a
  receipt. PR #692 (`1b64c9bb`) corrected the independent scanner to dereference
  each public collection's canonical detail endpoint because the owner-list
  endpoint embedded a stale four-member preview. A stable anonymous double
  scan from the merged scanner confirms 76 public datasets, 9 public
  collections, all five approved Policy AUS members/notes, and all six HEOR
  members with the five approved notes and the pre-existing NZ member
  preserved. The owner-list and detail-endpoint collection digests differ
  because they represent the stale preview and complete current detail
  respectively; the direct detail readback matches the approved target.
  Durable hosted receipt and full anonymous readback are preserved in
  `quality/qualifications/hf-public-metadata-publication-receipt-20261001.json`
  and `quality/qualifications/hf-public-metadata-readback-20261001.json`.
  No source payload bytes or values were read; no rights conclusion, v4
  admission, or federation acceptance is claimed. See the append-only evidence
  record for exact digests and run/commit identities.
- [x] Reconcile candidate raw paths against pinned public manifests using
  metadata only. All 1,736 Australian MBS/PBS candidate paths map to pinned
  manifests or the exact August 2026 MBS hosted receipt; 1,735 appear in root
  manifests, and available tree SHA-256 values match manifest digests. The MBS
  root manifest omitted the August XML at the time of this inventory;
  exact-revision metadata readback confirms
  its two unreviewed B1 records are distinct append-only events for the same
  raw source identity. Their different source-Parquet digests still require
  separate lineage. The approved candidate denominator does not resolve
  per-object source rights, root-manifest completeness, or v4 admission. See the dependent
  track's `quality/qualifications/australian-m112-manifest-join-audit-20260930.json`.
- [x] Reconcile the later exact-main MBS root-manifest append against the
  anonymous public state. After PR #1067 merged at
  `320112b821e861c19f4065f550273119ac219831` with all 39 required checks
  passing, hosted run `38939963456` appended the existing content-addressed
  August XML identity and anonymously verified public revision
  `3d2d528439bddf6f42e8e700c88917f0960a9f38`. The pinned parent manifest had
  27 rows; the new manifest has 28, with only the approved path added, no rows
  removed or existing rows changed, and the historical alias retained. Both
  paths bind SHA-256
  `c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565` and
  8,293,331 bytes. This is a metadata-only reconciliation: no source payload
  bytes were read or uploaded, and rights, admission, and the approved
  denominator did not change. Durable receipt:
  https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-6221047682 .
  It closes the root-manifest path omission only; M-112 rights, lineage,
  admission, full-denominator, and consumer-canary gates remain open.
- [x] Join the MBS/PBS source and utilisation receipt metadata to pinned raw
  paths and existing authorization scopes. All 20 utilisation sidecars match
  path/source/category/digest/size and remain within recorded authorization
  bounds; all eight MBS source candidates map to exact receipt/authorization/
  hosted-publication identities. The PBS archive receipt agrees with its
  manifest; Decision 0009 and issue #340 establish maintainer authorization and
  historic anonymous verification for the same digest. Upstream terms remain
  unresolved in the older source-rights ledger, and no v4 admission follows.
  See `quality/qualifications/australian-m112-receipt-sidecar-join-audit-20260930.json`
  and `quality/qualifications/australian-m112-source-archive-receipt-join-audit-20260930.json`.
- [ ] Configure an approved independent public recovery target, checksum
  inventory, RPO/RTO, and clean-room restore rehearsal; do not mislabel an HF
  duplicate as independent.
- [ ] Phase Verification & Checkpoint: collections are accurate discovery views
  and both primary and independent restore evidence are observable.

## Phase 6: Integrated qualification (AC-09)

- [x] Separate successful upload from verified public availability. The
  publication receipt records `uploaded` after gated transport and permits
  `public` only after anonymous readback confirms every planned file's exact
  path, SHA-256 digest, and byte count. Preparation and upload reject unbound
  files; Hugging Face reads are credential-free, host-pinned, bounded, and
  accept signed query strings only on allow-listed delivery redirects. The
  archive workflow retains the post-upload receipt separately. The focused
  publication/archive suite passes (117), routine and static checks pass, and
  PR #1030 merged with all 29 required checks passing and 100% Codecov diff
  coverage. The final full Test-Goblin run completed successfully on macOS with
  97.93% line and 93.36% branch coverage. Two earlier standalone browser tests
  had intermittent `browser.close()` timeouts; the final full run and hosted
  cross-platform E2E lane passed. No live upload or public data change was
  performed; external publication remains subject to its explicit maintainer
  gate.

- [x] Prepare and execute append-only donor-history preservation as a
  separate public archive transaction: exact heads, CAS, unchanged previous
  sibling objects, baseline/delta reconstruction, clean restoration, and
  durable anonymous verification before cleanup. GitHub Actions run
  [34005721959](https://github.com/edithatogo/global-medicines-atlas/actions/runs/34005721959)
  succeeded for the exact approved graph and scraper heads. The durable issue
  [#340 receipt](https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-5556271994)
  records public revision `97038008d17a48f620302f04fe6a3156fb8d5d57`, preserves
  the 26-object baseline, verifies both appended histories, and records clean
  restoration of both exact heads. Receipt SHA-256:
  `835e2532ae88bb38b13a78f54f00f526906c5eaf7071411ec3d92b903b754df0`.
  This reconciles the already completed, specifically authorized transaction;
  it does not authorize another publication, confer source admission or
  rights clearance, or change the separate publication gate for future data.

- [ ] Run focused tests, schema validation, Ruff, `ty`, BasedPyright, security,
  provenance, rights, deterministic regeneration, and full Test-Goblin where
  supported.
- [ ] Run Conductor review, repair findings, open scoped pull requests, wait for
  hosted checks and publication workflows, merge, and reconcile exact receipts.

## Raw B2 field-lineage contract gap (2026-10-18)

- [x] Add an immutable federation v4.1 schema that records field-lineage
  applicability explicitly. Raw Bronze B2 objects may carry a null v2
  field-lineage receipt only with `not_applicable_raw_b2`; all other layers and
  representations still require a receipt. Keep the v4.0 schema and digest
  unchanged. Bind the new pin through semantic validation, typed admission,
  receipt closure, the anonymous reader, consumer binding, distribution
  reconciliation, and the MBS profile.
- [ ] M-112 remains unaccepted. This change removes a contract-level blocker
  for raw B2 identity only; it does not supply source rights, object receipts,
  v1/v3 receipts, full-denominator admission, independent recovery, or consumer
  canaries. The approved 1,759-path denominator and all source-specific gates
  remain in force.
- [x] Complete Conductor review and exact-head hosted checks before merging.
  PR #1142 merged as `fa2091d`; all 39 required check rows passed on
  `47042af`, and the merge tree matches the tested head tree
  (`c4832b6fe8cb07724c9c17e26da874303e934992`).

## M-112 August alias anonymous digest readback (2026-10-18)

- [x] Stream the approved August MBS alias from its exact immutable public
  revision without credentials or local retention. The 8,293,331-byte
  response returned HTTP 200 and SHA-256
  `c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565`,
  matching the existing source receipt and content-addressed object. No source
  values were inspected.
- [x] Bind the path-specific readback in
  `quality/qualifications/australian-m112-august-alias-anonymous-readback-20261018.json`
  and the reproducible 1,759-path crosswalk. Anonymous digest readbacks rise
  from 28 to 29; the denominator remains 1,759, both August paths remain
  deferred, complete raw B1/B2 lineage remains one path, and v4 admissions and
  consumer canaries were zero at this 2026-10-18 checkpoint. The current
  2026-10-21 readback below records seven admissions and seven canaries. The
  alias's B1/B2 lifecycle gap is unchanged.
- [x] Verify the focused crosswalk tests (6 passed), broader M-112/rights
  tests (78 passed), routine profile, Ruff, `ty`, and BasedPyright. The full
  Test-Goblin run's pytest stage passed (6,682 passed, 3 skipped; 96.89%
  coverage); Gremlins recorded one unrelated PERF-QUERY failure at 266.068 ms
  against 250 ms in `test_direct_runner_cli_from_repository_root`. Its isolated
  serialized rerun passed (1 test, 7.52 s). Preserve the full-profile result
  as failed; do not infer a full pass from the isolated timing rerun.
- [x] Conductor review found no findings: the alias readback is pinned to the
  exact dataset revision/path, the digest and byte count bind to the approved
  source receipt, the report preserves deferral, and the negative revision
  test verifies fail-closed behavior.
- [~] Open a scoped PR and reconcile hosted exact-head checks before merging
  this crosswalk update. M-112 remains unaccepted until per-object lineage,
  v4 admission, recovery, and consumer-canary gates pass.

## M-112 August alias shared raw B1/B2 identity (2026-10-18)

- [x] Reconcile the alias path against the canonical August raw object using the
  exact pinned Git blob identity, byte count, SHA-256, source receipt, landed to
  accepted B1 lifecycle, immutable B2 reference, and the alias's own anonymous
  digest receipt. Keep historical producer-archive records intact; their
  separate projection lineage remains unqualified.
- [x] Refresh the path ledger: both August raw paths now bind to one qualified
  raw B1/B2 payload identity. The approved denominator remains 1,759; all
  1,759 paths remain deferred; v4 admissions and consumer canaries were zero
  at this 2026-10-18 checkpoint. See the current 2026-10-21 readback below.
- [x] Verify focused tests (7 passed), broader M-112/rights tests (79 passed),
  routine Test-Goblin, Ruff, `ty`, BasedPyright, context/ecosystem checks, and
  `git diff --check`. The previously recorded full profile remains failed for
  its isolated performance-threshold finding; it was not repeated.
- [~] Reconcile hosted exact-head checks on PR #1144 before merging. This
  identity join does not resolve projection lineage or admit either path.

## M-112 frozen inventory B1/B2 lineage completion (2026-10-19)

- [x] Reconcile all 1,759 frozen object identities against exact B1/B2 and
  projection evidence without changing the denominator or adding sources:
  1,736 raw paths and 23 projection paths now have complete recorded lineage.
  The 12 reimbursement-atlas producer projections were checked against pinned
  dataset and producer revisions; the remaining PBS Parquet projection was
  bound to its existing admitted raw archive and receipt.
- [x] Record the existing July 2026 CMS HCPCS source-version readback as
  reference-only B1/B2 evidence. Its 2,499,217-byte digest matches the pinned
  source version; payload bytes were not retained and payload values were not
  inspected. Rights remain unknown and reviewer state remains unreviewed.
- [x] Preserve the 1,759-object deferral, zero v4 admissions, zero consumer
  canaries, and existing rights conclusions at this 2026-10-19 checkpoint.
  The current 2026-10-21 readback below records seven admissions and seven
  canaries. Exact raw digest/path joins rise to 118, with one same-content alias
  counted separately (119 path identities).
- [x] Verify 5 focused tests, the routine Test-Goblin profile, Ruff, `ty`, and
  BasedPyright. Full inventory report and the appended source receipt bindings
  pass local readback checks.
- [~] Complete exact-head hosted checks, merge the scoped PR, and verify the
  merged qualification on `main`. This lineage checkpoint does not complete
  rights/release evidence, v4 admission, graph screening/calibration, recovery,
  or consumer canaries; M-112 remains unaccepted until those gates pass.

## M-112 July group CSV consumer canary (2026-10-20)

- [x] Attempt the bounded exact-main consumer workflow for the already-admitted
  `raw/mbs/utilisation/group/mbs-group-2016-july.csv` contract on main commit
  `537ec7aee25f2677a30d5f72bfb473445ba6fd43` (run
  [39371086605](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39371086605)).
  The workflow stopped before the reader because `--check` rebuilt mutable
  candidate-role URLs and rejected the exact immutable contract digest.
- [x] Correct the check path to validate the persisted canonical contract,
  bind its exact target identity, and compare receipt-role digests against the
  qualified local evidence. Keep the already-admitted contract bytes and digest
  unchanged. Validate the precise Q1 replay idempotency false positive without
  weakening full-history secret scanning.
- [x] Run affected M-112 tests (44 passed), Gitleaks allowlist tests (4 passed),
  local full-history Gitleaks scan (0 findings across 7 PR commits), Ruff,
  formatting, exact contract validation, and local receipt closure (12 roles,
  10 unique verified receipts; original contract digest unchanged).
- [x] Merge the scoped correction as PR #1232 at `4255ae0d187413d24a9055f33bd13f08b73e396e`
  after all 39 exact-head checks passed, then rerun the group CSV canary on that
  exact `main` head. Run [39375423835](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39375423835)
  passed through the production `FederatedReader`; its remote and streamed
  digests matched, the cache was empty after close, and the original contract
  digest remained `d1924c8c21a52baff437dcf0ec55e7abffe599bf091bdaea082bc020c203aab7`.
- [x] Qualify the separate Q1 March demographics contract on the same exact
  main head. Its 12 roles and 10 unique receipts passed local closure; hosted
  run [39375704078](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39375704078)
  admitted and canaried contract digest
  `3f4794f92a33b9e77950b2c864c7f4ae8a331a43b80297a15e73f1967814f6ce` with a
  remote digest and consumer-stream match and zero retained cache bytes.
- [x] Record the two exact metadata-only workflow receipts and refresh the
  role qualification: 5 unique v4 admissions and 5 unique consumer canaries
  across the approved 1,759 paths. The denominator is unchanged; 1,754 paths
  remain unadmitted. The wider M-112 gate remains open for source-specific
  schema, semantic, publication, recovery and consumer requirements.
- [x] Verify the refreshed role qualification in check mode, then run the
  affected admission/role tests (27 passed), Ruff checks, formatting, and
  `git diff --check`.
- [x] Correct the dependent current-rights reconciliation for the fifth exact
  v4 admission/canary and the 1,754 remaining paths. The affected suite passed
  37 tests; two copied-checkout tests hit the 30-second filesystem timeout
  during the suite and each passed in isolated reruns (one with a 90-second
  timeout). Ruff, format, qualification check, and `git diff --check` passed;
  exact-head hosted checks are pending on PR #1235.

## M-112 Q2 May replay and v4 admission (2026-10-20)

- [x] Run the exact-object hosted v3 replay for the Q2 May demographics CSV.
  Run [39414292406](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39414292406)
  on `295160bab1e694f9a01a70e0befc5f7e5bf660de` verified the pinned digest,
  read no source rows, and removed temporary payload bytes. Its plan and
  execution receipt are recorded under `quality/qualifications/`.
- [x] Reconcile the replay receipt against the frozen identity and regenerate
  the v4 role qualification. The candidate role set now has six v3 replay/cache
  receipts; the admitted count remains five and the approved 1,759-path
  denominator is unchanged.
- [x] Bind the complete exact Q2 May role closure into a live v4.1 contract
  and verify admission using the pinned trusted profile. Contract digest
  `cd7ccdce266d1d42fa658abe4b097c207627d80943b01c198f7d844c16241152`
  closes 12 roles with 10 verified receipts; source-native schema stays
  explicitly unqualified. The admission is now backed by an exact hosted
  consumer canary; the native source layout remains unqualified.
- [x] Run the bounded hosted consumer canary against exact `main` commit
  `516d56e8fd5274b37d65a2192257a41e7cb8cb94`. Workflow run
  [39419974066](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39419974066)
  passed: the FederatedReader streamed and remotely verified the exact digest,
  retained no source rows or bytes, and held zero cache bytes after close.
- [x] Refresh the Q2 admission receipt, role qualification, and current-rights
  reconciliation from the hosted canary readback. Current M-112 totals are six
  unique v4 admissions and six canaries out of the unchanged 1,759-path
  denominator; 1,753 remain unadmitted.
- [x] Bind the Q2 admission/canary receipt digest, exact hosted run and main
  commit, contract/object identity, consumer digest results, and no-retention
  boundaries into the current-rights reconciliation. A fail-closed regression
  now rejects a missing or malformed Q2 consumer-canary record.
- [x] Refresh the rights reconciliation on the latest main after PR #1236.
  The Q2 receipt remains explicitly bound; six admissions and six canaries are
  reconciled, with 1,753 paths deferred. The broader rights report records
  authorized payload screening separately from the Q2 canary, which interpreted
  no source rows and retained no payload or reader cache.
- [x] Refresh the dependent M-112 rights release preflight as snapshot #13,
  binding the current 6/6 admission/canary totals and exact Q2 receipt while
  preserving snapshot #12 and its 6/5 state as historical evidence.
- [x] Reconcile the consumer role against the six exact admitted-object
  canary receipts. The role qualification now reports six canaries for six
  current admissions instead of a stale zero; release preflight snapshot #14
  binds the refreshed qualification and preserves snapshot #13. The bounded
  checks used the FederatedReader and verified both digests plus zero cache
  bytes after close.
- [x] Verify a metadata-only v3 replay for the exact Q3 July HR workbook.
  Hosted run [39431880718](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39431880718)
  matched the 7,316,301-byte pinned identity, read no source values, and
  removed temporary source bytes. The replay is candidate evidence only;
  admission and canary counts remain six pending a complete v4 contract.
- [x] Resolve the exact-history scanner finding for that replay. The redacted
  report showed the planner-derived `idempotency_key` in its plan and receipt.
  A first allowlist entry had a two-character mismatch; the corrected value is
  now read directly from the replay plan in the regression test, and only that
  exact field/value is covered.
- [x] Add Q2 May's exact frozen identity to the bounded v4 contract builder
  and hosted consumer-canary input. The two missing-target regressions failed
  first; the affected admission, role, and rights reconciliation tests then
  passed (40 passed), with Ruff, formatting, actionlint, ty, role-qualification
  check, and `git diff --check` passing.

## M-112 current qualification readback (2026-10-21)

The latest bound preflight records 1,759/1,759 frozen objects with resolved
rights, seven exact v4 admissions and seven admitted-object canaries, and 1,752
deferred objects. The previous six-admission/six-canary checkpoint in this plan
is historical and superseded by preflight snapshot 20261021-7. This is not full
federation acceptance: source-native layout, complete per-object roles, recovery,
and product consumer qualification remain separate gates. No public dataset
mutation or external publication was performed. Current evidence:
`quality/qualifications/australian-m112-rights-release-preflight-20261021-7.json`,
`quality/qualifications/australian-m112-current-rights-reconciliation-20261021.json`,
`quality/qualifications/australian-m112-v4-contract-role-evidence-qualification-20261020.json` (the role report bound by this preflight),
the later candidate-role refresh
`quality/qualifications/australian-m112-v4-contract-role-evidence-qualification-20261021.json`,
and the reviewed MBS lineage overlay. The later role refresh preserves the same
7/7 counts and 1,752 deferrals without changing the preflight admission or
canary evidence. That overlay closes the July 2025 XML and
legacy P7 B1/B2 joins and reports 22 complete raw lineages; it does not change
the 1,759 denominator or imply broader federation acceptance.
