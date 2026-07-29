# Implementation Plan

## Phase 1: Package contracts

- [x] Task: Define data dictionary, dataset card and Croissant contracts ([#33](https://github.com/edithatogo/global-medicines-atlas/issues/33)) `93f0a09`
- [x] Task: Write deterministic generation and forbidden-content tests ([#33](https://github.com/edithatogo/global-medicines-atlas/issues/33)) `93f0a09`
- [x] Task: Define publication state and verification receipts ([#33](https://github.com/edithatogo/global-medicines-atlas/issues/33)) `93f0a09`
- [x] Task: Define SemVer, dynamic-version, changelog, citation and licence-consistency gates ([#33](https://github.com/edithatogo/global-medicines-atlas/issues/33)) `93f0a09`
- [x] Task: Phase Verification & Checkpoint — 641 passed, 3 expected Windows symlink skips; 93.95% branch coverage; Ruff, ty and BasedPyright passed

## Phase 2: Release pipeline

- [x] Task: Generate reviewed Parquet configs and coverage manifests ([#34](https://github.com/edithatogo/global-medicines-atlas/issues/34)) `6919040`
- [x] Task: Generate citations, SBOM, checksums and attestations ([#34](https://github.com/edithatogo/global-medicines-atlas/issues/34)) `6919040`
- [x] Task: Add dry-run Hugging Face and archival workflows ([#34](https://github.com/edithatogo/global-medicines-atlas/issues/34)) `6919040`
- [x] Task: Replace post-publication checks with pre-publication qualification and immutable assets ([#34](https://github.com/edithatogo/global-medicines-atlas/issues/34)) `6919040`
- [x] Task: Phase Verification & Checkpoint — 727 passed, 6 expected Windows symlink skips; 94.28% branch coverage; Zizmor, Ruff, ty and BasedPyright passed

## Phase 3: Qualification

- [ ] Task: Rehearse package verification without external publication ([#35](https://github.com/edithatogo/global-medicines-atlas/issues/35))
- [ ] Task: Complete rights, privacy, licence and provenance review gates ([#35](https://github.com/edithatogo/global-medicines-atlas/issues/35))
- [ ] Task: Verify SBOM and provenance from a consumer clean room ([#35](https://github.com/edithatogo/global-medicines-atlas/issues/35))
- [ ] Task: Record v0.7 release evidence ([#35](https://github.com/edithatogo/global-medicines-atlas/issues/35))
- [ ] Task: Phase Verification & Checkpoint

## GitHub hierarchy

- Parent: [#32 Governed publication](https://github.com/edithatogo/global-medicines-atlas/issues/32)
- Package contracts: [#33](https://github.com/edithatogo/global-medicines-atlas/issues/33)
- Qualified release pipeline: [#34](https://github.com/edithatogo/global-medicines-atlas/issues/34)
- Publication qualification: [#35](https://github.com/edithatogo/global-medicines-atlas/issues/35)

## Phase 1 Review Fixes

- [x] Task: Require state-specific safe-URL verification evidence and explicit privacy/forbidden-content checks `7ad6ccd`
- [x] Task: Enforce changelog/citation date agreement and resolved artifact-root containment `7ad6ccd`
- [x] Task: Re-run focused review-fix verification — 85 passed, 2 expected Windows symlink skips; Ruff, ty and BasedPyright passed
