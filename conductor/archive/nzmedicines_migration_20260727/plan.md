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

- [x] Task: Integrate quality harness
  - [x] Add unit, integration, end-to-end, smoke, property, and mutation lanes
  - [x] Add the maintainer-owned test-goblin dependency and CI profile
  - [x] Document the maintainer-owned Test-Goblin compatibility profile
  - [x] Add `ty`, BasedPyright, Scalene, and >90% Codecov gates
  - [x] Add deterministic generation and source-boundary checks
- [x] Task: Add GitHub automation
  - [x] Add Renovate configuration
  - [x] Add SHA-pinned CI, CodeQL, actionlint, zizmor, SBOM, and attestations
    - [x] SHA-pin active GitHub Actions
    - [x] Add CodeQL, actionlint, zizmor, dependency audit, and CycloneDX SBOM lanes
    - [x] Add release-only provenance attestations
  - [x] Add structured issue forms and labels
  - [x] Add dry-run track/issue synchronization
- [x] Task: Create issue hierarchy
  - [x] Prepare parent and phase issue drafts for later publication
  - [x] Create parent migration issue
  - [x] Create linked phase/task subissues
  - [x] Backfill issue URLs into track metadata and plans
- [x] Task: Phase Verification & Checkpoint
  - [x] Add root agent contract and machine-readable context manifest
  - [x] Add context-drift tests and CI receipt
  - [x] Add sole-maintainer pull-request and ownership policy
  - [x] Add validated GitHub/Hugging Face authority and reuse registry

## Phase 5: Compatibility Mirror and Handoff ([GitHub #6](https://github.com/edithatogo/global-medicines-atlas/issues/6))

- [x] Task: Prepare migration notices
  - [x] Add canonical-repository notice locally
  - [x] Draft upstream compatibility-mirror notice
  - [x] Document history restoration from the Git bundle
- [x] Task: Verify consolidation
  - [x] Verify every upstream artifact has a disposition and source digest
  - [x] Verify the isolated import boundary and bounded local preservation claims
  - [x] Verify clean-clone and bundle restoration procedures
  - [x] Record remaining external archive or publication gates
- [x] Task: Phase Verification & Checkpoint

## Rights follow-up #51 — 2 November 2026

The archived migration's original acceptance remains complete. The maintainer
explicitly selected this rights/publication follow-up; Australian federation
and Stable qualification remain deferred.

- [x] Verify official terms source by source without publishing private evidence.
- [x] Reconcile the 162-asset historical inventory and current file availability.
- [x] Verify the unchanged 15-file software cohort and anonymously verify the five existing Pharmac/RxNorm public objects; reuse exact snapshots without duplicate uploads.
- [x] Publish the source-specific written decisions and updated public metadata manifest through a protected technical PR.
- [ ] Unrestricted publication of licensed NZF content, full SNOMED/AMT semantics or proprietary RxNorm source-vocabulary content: confirmed source restrictions remain; Medsafe commercial-use conditions also remain attached to its data.

See [the current review](../../../docs/migrations/nz-rights-review-20261102.md)
and its hash-bound receipt. Missing local 2023 payloads are an availability
finding, not a finding that NZULM or Pharmac prohibit redistribution.
