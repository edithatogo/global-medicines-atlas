# Stable v1 measured coverage qualification

This qualification answers a narrow question: what jurisdiction and source
coverage is evidenced by the authoritative catalog and the repository's
currently executable, committed fixtures?

It does not access live services or publish data. It also does not infer that a
medicine is unapproved, unfunded or absent when a source is unqualified.

## Evidence layers

| Layer | Meaning | Promotion requirement |
|---|---|---|
| `catalogue` | The source has a validated row in the authoritative catalog. Its information domains, entities and fields are declarations, not current medicine-level evidence. | Valid catalog row. |
| `fixture` | A committed representative payload was content-hashed and executed through its named adapter. The dimensions and record count are measured from adapter output. | Fixture, implementation identity and successful local probe. |
| `live` | A current source acquisition is bound to a durable receipt and the executable capability registry declares live-receipt support. | Durable source receipt and explicit live capability. |

The layers are cumulative. A fixture cannot become live merely because the
source has a URL or an adapter. In the current offline receipt, all live counts
are zero.

## Dimension semantics

Regulatory, funding, formulary and terminology are separate dimensions. Every
source row carries both the catalog-declared primary dimension and, when a
fixture is executable, the dimensions actually emitted by its adapter.

This distinction exposes a useful boundary in the current evidence: the CMS
Part D resource is catalogued in the broader funding domain, while its fixture
emits plan-level `formulary` assertions. The receipt reports that disagreement
instead of silently relabelling the adapter output as national funding.

## Deterministic execution

Generate the receipt from the repository root:

```shell
uv run --python 3.14.6 --group dev python scripts/qualify_stable_v1_measured_coverage.py
```

Verify that the committed receipt exactly matches the catalog, schema,
qualification implementation, capability registry, adapters and fixtures:

```shell
uv run --python 3.14.6 --group dev python scripts/qualify_stable_v1_measured_coverage.py --check
```

The output is
`quality/qualifications/stable-v1-measured-coverage.json`, validated by
`schemas/stable-v1-measured-coverage-v1.json`. The receipt is canonical JSON
with a SHA-256 digest over its body. Verification rebuilds the entire receipt;
a changed catalog, fixture, adapter, schema or qualification implementation
fails closed until the evidence is reviewed and regenerated.

## Claim boundary

The receipt measures catalog rows and representative local fixtures only. It
does not claim:

- exhaustive global, national or medicine-level coverage;
- current source currency, completeness or production readiness;
- redistribution permission;
- live regulatory, reimbursement or formulary status;
- that missing evidence means a negative medicine status; or
- external publication or release approval.

Consumers must call the fail-closed `require_coverage` guard before making a
coverage-dependent claim. Requests for unknown sources, unavailable maturity
or dimensions not emitted at the requested evidence layer are rejected.
