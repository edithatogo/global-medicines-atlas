# Implementation Plan

## Phase 1: Preserve and Inventory Upstream ([GitHub #2](https://github.com/edithatogo/global-medicines-atlas/issues/2))

- [x] Task: Capture immutable upstream history and snapshot
  - [x] Clone `edithatogo/nzmedicines` without modifying the active worktree
  - [x] Create and verify a complete Git bundle
  - [x] Import an immutable snapshot under `vendor/nzmedicines/`
  - [x] Record cryptographic digests and source provenance
- [x] Task: Reconcile upstream and local assets
  - [x] Write inventory tests that require a disposition for every upstream file
  - [x] Inventory local NZULM/NZMT/FHIR assets without hydrating unrelated data
  - [x] Classify each upstream artifact as adopted, adapted, superseded, fixture, or excluded
  - [x] Record conflicts and local-only enhancements
- [x] Task: Phase Verification & Checkpoint

## Phase 2: Build the NZ Adapter and Fixture Boundary ([GitHub #3](https://github.com/edithatogo/global-medicines-atlas/issues/3))

- [x] Task: Define canonical NZ source contracts
  - [x] Write schema and provenance tests
  - [x] Define NZMT hierarchy, identifiers, authority, status, and temporal contracts
  - [x] Define FHIR projection contracts and extension validation
- [x] Task: Create adapter implementation
  - [x] Add unit and property tests for the initial adapter boundary
  - [x] Implement source-native bundle parsing
  - [x] Implement canonical medicine/product/assertion output
  - [x] Implement deterministic index generation
- [x] Task: Curate fixtures
  - [x] Preserve upstream paracetamol, ibuprofen, and warfarin examples with provenance
  - [x] Add malformed, conflicting, and negative-control fixtures
  - [x] Verify canonical projections do not embed source payloads or infer status
- [x] Task: Phase Verification & Checkpoint

## Phase 3: Provide RxNorm/RxNav-Compatible Terminology Resolution ([GitHub #4](https://github.com/edithatogo/global-medicines-atlas/issues/4))

- [x] Task: Define resolver and adapter contracts
  - [x] Write availability, timeout, and fallback tests
  - [x] Define local-only configuration and licensing controls
  - [x] Define read-only query and provenance records
- [x] Task: Implement tiered terminology resolution
  - [x] Add a reproducible local fixture lifecycle
  - [x] Implement Python 3.14 resolver with deterministic fallback
  - [x] Add public RxNav API and optional RxNav-compatible local-service adapter
  - [x] Record Mojo promotion as unjustified for the current lookup boundary
  - [x] Add offline fixtures and integration tests
- [x] Task: Phase Verification & Checkpoint

## Phase 4: Harness, CI/CD, and Traceability ([GitHub #5](https://github.com/edithatogo/global-medicines-atlas/issues/5))

- [ ] Task: Integrate quality harness
  - [ ] Add unit, integration, end-to-end, smoke, property, and mutation lanes
  - [x] Add the maintainer-owned test-goblin dependency and CI profile
  - [x] Document the maintainer-owned Test-Goblin compatibility profile
  - [ ] Add `ty`, BasedPyright, Scalene, and >90% Codecov gates
  - [ ] Add deterministic generation and source-boundary checks
- [ ] Task: Add GitHub automation
  - [x] Add Renovate configuration
  - [ ] Add SHA-pinned CI, CodeQL, actionlint, zizmor, SBOM, and attestations
  - [x] Add structured issue forms and labels
  - [ ] Add dry-run track/issue synchronization
- [x] Task: Create issue hierarchy
  - [x] Prepare parent and phase issue drafts for later publication
  - [x] Create parent migration issue
  - [x] Create linked phase/task subissues
  - [x] Backfill issue URLs into track metadata and plans
- [ ] Task: Phase Verification & Checkpoint

## Phase 5: Compatibility Mirror and Handoff ([GitHub #6](https://github.com/edithatogo/global-medicines-atlas/issues/6))

- [ ] Task: Prepare migration notices
  - [x] Add canonical-repository notice locally
  - [ ] Draft upstream compatibility-mirror notice
  - [ ] Document history restoration from the Git bundle
- [ ] Task: Verify consolidation
  - [ ] Verify every upstream artifact has a disposition and source digest
  - [ ] Verify no local work was overwritten
  - [ ] Verify clean-clone and bundle restoration procedures
  - [ ] Record remaining external archive or publication gates
- [ ] Task: Phase Verification & Checkpoint
