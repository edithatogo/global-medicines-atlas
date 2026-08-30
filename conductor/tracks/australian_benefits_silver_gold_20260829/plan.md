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
  Loss-aware scalar conversion is being implemented; typed Arrow schemas and
  B1/v4 lineage integration remain pending. Structural coverage is not
  promoted Silver or public data.
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
- [x] Verify the review fixes against exact-head hosted checks before merge.
  PR #371 merged as `3dbf53f` after all 38 exact-head checks passed.
  Full local run: 2,888 passed, three failed,
  one skipped, 96.49% coverage; exact interpreter and unchanged timeout
  constraints remain documented, not weakened.

## Typed scalar prerequisite

- [x] Test and implement loss-aware conversion for the existing 40-field MBS
  contract: retain native text/state, string identifiers, exact AUD decimals,
  source-magnitude percentages, and explicit date-format selection.
  Implemented in `196e2a6`; 108 focused tests pass, scalar branch coverage
  100%, Ruff/ty/BasedPyright pass. PR #373 merged as `c9102e3` after all 38
  exact-head hosted checks passed. Local full diagnostic: 2,923 passed,
  four failed, one skipped; not an exact-tree certification because main was
  integrated during that run. Runtime and local timing failures are recorded.
- [~] Bind conversion to versioned Arrow tables and exact B1/v4 lineage;
  reject unrepresentable decimal precision without rounding. Scalar tests do
  not establish real-source era qualification or publication readiness.
  Six XML Arrow table candidates now retain all 40 native fields, exact B1
  receipt digests and B2 digests. Public v4 location verification, workbook/PBS
  tables and real-source date-era qualification remain pending.
- [~] Add the documented MBS DD.MM.YYYY profile alongside explicit ISO input;
  retain source text, reject calendar/format errors and bind conversion v2 to
  Arrow metadata. Official XML specification checked 2026-08-30; real-corpus
  hosted qualification remains pending rather than inferred from fixtures.
  (`1619e2b`; 10 intended failing cases followed by 150 combined focused
  passes, both changed modules at 100% branch coverage; hosted recheck pending.)

## Arrow review fixes

- [x] Remove raw receipt metadata from Arrow/Parquet; retain the exact digest
  and selected redacted provenance. Add synthetic userinfo, query credential,
  redirect, fragment and rights-reference regression tests before rechecking
  hosted CI. No raw receipt or credential publication occurred.
  (`ddb62f6`; synthetic regression red then 104 focused tests passed,
  100% module branch coverage, Ruff/ty/BasedPyright passed.)
- [x] Recheck exact-head hosted gates after the privacy fix, then merge only
  after the coordinated data-plane reader merge hold is released.
  PR #374 merged `8a5a790` after all 38 checks passed on `1d2b6af` and the
  privacy review was resolved. Final local full: 2,981 passed, four failed,
  one skipped, 96.54%; runtime/product/rehearsal limitations remain recorded.

## Legacy workbook cell prerequisite

- [x] Preserve every sheet/cell in typed storage-level Arrow candidates,
  including empty sheets, raw/display values, presence, formula caches,
  error codes, exact decimals, boolean values and field addresses.
- [x] Reject negative shared-string references and test extreme decimal
  exponents without losing native values or relying on Decimal trap settings.
  String-index guard implemented in `18d304e`; 60 focused tests passed.
  Cell candidates in `79a11ee`; 148 combined focused tests pass, static
  checks pass. PR #376 merged as `30062b2` after all 38 hosted checks passed
  on `4041086`, including the subsequent portability fix. Real-source
  qualification remains pending.
