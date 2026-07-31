# Implementation Plan

Execution policy: [autonomous, decision-gated](../../autonomy.md).

## Phase 1: Qualification contract

- [~] Task: Build requirement, maturity and release-evidence matrices ([#41](https://github.com/edithatogo/global-medicines-atlas/issues/41))
  - Initial fail-closed projection: `quality/qualifications/stable-v1-contract.json`
    validated by `schemas/stable-v1-qualification-v1.json`; implementation and
    durable-evidence qualification remain open.
- [x] Task: Define clean-room reproduction and migration rehearsals ([#41](https://github.com/edithatogo/global-medicines-atlas/issues/41))
  - Four receipt-producing rehearsal definitions distinguish release clean-room
    reproduction, structural canonical migration, rollback, and governed
    recovery without implementing the runtime schema migration.
- [x] Task: Define support, limitation and residual-risk gates ([#41](https://github.com/edithatogo/global-medicines-atlas/issues/41))
  - The support-readiness register records candidate platforms, the optional
    semantic boundary, user-facing limitations, ownership, and fail-closed
    blocking risks.
- [x] Task: Define jurisdiction/source maturity and documentation-readiness matrices ([#41](https://github.com/edithatogo/global-medicines-atlas/issues/41))
  - A deterministic projection covers every canonical catalog `source_id` and
    jurisdiction while conservatively capping catalog-derived maturity at M2.
- [~] Task: Contract canonical medicine schema v2 and migration compatibility for substances, products, packages, indications, prices and restrictions ([#41](https://github.com/edithatogo/global-medicines-atlas/issues/41))
  - Structural contract added as `schemas/canonical-medicine-v2.json`; runtime
    migration and rollback rehearsal remain open and are explicitly distinct
    from the temporal assertion `v1_to_v2` migration.
- [~] Task: Contract comparison-validity semantics for granularity, indication, population, mapping, normalization, material mismatches and inappropriate comparisons ([#41](https://github.com/edithatogo/global-medicines-atlas/issues/41))
  - Vocabulary added as `schemas/comparison-validity-v1.json`; runtime adoption
    and end-to-end qualification remain open.
- [~] Task: Contract bounded concept discovery, catalog APIs, CLI commands, accessible autocomplete and match explanations ([#41](https://github.com/edithatogo/global-medicines-atlas/issues/41))
  - Deterministic core contracts and the read-only DuckDB query service now
    provide bounded exact-identifier and normalized lexical discovery, concept
    detail, jurisdiction/source catalogues, explicit non-equivalence match
    explanations, and signed keyset cursors. API, CLI, atlas autocomplete, and
    semantic augmentation remain later increments.
- [ ] Task: Define clean-wheel consumer, supported-platform, package-metadata and public-API compatibility gates ([#41](https://github.com/edithatogo/global-medicines-atlas/issues/41))
- [ ] Task: Define core and optional-semantic installation boundaries, LanceDB index/model identity and deterministic fallback gates ([#41](https://github.com/edithatogo/global-medicines-atlas/issues/41))
- [ ] Task: Define non-overlapping GitHub, Hugging Face, Zenodo and OSF dataset/protocol identities and licence gates ([#41](https://github.com/edithatogo/global-medicines-atlas/issues/41))
- [ ] Task: Phase Verification & Checkpoint

## Phase 2: v0.9 candidate

- [ ] Task: Execute independent reproduction and disaster-recovery rehearsal ([#42](https://github.com/edithatogo/global-medicines-atlas/issues/42))
- [ ] Task: Rehearse compromised-source quarantine, signing/credential revocation, dataset withdrawal, corrected replacement and downstream notification ([#42](https://github.com/edithatogo/global-medicines-atlas/issues/42))
- [ ] Task: Verify every protected CI, security and publication receipt ([#42](https://github.com/edithatogo/global-medicines-atlas/issues/42))
- [ ] Task: Audit task-oriented documentation, examples and support paths ([#42](https://github.com/edithatogo/global-medicines-atlas/issues/42))
- [ ] Task: Migrate canonical records to schema v2 and verify source-native round trips ([#42](https://github.com/edithatogo/global-medicines-atlas/issues/42))
- [ ] Task: Verify comparison-validity outcomes and negative controls never imply equivalence, substitutability or equal benefit ([#42](https://github.com/edithatogo/global-medicines-atlas/issues/42))
- [ ] Task: Verify concept search, concept detail, jurisdictions and sources through API, CLI and atlas end to end ([#42](https://github.com/edithatogo/global-medicines-atlas/issues/42))
- [ ] Task: Install built wheel and sdist in clean environments and run import, CLI, API, version and reinstall checks ([#42](https://github.com/edithatogo/global-medicines-atlas/issues/42))
- [ ] Task: Snapshot and semantically diff the public OpenAPI contract and smoke-test a generated client ([#42](https://github.com/edithatogo/global-medicines-atlas/issues/42))
- [ ] Task: Resolve or explicitly block every Must requirement ([#42](https://github.com/edithatogo/global-medicines-atlas/issues/42))
- [ ] Task: Phase Verification & Checkpoint

## Phase 3: v1.0 promotion

- [ ] Task: Verify measured jurisdiction and source coverage ([#43](https://github.com/edithatogo/global-medicines-atlas/issues/43))
- [ ] Task: Verify hosted governance, security features and project views ([#43](https://github.com/edithatogo/global-medicines-atlas/issues/43))
- [ ] Task: Produce signed release package and consumer verification guide ([#43](https://github.com/edithatogo/global-medicines-atlas/issues/43))
- [ ] Task: Verify dataset cards, Croissant records, checksums and GitHub/Hugging Face/Zenodo/OSF identifier links without publishing restricted data ([#43](https://github.com/edithatogo/global-medicines-atlas/issues/43))
- [ ] Task: Obtain explicit maintainer licence and release approval ([#43](https://github.com/edithatogo/global-medicines-atlas/issues/43))
- [ ] Task: Record stable-v1 evidence and post-release monitoring plan ([#43](https://github.com/edithatogo/global-medicines-atlas/issues/43))
- [ ] Task: Phase Verification & Checkpoint

## GitHub hierarchy

- Parent: [#40 Stable v1 qualification](https://github.com/edithatogo/global-medicines-atlas/issues/40)
- Qualification contract: [#41](https://github.com/edithatogo/global-medicines-atlas/issues/41)
- v0.9 clean-room candidate: [#42](https://github.com/edithatogo/global-medicines-atlas/issues/42)
- v1.0 promotion and external gates: [#43](https://github.com/edithatogo/global-medicines-atlas/issues/43)
