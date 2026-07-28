# Specification: Cross-Jurisdiction Matching

Archived implementation specification.

## Outcome

Deliver v0.5 reviewable mappings across ingredients, medicines and products
without claiming therapeutic equivalence.

## Requirements

- M-003, M-033, M-040, M-041, M-050 to M-053, M-072 and S-002.
- Use deterministic identifiers and lexical features before optional vectors.
- Record method, evidence, confidence, model/index version and review state.
- Route ambiguous and conflicting candidates to adjudication.

## Acceptance

- Positive, negative and adversarial fixtures quantify mapping quality.
- Python is authoritative until Mojo/Rust parity passes.
- LanceDB and optional Tantivy indexes are fully regenerable.

## Out of scope

- Clinical equivalence or substitution recommendations.
- Unreviewed semantic matches presented as facts.
