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

- [ ] Write failing JSON Schema and semantic tests for all mandatory v4
  authority, location, digest, visibility, verification, rights, collection,
  replica, schema-era, comparison, lineage, and cache fields.
- [ ] Confirm the intended failure before implementation.
- [ ] Commit immutable v4 schema, valid/invalid fixtures, documentation, and
  cross-repository conformance canaries.
- [ ] Approve stable names and create public MBS source, PBS source, and
  Australian benefits medallion datasets from GitHub Actions.
- [ ] Require source-specific data cards, Croissant, citations, provenance,
  coverage, rights/permission, withdrawal/correction, and version histories.
- [ ] Phase Verification & Checkpoint: datasets exist publicly but contain only
  exact approved manifests; empty repositories are not claimed as data.

## Phase 3: Publish the donor and continuing raw corpus (AC-03, AC-06)

- [ ] Write failing hosted-workflow tests for exact donor digests, duplicate or
  missing files, path traversal, private/gated output, local upload attempts,
  partial uploads, anonymous digest mismatch, and premature cleanup.
- [ ] Confirm the intended failure before implementation.
- [ ] Publish the July 2025 MBS XML and July 2024 P7 workbook as separate exact
  B2 objects with B1 receipts and legacy/current labels.
- [ ] Publish continuing MBS/PBS exact source manifests only after acquisition,
  admission, authorization, and source-version gates pass.
- [ ] Retain archive/container bytes as well as member manifests; never replace
  an XML/ZIP/XLSX raw object with Parquet.
- [ ] Remove temporary local source bytes only after token-free clean-room
  verification succeeds and its cleanup receipt is durable.
- [ ] Phase Verification & Checkpoint: every approved non-empty raw object is
  public and no durable workstation-only copy is required.

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
