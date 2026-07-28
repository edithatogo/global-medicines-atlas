# Implementation Plan

## Phase 1: Registry and first cohort

- [x] Define jurisdiction source and adapter protocols.
- [x] Require regulatory source coverage at registration.
- [x] Keep regulatory, funding, formulary, and terminology dimensions separate.
- [x] Register NZL, AUS, USA, GBR, CAN, JPN, and EU source contracts.
- [x] Add duplicate, missing-regulatory, cohort, and separation tests.
- [x] Verify focused Python 3.14 Test-Goblin suite.
- [x] Create the initial machine-readable API/download/source catalog.
- [x] Record access mode, cadence, rights status, readiness, and evidence limits.
- [x] Add catalog integrity and first-cohort coverage tests.

## Phase 2: Source ingestors

- [~] Implement and harden the NZ FHIR/NZMT ingestor in the migration track.
- [ ] Add Pharmac production XML and Medsafe registry adapters with separate
  funding and regulatory assertions.
- [ ] Add Australian ARTG discovery/export and PBS API/XML adapters.
- [~] Add US regulatory and funding adapters while explicitly modelling the
  absence of one national medicines funding list.
  - [x] Implement fixture-driven Drugs@FDA bulk product/status projection.
  - [ ] Add receipt-backed Drugs@FDA acquisition and API/bulk parity checks.
  - [ ] Add CMS Part D plan-level formulary and pricing projection.
- [ ] Add Health Canada DPD API/bulk and NOC extract adapters.
- [ ] Add EU Union Register/EMA medicine downloads and national-register
  expansion contracts.
- [ ] Add MHRA, NICE syndication/appraisal, and licensed NHS dm+d adapters.
- [ ] Add PMDA approval and MHLW NHI price-list adapters.
- [ ] Record receipts, checksums, licences, retrieval times, and fixture lineage.
- [ ] Add contract tests that compare API and bulk representations where both
  exist.

## Phase 3: Global comparison

- [x] Materialise portable Parquet assertion tables.
- [x] Add DuckDB queries and coverage metrics.
- [ ] Add temporal and conflicting-source fixtures.
- [ ] Add end-to-end country comparison tests.
- [ ] Publish only after provenance, licence, and coverage gates pass.

## Phase 4: Global source census

- [~] Use WHO database and regulatory-authority directories as discovery
  denominators, not product-level approval evidence.
- [ ] Add WLA/ML3/ML4 jurisdictions and their official medicine registers.
- [ ] Add national HTA, reimbursement, formulary, and public price sources.
- [ ] Add Brazil, South Korea, Singapore, Switzerland, India, South Africa,
  Gulf-region, Latin-American, and African regional priority cohorts.
- [ ] Measure countries with regulatory source, funding source, API, bulk
  download, implemented ingestion, and current receipt.
- [ ] Schedule source-health and schema-drift monitoring.
