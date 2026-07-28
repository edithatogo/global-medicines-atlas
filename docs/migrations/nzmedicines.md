# nzmedicines Consolidation

[`edithatogo/global-medicines-atlas`](https://github.com/edithatogo/global-medicines-atlas)
is the canonical hosted repository and this local workspace is its canonical
implementation source. The original
[`edithatogo/nzmedicines`](https://github.com/edithatogo/nzmedicines)
repository is being incorporated as the NZULM/NZMT FHIR adapter and fixture
source.

## Preservation

- Upstream snapshot: `vendor/nzmedicines/`
- Complete Git bundle: `vendor/history/nzmedicines-all.bundle`
- Captured commit: `6a8ecfae67f15d635750d11d5f446b93d76c1865`
- Migration track: `conductor/tracks/nzmedicines_migration_20260727/`
- Canonical repository: `https://github.com/edithatogo/global-medicines-atlas`

The snapshot is immutable evidence. First-party implementation files will be created outside the vendor directory and will retain file-level provenance.

## Compatibility Plan

The upstream repository will not be archived until:

1. every upstream artifact has a recorded disposition;
2. the NZ adapter and fixtures pass validation;
3. restoration from the Git bundle is verified;
4. migration links and compatibility guidance are published;
5. the user explicitly approves the external archival or mirror change.
