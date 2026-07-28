# Consolidate nzmedicines into the canonical global medicines monorepository

**Conductor track:** `conductor/tracks/nzmedicines_migration_20260727/`  
**GitHub issue:** https://github.com/edithatogo/global-medicines-atlas/issues/1  
**Requirements:** M-010–M-014, M-020–M-025, M-050–M-053  
**Type:** Refactor / migration  
**Status:** Active — Phase 1 complete; Phase 2 active

## Outcome

Every relevant artifact from `edithatogo/nzmedicines` is preserved, reconciled, and incorporated as the NZULM/NZMT FHIR adapter and fixture package without losing richer local work.

## Acceptance evidence

- Verified complete upstream Git bundle.
- Immutable snapshot tied to commit `6a8ecfae67f15d635750d11d5f446b93d76c1865`.
- File-level migration inventory.
- Passing NZ adapter, FHIR fixture, index-regeneration, and RxNav integration harnesses.
- Compatibility-mirror notice and restoration instructions.

## Planned subissues

1. Preserve and reconcile upstream history and files.
2. Build the NZ adapter and FHIR fixture boundary.
3. Operationalize RxNav-in-a-Box.
4. Integrate maximal harness and CI/CD.
5. Prepare compatibility mirror and migration handoff.
