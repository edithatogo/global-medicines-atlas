# Bronze maturity qualification

The machine-readable report is
[`quality/qualifications/bronze-maturity.json`](../../quality/qualifications/bronze-maturity.json).
The schema is
[`schemas/bronze-maturity-qualification-v1.json`](../../schemas/bronze-maturity-qualification-v1.json).

The current qualification horizon is the maintainer-approved, versioned
`bronze-bounded-public-scope-v1`: 42 source IDs with existing observable
landing evidence. The checked-in report retains full-universe accounting for
all 157 public/no-credential sources, including the 115 deferred sources that
still lack qualifying landing evidence. The [scope decision](../../quality/qualifications/bronze-bounded-scope-decision-v1.json)
is hash-bound to the full source universe, and the [future-source ledger](./bronze-bounded-scope-future-sources.md)
records each deferred source's reason and next action. Deferral does not imply
negative medicines evidence or grant source rights or acquisition authority.

The separate [receipt-backed cohort report](../../quality/qualifications/bronze-receipt-cohort-v1.json)
remains a narrower measure: 28 direct successful source receipts. It retains
the original 157-source assessment and does not replace the 42-source bounded
horizon.

Bronze is mature only when every mandatory property is evidenced. Explicit
blockers keep the report complete; they do not declare maturity.

The three-strata substrate result is separate and independent:
[`quality/qualifications/bronze-three-strata-qualification.json`](../../quality/qualifications/bronze-three-strata-qualification.json)
(schema
[`schemas/bronze-three-strata-qualification-v1.json`](../../schemas/bronze-three-strata-qualification-v1.json))
records `three_strata_qualified` for the B0/B1/B2 authority boundary and
rebuildable projections. A qualified three-strata substrate does not imply
`bronze_mature`: live acquisition completeness remains a distinct blocker.

Hugging Face publication, stable-v1 qualification success, dashboards, and
Silver/Gold behaviour are not bronze evidence. Missing catalog coverage is
not negative evidence.
