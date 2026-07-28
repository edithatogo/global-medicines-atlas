# Global Medicines Atlas

Global Medicines Atlas is an evidence-first system for comparing medicine
regulatory approval, public funding, formulary status, and terminology across
jurisdictions.

The project keeps those dimensions independent. A terminology match, product
listing, price, or formulary entry is never treated as regulatory approval
without source-specific evidence.

## Current scope

- New Zealand NZULM/NZMT and FHIR adapter boundary.
- Tiered offline-first RxNorm/RxNav-compatible terminology resolution.
- Governed global API and downloadable-source catalog.
- Initial country contracts for New Zealand, Australia, the United States,
  United Kingdom, Canada, Japan, and the European Union.
- Fixture-driven Drugs@FDA bulk projection.

Detailed requirements, design, plans, and evidence are under
[`conductor/`](conductor/index.md). GitHub issues mirror each active Conductor
track in the
[Global Medicines Atlas Conductor Project](https://github.com/users/edithatogo/projects/35).

## Data boundaries

The repository does not publish the local NZULM release, restricted
terminologies, credentials, or derived private research outputs. Source
catalog entries describe access surfaces; they do not claim complete ingestion
or global coverage.
