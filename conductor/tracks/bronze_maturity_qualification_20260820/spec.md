# Specification: Bronze maturity qualification

## Outcome

Qualify the current-scope bronze medallion layer against measurable
repository evidence. Declare Bronze mature only when every mandatory
property is evidenced. Explicit blockers complete the report but do not
make Bronze mature.

This track measures bronze. It does not implement Silver, Gold, dashboards,
or publication. It does not duplicate
`bronze_medallion_completion_20260819`; that track lands bronze, this track
qualifies it.

The immutable source payload and its content-addressed receipt are
evidentiary truth; source-faithful Parquet is the portable analytical
representation; table/catalogue layers are rebuildable metadata over those
artefacts.

## Authoritative inputs

- `conductor/requirements.md` (M-092 to M-100, S-012, S-013, W-007, W-008)
- `conductor/maturity-model.json`
- `conductor/tracks/bronze_medallion_completion_20260819/spec.md`
- `src/global_medicines_atlas/data/medicine_source_catalog.json`
- `docs/ECOSYSTEM_REUSE.md`
- Existing qualification patterns under `quality/qualifications/` and
  `schemas/stable-v1-qualification-v1.json`

## Mandatory properties

Completeness, immutability, temporal identity, provenance, rights, reuse
discovery, lineage, quarantine, reproducibility, disaster recovery,
security, performance, interoperability, and documentation.

## Evaluation rules

- Missing coverage is not negative evidence. Excluded and fixture-only
  catalog rows are not scored as incomplete bronze.
- Hugging Face publication, stable-v1 success, dashboards, and Silver/Gold
  behaviour are not bronze maturity evidence.
- An independent adversarial review is a criteria-versus-code/tests/docs
  check, not a second maintainer.
- Human gates remain: licensing conclusions, public releases, external
  dataset publication, and consequential claims.

## Acceptance

- A JSON Schema contract validates the maturity report, residual-risk
  register, and blockers.
- Tests fail closed if Bronze is declared mature while a mandatory property
  is blocked.
- The committed report is regenerated from the evaluator.
- Bronze is declared mature only when every mandatory property is evidenced.

## Out of scope

- Implementing remaining bronze landing (owned by #167).
- Silver, Gold, platinum, dashboards, or Hugging Face publication.

## External gates

- Licensing conclusions.
- Public release and external dataset publication.
- Consequential clinical or policy claims.
- Production disaster-recovery authority.
