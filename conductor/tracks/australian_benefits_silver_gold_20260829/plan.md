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
- [x] Build bounded element-level item/presentation/reference candidate rows
  with parent and item occurrence lineage, explicit native text/tail/ID states
  and all original field slots, including unknowns. Synthetic-only scope;
  date/price conversion and domain-wide completeness remain pending.
  Implemented `a4bc2fe`; 115 focused/context passes, 98.70% new-module
  coverage; Ruff, ty and BasedPyright pass. PR #387 merged `d84c887` after
  all 38 checks passed on `739ceef`; frozen local full: 3,151 passed,
  two interpreter-pin failures, one skipped (96.67% coverage).

- [x] Entity review fix: reuse the nested Arrow schema once per input rather
  than reconstructing it for every source element. (`a5766dc`; regression
  red at 10 constructions instead of one; 116 focused/context passes,
  98.78% coverage, static checks pass. Fresh hosted recheck passed in #387.)

- [x] Annotate entity rows with fixture-supported literal item identifiers,
  AMT reference text/RDF resource attributes and exact type=ATC references.
  Preserve unknowns, duplicate occurrences and missing/empty distinctions;
  bounded source-local diagnostics must not imply vocabulary resolution,
  medicine equivalence or funding/regulatory assertions. Synthetic-only;
  real-corpus qualification and date/price contracts remain pending.
  Implemented `ae319f2`; 138 focused/context/ecosystem tests pass, 99.37%
  module coverage; Ruff, ty and BasedPyright pass. PR #388 merged `b6d4f4f`
  after all 38 checks passed on `59e0ea1`. Frozen local full: 3,172 passed,
  two interpreter-pin failures, one skipped, 96.69% coverage; performance pass.

- [x] Add fixture-supported date-slot candidates with an explicit opt-in
  calendar-date profile, native values/states, exact field and occurrence
  lineage, and duplicate/repeated element preservation. Keep unsupported
  formats and invalid dates visible; no source-era qualification, precedence,
  status, interval, timezone, price or entitlement inference.
  Implemented `c83b367`; 160 combined focused/context/ecosystem passes,
  final 23 date tests pass; 99.09% module coverage. Ruff, ty and BasedPyright
  pass. PR #389 merged `77d52c4` after 38 checks passed on `d82e350`.
  Frozen local full: 3,194 passed, three failed, one skipped, 96.70% coverage;
  two interpreter-pin failures and product latency failure (one isolated
  rerun passed). No all-green local-full or real-corpus qualification claim.

- [x] Bind historical PBS archive B1/B2 to its exact XML member with source
  identity unchanged, required parent receipt digest, archive/member byte
  evidence, native member path and explicit extraction relationship.
  Revalidate all inputs; preserve ordinary adapter/source checks. Candidate
  identity only, not source aliasing, admission or automatic date selection.
  Implemented `4cb2922`; 216 focused/context/ecosystem passes, 100% new-module
  coverage; Ruff, ty and BasedPyright pass. PR #390 merged `2cd028f` after
  38 checks passed on `f4debba`; frozen-full limitations remain recorded.

- [x] Member bridge review fixes: reject a declared ZIP member size that
  differs from bytes read, and regenerate the adapter-content-bound measured
  coverage receipt without changing coverage/qualification claims.
  (`d416b57`; intended size-mismatch regression failure, then 242 focused
  passes; 100% bridge coverage and static checks pass. Receipt diff only
  adapter digest/size and outer receipt digest. Fresh hosted checks passed
  in #390; original full-run failures remain in evidence.)

- [x] Add a separate historical-member native/Silver entry point requiring
  exact parent B1, archive B2 and validated member binding before output.
  Preserve historical source identity, unknown/native slots and occurrence
  lineage without broadening ordinary source acceptance or selecting dates.
  Implemented `22d20b6`; 233 combined focused/context/ecosystem passes,
  final 18 historical tests pass; 98.94% combined new-module coverage.
  Ruff, ty, BasedPyright and measured-receipt check pass. PR #391 merged
  `f1da9c2` after all 38 checks passed on `62dad1d`. Frozen full: 3,240 passed,
  three failed, one skipped, 96.72% coverage. Two local interpreter-pin
  failures and performance 332.240ms >250ms; isolated rerun also failed at
  266.143ms. Local performance remains unqualified despite hosted success.

- [x] Extend historical native candidates through shared bounded domain and
  entity transforms, preserving parent/archive/member binding in rows and
  metadata without broadening ordinary source acceptance. Unknown namespaces,
  empty/mixed-text elements and duplicate identities must survive unchanged.
  Historical reference/date projections and real-corpus qualification remain
  pending; no automatic date profile, admission or publication.
  Implemented `4ae27b5`; intended missing-module failure followed by 230
  focused/context/ecosystem passes and 99.37% changed-module coverage.
  Ruff, ty and BasedPyright pass. PR #392 merged `3bb5c71` after all 38 checks
  passed on `4aba9ee`; frozen full: 3,263 passed, three failed, one skipped,
  96.73% coverage. Two local interpreter-pin failures and PERF388.551ms >250ms;
  one isolated rerun passed. Original local-full failure remains recorded.

- [x] Reuse shared reference/date candidate transforms behind explicit
  historical wrappers requiring validated original inputs for every pass.
  Preserve all lineage and reject cross-pass identity drift; retain bounded
  literal/ambiguous/unresolved diagnostics and default-unselected dates.
  No factory admission bypass, ordinary-source broadening or real-era claim.
  Implemented `e31bf74`; intended missing-module failure followed by 259
  focused/context/ecosystem passes, 99.33% changed-module coverage and
  Ruff/ty/BasedPyright passes. PR #393 merged `bcd366f` after 38 checks passed
  on `86e0171`. Frozen full: 3,292 passed, three failed, one skipped, 96.73%
  coverage; two local interpreter pins and PERF302.979ms >250ms. Single
  isolated rerun passed; original local-full failure remains recorded.

- [x] Add a synthetic-tested historical structural/storage qualification
  report over independent ordered XML-slot digests and complete denominators
  for all five projections, with top-level/nested occurrence lineage and
  metadata-aware per-batch Parquet parity. Emit counters/IDs, not raw text;
  keep dates unselected and real-corpus/source-era qualification separate.
  Implemented `55f0df1`; intended missing-module and occurrence-corruption
  failures followed by 272 focused/context/ecosystem passes, 100% qualifier
  branch coverage and static passes. PR #394 merged `af2db13` after 38 checks
  passed on `70867aa`; frozen full: 3,305 passed, three failed, one skipped,
  96.74% coverage. Two local interpreter pins and PERF794.238ms >250ms;
  single isolated rerun passed. Original full failure remains recorded.

- [x] Prepare an Actions-only pinned public historical PBS qualifier harness,
  anonymously restoring original B1 and ZIP, extracting the exact member,
  checking all five projections and durably posting bounded aggregate receipts
  to issue #341. Preserve source identity, deny local/mutable/private/unsafe
  retrieval and keep dates unselected. Implementation does not authorize or
  dispatch a run; reconcile exact commit, existing public inputs and read-only
  authority first. See `docs/qualification/pbs-public-qualification.md`.
  Implemented `ce41c25`; 304 focused/context/ecosystem passes, 98% combined
  harness/CLI coverage; Ruff/ty/BasedPyright/actionlint/zizmor pass. Public
  metadata and original B1 validation pass; no source ZIP/XML downloaded.
  PR #395 merged `a65469c` after all 38 checks passed on `5ffefd6`.
  Frozen full: 3,337 passed, three failed, one skipped, 96.75%; two local
  interpreter pins and PERF452.868ms >250ms, isolated rerun passed. Original
  failure retained. Authorized run `33334961106` failed with only a generic
  receipt; actual corpus qualification remains unobserved.

- [x] Hosted qualifier review fix: isolate the synthetic deadline clock from
  process-wide test-runner time. (`9d782bb`; clock-identity regression failed
  before correction, then 304 focused/context/ecosystem tests passed; Ruff
  pass. Production harness unchanged; fresh hosted gates passed in #395.)

- [x] Diagnose the failed hosted qualifier with fixed allowlisted stage and
  error-category receipts, without exception text, source values or signed
  URLs. Preserve all context/network/integrity limits, add synthetic redaction
  and stage regressions, and reconcile the reviewed merged correction before
  one coordinated retry. Metadata-only reproduction identified exact Hub cache
  redirects rejected by the client: encoded nested suffix and encoded
  original-path query with an empty value. Support only their exact pinned
  forms (bare key or empty assignment), with mutable,
  unrelated, traversal, double-encoding and unknown/duplicate-query negatives.
  This client defect is not a source defect or corpus qualification result.
  Implemented `dc0c65a`; 63 harness tests pass, 98.62% changed-module coverage.
  Final affected run: 286 pass and one unchanged date-property timing failure;
  isolated date rerun also timed out. Earlier affected run passed 284 tests.
  Ruff/ty/BasedPyright/actionlint/zizmor pass; live metadata-only public state,
  manifest and original B1 digest/identity recheck passed. Frozen full at
  `d2ec48b`: 3,362 passed, nine failed, one skipped, 96.76%; exact interpreter
  pins and product/rehearsal/monitoring/preregistration failures retained.
  Single isolated product rerun also failed PERF835.390ms >250ms; local
  performance remains unqualified. Hosted coverage passed 3,371 tests with
  one skip. PR #396 merged `3ca5b6e` after all 38 final-head checks passed on
  `29fd88c`; exact merged/reviewed trees verified. Corrected run `33336369595`
  failed later at receipt-read/transport, not the original redirect guard.

- [x] Add fixed transport subclass diagnostics and one shared run-wide retry
  for connection/read/remote-protocol failures only. Preserve original deadline,
  per-attempt byte/hop and exact source guards; close/discard partial responses,
  restart from the pinned URL and retain the initial failure's fixed codes in
  all resulting receipts. Timeouts, policy, integrity and decoding failures
  remain terminal. Metadata-only B1/manifest recheck passed; the original
  transport subclass is unknown. Test, review and merge before hosted retry.
  Implemented `2ce70fa`; four intended red failures followed by 300 combined
  focused/context/ecosystem passes and 78 final harness passes, 98.81% changed
  coverage. Static/security checks pass; pre-freeze agent review strengthened
  exact subtype assertions. Frozen full `4c73c76`: 3,379 passed, seven failed,
  one skipped, 93.75%; two interpreter pins, product latency, three rehearsal
  timeouts and a worker SIGSEGV in unchanged product CLI. Isolated crash/context
  checks passed; isolated product latency still failed at 822.028ms >250ms.
  Local limitations retained. All 38 final-head hosted gates subsequently
  passed on `3592864`; #397 merged as `f7550d5` with exact tree agreement.

- [x] Review documentation correction: distinguish the earlier dispatched
  redirect fix from the pending transport-recovery version. (`30d9a08`;
  context validation passes; no production change after frozen full.)

- [x] Diagnose the 55-minute timeout from run `33337502925` and retain
  timeout-surviving, fixed aggregate progress without raw payload logging.
  Transport recovery merged as #397 (`f7550d5`) after all 38 checks passed
  on `3592864`; closure is issue #341 comment `5471468401`. The subsequent
  run failed at the unchanged timeout; fallback comment `5471752828` has no
  stage or retry evidence. Synthetic profiling identifies row conversion and
  JSON encoding as material costs, not proof of the real timeout stage.
  Add atomic incomplete checkpoints for stages, projection phases, processed
  batch/row prefixes, elapsed time and retry-budget consumption; verify
  interrupted writes preserve the previous digest-bound receipt. No dispatch,
  timeout increase, raw local data, HF writes or corpus-promotion claim.
  Implemented `34e36c9`; 102 focused tests pass with 99.00% coverage.
  Broader tests: 310 passes, two unchanged Hypothesis timing failures retained.
  Ruff, ty, BasedPyright, actionlint and offline pedantic zizmor pass.
  Frozen full `a4b59b5`: 3,393 passed, four failed, one skipped, 96.78%
  coverage. Failures: two local interpreter-pin mismatches, product runner
  25-second timeout, monitoring script 30-second timeout. One isolated product
  rerun failed at 936.516ms >250ms; no thresholds relaxed. All 38 hosted checks
  passed on that head with no review threads. PR #398 subsequently merged
  `e7124b7` after all 38 checks passed on final head `e537cda`; reviewed and
  merged trees match. Closure: issue #341 comment `5473211434`. Checkpoint
  implementation is complete; the real-corpus timeout stage remains unknown.
- [~] Optimize measured redundant projection/serialization work with exact
  output, lineage, bound and call-count regression tests; preserve independent
  denominator and per-batch Parquet verification. Review/merge before deciding
  whether another pinned hosted qualification run is warranted.
  First bounded slice: preserve native Arrow buffers and slice offsets while
  materializing only record ID and source digest for the unchanged three
  domain annotations. Seven regression tests failed on the old algorithm;
  ordinary/historical, empty/sliced inputs now match its exact values/schema/
  metadata. Profile the synthetic isolated transform, not corpus throughput.
  No validation pass, independent denominator, Parquet check or limit removed.
  Implemented `faa7888`; 320 affected/context/ecosystem tests passed and
  changed-module coverage is 100%. Ruff, ty and BasedPyright pass. The
  reproducible fixture-only paired profiler verifies exact metadata parity;
  Scalene observation recorded separately from unprofiled timing. Frozen full
  `3d9c587`: 3,401 passed, three failed, one skipped, 96.78% coverage;
  release-reproducibility checks on local3.14.7 and product-runner failure
  retained. One isolated product rerun failed at 453.201ms >250ms. All 38
  hosted checks passed on that head. PR #399 merged `73b34d3` after all 38
  final-head (`c512841`) checks passed, with no unresolved review threads and
  exact reviewed/merged tree equality. Closure: issue #341 comment `5473889681`.
  No production change after freeze.
  Second bounded slice: reuse already-measured native-field JSON byte counts
  when measuring enclosing entities; retain the same encoder, exact limits,
  historical lineage and output. Four intended red tests confirmed duplicate
  encoding and missing size propagation. Unicode/null property, exact-limit
  acceptance/rejection, call-count and existing Parquet tests guard parity.
  Implemented `fd0fb68`; 53 focused passes, 323 broader passes and two
  unchanged Hypothesis timing failures; changed-module coverage 100%.
  Paired synthetic CPU medians improve with exact byte parity; no timing SLA.
  Frozen full `ee8fd05`: 3,406 passed, three failed, one skipped, 96.77%
  coverage. Two failures require Python3.14.6 rather than local3.14.7;
  product PERF-QUERY1218.492ms >250ms. One isolated product rerun failed
  at756.788ms. Static/context/ecosystem and clean package checks pass.
  No production changes after freeze. PR #400 merged `6550c15` after all 38
  checks passed on final head `8586603`; reviewed/merged trees match.
  Durable closeout: issue #341 comment `5474092117`.
  Next reconcile one checkpoint-enabled pinned hosted qualification after
  merge, preserving run33337502925 and55-minute limit. No timeout-recovery
  claim or repeated automatic dispatch.

- [~] Reconcile the reviewed checkpoint/optimization run and retain its exact
  failure before further diagnostics. Run `33379551308` at `6550c15` failed
  `public-before/transport-connect` after consuming its one retry; no source
  file or projection was reached. Receipt: issue #341 comment `5476646551`.
  A local same-guarded metadata-only check passed; original Actions cause is
  unknown. Correct separately reproduced loss of OS DNS preference without
  extra attempts or policy relaxation (`8a701ac`; 184 focused passes, static
  checks pass, agent review found no blocker). Integrated gates pending.
  No further dispatch, timeout change, local raw PBS file or publication.

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

### Bounded native comparison prerequisite

- [x] Add a source-independent native snapshot comparison candidate contract
  with exact declared B1/B2 lineage, source/profile/dimension separation,
  row/field denominators, explicit incomplete/ambiguous abstention and bounded
  allocation. Preserve literal values, occurrences and both snapshots; presence
  differences are not additions, cessations, entitlement or current status.
  JSON/semantic contract only; Arrow and real producer integration follow.
  Revalidate copied/constructed nested models into immutable values; reject
  invalid inputs and fabricated outputs.
  Implemented `972f619`, review fixes `7740be3` (agent originals `4f7c9b1`,
  `b22f24a`). Initial missing-module red; 22 review regressions failed before
  correction. Agent final 165 focused/compatibility passes, new module 100%
  coverage; reviewer independently reproduced and closed the mutable-input
  finding. Agent review is not independent maintainer approval.
  Delivered in PR #401: reviewed `f0799c4`, merged `2543720`, all 38
  checks passed; reviewed and merged trees match. No real-source promotion.
- [ ] Bind independently qualified producer snapshots and portable Parquet
  representations before real-source comparison/publication claims.
- [x] Implement the receipt-bound MBS XML comparison-cohort producer
  (`e3bfca5`, agent original `defb755`). Parse the whole bounded source before
  selecting literal item/subitem keys; retain every selected duplicate and
  ordinal, selected/omitted/full denominators and a canonical scope manifest.
  Different scopes abstain. The 4,096-row candidate limit must not truncate the
  5,989-row legacy corpus; completeness describes only an explicit selection.
  Strict table/ordinal/derivable-key lineage and immutable nested validation
  are enforced. LIVE receipts require an explicit real cohort label, not a
  qualification claim; all tests use constructed source bytes. 106 focused
  tests and 14 independent automated review tests passed. Coverage corrected
  for the ellipsis exclusion is 97% producer and 100% comparator. Real-source
  execution, Parquet products and promotion remain pending.
- [x] Correct PR #402 review P1: separate a stable caller-declared comparison
  `schema_era` from the exact `expected_source_revision` checked against
  receipt `catalog_version`. Monthly release dates must not force different
  comparison eras. Implemented `4a88b7f` (agent `7fe0388`); same-era monthly
  comparison failed before the fix, then 118 focused and 213 broader agent
  tests passed. Root integrated 168 tests pass, corrected 98.45% combined
  coverage. Different declared eras still abstain; revision mismatch rejects
  before parsing. The existing receipt, parser and public metadata are not
  relabelled, and a declared profile is not independent schema qualification.
- [ ] Version the broader MBS metadata separation: preserve source release
  revision and immutable B1/B2 identities while adding independently qualified
  schema/profile identities to native bindings, Silver and federated products.
  Existing parser/Bronze/Silver `schema_era` values still carry historical
  catalog labels; do not reinterpret them or rewrite published Parquet/receipts
  silently. Require compatibility tests and explicit schema/profile evidence
  before real cross-release qualification or profile migration.
- [~] Add an opt-in, versioned MBS schema-profile declaration wrapper around
  existing Silver batches. Bind exact source revision and B1/B2 identities;
  retain every default native value and legacy metadata key unchanged. New
  namespaced metadata is explicitly declared, never qualified, and cannot
  select a date profile. Test all tables, duplicate/batch boundaries, copied
  model rejection and Parquet round-trip/default-output compatibility.
  Implemented `f24b166` (agent `9187132`): 33 focused and 246 broader tests
  passed; independent automated review passed 19 selected regressions.
- [ ] Define a versioned federation profile-declaration consumer before
  publishing these optional outputs. Federation v4 does not accept the native
  comparison `historical` cohort; reject rather than silently mapping it to
  `legacy` or `current` until a compatible versioned contract exists.
- [x] Add allowlisted PBS transport cause codes (`11a065a`, original
  `1b26737`) with eight-object explicit-cause traversal, cycle protection and
  separate first-retry/terminal fields. No exception text, IP, hostname,
  credentials, retry-policy or request-count changes. 163 affected tests and
  15 reciprocal review tests passed. Existing hosted failure remains unknown;
  a bounded metadata-only hosted diagnostic is the next acquisition unblocker.
- [~] Implement a separate exact-main Actions PBS public-metadata diagnostic:
  one fixed public revision metadata request, existing bounded retry/transport
  guards, no manifest/receipt/archive/member retrieval and no projection. Emit
  explicitly scoped success/failure/interruption receipts with
  `corpus_qualified=false`; independently review before one hosted observation.
  Implemented `11c3c15` (agent `83885d0`): 175 affected tests passed. An exact
  metadata URL hook rejects archive/CDN redirects before transport; generic
  corpus success cannot become metadata verification. No hosted run yet.
- [x] Correct the unanchored coverage ellipsis exclusion, which could suppress
  functions containing variadic tuple type hints. Preserve the pinned coverage
  library's exact stub exclusion and the 91% threshold. Three regression
  signatures failed before correction; recompute coverage without that blind
  spot. Previously recorded percentages remain historical configured results.
  PR #402 merged as `e75ef68`; reviewed `98a350d`, all 38 hosted checks
  succeeded, review threads resolved and reviewed/merged trees identical.
  This closes the four code tasks above, not real-source qualification.

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

- [ ] Profile the persistent local `PERF-QUERY` failure by separating connection
  lifecycle, cohort-validity SQL, page SQL and conclusion construction. Static
  audit finds repeated keys/assertion/coverage queries for overlapping cohort
  and page pairs, but does not establish the timing cause. Consider bounded
  request-local result reuse only after profiling and parity tests for paging,
  coverage, absent states and validity; do not relax the 250 ms threshold or
  treat green Linux checks as a local performance qualification.
- [ ] Run focused, property, metamorphic, mutation, performance, coverage,
  Ruff, `ty`, BasedPyright, security, rights, provenance, regeneration, and full
  Test-Goblin lanes where supported.
- [ ] Run Conductor review, repair findings, open scoped pull requests, wait for
  hosted checks, merge, and reconcile all evidence.
