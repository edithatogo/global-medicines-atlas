# Implementation Plan

Execution policy: [autonomous, decision-gated](../../autonomy.md).

Every task traces to the approved acceptance criteria in `spec.md`. The six
technology evaluations are non-blocking experiments; unmet entry conditions
produce explicit not-run evidence rather than weakened gates.

## Phase 1: Shared experiment contract and fixtures

- [x] Task: Write failing contract tests for the experiment matrix (AC-01, AC-08) (`9231554`)
    - [x] Require every requested experiment and every explicit outcome state
    - [x] Require pinned specifications, dependency identities, fixture digests, limitations, and rollback procedures
    - [x] Prove the Python 3.14 core imports and Bronze recovery path remain independent of experiment dependencies
    - [x] Confirm the intended failures before implementation
- [x] Task: Implement the shared matrix, schemas, governed fixtures, and receipt writer (AC-01, AC-08, AC-09) (`9231554`)
    - [x] Reuse existing Bronze Parquet, table-specification, storage-policy, and acquisition/snapshot contracts
    - [x] Add deterministic regeneration and schema validation
    - [x] Record dependency classification and retirement conditions
- [x] Task: Review fixes for experiment-contract edge coverage (AC-01, AC-09) (`acd41da`)
    - [x] Exercise unpinned specifications and executed outcomes with unmet prerequisites
    - [x] Raise the shared contract module to 100% line and branch coverage
- [x] Task: Phase review and verification checkpoint (AC-09)
    - [x] Run focused and affected tests, coverage, Ruff, ty, BasedPyright, dependency, provenance, and security checks
    - [x] Record review findings and append-only evidence

## Phase 2: Iceberg REST and Iceberg v3

- [ ] Task: Exercise an actual disposable Iceberg REST catalogue (AC-02)
    - [ ] Select and pin at least one implementation through ecosystem and dependency review
    - [ ] Test namespace/table lifecycle, commits, snapshots, evolution, teardown, and failure receipts
    - [ ] Reconstruct catalogue state from governed Parquet and acquisition/snapshot bindings
- [ ] Task: Exercise Iceberg v3 capabilities and fallback (AC-03)
    - [ ] Pin the authoritative v3 specification and implementation capability surface
    - [ ] Test advertised capabilities individually and reject silent downgrade
    - [ ] Verify fallback to the existing contract without identity drift
- [ ] Task: Phase review and verification checkpoint (AC-02, AC-03, AC-09)
    - [ ] Run interoperability, negative-control, recovery, core-isolation, and full affected validation
    - [ ] Record implementation-specific limitations without universal conformance claims

## Phase 3: DuckLake comparison

- [ ] Task: Write the common DuckLake comparison workload (AC-04)
    - [ ] Use identical governed inputs, queries, mutations, failure injections, and recovery objectives
    - [ ] Define correctness, portability, performance, maintenance, and operational measures before execution
- [ ] Task: Execute and record the DuckLake comparison (AC-04, AC-08)
    - [ ] Keep DuckDB embedded analytics usable without DuckLake
    - [ ] Verify rebuildability and rollback from evidentiary truth
- [ ] Task: Phase review and verification checkpoint (AC-04, AC-09)
    - [ ] Review benchmark validity, dependency isolation, and evidence language
    - [ ] Run focused and full affected validation

## Phase 4: Object-versioning workflow

- [ ] Task: Validate the durable-storage entry condition (AC-05)
    - [ ] Require deployed non-production object storage, versioning or Object Lock/WORM, independent replication, checksum inventory, restore rehearsal, and explicit RPO/RTO evidence
    - [ ] Record `not_run_prerequisite_unmet` without provisioning credentials when evidence is absent
- [ ] Task: Exercise lakeFS or a documented equivalent when authorized (AC-05)
    - [ ] Test commit, branch, merge/conflict, rollback, retention, and independent restore
    - [ ] Verify workflow metadata cannot substitute for provider or Bronze storage receipts
- [ ] Task: Phase review and verification checkpoint (AC-05, AC-09)
    - [ ] Run fault injection, recovery, security, sensitivity, and credential-leak checks
    - [ ] Record the prerequisite or experiment receipt

## Phase 5: Cryptographic batch attestation

- [ ] Task: Write deterministic tamper and inclusion vectors (AC-06)
    - [ ] Cover reproducible roots, inclusion proofs, absence or explicit non-membership semantics, ordering rules, incremental updates, duplicate identities, and corrupted leaves
    - [ ] Confirm the intended failures before implementation
- [ ] Task: Implement additive batch manifests or Merkle-root receipts (AC-06, AC-08)
    - [ ] Bind roots to the existing per-object content IDs and SHA-256 receipts
    - [ ] Preserve deterministic reconstruction and algorithm/version agility
- [ ] Task: Phase review and verification checkpoint (AC-06, AC-09)
    - [ ] Run focused, property, mutation, recovery, and full affected validation
    - [ ] Verify no receipt authority was transferred to the batch root

## Phase 6: Delta Lake and Hudi comparison

- [ ] Task: Validate the high-update workload entry condition (AC-07)
    - [ ] Define measurable update, delete, concurrency, and transaction requirements
    - [ ] Record `not_run_prerequisite_unmet` when current source evidence does not meet them
- [ ] Task: Execute equivalent Delta Lake and Hudi workloads when the entry condition is met (AC-07, AC-08)
    - [ ] Pin dependencies and run identical concurrency, failure, recovery, compaction, and portability scenarios
    - [ ] Compare both with the Iceberg-ready baseline without speculative promotion
- [ ] Task: Phase review and verification checkpoint (AC-07, AC-09)
    - [ ] Review workload validity, maintenance costs, Python 3.14 compatibility, and rollback evidence
    - [ ] Run focused and full affected validation

## Phase 7: Cross-experiment disposition

- [ ] Task: Produce the cross-experiment decision matrix (AC-10)
    - [ ] Classify each capability as adopt-candidate, continue-experiment, reject, supersede, or not-run
    - [ ] Separate observed evidence from inference and unmet prerequisites
    - [ ] Preserve Bronze, storage, sensitivity, and publication boundaries
- [ ] Task: Whole-track automated review and completion verification (AC-09, AC-10)
    - [ ] Run the full Test-Goblin profile where platform support permits
    - [ ] Validate schemas, deterministic regeneration, documentation, provenance, licensing, and Conductor/GitHub traceability
    - [ ] Record unresolved external gates and do not imply deployment or promotion

## GitHub hierarchy

- Parent issue: [#207](https://github.com/edithatogo/global-medicines-atlas/issues/207)
- Nested subissues:
    - [ ] [#208](https://github.com/edithatogo/global-medicines-atlas/issues/208): actual Iceberg REST catalogue interoperability (AC-02)
    - [ ] [#209](https://github.com/edithatogo/global-medicines-atlas/issues/209): Iceberg v3 capability and fallback testing (AC-03)
    - [ ] [#210](https://github.com/edithatogo/global-medicines-atlas/issues/210): DuckLake comparison (AC-04)
    - [ ] [#211](https://github.com/edithatogo/global-medicines-atlas/issues/211): lakeFS or equivalent object-versioning workflow (AC-05)
    - [ ] [#212](https://github.com/edithatogo/global-medicines-atlas/issues/212): cryptographic batch manifests or Merkle-root attestations (AC-06)
    - [ ] [#213](https://github.com/edithatogo/global-medicines-atlas/issues/213): Delta Lake and Hudi comparison for evidenced high-update sources (AC-07)
