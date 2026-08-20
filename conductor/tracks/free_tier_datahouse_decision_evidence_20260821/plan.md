# Implementation Plan

Execution policy: [autonomous, decision-gated](../../autonomy.md).

## Phase 1: Rights, fixtures, and experiment contract

- [ ] Task: Write failing contract tests for the rights-cleared evidence package (AC-01, AC-07)
    - [ ] Require origin, licence, sensitivity, digest, publication state, and exclusion reason
    - [ ] Reject source-derived, credential-bearing, sensitive, or unresolved-rights artifacts
    - [ ] Confirm the intended failures before implementation
- [ ] Task: Implement the synthetic package, schemas, dataset card, and deterministic manifest (AC-01, AC-07)
    - [ ] Bind all artifacts to Apache-2.0 repository provenance
    - [ ] Keep every source-derived payload outside the package
- [ ] Task: Phase review and verification checkpoint (AC-01, AC-06, AC-08)
    - [ ] Run focused tests, coverage, typing, security, licence, provenance, and core-isolation checks
    - [ ] Record publication boundary evidence

## Phase 2: Free-tier workflow mechanics and recovery

- [ ] Task: Write deterministic workflow and recovery vectors (AC-02)
    - [ ] Cover branch, divergent update, conflict, merge, rollback, inventory, loss, and clean restore
- [ ] Task: Implement and run the GitHub-hosted mechanics experiment (AC-02, AC-06)
    - [ ] Measure experimental RPO/RTO and dependency footprint
    - [ ] Reject WORM, Object Lock, geographic guarantee, and production-SLA claims
- [ ] Task: Phase review and verification checkpoint (AC-02, AC-08)
    - [ ] Run fault, tamper, credential-leak, deterministic-replay, and restoration checks
    - [ ] Record hosted workflow evidence

## Phase 3: Hugging Face replication and restore

- [ ] Task: Validate authenticated free-tier and public-package prerequisites (AC-01, AC-03)
    - [ ] Verify account access without exposing credential material
    - [ ] Verify dataset card, licence, sensitivity, digests, and maintainer authorization
- [ ] Task: Publish and restore the approved synthetic evidence package (AC-03)
    - [ ] Create or reuse a clearly experimental public dataset repository
    - [ ] Pin the resulting revision and restore into a clean workspace
    - [ ] Verify every digest and record mutability/SLA limitations
- [ ] Task: Phase review and verification checkpoint (AC-03, AC-08)
    - [ ] Run public-package boundary, remote inventory, clean restore, and checksum checks
    - [ ] Record the exact public revision or failure receipt

## Phase 4: Workload demand and table-format comparison

- [ ] Task: Measure real Atlas workload demand (AC-04)
    - [ ] Count evidenced updates, deletes, snapshot replacement, and concurrent-writer requirements
    - [ ] Separate observed demand from synthetic stress scenarios
- [ ] Task: Write the common synthetic Iceberg-ready, Delta, and Hudi workload (AC-05)
    - [ ] Define correctness, conflict, recovery, compaction, portability, time, memory, and dependency measures
    - [ ] Confirm negative and failure controls before engine execution
- [ ] Task: Execute bounded equivalent engine workloads (AC-05, AC-06)
    - [ ] Pin runtime and format identities
    - [ ] Record complete results or reproducible implementation-specific failures
- [ ] Task: Phase review and verification checkpoint (AC-04, AC-05, AC-08)
    - [ ] Review benchmark comparability, runner cost, dependency isolation, and evidence language
    - [ ] Run focused and affected validation

## Phase 5: Maintainer decision evidence

- [ ] Task: Produce the schema-validated decision packet (AC-07)
    - [ ] Classify each capability and separate evidence, inference, and external gates
    - [ ] Include benefits, risks, costs, compatibility, rollback, and recommended disposition
- [ ] Task: Whole-track Conductor review and completion verification (AC-08)
    - [ ] Run the full hosted Test-Goblin matrix and required repository checks
    - [ ] Reconcile GitHub issues, public Hugging Face revision, receipts, metadata, and registry
    - [ ] Preserve the final technology-promotion decision for the maintainer

## GitHub hierarchy

- Parent issue: [#231](https://github.com/edithatogo/global-medicines-atlas/issues/231)
- Nested subissues:
    - [ ] [#232](https://github.com/edithatogo/global-medicines-atlas/issues/232): rights-cleared synthetic public evidence (AC-01, AC-03)
    - [ ] [#233](https://github.com/edithatogo/global-medicines-atlas/issues/233): free-tier workflow mechanics and restore (AC-02)
    - [ ] [#234](https://github.com/edithatogo/global-medicines-atlas/issues/234): measured Atlas workload demand (AC-04)
    - [ ] [#235](https://github.com/edithatogo/global-medicines-atlas/issues/235): Iceberg-ready, Delta, and Hudi comparison (AC-05, AC-06)
    - [ ] [#236](https://github.com/edithatogo/global-medicines-atlas/issues/236): maintainer decision packet (AC-07, AC-08)
