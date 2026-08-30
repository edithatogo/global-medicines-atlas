# Plan: public Hugging Face federated data plane

## Phase 1: Freeze and remediate the current estate (AC-01, AC-02, AC-08)

- [~] Write failing tests for complete estate enumeration, exact revision and
  manifest allowlists, public/non-gated state, and anonymous restoration.
- [ ] Confirm the intended failure before implementation.
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
- [~] Commit immutable v4 schema, valid/invalid fixtures, documentation, and
  cross-repository conformance canaries.
  Schema, offline semantic validation and portable canary fixtures implemented
  in `6055379`; 54 focused tests pass with 100% semantic-module branch coverage.
  Downstream adoption and live receipt emission are not yet qualified.
  This independent Phase 2 contract slice does not close the remaining Phase 1
  complete-estate inventory tasks.
- [x] Approve the stable `edithatogo/australian-mbs-source-archive` name and
  implement its create-private, publish, and anonymous-verification transaction
  entirely in GitHub Actions. The exact revision is public, non-gated, and
  anonymously digest verified. (`4d1dae4`, run `33244323861`)
- [ ] Create the continuing PBS source and Australian benefits medallion
  datasets from GitHub Actions once their non-empty manifests exist.
- [ ] Require source-specific data cards, Croissant, citations, provenance,
  coverage, rights/permission, withdrawal/correction, and version histories.
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

- [x] Write failing tests that map every produced Bronze/Silver/Gold/Platinum
  object to one public destination and reject mutable/unpinned references.
  (`620aaf7`; synthetic caller-owned denominator, 32 cases, all four layers.)
- [x] Confirm the intended failure before implementation. (`620aaf7`;
  test collection failed because the distribution module did not exist.)
- [~] Qualify offline distribution-inventory reconciliation and integrate the
  complete producer denominator. (`620aaf7`; 123 focused federation tests pass,
  new module 100% coverage; full harness and hosted qualification pending.
  Receipt admission and live producer integration remain open.)
- [ ] Publish source-faithful Parquet, typed tables, graph edge/node tables,
  products, coverage, lineage, and promotions with v4 identities.
- [~] Implement remote-first readers with bounded cache and offline behavior;
  verify local cache eviction cannot change content identity.
  Runtime transport/cache slice in progress; only independently admitted v4
  documents may be consumed. No live source acquisition or publication planned.
  `2ed6d8d` (rebased from `78abde9`): 89 focused tests pass, reader 100% branch coverage; optional
  installed-consumer import passes. Exact-head hosted qualification passed in
  PR #375 (`5d4f382`, reviewed `96ac770`, all 38 checks passed).
  Live admission/receipt integration remains pending.
- [ ] Phase Verification & Checkpoint: exact remote revisions reproduce all
  products and local storage is demonstrably transient.

## Review fixes: runtime reader

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

- [x] Close expired cache spools on open and occupancy inspection. (`9f2b929`;
  automated P2 review; regression failed first, then 91 tests and 100% coverage.)
- [x] Declare format plugins in the CI test group as well as the optional runtime
  extra. (`66561b2`; exact unit-job failure reproduced in isolated test group;
  corrected locked isolated reader/contract/receipt/matrix suite: 130 passed.)

## Phase 5: Collections, estate registry, and recovery (AC-05, AC-07)

- [ ] Write failing reconciliation tests for collection visibility, item
  membership, notes, revisions, estate-registry identity, and stale entries.
- [ ] Confirm the intended failure before implementation.
- [ ] Populate and make `Policy AUS` public, update HEOR membership/notes, and
  refresh the public dataset-estate registry.
- [ ] Configure an approved independent public recovery target, checksum
  inventory, RPO/RTO, and clean-room restore rehearsal; do not mislabel an HF
  duplicate as independent.
- [ ] Phase Verification & Checkpoint: collections are accurate discovery views
  and both primary and independent restore evidence are observable.

## Phase 6: Integrated qualification (AC-09)

- [ ] Run focused tests, schema validation, Ruff, `ty`, BasedPyright, security,
  provenance, rights, deterministic regeneration, and full Test-Goblin where
  supported.
- [ ] Run Conductor review, repair findings, open scoped pull requests, wait for
  hosted checks and publication workflows, merge, and reconcile exact receipts.
