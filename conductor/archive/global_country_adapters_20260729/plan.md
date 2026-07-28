# Implementation Plan

Archived after reviewed implementation merged in PR #55. External qualification
continues in GitHub issue #54.

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

- [x] Implement and harden the NZ FHIR/NZMT ingestor in the migration track.
- [x] Add Pharmac production XML and Medsafe registry adapters with separate
  funding and regulatory assertions.
- [x] Add Australian ARTG discovery/export and PBS XML adapters; record PBS
  XML as the selected canonical surface without claiming an unevidenced API.
- [x] Add US regulatory and funding adapters while explicitly modelling the
  absence of one national medicines funding list.
  - [x] Implement fixture-driven Drugs@FDA bulk product/status projection.
  - [x] Add receipt-backed Drugs@FDA acquisition and API/bulk parity checks.
  - [x] Add CMS Part D plan-level formulary and pricing projection.
- [x] Add Health Canada DPD API/bulk and NOC extract adapters.
  - [x] Define separated, receipt-backed synthetic source contracts.
  - [x] Parse representative native DPD and NOC formats.
- [x] Add EU Union Register/EMA medicine downloads and national-register
  expansion contracts.
  - [x] Define separated, receipt-backed synthetic source contracts.
  - [x] Parse representative native EMA and Union Register formats.
- [x] Add MHRA, NICE syndication/appraisal, and a fail-closed licensed NHS dm+d
  dependency declaration.
  - [x] Define separated MHRA/NICE fixture contracts and dm+d access gate.
  - [x] Parse representative native MHRA and NICE formats.
- [x] Add PMDA approval and MHLW NHI price-list adapters.
  - [x] Define separated, receipt-backed synthetic source contracts.
  - [x] Parse representative native PMDA and MHLW formats.
- [x] Record receipts, checksums, rights states, retrieval times, and fixture
  lineage without claiming fixture receipts are current live-source evidence.
  - [x] Enforce fixture receipt and payload lineage.
  - [x] Transfer current live-source, rights, dm+d access, and translation
    qualification to durable follow-up issue #54.
- [x] Add contract tests that compare API and bulk representations where both
  exist.
  - [x] Qualify fixture-level Drugs@FDA API/bulk parity.
  - [x] Qualify fixture-level Health Canada DPD API/bulk parity.
  - [x] Do not claim PBS parity because XML is the selected acquisition surface.

## Phase 3: Global comparison

- [x] Materialise portable Parquet assertion tables.
- [x] Add DuckDB queries and coverage metrics.
- [x] Add temporal and conflicting-source fixtures.
- [x] Add end-to-end country comparison tests.
- [x] Enforce fail-closed publication gating over provenance, rights, live
  receipt currency, declared denominators, coverage, conflicts, and exclusions.

## Phase 4: Global source census

- [x] Use WHO database and regulatory-authority directories as discovery
  denominators, not product-level approval evidence.
- [x] Add WLA/ML3/ML4 jurisdiction fields pending live receipt verification,
  separate from product evidence.
- [x] Add national HTA, reimbursement, formulary, and public price sources.
- [x] Add Brazil, South Korea, Singapore, Switzerland, India, South Africa,
  Gulf-region, Latin-American, and African regional priority cohorts.
- [x] Measure countries with regulatory source, funding source, API, bulk
  download, implemented ingestion, and current receipt.
- [x] Schedule bounded source-health and schema-drift monitoring without
  retaining restricted source payloads.
