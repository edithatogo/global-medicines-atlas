# Bronze maturity qualification

The machine-readable report is
[`quality/qualifications/bronze-maturity.json`](../../quality/qualifications/bronze-maturity.json).
The schema is
[`schemas/bronze-maturity-qualification-v1.json`](../../schemas/bronze-maturity-qualification-v1.json).

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
