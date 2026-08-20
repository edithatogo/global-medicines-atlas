# Implementation Plan

Execution policy: [autonomous, decision-gated](../../autonomy.md).

This qualification track measures bronze. It does not implement Silver,
Gold, or dashboards. Related bronze landing remains
[tracks/bronze_medallion_completion_20260819](../bronze_medallion_completion_20260819/index.md)
and GitHub [#167](https://github.com/edithatogo/global-medicines-atlas/issues/167).

## Phase 1: Criteria, schema, and failing tests

- [x] Task: Write failing tests for bronze maturity qualification
    - [x] Assert 14 mandatory properties are evaluated
    - [x] Assert excluded catalog sources are not negative evidence
    - [x] Assert stable-v1 and Hugging Face publication artefacts cannot
      evidence bronze
    - [x] Assert schema rejects mature declaration with blockers
    - [x] Confirm the intended failure before implementation
- [x] Task: Publish the JSON Schema and evaluator contract
    - [x] Reuse stable-v1 qualification fail-closed patterns
    - [x] Keep payload/receipt as evidentiary truth in notes and authorities
- [x] Task: Phase Verification & Checkpoint
    - [x] Run focused tests
    - [x] Record evidence

## Phase 2: Evaluator, adversarial review, and report

- [x] Task: Implement repository-evidence evaluation
    - [x] Classify bronze-in-scope, fixture-only, and excluded sources
    - [x] Probe code, tests, and docs per property
    - [x] Emit residual risks and explicit blockers
- [x] Task: Independent adversarial review of criteria versus evidence
    - [x] Actor is `criteria-versus-code-tests-docs`, not a person
    - [x] Fail closed on forbidden later-layer evidence and false maturity
- [x] Task: Generate `quality/qualifications/bronze-maturity.json`
- [x] Task: Phase Verification & Checkpoint
    - [x] Run focused tests, typing where available
    - [x] Record evidence; do not declare Bronze mature if blockers remain

## Review Fixes

- [x] Task: Requalify against the merged bronze implementation
    - [x] Refresh the committed report at exact main revision `fde2340`
    - [x] Repair worktree-aware Git revision discovery
    - [x] Reconcile Iceberg-ready evidence probes with the merged contracts
    - [x] Keep completeness and production disaster recovery fail-closed
