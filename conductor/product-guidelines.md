# Product Guidelines

## Purpose

These guidelines define how the Global Medicines Registration and Funding Comparison System communicates evidence, uncertainty, coverage, and cross-jurisdictional differences. Bronze outputs describe source-native landed records; they must not be presented as silver, gold, or platinum conclusions.

## Voice and Tone

- Use clear, neutral, evidence-focused language.
- Write for policy, regulatory, clinical, research, and technical audiences.
- Prefer precise definitions over promotional language.
- Explain specialist terms when first introduced.
- Avoid implying clinical advice, regulatory authority, or funding entitlement.
- State limitations directly without obscuring useful findings.

## Core Communication Principles

### Separate Regulatory and Funding Status

Never treat regulatory approval, market registration, public funding, reimbursement, formulary inclusion, procurement, and commercial availability as interchangeable.

Every displayed status must identify:

- The status dimension.
- The responsible organisation or system.
- The jurisdiction.
- The medicine or product level.
- The relevant date or reporting period.
- The supporting source.

### Report Evidence, Not Assumptions

Use explicit evidence labels such as:

- Confirmed by primary source.
- Derived from primary-source records.
- Inferred through cross-jurisdictional matching.
- Awaiting manual review.
- Conflicting evidence.
- Not yet covered.
- Source unavailable or inaccessible.

An absent record must not be presented as evidence that a medicine is unapproved, unregistered, unfunded, or unavailable.

### Preserve Granularity

Clearly distinguish between:

- Ingredient and medicinal product.
- Brand and generic concept.
- Strength and dose form.
- Presentation and package.
- Indication and general approval.
- Population-specific and unrestricted status.
- Current and historical status.

Do not generalize a product-level observation to an ingredient-level conclusion unless the transformation is documented and justified.

### Make Uncertainty Visible

Matching confidence, unresolved ambiguity, incomplete source coverage, stale data, and conflicting records must be visible in analytical outputs.

Do not hide uncertainty to simplify a comparison.

## Terminology

- Use jurisdiction-native terminology when describing a source system.
- Map native terms to canonical concepts without replacing or erasing the original term.
- Prefer “medicine” as the general user-facing term unless a more specific level is required.
- Use “regulatory status” and “funding status” as separate headings.
- Use “not found in the covered source” rather than “not approved” or “not funded” when evidence is incomplete.
- Use country and jurisdiction names consistently and maintain standard identifiers where possible.

## Interface and Reporting Principles

### Comparisons

- Display comparable dimensions side by side.
- Preserve meaningful jurisdiction-specific differences.
- Make dates, source scope, and update status prominent.
- Allow users to inspect the evidence behind every conclusion.
- Provide filters for jurisdiction, ingredient, product, indication, status type, and time.
- Distinguish current snapshots from historical comparisons.

### Coverage

Every report should state:

- Jurisdictions included.
- Regulatory and funding sources included.
- Data retrieval or effective dates.
- Known exclusions.
- Matching and review status.
- Material licensing or redistribution constraints.

“Global” must always be accompanied by measurable coverage information.

### Visual Design

- Prioritize readability and information hierarchy.
- Use color as a secondary signal, never the only signal.
- Pair status colors with text and icons.
- Use accessible contrast and keyboard-compatible interactions.
- Avoid binary visualizations where the evidence has unknown, partial, restricted, or conflicting states.
- Keep source and provenance details available without overwhelming the primary comparison.

## Data and Evidence Standards

- Prefer official primary sources.
- Preserve source URLs, identifiers, retrieval dates, and effective dates.
- Keep bronze (raw-as-landed) evidence distinguishable from later medallion layers.
- Record transformation and matching methods.
- Version datasets and derived outputs.
- Retain historical observations where legally and technically feasible.
- Document source licensing and permitted redistribution.
- Make automated and manually reviewed records distinguishable.
- Use reproducible quality checks for ingestion, normalization, matching, and export.

## Safety and Responsible Use

- Do not provide individual clinical recommendations.
- Do not infer safety, effectiveness, therapeutic equivalence, or substitutability solely from registration or funding status.
- Do not imply that public funding guarantees access for every patient or indication.
- Do not imply regulatory disapproval from missing data.
- Protect confidential, licensed, or access-controlled source material.
- Clearly label research and policy outputs that are not authoritative official records.

## Ecosystem and Reuse Doctrine

- Treat the maintainer's repositories, packages, schemas, fixtures, workflows, and publication systems as an ecosystem to extend.
- Search that ecosystem before introducing a new implementation or third-party abstraction.
- Prefer building on an existing maintainer-owned component when its contract is suitable or can be evolved safely.
- Extract reusable components into explicit packages or contracts rather than copying code without provenance.
- Preserve source repository, commit, version, licence, and compatibility evidence for reused work.
- Standardize common capabilities across repositories at the current supported frontier.
- Do not preserve a legacy dependency merely because historical code used it.
- Isolate legacy compatibility at adapters and migration boundaries.
- Require a documented reason when new work duplicates or bypasses an existing maintainer-owned capability.
- Use third-party foundational libraries when recreating them would not add distinctive maintainer-owned value.

## Quality Standard

A product output is ready for use only when:

- Status dimensions are clearly identified.
- Jurisdiction and medicine granularity are explicit.
- Evidence and dates are traceable.
- Coverage limitations are disclosed.
- Uncertainty and conflicts are represented.
- Regulatory and funding conclusions are not conflated.
- The output can be reproduced from documented inputs and transformations.
