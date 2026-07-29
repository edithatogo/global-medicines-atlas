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

- [x] Task: Rehearse package verification without external publication ([#35](https://github.com/edithatogo/global-medicines-atlas/issues/35)) `7ff68c1`
- [x] Task: Complete rights, privacy, licence and provenance review gates ([#35](https://github.com/edithatogo/global-medicines-atlas/issues/35)) — fixture gates evidenced; production licence, rights and maintainer approvals explicitly blocked `7ff68c1`
- [x] Task: Verify SBOM and provenance from a consumer clean room ([#35](https://github.com/edithatogo/global-medicines-atlas/issues/35)) `7ff68c1`
- [x] Task: Record v0.7 release evidence ([#35](https://github.com/edithatogo/global-medicines-atlas/issues/35)) `7ff68c1`
- [x] Task: Phase Verification & Checkpoint — 775 passed, 7 expected Windows symlink skips; 94.14% branch coverage; Ruff, ty and BasedPyright passed

## GitHub hierarchy

- Parent: [#32 Governed publication](https://github.com/edithatogo/global-medicines-atlas/issues/32)
- Package contracts: [#33](https://github.com/edithatogo/global-medicines-atlas/issues/33)
- Qualified release pipeline: [#34](https://github.com/edithatogo/global-medicines-atlas/issues/34)
- Publication qualification: [#35](https://github.com/edithatogo/global-medicines-atlas/issues/35)

## Phase 1 Review Fixes

- [x] Task: Require state-specific safe-URL verification evidence and explicit privacy/forbidden-content checks `7ad6ccd`
- [x] Task: Enforce changelog/citation date agreement and resolved artifact-root containment `7ad6ccd`
- [x] Task: Re-run focused review-fix verification — 85 passed, 2 expected Windows symlink skips; Ruff, ty and BasedPyright passed

## Phase 2 Review Fixes

- [x] Task: Bind privacy and forbidden-content qualification to exact staged package bytes `b5ad86c`
- [x] Task: Integrate governed dataset generation and qualification into the release workflow `b5ad86c`
- [x] Task: Validate release tag, commit, dynamic version, changelog, citation, licence, wheel and SBOM agreement `b5ad86c`
- [x] Task: Re-run focused review-fix verification — 42 passed; Zizmor, Ruff, ty and BasedPyright passed
- [x] Task: Add rights-safe synthetic dry-run inputs and complete runtime-SBOM closure validation `84fedd4`

## Phase 3 Review Fixes

- [x] Task: Verify trusted provenance-attestation subjects and semantic package/SBOM/runtime-lock closure in the clean room `5441c37`
- [x] Task: Make fixture, production and publication-state conflation structurally invalid in the qualification schema `5441c37`
- [x] Task: Re-run complete protected harness after cache reclamation — 804 passed, 7 expected Windows symlink skips; 94.08% branch coverage
- [x] Task: Require offline GitHub/Sigstore bundle verification against an independently supplied repository/workflow trust policy `5900245`
- [x] Task: Digest-bind an independently supplied trusted root and classify child-process network isolation honestly `90c81c4`
