Conductor track: `conductor/tracks/global_country_adapters_20260729/`

## Phase 1 — registry and representative cohort

- [x] Define adapter and source contracts
- [x] Require a regulatory source contract
- [x] Separate regulatory, funding, formulary, and terminology dimensions
- [x] Declare NZL, AUS, USA, GBR, CAN, JPN, and EU source contracts
- [x] Add focused Python 3.14 tests

## Phase 2 — source ingestors

- [x] Implement initial NZ FHIR/NZMT canonical projection (tracked in #3)
- [ ] Add Australia ARTG and PBS ingestors
- [ ] Add US Drugs@FDA ingestor and explicit national-funding coverage semantics
- [ ] Add EU, UK, Canada, and Japan ingestors
- [ ] Record source receipts, checksums, licences, retrieval times, and fixture lineage

## Phase 3 — comparison layer

- [ ] Materialise portable Parquet assertion tables
- [ ] Add DuckDB comparison and coverage metrics
- [ ] Add temporal/conflict fixtures and end-to-end comparisons
- [ ] Pass provenance, licensing, and coverage publication gates

Related terminology resolver: #4

This issue represents declared and implemented scope only; it must not be
interpreted as a claim of global ingestion coverage.
