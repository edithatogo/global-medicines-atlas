# Implementation Plan

Archived after reviewed implementation merged in PR #59.

## Phase 1: Evaluation contract

- [x] Task: Define mapping candidate, feature and adjudication schemas
- [x] Task: Build positive, negative, ambiguous and multilingual fixtures
- [x] Task: Define precision, recall, calibration and abstention gates
- [x] Task: Phase Verification & Checkpoint

## Phase 2: Retrieval and scoring

- [x] Task: Implement deterministic identifier and lexical matching
- [x] Task: Integrate tiered RxNorm fallback and optional semantic retrieval
- [x] Task: Add explainable confidence and abstention behavior
- [x] Task: Phase Verification & Checkpoint

## Phase 3: Qualification

- [x] Task: Add review queue and reproducible index generation
- [x] Task: Add Mojo/Rust parity only where benchmarks justify promotion
  - [x] Keep Python 3.14 authoritative because no representative-scale
    benchmark or Scalene evidence yet justifies Mojo, Rust, or Tantivy
    promotion.
- [x] Task: Record fail-closed v0.5 quality and limitation evidence
- [x] Task: Phase Verification & Checkpoint