- [~] Qualify the exact legacy workbook header/style/epoch denominator in
  hosted execution and add source-specific harmonised annotation mappings.
  Cell-storage typing is not a substitute for domain/currency/date mapping.
  Storage run `33305281887` passed against the exact public workbook: 13,742
  cells, four formulas, two errors; 36 unrepresentable decimals retained
  natively. Header/style metadata now grounds strict per-column mappings;
  mapping execution passed in run `33307737257`; full semantic value
  harmonisation remains pending.
  An Actions-only pinned public workbook profiler is implemented in `ab26f90`
  (own unpublished `209e08d` rebased onto the same-tree PR #376 merge).
  All 114 focused tests pass; qualifier statement/branch coverage is 100%.
  Synthetic
  qualification checks all-sheet cell denominators, Parquet preservation,
  native headers/formats, and local-download rejection. Hosted storage and
  domain-mapping execution passed in runs `33305281887` and `33307737257`.

## Workbook portability review fixes

- [x] Record real-source storage qualification with complete sheet/cell,
  formula/error, conversion, header and native format denominators.
  Run `33305281887`; durable issue #341 receipt `5468037256`.
- [x] Bind all native cells to the observed four-sheet header profile and
  source row/column lineage without inventing meaning for unlabelled cells.
  (`7f9733b`; 88 focused passes, new module 100% branch coverage; PR #379
  merged `cccdc63` after 38 passing checks; run `33307737257` accounted for
  all 13,742 cells including 97 headers and four unlabelled cells.)
- [~] Run the extended hosted qualifier after merge to count actual header
  mappings, then continue source-specific date/currency/value harmonisation.
  Header mapping run passed; value candidates and their per-field outcome
  profiler are now implemented. Value-level real-source execution passed in
  run `33310284274`, with unsupported values explicitly retained.

## Workbook value harmonisation

- [x] Retain the durable issue receipt URL and exact hosted artifact ID/digest
  in the workbook value qualification record and append-only ledger.
  Review correction for PR #381; 11 focused/context tests pass. No rerun or
  source acquisition was needed.
  PR #381 merged `75b9b04` after 37 passing checks on `9c21326`, with the
  review resolved and exact reviewed/merged trees verified.

- [x] Review correction: leave the hosted workbook date profile unselected;
  the XML date profile does not independently qualify the workbook era.
  (`3df81f6`; 134 focused/context tests pass; Ruff, ty, BasedPyright pass.)
- [~] Independently qualify the workbook-era date format before selecting a
  conversion profile. Preserve all native dates and unsupported outcomes in
  the meantime; date functionality remains in scope.
  First observe storage and lexical-shape counts without interpreting dates;
  no workbook date conversion profile is selected by this prerequisite.
  (`10b36b0`; 10 intended missing-output regression failures preceded the
  implementation, 32 focused tests pass with 100% changed-module coverage.
  Hosted observation passed in run `33318355531`; independently qualified
  format selection remains pending.)
- [x] Keep native OOXML date storage distinct from ordinary date-shaped text.
  (`43ea70c`; P2 regression failed before correction, then 33 focused tests
  passed with 100% changed-module branch coverage; static checks pass.)
- [x] Requalify the corrected date-encoding observer on its exact hosted head;
  only then collect new observations through Actions, without selecting a
  date convention or repeating a completed qualifier version.
  PR #382 merged `72e0b76` after 39 passing checks on `ba18a8d` and resolved
  review. Run `33318355531` passed: 1,280 populated dates have two-two-four
  dotted text shape, 2,240 are missing and 22 are headers. The durable report
  and exact artifact identity are recorded; day/month order remains unqualified.

- [~] Reuse existing scalar contracts and numeric storage conversion for
  source-native identifiers, money, dates, annotation text and formula caches.
  Preserve errors, missing/null states, unsupported serial dates and precision
  loss. New value module has 100% branch coverage; 132 focused tests pass.
- [x] Complete full/hosted review, then run the extended qualifier at the
  merged commit and examine per-field value conversion outcomes before
  treating the actual source era as qualified.
  PR #380 merged `08b518d` after 38 exact-head passing checks and resolved
  review. Run `33310284274` passed: all 13,742 cells accounted for, 924
  converted, 36 unrepresentable decimals and 1,280 unqualified dates retained.
  No date-era qualification, semantic promotion or publication is inferred.

- [x] Preserve sheet identity when combining batches and round-tripping
  Parquet, including an explicit empty-sheet manifest and property presence.
  (`dd5e02a`; intended regression failure followed by 149 focused passes;
  Ruff, ty and BasedPyright pass.)
- [x] Recheck exact-head hosted gates after integration with PR #375.
  PR #376 merged as `30062b2` on 2026-08-30T08:49:37Z with all 38 checks
  passing on `4041086` and the P1 portability review resolved.
  Previous-head full: 3,006 passed, three failed, one skipped, 96.56% coverage;
  two interpreter-pin failures and a product-runner failure that passed one
  bounded isolated rerun. This is not an all-green local-full claim.

## Phase 2: Implement MBS Silver (AC-01, AC-02, AC-06)

- [x] Correct the hosted qualifier job-name policy finding without weakening
  security lint. (`7e049cd`; actionlint and zizmor 1.28.0 pedantic pass.)
- [x] Recheck PR #378 exact-head hosted gates before real-workbook dispatch.
  Merged as `11a8c4f` with 38 passing checks on `ceed3e1`; no review threads.
  Read-only pinned workbook run `33305281887` passed. Metadata receipt and
  exact summary digest retained; no dataset publication or semantic promotion.

- [~] Write failing golden, property, malformed-input, schema-drift,
  determinism, decimal/currency, date, formula-error, duplicate, and lineage
  tests for each MBS table.
  XML candidate tests cover every field, all six destinations, exact decimal
  overflow/scale rejection, explicit dates, duplicate item occurrences,
  receipt mismatch, bounded batching and deterministic Parquet round trips.
  Legacy annotations, temporal changes and publication tests remain pending.
- [~] Confirm the intended failure before implementation.
  Missing `mbs_silver` module observed for the XML table slice.
- [~] Implement streaming source-faithful MBS service, hierarchy, description,
  fee/benefit, participant, and legacy annotation tables.
  XML candidates use the existing 9 MB bounded parser and at most 4,096 rows
  per Arrow batch; this is bounded parsing plus batch output, not unbounded
  input streaming or complete real-corpus qualification.
- [ ] Add explicit schema-era mappings and historical/current change events
  without overwriting source values.
- [ ] Emit field-level lineage, coverage denominators, quality findings, and
  promotion candidates.
- [ ] Phase Verification & Checkpoint: every MBS source field is preserved or
  explicitly mapped with deterministic output evidence.

## Phase 3: Implement PBS Silver (AC-01, AC-02, AC-03)

- [x] Add bounded Arrow native-field candidates over the existing PBS
  inventory, preserving ordered element/text/tail/attribute identities and
  exact B1/B2 bindings. Synthetic qualification only; domain tables,
  typed value harmonisation and real-corpus qualification remain pending.
  Implemented `39f3b20`; 118 focused/context tests pass, new module 100%
  branch coverage; Ruff, ty and BasedPyright pass. PR #385 merged `b7663bc`
  after 38 checks passed on `70e88be`; full local limitations are recorded.
- [x] Map fixture-established PBS structural families to candidate table
  destinations with native item-occurrence lineage. Preserve unknown fields;
  price/date conversion and full domain harmonisation remain pending.
  Implemented `8a8650a`; 105 focused/context tests pass, new module 100%
  branch coverage; Ruff, ty and BasedPyright pass. PR #386 merged `f3aaf16`
  after 38 checks passed on `caa99f2`; local full limitations remain recorded.
- [~] Build bounded element-level item/presentation/reference candidate rows
  with parent and item occurrence lineage, explicit native text/tail/ID states
  and all original field slots, including unknowns. Synthetic-only scope;
  date/price conversion and domain-wide completeness remain pending.
  Implemented `a4bc2fe`; 115 focused/context passes, 98.70% new-module
  coverage; Ruff, ty and BasedPyright pass. Full/hosted review pending.

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
