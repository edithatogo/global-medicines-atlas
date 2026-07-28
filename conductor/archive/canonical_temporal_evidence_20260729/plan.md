# Implementation Plan

Archived after reviewed fixture/software qualification merged in PR #57.

## Phase 1: Contracts and tests

- [x] Task: Define bitemporal assertion and conflict schemas
- [x] Task: Write golden, property and malformed-input tests
- [x] Task: Phase Verification & Checkpoint

## Phase 2: Reference implementation

- [x] Task: Implement Python 3.14/Polars reference transformations
- [x] Task: Materialise deterministic Parquet and DuckDB views
- [x] Task: Add schema migration and compatibility fixtures
- [x] Task: Phase Verification & Checkpoint

## Phase 2 review fixes

- [x] Task: Retain restrictions and source provenance in schema v2
- [x] Task: Require timezone-aware temporal and query clocks
- [x] Task: Enforce exact effective and valid interval consistency
- [x] Task: Re-run focused and repository-wide verification

## Phase 3: Qualification

- [x] Task: Add governed temporal receipt and coverage-denominator machinery
  - [x] Add immutable receipt and governed acquisition contracts
  - [x] Add temporal coverage denominators and DuckDB views
  - [x] Add fixture-only snapshot and lineage qualification
  - [x] Transfer lawful live-payload and defensible live-denominator
    qualification to GitHub issue #54
- [x] Task: Run full Test-Goblin, typing, security and regeneration gates
  - [x] Add two-order deterministic regeneration profile
  - [x] Pass local tests, coverage, Ruff, ty and strict BasedPyright
  - [x] Pass hosted mutation, security, dependency and CodeQL gates
- [x] Task: Record fail-closed v0.4 release-evidence machinery
  - [x] Add fail-closed release-evidence model, schema and CLI
  - [x] Prove fixture evidence cannot satisfy live qualification
  - [x] Transfer lawful live-qualified v0.4 evidence and release approval to
    GitHub issue #54 without creating a false live-qualified record
- [x] Task: Phase Verification & Checkpoint — fixture/software qualification
  complete; live promotion remains external in #54
