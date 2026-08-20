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

- [x] Task: Exercise an actual disposable Iceberg REST catalogue (AC-02) (`ae81bd2`)
    - [x] Select and digest-pin Apache Iceberg REST fixture 1.11.0 through ecosystem and dependency review
    - [x] Test namespace/table lifecycle, snapshots, evolution, teardown, and failure controls
    - [x] Reconstruct catalogue state from governed fixture and acquisition binding
- [x] Task: Exercise Iceberg v3 capabilities and fallback (AC-03) (`ae81bd2`)
    - [x] Pin the authoritative v3 specification and PyIceberg capability surface
    - [x] Test advertised capabilities individually and record partial support as degraded
    - [x] Verify the existing v2 contract and acquisition identity remain unchanged
- [x] Task: Phase review and verification checkpoint (AC-02, AC-03, AC-09)
    - [x] Run contract coverage, negative controls, recovery, core isolation, and the actual hosted REST fixture
    - [x] Record implementation-specific limitations without universal conformance claims

## Phase 3: DuckLake comparison

- [x] Task: Write the common DuckLake comparison workload (AC-04) (`ae81bd2`)
    - [x] Use identical governed inputs, queries, mutations, failure injections, and recovery objectives
    - [x] Define correctness, portability, performance, maintenance, and operational measures before execution
- [x] Task: Execute and record the DuckLake comparison (AC-04, AC-08) (`ae81bd2`)
    - [x] Keep DuckDB embedded analytics usable without DuckLake
    - [x] Verify rebuildability and rollback from evidentiary truth
- [x] Task: Phase review and verification checkpoint (AC-04, AC-09)
    - [x] Review benchmark validity, dependency isolation, and evidence language
    - [x] Run focused and full affected validation

## Phase 4: Object-versioning workflow

- [x] Task: Validate the durable-storage entry condition (AC-05) (`ae81bd2`)
    - [x] Require deployed non-production object storage, versioning or Object Lock/WORM, independent replication, checksum inventory, restore rehearsal, and explicit RPO/RTO evidence
    - [x] Record `not_run_prerequisite_unmet` without provisioning credentials when evidence is absent
- [ ] Task: Exercise lakeFS or a documented equivalent when authorized (AC-05)
    - [ ] Test commit, branch, merge/conflict, rollback, retention, and independent restore
    - [ ] Verify workflow metadata cannot substitute for provider or Bronze storage receipts
- [x] Task: Phase review and verification checkpoint (AC-05, AC-09)
    - [x] Run fail-closed contract, security-boundary, and credential-free validation
    - [x] Record the prerequisite receipt; fault injection remains gated until deployed storage is authorized

## Phase 5: Cryptographic batch attestation

- [x] Task: Write deterministic tamper and inclusion vectors (AC-06) (`ae81bd2`)
    - [x] Cover reproducible roots, inclusion proofs, explicit non-membership semantics, ordering rules, incremental updates, duplicate identities, and corrupted leaves
    - [x] Confirm the intended failures before implementation
- [x] Task: Implement additive batch manifests or Merkle-root receipts (AC-06, AC-08) (`ae81bd2`)
    - [x] Bind roots to the existing per-object content IDs and SHA-256 receipts
    - [x] Preserve deterministic reconstruction and algorithm/version agility
- [x] Task: Phase review and verification checkpoint (AC-06, AC-09)
    - [x] Run focused, property-style vector, tamper, recovery, and full affected validation
    - [x] Verify no receipt authority was transferred to the batch root

## Phase 6: Delta Lake and Hudi comparison

- [x] Task: Validate the high-update workload entry condition (AC-07) (`ae81bd2`)
    - [x] Define measurable update, delete, concurrency, and transaction requirements
    - [x] Record `not_run_prerequisite_unmet` when current source evidence does not meet them
- [ ] Task: Execute equivalent Delta Lake and Hudi workloads when the entry condition is met (AC-07, AC-08)
    - [ ] Pin dependencies and run identical concurrency, failure, recovery, compaction, and portability scenarios
    - [ ] Compare both with the Iceberg-ready baseline without speculative promotion
- [x] Task: Phase review and verification checkpoint (AC-07, AC-09)
    - [x] Review the unmet workload gate, optional dependency boundary, and rollback requirement
    - [x] Run focused and full affected validation; equivalent engine workloads remain gated

## Phase 7: Cross-experiment disposition

- [x] Task: Produce the cross-experiment decision matrix (AC-10) (`ae81bd2`)
    - [x] Classify each experiment using the governed outcome vocabulary
    - [x] Separate observed evidence from inference and unmet prerequisites
    - [x] Preserve Bronze, storage, sensitivity, and publication boundaries
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
