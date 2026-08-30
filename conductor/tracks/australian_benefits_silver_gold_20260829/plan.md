# Plan: Australian benefits Silver and Gold

## Phase 1: Freeze source denominators and semantics (AC-01, AC-03)

- [x] Write failing schema-coverage tests against every MBS XML field, workbook
  sheet/column/formula state, and PBS v3 source element in the approved fixtures.
  (`70cdbec`; 38 synthetic contract tests, 100% module branch coverage.)
- [x] Confirm the intended failure before implementation.
  (Missing `australian_source_contracts` module before implementation.)
- [~] Define versioned MBS service-benefit and PBS funding/formulary semantic
  contracts, native row identities, schema eras, currency/time/null rules, and
  prohibited cross-dimension coercions.
  Native JSON contracts, all 40 MBS field destinations/types, full workbook
  cell-property and PBS element/attribute/text inventories now exist.
  Typed Arrow schemas, currency/date conversion and B1/v4 lineage integration
  remain pending; structural coverage is not promoted Silver or public data.
- [~] Add negative tests for MBS-as-medicine, PBS-as-regulatory,
  terminology-as-funding, candidate-as-reviewed, and absence-as-negative status.
  Source-table contracts reject these coercions; later typed/graph APIs still
  require their own negative controls. No candidate promotion API is added.
- [ ] Phase Verification & Checkpoint: field and semantic denominators are
  complete and fail closed.

## Source-contract review fixes

- [x] Express domain and value-state constraints in portable JSON schemas;
  preserve OOXML property presence rather than guessing absent/null states.
  (`10c5a8a`; 57 focused tests, 100% native-contract module coverage.)
- [~] Verify the review fixes against exact-head hosted checks before merge.
  Prior head passed 38 checks. Full local run: 2,888 passed, three failed,
  one skipped, 96.49% coverage; exact interpreter and unchanged timeout
  constraints remain documented, not weakened.

## Phase 2: Implement MBS Silver (AC-01, AC-02, AC-06)

- [ ] Write failing golden, property, malformed-input, schema-drift,
  determinism, decimal/currency, date, formula-error, duplicate, and lineage
  tests for each MBS table.
- [ ] Confirm the intended failure before implementation.
- [ ] Implement streaming source-faithful MBS service, hierarchy, description,
  fee/benefit, participant, and legacy annotation tables.
- [ ] Add explicit schema-era mappings and historical/current change events
  without overwriting source values.
- [ ] Emit field-level lineage, coverage denominators, quality findings, and
  promotion candidates.
- [ ] Phase Verification & Checkpoint: every MBS source field is preserved or
  explicitly mapped with deterministic output evidence.

## Phase 3: Implement PBS Silver (AC-01, AC-02, AC-03)

- [ ] Write failing tests for schedules, items, presentations, restrictions,
  prices, effective dates, AMT references, ATC codes, namespaces, schema drift,
  and source-native identity.
- [ ] Confirm the intended failure before implementation.
- [ ] Implement bounded PBS v3 source-faithful tables and harmonised medicine
  references using the existing canonical medicine model.
- [ ] Keep PBS funding/formulary, ARTG regulatory, AMT terminology, and ATC
  classification assertions independent in storage, lineage, and coverage.
- [ ] Phase Verification & Checkpoint: PBS Silver is complete for the approved
  denominator without restricted terminology payload publication.

## Phase 4: Implement Gold graph contracts (AC-04, AC-05)

- [ ] Acquire and load SNOMED CT-AU RF2 into a rights-constrained terminology
  projection only after exact source/version/access/reuse approval; preserve
  native concepts, descriptions and relationships with receipts and tests.
  Keep restricted bytes out of public products; absence of approval is blocked,
  not completed. This preserves the donor's unimplemented acquisition intent.
- [ ] Acquire complete AMT hierarchy and official AMT/SNOMED mappings only
  after exact source/version/access/reuse approval; test native identifiers,
  relationship coverage and versioned lineage separately from PBS references.
- [ ] Acquire complete ATC hierarchy only after source-specific rights and
  denominator approval; preserve versioned parent/child evidence separately
  from the ATC codes already extracted from PBS records.
- [ ] Write failing JSON/Arrow schema, semantic, property, negative-control,
  confidence, review-state, temporal, contradiction, and rights tests for nodes
  and edges.
- [ ] Confirm the intended failure before implementation.
- [ ] Generate stable node/edge tables for MBS, PBS, medicines, restrictions,
  source documents, organizations, and terminology references.
- [ ] Implement official/source-explicit and deterministic mappings first;
  isolate lexical, ontology-assisted, embedding, and NLP candidates.
- [ ] Add adjudication queues, calibrated thresholds, conflict/supersession, and
  review receipts before any candidate promotion.
- [ ] Phase Verification & Checkpoint: every edge is evidence-bearing and no
  candidate class can masquerade as an authoritative link.

## Phase 5: Historical comparisons and publication (AC-06, AC-07)

- [ ] Write failing tests for additions, cessations, renumbering, fee/benefit/
  restriction changes, schema-era drift, source failures, missing periods, and
  current-versus-legacy labels.
- [ ] Confirm the intended failure before implementation.
- [ ] Build deterministic change/event and comparison tables with explicit
  denominators and uncertainty.
- [ ] Publish Silver, Gold, lineage, coverage, promotions, and v4 identities to
  public Hugging Face through the hosted data-plane workflow.
- [ ] Verify token-free clean-room regeneration and remove only verified
  transient local outputs.
- [ ] Phase Verification & Checkpoint: old-versus-new analysis is reproducible,
  public, and cannot be mistaken for complete current coverage.

## Phase 6: Integrated qualification (AC-08)

- [ ] Run focused, property, metamorphic, mutation, performance, coverage,
  Ruff, `ty`, BasedPyright, security, rights, provenance, regeneration, and full
  Test-Goblin lanes where supported.
- [ ] Run Conductor review, repair findings, open scoped pull requests, wait for
  hosted checks, merge, and reconcile all evidence.
