# Global Medicines Atlas analysis and validation plan

> Generated offline from `research/protocol/academic-analysis-plan-v1.json`.
> Status: `prospective_draft`. This is a prospective methods contract, not a
> report of completed analyses or an external registration.

## Outcome boundary

Regulatory and funding outcomes remain separate. Joint outcome inference is
not planned. Every comparison is qualified using M-090 validity semantics.

## Matching and adjudication

- Candidate generation: Deterministic identifiers and declared normalized features generate candidates separately from acceptance decisions.
- Automatic acceptance: `exact_rules_only`
- Unresolved evidence: `insufficient_evidence`
- Material mismatch: `inappropriate_comparison`
- Adjudication: 2 independent
  reviewers; consensus is required and unresolved disagreements are retained.
- Inter-rater summaries: percent_agreement, cohen_kappa_with_95_percent_ci.
  Agreement is a reliability description, not proof of validity.

### Negative controls

- NC-ENTITY (entity): Pair ingredient-level and pack-level records without an exact declared bridge. -> `inappropriate_comparison`
- NC-INDICATION (indication): Pair materially non-overlapping indication scopes. -> `inappropriate_comparison`
- NC-POPULATION (population): Pair materially non-overlapping eligibility populations. -> `inappropriate_comparison`
- NC-TEMPORAL (temporal): Pair non-overlapping valid-time intervals. -> `inappropriate_comparison`
- NC-MAPPING (mapping): Pair records with unresolved mapping evidence. -> `insufficient_evidence`
- NC-STATUS (status_dimension): Attempt to compare a regulatory assertion directly with a funding assertion. -> `inappropriate_comparison`

## Missingness, conflicts, coverage, and uncertainty

- Absence: `insufficient_evidence_not_negative_status`.
- Conflicts: `retain_all_assertions`; silent overwrite is forbidden.
- Unknown states are reported separately and uncertainty is not collapsed into
  a negative regulatory or funding status.

Coverage denominators:

- catalog_sources: All governed catalog source surfaces eligible under the prospective source-selection rules.
- eligible_entities: All source-native entities in the declared lawful analysis extract.
- eligible_assertions: All assertions eligible for the stated outcome and valid-time window.
- valid_comparisons: All candidate comparisons evaluated under M-090.

## Planned analyses

### Descriptive

- DA-REG [regulatory_status]: Counts and proportions by source-native regulatory status, jurisdiction, entity granularity, indication, population, and valid-time window.
- DA-FUND [funding_status]: Counts and proportions by source-native funding status, jurisdiction, entity granularity, indication, population, and valid-time window.
- DA-COVER [coverage]: Numerators and declared denominators for source, entity, assertion, field, temporal, and comparison coverage.
- DA-VALID [comparison_validity]: Counts and proportions for each M-090 validity state and material mismatch dimension.

### Sensitivity

- SA-EXACT: Restrict to exact entity mappings and overlapping valid-time intervals. — Assesses dependence on caveated mappings.
- SA-SOURCE: Restrict to sources with current live qualification receipts, then compare with governed-fixture results. — Separates source availability from method behavior.
- SA-CONFLICT: Report unresolved conflicts as a separate stratum and exclude them in a secondary summary. — Bounds sensitivity to conflict handling without overwriting evidence.
- SA-MISSING: Compare complete-case descriptive summaries with explicit missingness strata; do not impute status. — Shows the effect of observable missingness without treating absence as a negative.
- SA-UNIT: Repeat eligible summaries at ingredient and source-native product granularities where valid mappings exist. — Assesses dependence on unit of analysis.

### Multiplicity boundary

No confirmatory hypothesis tests or p-values are planned. Confidence intervals
describe uncertainty and are not used as significance tests. Unplanned
analyses must be labelled exploratory and entered in the deviation register.

## Immutable reproducibility identities

- software: full_git_commit_sha_and_clean_tree (verify: git rev-parse HEAD plus recorded tree digest)
- schemas: repository_path_schema_version_and_sha256 (verify: Draft 2020-12 validation plus checksum manifest)
- fixtures: fixture_manifest_paths_source_ids_and_sha256 (verify: offline fixture verification gate)
- random_seed: integer_seed_20260729_and_algorithm_identifier (verify: record seed and library algorithm/version in every stochastic receipt)
- environment: python_version_os_architecture_uv_lock_and_toolchain_digests (verify: generated environment receipt and lock checksum)

Mutable references are not sufficient evidence for any identity. The random
seed controls only deterministic procedures and does not make uncertain source
evidence certain.

## Deviations

The append-only register is `research/protocol/deviations.jsonl`. Changes
after registration are amendments; undeclared outcome switching is prohibited.

## Traceability

- Requirements: M-035, M-078, M-081, M-088, M-090, M-091
- GitHub analysis issue: [68](https://github.com/edithatogo/global-medicines-atlas/issues/68)
