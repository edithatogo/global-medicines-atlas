# Canonical schema v2 adapter-cohort qualification

This qualification measures canonical schema-v1 to structural schema-v2
migration over bounded fixtures already committed to the repository. It emits
a deterministic, content-bound receipt and verifies exact schema-v2 to
schema-v1 rollback for every migrated record.

Run it with Python 3.14:

```powershell
uv run --python 3.14.6 --group dev python scripts/qualify_canonical_v2_cohorts.py
```

The command regenerates
`quality/qualifications/canonical-v2-cohorts.json`. The outer
`receipt_sha256` binds the canonical JSON representation of the inner receipt.
Fixture paths and SHA-256 identities bind every measured cohort to committed
inputs.

## Measured scope

| Cohort | Records | Disposition | Assertion boundary |
| --- | ---: | --- | --- |
| Preserved NZULM/NZMT FHIR snapshot | 42 | 42 migrated with exact rollback | The canonical-v1 adapter intentionally emits no status assertions |
| Representative PMDA CSV | 1 | Migrated with exact rollback | Regulatory only |
| Representative Drugs@FDA API JSON | 1 | Blocked: committed sample omits active ingredient structure | Regulatory only |
| Representative PBS XML | 1 | Blocked: committed sample omits ingredient and product hierarchy | Funding only |
| Representative EMA CSV | 1 | Blocked: committed sample omits substance structure | Regulatory only |

The NZ cohort maps only explicit FHIR fields: NZMT identity/type, ingredient
coding, ingredient strength, dose form and package amount. The PMDA cohort uses
the explicit generic-name column as its substance label. No medicine name is
parsed to manufacture an ingredient, strength, form, package or hierarchy.
The receipt names `nzmedicines-fixtures` as the actual imported provenance;
NZULM/NZMT describes the fixture source family and is not a claim of direct
live NZULM or NZHTS acquisition. Structural identifiers are record-local and
do not claim cross-record ingredient or product deduplication.

Regulatory, funding and formulary counts are separate fields at record, cohort
and aggregate levels. In particular, EMA authorisation does not imply funding,
and PBS listing does not imply regulatory approval.

## Evidence limits

This is fixture qualification, not live-source qualification. It does not show
current or complete NZULM, NZMT, FDA, PBS, EMA or PMDA coverage; it does not
resolve source redistribution rights; and it does not qualify publication.
The preserved NZ fixture remains bound to the imported `nzmedicines` source
commit. Japanese field semantics retain the adapter's independent translation
review gate.

Blocked records are a positive fail-closed result. They demonstrate that the
migration refuses to infer schema-v2 structure from a display name. A later
adapter cohort may migrate them only after a governed fixture exposes the
required native structure and passes the same receipt and rollback checks.
