Conductor track: `conductor/tracks/global_country_adapters_20260729/`

## Phase 1 — registry and representative cohort

- [x] Define adapter and source contracts
- [x] Require a regulatory source contract
- [x] Separate regulatory, funding, formulary, and terminology dimensions
- [x] Declare NZL, AUS, USA, GBR, CAN, JPN, and EU source contracts
- [x] Add focused Python 3.14 tests

## Phase 2 — source ingestors

- [x] Implement initial NZ FHIR/NZMT canonical projection (tracked in #3)
- [x] Add Australia ARTG and PBS ingestors
- [x] Add US Drugs@FDA ingestor and explicit national-funding coverage semantics
- [x] Add EU, UK, Canada, and Japan receipt-backed representative native-format
  ingestors
- [x] Record governed fixture receipts, checksums, rights states, retrieval
  times, and lineage; transfer current live qualification to #54

## Phase 3 — comparison layer

- [x] Materialise portable Parquet assertion tables
- [x] Add DuckDB comparison and coverage metrics
- [x] Add temporal/conflict fixtures and end-to-end comparisons
- [x] Enforce fail-closed provenance, licensing, receipt-currency, coverage,
  conflict, and exclusion publication gates

Related terminology resolver: #4

This issue represents declared and implemented scope only; it must not be
interpreted as a claim of global ingestion coverage.
