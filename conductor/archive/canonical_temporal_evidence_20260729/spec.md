# Specification: Canonical Temporal Evidence

Archived implementation specification; live promotion remains governed by #54.

## Outcome

Deliver v0.4 evidence storage that preserves source-effective and
system-observation time, supersession, conflicts and measured coverage without
collapsing regulatory and funding assertions.

## Requirements

- M-001 to M-005, M-030 to M-035, M-071 and M-078.
- Version Arrow/Parquet schemas and deterministic migrations.
- Preserve immutable source snapshots and transformation lineage.
- Represent conflicting, missing, unknown and not-covered evidence explicitly.

## Acceptance

- Golden and property tests cover temporal boundaries and conflicting sources.
- DuckDB queries reproduce point-in-time and as-observed views.
- Schema migrations are deterministic and backward compatibility is documented.

## Out of scope

- Inferring status from missing evidence.
- Public release before rights and coverage gates pass.
