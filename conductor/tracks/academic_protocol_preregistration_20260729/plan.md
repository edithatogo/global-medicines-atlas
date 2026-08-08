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
- [x] Task: Phase Verification & Checkpoint
  - PR #113 merged as `8e7ba8e` after all 29 protected checks passed.
    Independent Conductor review found no actionable findings and verified the
    23 focused contract tests, the 862-test unit lane, deterministic generation,
    routine quality gates, and BasedPyright strict with zero findings. No
    external registration or publication gate was exercised.

## Phase 3: OSF-ready preregistration package

- [x] Task: Generate the covering OSF preregistration narrative and structured attachments
- [x] Task: Add amendment history, deviation register, data-management and ethics statements
- [x] Task: Generate citations, checksums and a machine-readable submission manifest
- [x] Task: Rehearse a clean offline build and validate every documented command
- [~] Task: Obtain explicit maintainer review before any external submission
  - Repository package review is recorded in
    `docs/publication/osf-maintainer-review.md` and
    `quality/qualifications/osf-maintainer-review.json`.
  - Final wording, ethics applicability, authenticated OSF authority, and
    post-registration receipt remain open.
- [x] Task: Phase Verification & Checkpoint
  - The deterministic offline rehearsal contains ten committed files, validates
    strict package and manifest schemas, verifies every declared byte count and
    SHA-256 digest, and executes both documented commands in an isolated output
    directory. Focused tests, routine checks, BasedPyright strict, the 868-test
    unit lane, and the 1,570-test 95.19% coverage gate passed locally. The draft
    remains `draft_not_submitted`; maintainer review and every external record
    remain explicitly open.
  - PR #117 merged as `dc466ed` after all 29 protected checks passed.
    Independent Conductor review found no findings and confirmed package
    completeness, exact checksums, deterministic regeneration, documented
    command rehearsal, and fail-closed external-action flags.

## Phase 4: Persistent identities and external verification

- [x] Task: Define non-overlapping GitHub software, Hugging Face dataset, Zenodo record and OSF study identities
  - Reuses the strict four-object registry in
    `quality/qualifications/publication-identities.json`: GitHub is the software
    source/release, Hugging Face is a derived dataset distribution, Zenodo is
    the archival DOI record, and OSF is the protocol/preregistration. Null
    external identifiers remain unresolved rather than guessed.
- [x] Task: Create and cross-link [GitHub parent #66](https://github.com/edithatogo/global-medicines-atlas/issues/66) and native phase subissues [#67](https://github.com/edithatogo/global-medicines-atlas/issues/67), [#68](https://github.com/edithatogo/global-medicines-atlas/issues/68), [#69](https://github.com/edithatogo/global-medicines-atlas/issues/69) and [#70](https://github.com/edithatogo/global-medicines-atlas/issues/70)
- [x] Task: Create the OSF preregistration and any source-derived Hugging Face or Zenodo dataset records only after rights and maintainer gates pass
  - The catalogue-only Hugging Face distribution and software-only Zenodo record
    already exist and are reconciled below. They do not satisfy this task's OSF
    or source-derived-data gate. OSF registration `ej5nf` was created from the
    completed private draft; no source-derived payload was added.
- [~] Task: Verify the OSF identifier, DOI relationships, licences and public landing pages
  - GitHub `v1.0.0rc1`, the catalogue-only Hugging Face distribution, Zenodo
    DOI `10.5281/zenodo.21734811`, and OSF registration
    `https://osf.io/ej5nf/` were verified on 2026-08-03. OSF DOI
    `10.17605/OSF.IO/EJ5NF`, public landing state, Zenodo relationship links,
    and Apache-2.0 declarations for GitHub/Hugging Face/Zenodo are recorded in
    `quality/qualifications/post-registration-reconciliation-20260803.json`.
    The OSF registration record does not expose a licence, so the licence
    sub-gate remains unresolved; no source-derived-data record is approved.
- [x] Task: Record publication receipts or explicit external blockers
  - `docs/publication/external-publication-receipt.md` and the post-registration
    reconciliation record the verified GitHub, catalogue-only Hugging Face,
    software-only Zenodo and public OSF identities. Remaining blockers are the
    OSF registration-record licence state, source-by-source data rights, and
    the distinct source-derived-data record.
- [~] Task: Phase Verification & Checkpoint
  - Repository-owned identity and OSF registration receipt work is complete;
    OSF public landing state is verified. The OSF registration-record licence,
    source-derived-data rights, and any future dataset release remain genuine
    external gates.

## GitHub hierarchy

- Parent: [#66](https://github.com/edithatogo/global-medicines-atlas/issues/66)
- Protocol/methods: [#67](https://github.com/edithatogo/global-medicines-atlas/issues/67)
- Analysis/validation: [#68](https://github.com/edithatogo/global-medicines-atlas/issues/68)
- Preregistration/rehearsal: [#69](https://github.com/edithatogo/global-medicines-atlas/issues/69)
- Persistent identities: [#70](https://github.com/edithatogo/global-medicines-atlas/issues/70)
