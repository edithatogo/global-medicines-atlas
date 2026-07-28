# Specification: nzmedicines Consolidation

## Overview

Consolidate every relevant artifact from `edithatogo/nzmedicines` into this canonical global medicines monorepository as a governed NZULM/NZMT FHIR adapter and fixture package. Preserve upstream history and commit identity, reconcile richer local material, and retain a compatibility path without treating the narrow upstream repository as the global system.

## Functional Requirements

1. Preserve a complete verifiable upstream Git bundle and immutable source snapshot.
2. Inventory each upstream file and classify its disposition.
3. Compare upstream FHIR resources, indexes, extensions, and workflows with local NZULM/NZMT assets.
4. Create first-party NZ adapter, schema, projection, and fixture boundaries.
5. Preserve NZMT identifiers and hierarchy relationships.
6. Keep Medsafe and PHARMAC assertions separate.
7. Validate FHIR resources and generated indexes deterministically.
8. Promote RxNav-in-a-Box to an operational local-only adapter with fallback and integration tests.
9. Add migration and compatibility-mirror notices.
10. Link requirements, track tasks, GitHub issues, tests, and evidence.

## Non-Functional Requirements

- No local file may be overwritten merely because an upstream file has the same purpose.
- Restricted terminology or medicine-source data must remain local-only unless redistribution is reviewed.
- Every imported artifact must retain source repository, path, commit, and digest.
- Test coverage for governed new code must remain above 90%.
- Mojo or Rust promotion requires Python parity and benchmark evidence.
- External repository archival is a later explicit action after verification.

## Acceptance Criteria

- The upstream bundle verifies as complete.
- Every upstream file appears in the migration inventory.
- Reconciled NZ fixtures validate and indexes regenerate deterministically.
- The NZ adapter emits canonical records with provenance and distinct regulatory/funding assertions.
- RxNav operational status is tested and accurately reported.
- Conductor and GitHub traceability is machine-checkable.
- The compatibility mirror notice points to the canonical repository.
- No existing local changes are lost.

## Out of Scope

- Immediate archival of the upstream repository.
- Public redistribution of unreviewed NZULM, NZF, SNOMED CT, RxNorm, or PHARMAC source payloads.
- Claims that FHIR projections are formally registered implementations without external evidence.
- A full global jurisdiction rollout within this migration track.
