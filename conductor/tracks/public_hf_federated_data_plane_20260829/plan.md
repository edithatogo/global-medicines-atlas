# Plan: public Hugging Face federated data plane

## Phase 1: Freeze and remediate the current estate (AC-01, AC-02, AC-08)

- [ ] Write failing tests for complete estate enumeration, exact revision and
  manifest allowlists, public/non-gated state, and anonymous restoration.
- [ ] Confirm the intended failure before implementation.
- [ ] Generate a public-safe estate registry snapshot without credentials or
  restricted contents.
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

## Phase 3: Publish the donor and continuing raw corpus (AC-03, AC-06)

## Review Fixes: v4 federation foundation

- [x] Reject B0 projections, blank or padded mandatory text, null independent
  replica RPO/RTO, and case/whitespace aliases of the same recovery domain.
  (`7ac4ada`; nine intended regression failures before correction)
- [~] Requalify the corrected contract through focused tests and exact-head
  hosted checks; retain partial local full-suite evidence separately.

## Phase 3 continued: donor and continuing raw corpus

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

- [ ] Write failing tests that map every produced Bronze/Silver/Gold/Platinum
  object to one public destination and reject mutable/unpinned references.
- [ ] Confirm the intended failure before implementation.
- [ ] Publish source-faithful Parquet, typed tables, graph edge/node tables,
  products, coverage, lineage, and promotions with v4 identities.
- [ ] Implement remote-first readers with bounded cache and offline behavior;
  verify local cache eviction cannot change content identity.
- [ ] Phase Verification & Checkpoint: exact remote revisions reproduce all
  products and local storage is demonstrably transient.

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
