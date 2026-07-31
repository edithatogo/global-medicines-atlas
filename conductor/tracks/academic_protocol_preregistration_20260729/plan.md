# Implementation Plan

Execution policy: [autonomous, decision-gated](../../autonomy.md).

## Phase 1: Protocol and source-selection contract

- [x] Task: Write failing schema and completeness tests for the protocol package
- [x] Task: Define objectives, estimands, users and non-clinical scope
- [x] Task: Define jurisdiction/source census, inclusion, exclusion and rights rules
- [x] Task: Define entity, indication, population, temporal and comparison-validity semantics
- [x] Task: Cross-reference requirements, design, source catalog and [GitHub methods subissue #67](https://github.com/edithatogo/global-medicines-atlas/issues/67)
- [x] Task: Phase Verification & Checkpoint
  - PR #111 merged as `06f2eb9` after all 29 protected checks passed; one
    representative-performance runner variance passed its bounded rerun.
    Independent post-merge Conductor review found no findings and verified
    deterministic generation, exact 34-jurisdiction/96-source census,
    M-090 semantics, strict typing and 95.23% hosted coverage.

## Phase 2: Analysis and validation plan

- [x] Task: Write failing tests for analysis-plan, sensitivity and deviation contracts
- [x] Task: Specify matching, adjudication, negative controls and inter-rater handling
- [x] Task: Specify missingness, conflicts, coverage denominators and uncertainty
- [x] Task: Specify descriptive analyses, sensitivity analyses and multiplicity boundaries
- [x] Task: Define software, schema, fixture, seed and environment identities
- [~] Task: Phase Verification & Checkpoint
  - Local implementation evidence passes: 23 focused Phase 1+2 tests, routine
    formatting and lint, formal BasedPyright with zero findings, and the unit
    lane with 862 passed plus two expected Windows symlink skips. Independent
    Conductor review and hosted protected checks remain pending; no external
    registration or publication gate was exercised.

## Phase 3: OSF-ready preregistration package

- [ ] Task: Generate the covering OSF preregistration narrative and structured attachments
- [ ] Task: Add amendment history, deviation register, data-management and ethics statements
- [ ] Task: Generate citations, checksums and a machine-readable submission manifest
- [ ] Task: Rehearse a clean offline build and validate every documented command
- [ ] Task: Obtain explicit maintainer review before any external submission
- [ ] Task: Phase Verification & Checkpoint

## Phase 4: Persistent identities and external verification

- [ ] Task: Define non-overlapping GitHub software, Hugging Face dataset, Zenodo record and OSF study identities
- [x] Task: Create and cross-link [GitHub parent #66](https://github.com/edithatogo/global-medicines-atlas/issues/66) and native phase subissues [#67](https://github.com/edithatogo/global-medicines-atlas/issues/67), [#68](https://github.com/edithatogo/global-medicines-atlas/issues/68), [#69](https://github.com/edithatogo/global-medicines-atlas/issues/69) and [#70](https://github.com/edithatogo/global-medicines-atlas/issues/70)
- [ ] Task: Create OSF, Hugging Face and Zenodo records only after rights and maintainer gates pass
- [ ] Task: Verify external identifiers, DOI relationships, licences and public landing pages
- [ ] Task: Record publication receipts or explicit external blockers
- [ ] Task: Phase Verification & Checkpoint

## GitHub hierarchy

- Parent: [#66](https://github.com/edithatogo/global-medicines-atlas/issues/66)
- Protocol/methods: [#67](https://github.com/edithatogo/global-medicines-atlas/issues/67)
- Analysis/validation: [#68](https://github.com/edithatogo/global-medicines-atlas/issues/68)
- Preregistration/rehearsal: [#69](https://github.com/edithatogo/global-medicines-atlas/issues/69)
- Persistent identities: [#70](https://github.com/edithatogo/global-medicines-atlas/issues/70)
