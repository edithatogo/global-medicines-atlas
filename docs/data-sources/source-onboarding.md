# Medicine source onboarding

## Intake

Start with the source-onboarding issue form. Record the jurisdiction,
accountable authority, evidence dimension, official URL, access surfaces,
authentication class, cadence, rights and redistribution state, valid-time and
observed-time semantics, historical coverage, and known interpretation limits.

## Qualification lifecycle

1. Verify that the publisher is the relevant regulator, funder, formulary,
   terminology steward, or official delegate.
2. Add a source-catalog entry conforming to the
   [international resource schema](international-resource-schema.md).
3. Record rights as permitted, prohibited, conditional, unclear, or
   review-required; do not infer redistribution permission from public access.
4. Define acquisition policy, expected content type, resource bounds,
   authentication class, and a credential-free synthetic fixture.
5. Implement bounded parsing and projection while retaining native identifiers
   and terminology.
6. Preserve regulatory, funding, formulary, price, procurement, availability,
   and terminology as distinct dimensions.
7. Declare temporal semantics, provenance, evidence limits, and absence
   semantics.
8. Add unit, integration, property or edge tests and deterministic receipts.
9. Register monitoring and schema-drift expectations.
10. Promote from declared to fixture, documentation, or live qualification
    only when the corresponding evidence exists.

## Acceptance and deferral

Accept onboarding when authority, dimension, rights state, access surface,
temporal model, schema, fixtures, tests, and monitoring disposition are
explicit. Defer portal-only sources without a reproducible acquisition path,
unclear-rights redistribution, unstable undocumented endpoints, sources
requiring unavailable credentials, and clinically ambiguous mappings. A
deferred source remains catalogued with its limitation; it is not silently
treated as absent coverage.
