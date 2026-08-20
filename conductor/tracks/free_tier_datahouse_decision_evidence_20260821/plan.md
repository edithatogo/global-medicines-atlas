# Implementation Plan

Execution policy: [autonomous, decision-gated](../../autonomy.md).

## Phase 1: Rights, fixtures, and experiment contract

- [x] Task: Write failing contract tests for the rights-cleared evidence package (AC-01, AC-07) (`5a894f3`)
    - [x] Require origin, licence, sensitivity, digest, publication state, and exclusion reason
    - [x] Reject source-derived, credential-bearing, sensitive, or unresolved-rights artifacts
    - [x] Confirm the intended failures before implementation
- [x] Task: Implement the synthetic package, schemas, dataset card, and deterministic manifest (AC-01, AC-07) (`5a894f3`)
    - [x] Bind all artifacts to Apache-2.0 repository provenance
    - [x] Keep every source-derived payload outside the package
- [ ] Task: Phase review and verification checkpoint (AC-01, AC-06, AC-08)
    - [ ] Run focused tests, coverage, typing, security, licence, provenance, and core-isolation checks
    - [ ] Record publication boundary evidence

## Phase 2: Free-tier workflow mechanics and recovery

- [x] Task: Write deterministic workflow and recovery vectors (AC-02) (`5a894f3`)
    - [x] Cover branch, divergent update, conflict, merge, rollback, inventory, loss, and clean restore
- [x] Task: Implement and run the GitHub-hosted mechanics experiment (AC-02, AC-06) (`5a894f3`)
    - [x] Measure experimental RPO/RTO and dependency footprint
    - [x] Reject WORM, Object Lock, geographic guarantee, and production-SLA claims
- [ ] Task: Phase review and verification checkpoint (AC-02, AC-08)
    - [ ] Run fault, tamper, credential-leak, deterministic-replay, and restoration checks
    - [ ] Record hosted workflow evidence

## Phase 3: Hugging Face replication and restore

- [x] Task: Validate authenticated free-tier and public-package prerequisites (AC-01, AC-03) (`420da5c`)
    - [x] Verify account access without exposing credential material
    - [x] Verify dataset card, licence, sensitivity, digests, and maintainer authorization
- [x] Task: Publish and restore the approved synthetic evidence package (AC-03) (`420da5c`)
    - [x] Create or reuse a clearly experimental public dataset repository
    - [x] Pin the resulting revision and restore into a clean workspace
    - [x] Verify every digest and record mutability/SLA limitations
- [x] Task: Phase review and verification checkpoint (AC-03, AC-08) (`420da5c`)
    - [x] Run public-package boundary, remote inventory, clean restore, and checksum checks
    - [x] Record the exact public revision or failure receipt

## Phase 4: Workload demand and table-format comparison

- [x] Task: Measure real Atlas workload demand (AC-04) (`5a894f3`)
    - [x] Count evidenced updates, deletes, snapshot replacement, and concurrent-writer requirements
    - [x] Separate observed demand from synthetic stress scenarios
- [x] Task: Write the common synthetic Iceberg-ready, Delta, and Hudi workload (AC-05) (`5a894f3`)
    - [x] Define correctness, conflict, recovery, compaction, portability, time, memory, and dependency measures
    - [x] Confirm negative and failure controls before engine execution
- [x] Task: Execute bounded equivalent engine workloads (AC-05, AC-06) (`5a894f3`)
    - [x] Pin runtime and format identities
    - [x] Record complete results or reproducible implementation-specific failures
- [ ] Task: Phase review and verification checkpoint (AC-04, AC-05, AC-08)
    - [ ] Review benchmark comparability, runner cost, dependency isolation, and evidence language
    - [ ] Run focused and affected validation

## Phase 5: Maintainer decision evidence

- [x] Task: Produce the schema-validated decision packet (AC-07) (`2966d38`)
    - [x] Classify each capability and separate evidence, inference, and external gates
    - [x] Include benefits, risks, costs, compatibility, rollback, and recommended disposition
- [ ] Task: Whole-track Conductor review and completion verification (AC-08)
    - [ ] Run the full hosted Test-Goblin matrix and required repository checks
    - [ ] Reconcile GitHub issues, public Hugging Face revision, receipts, metadata, and registry
    - [ ] Preserve the final technology-promotion decision for the maintainer

## Review Fixes

- [x] Task: Make retained-reference, conflict, compaction, portability, and reconstruction outcomes explicit (`a314d80`)
- [x] Task: Regenerate digest-bound local and public receipts after review remediation (`3addadc`)
- [x] Task: Remove the duplicate core Hudi path and close optional-engine/publication branch coverage (`ccf15a0`)

## GitHub hierarchy

- Parent issue: [#231](https://github.com/edithatogo/global-medicines-atlas/issues/231)
- Nested subissues:
    - [ ] [#232](https://github.com/edithatogo/global-medicines-atlas/issues/232): rights-cleared synthetic public evidence (AC-01, AC-03)
    - [ ] [#233](https://github.com/edithatogo/global-medicines-atlas/issues/233): free-tier workflow mechanics and restore (AC-02)
    - [ ] [#234](https://github.com/edithatogo/global-medicines-atlas/issues/234): measured Atlas workload demand (AC-04)
    - [ ] [#235](https://github.com/edithatogo/global-medicines-atlas/issues/235): Iceberg-ready, Delta, and Hudi comparison (AC-05, AC-06)
    - [ ] [#236](https://github.com/edithatogo/global-medicines-atlas/issues/236): maintainer decision packet (AC-07, AC-08)
