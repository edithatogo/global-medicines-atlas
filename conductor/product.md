# Global Medicines Registration and Funding Comparison System

## Product Vision

Create a global, evidence-based medallion datahouse for comparing medicines across national regulatory approval systems and public funding, reimbursement, and formulary systems.

The datahouse lands immutable source payloads and content-addressed receipts first, then derives source-faithful Parquet and later silver, gold, and platinum layers without collapsing regulatory, funding, formulary, or terminology meanings. Current delivery completes bronze for in-scope public and no-credential sources; later layers remain planned, not implied complete.

The platform will begin with available data from New Zealand, Australia, and the United States, then expand systematically across jurisdictions. New Zealand Universal List of Medicines and New Zealand Medicines Terminology (NZULM/NZMT) product structures are a named first-class source family. The platform will preserve source provenance, effective dates, terminology mappings, and the distinction between regulatory approval and funding status.

## Product Mission

Operate a provenance-first medicines datahouse that makes regulatory approval and public funding comparable across jurisdictions while remaining honest about coverage, rights, uncertainty, and layer.

## Product Purpose

Give researchers, policymakers, clinicians, and analysts a reproducible, layer-explicit evidence platform: the immutable source payload and its content-addressed receipt are evidentiary truth; source-faithful Parquet is the portable analytical representation; table/catalogue layers are rebuildable metadata over those artefacts. Hugging Face archives reviewed public bronze outputs; it is not the source of truth.

## Bronze Internal Strata

Bronze comprises three internal Bronze strata, not additional medallion levels.
**B0 Source Index** is the versioned index of agencies, datasets, APIs, and
source surfaces; indexing does not imply acquisition, coverage, qualification,
or currency. **B1 Acquisition Metadata** is the append-only record of
acquisition events, receipts, temporal identity, rights state, reuse decisions,
HTTP or other retrieval evidence, admission state, and provenance
relationships. Native receipts and acquisition/admission events are the B1
authority. The deterministic acquisition manifest is a rebuildable query
projection; OpenLineage and table catalogues are interoperability projections,
not authoritative metadata records. **B2 Raw Evidence** is immutable
source-native bytes, or a rights-constrained immutable reference when bytes
cannot lawfully be retained.

Source-faithful Parquet, archive-member manifests, OpenLineage, Iceberg,
DuckDB, and other query/catalogue objects are rebuildable Bronze projections
over B1/B2, not a fourth evidentiary source of truth. Silver remains
source-faithful typed or harmonised structures; Gold remains
cross-jurisdiction matched evidence; Platinum remains products and
presentation.

## Problem

Medicine availability differs substantially between countries. Regulatory approval, market registration, public reimbursement, formulary inclusion, restrictions, indications, and product presentation are recorded by separate organisations using incompatible identifiers and terminology.

Researchers, policymakers, clinicians, and analysts lack a unified way to determine:

- Whether a medicine is registered or approved in each jurisdiction.
- Whether it is publicly funded, reimbursed, or included in a formulary.
- Which indications, populations, restrictions, and product forms apply.
- How statuses differ between jurisdictions and over time.
- Which conclusions are supported by current primary-source evidence.

## Intended Users

- Medicines-policy and health-system researchers.
- Government and regulatory analysts.
- Health technology assessment and reimbursement professionals.
- Clinicians, pharmacists, and formulary teams.
- Public-interest organisations and medicine-access researchers.
- Data engineers maintaining cross-jurisdictional medicine datasets.

## Core Capabilities

1. Ingest data from official regulatory and funding-system sources.
2. Normalize medicines, ingredients, brands, strengths, dosage forms, indications, and identifiers.
3. Maintain jurisdiction-specific regulatory and funding records without collapsing their distinct meanings.
4. Match equivalent medicines and products across countries.
5. Compare approval, registration, funding, reimbursement, formulary, and restriction statuses.
6. Preserve source URLs, retrieval dates, effective dates, licensing terms, and transformation provenance.
7. Represent uncertainty, incomplete coverage, ambiguous matches, and conflicting evidence explicitly.
8. Support reproducible exports, analytical queries, reports, and visual comparisons.
9. Monitor sources and refresh data according to documented schedules.
10. Expand through a repeatable jurisdiction-onboarding framework.

## Geographic Strategy

Initial implementation will consolidate the available New Zealand, Australian, and United States materials.

Expansion will prioritize jurisdictions according to:

- Availability and reliability of official data.
- Legal and licensing feasibility.
- Public-health and policy value.
- Coverage of diverse regulatory and funding models.
- Technical effort required for ingestion and maintenance.

“Global” will be reported through measurable jurisdiction and source coverage, not inferred from the architecture alone.

## Data Principles

- Regulatory approval and public funding are separate dimensions.
- Ingredient-level and product-level conclusions must remain distinguishable.
- Historical status must not be overwritten by current status.
- Primary official sources take precedence over secondary aggregators.
- Every comparison must be traceable to source evidence.
- Missing data means unknown or not yet covered, not unapproved or unfunded.
- Automated matches must include confidence and review status.
- Material transformations must be reproducible and documented.

## Initial Scope

- Audit and consolidate existing project datasets and code.
- Inventory and ingest the available NZULM/NZMT, Medsafe, New Zealand Formulary, and PHARMAC-related artifacts under explicit source and licensing contracts.
- Establish a canonical cross-jurisdictional medicine data model.
- Implement reliable matching for the initial jurisdictions.
- Produce regulatory-versus-funding comparison outputs.
- Add provenance, data-quality checks, and manual-review workflows.
- Define a reusable process for adding further countries and source systems.

## Out of Scope for the Initial Product

- Clinical prescribing recommendations.
- Claims that a medicine is safe, effective, or appropriate for an individual.
- Substitution for official regulatory, reimbursement, or formulary records.
- Unsupported assumptions that absent records indicate non-approval or non-funding.
- Immediate complete coverage of every country.
- Redistribution of source data where licensing does not permit it.

## Success Criteria

- Regulatory and funding statuses are modeled separately and correctly.
- Existing NZ, Australian, and available US sources are inventoried with documented coverage.
- Cross-jurisdictional matches are reproducible and confidence-scored.
- Every reported status is linked to provenance and relevant dates.
- Coverage and data gaps can be quantified by country, source, medicine, and status type.
- New jurisdictions can be added through a documented, testable onboarding process.
- Outputs clearly distinguish confirmed findings, inferred matches, unresolved conflicts, and missing coverage.
