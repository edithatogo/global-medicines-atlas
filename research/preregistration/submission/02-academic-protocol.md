# Global Medicines Atlas academic protocol

> Generated offline from `research/protocol/academic-protocol-v1.json`.
> Status: `prospective_draft`. This Phase 1 protocol is not an OSF
> registration. OSF is deprecated. The persistent public identity is the
> in-repo protocol plus Zenodo DOI `10.5281/zenodo.21734811`. This document
> does not report study results.

## Title

Global comparison of medicine regulatory approval and public funding

## Objectives

- Describe documented medicine regulatory status across included jurisdictions and times.
- Describe documented public funding, reimbursement, or formulary status separately from regulatory status.
- Quantify source and jurisdiction coverage and qualify cross-jurisdiction comparisons using explicit validity evidence.

## Intended users and non-clinical scope

- medicines-policy and health-system researchers
- regulatory, reimbursement, and formulary analysts
- public-interest medicine-access researchers
- data stewards maintaining cross-jurisdiction evidence

Permitted uses:

- descriptive policy research
- coverage auditing
- reproducible source-qualified comparison

Prohibited claims:

- clinical prescribing recommendation
- medicine equivalence or substitutability
- causal effect of approval or funding
- absence means unapproved or unfunded

The protocol does not provide clinical decision support, support individual
patient inference, or claim exhaustive global coverage.

## Estimands

### EST-01: regulatory_status

- Target: The source-native regulatory status for a defined medicine entity, indication, population, jurisdiction, and valid-time interval.
- Unit: One provenance-bearing regulatory assertion at declared entity granularity.
- Summary measure: Counts and proportions by source-native status among assertions with a defined catalog denominator.
- Interpretation: A descriptive legal or administrative status, not evidence of comparative clinical benefit.

### EST-02: funding_status

- Target: The source-native public funding, reimbursement, or formulary status for a defined medicine entity, indication, population, jurisdiction, and valid-time interval.
- Unit: One provenance-bearing funding assertion at declared entity granularity.
- Summary measure: Counts and proportions by source-native status among assertions with a defined catalog denominator.
- Interpretation: A descriptive public-system status, not a regulatory approval or clinical recommendation.

Regulatory and funding outcomes are separate estimands. Absence or uncovered
data is not interpreted as unapproved or unfunded.

## Jurisdiction and source census

The governed denominator is catalog schema v5
at `src/global_medicines_atlas/data/medicine_source_catalog.json`: 45 jurisdictions and
172 source surfaces. The prospective census is every jurisdiction and source row in catalog schema v5; implementation and current-receipt coverage are reported separately and never inferred from catalog presence.

### Jurisdiction inclusion

- Include every jurisdiction declared in the governed catalog denominator.
- Retain supra-national systems such as the EU as explicit jurisdictions rather than allocating their assertions to member states without source evidence.

### Source inclusion

- Include an official regulatory, reimbursement, funding, formulary, terminology, or reference surface with a stable catalog identity.
- Require authority, access mode, evidence limits, provenance, and rights state before acquisition or analysis.
- Include APIs, bulk downloads, searchable registers, and lawful licensed feeds while identifying their different reproducibility limits.

### Source exclusion

- Exclude secondary aggregators from authoritative status claims unless explicitly classified as terminology or discovery evidence.
- Exclude source payloads whose provenance, scope, or retrieval identity cannot be established; record the gap rather than a negative status.
- Exclude restricted or rights-unknown payload bytes from public packages while retaining lawful metadata and retrieval instructions.

### Rights boundary

Restricted and rights-unknown payloads are excluded from public packages.
Metadata and retrieval code may be retained; payload redistribution requires
source-specific permission. This protocol does not grant source-data rights.

## Comparison semantics

- Entity: Declare source-native and canonical granularity: ingredient, medicinal product, branded product, presentation, pack, or another explicitly mapped entity.
- Indication: Declare the authorised, funded, restricted, all-recorded, absent-from-source, or unknown indication scope without treating silence as unrestricted use.
- Population: Declare age, sex, clinical, prescriber, care-setting, or other source-native eligibility constraints and preserve unknowns.
- Temporal: Declare valid time and retrieval time; compare statuses only for overlapping or explicitly related periods and never overwrite history.
- Mapping: Declare exact, broader, narrower, related, unresolved, or source-native mapping relationships and the normalization method used.

Permitted M-090 validity states are: valid, valid_with_caveats, inappropriate_comparison, insufficient_evidence.
A mismatch in entity granularity, indication, population, mapping, normalization, status dimension, or non-overlapping temporal scope makes the intended status comparison inappropriate; missing evidence yields insufficient_evidence.

Validity qualifies only the stated status comparison. It never establishes
clinical equivalence, substitutability, therapeutic interchangeability, or
equal benefit.

## Traceability

- Requirements: M-002, M-003, M-004, M-035, M-078, M-081, M-088, M-090, M-091
- Design sections: Medicine Evidence Model, Source Information and Adapter Capability Contract, Comparison Validity Boundary, Governed Research and Dataset Identity
- GitHub methods issue: [67](https://github.com/edithatogo/global-medicines-atlas/issues/67)
- Governed repository paths:
- `conductor/requirements.md`
- `conductor/design.md`
- `schemas/comparison-validity-v1.json`
- `src/global_medicines_atlas/data/medicine_source_catalog.json`
- `conductor/tracks/academic_protocol_preregistration_20260729/plan.md`
- `.github/generated-issues/academic-protocol-methods.md`
