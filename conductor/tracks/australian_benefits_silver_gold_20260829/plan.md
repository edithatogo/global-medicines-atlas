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
- [x] Add negative tests for MBS-as-medicine, PBS-as-regulatory,
  terminology-as-funding, candidate-as-reviewed, and absence-as-negative status.
  Source-table contracts reject dimension coercions, implicit review promotion,
  and negative absence interpretation. MBS/PBS Gold candidates preserve only
  service-benefit or source-structure edges, keep review state `not_reviewed`,
  and expose no admission, inference, or terminology-resolution path. No
  candidate promotion API is added. Verified by the focused source-contract,
  MBS/PBS Gold, and Gold edge-review test suites on current main.
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
  receipt digests and B2 digests. The July 2025 XML was source-era qualified
  against the official release, its `mbs-dmy` profile produced zero quality
  findings across 5,989 records and 239,560 field occurrences, and all six
  versioned tables were anonymously verified at public v4 revision
  `ba82cd1d0f9b0f28514df431b8da3a6c207d76fa` (runs `36345410208` and
  `36348699885`). Legacy workbook and PBS table bindings remain open.
- [x] Add the documented MBS DD.MM.YYYY profile alongside explicit ISO input;
  retain source text, reject calendar/format errors and bind conversion v2 to
  Arrow metadata. Official XML specification checked 2026-08-30. Exact-main
  run `36345410208` verified the official July 2025 release and qualified the
  `mbs-dmy` projection over all 5,989 records with zero quality findings.
  (`1619e2b`; 10 intended failing cases followed by 150 combined focused
  passes; both changed modules at 100% branch coverage.)

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
  - [x] Add and run a value-free calendar-compatibility profile on the exact
    merged main commit. Run `36381100367` observed 1,276 dotted dates valid
    under both DMY and MDY and four valid only under DMY; the per-field counts
    are recorded in `evidence.jsonl`. The report leaves `date_profile` unset
    and `semantic_promotion` false. This narrows calendar compatibility but
    does not independently establish the workbook's date convention; source-
    specific documentation is still required before conversion. Durable
    value-free receipt: `quality/qualifications/mbs-workbook-date-order-compatibility-20260928.json`.
  - [x] Review the official MBS XML field specification and July 2024 downloads
    page. The XML specification defines `DD.MM.YYYY` for XML date fields, but
    neither source documents the date convention for the distinct legacy P7
    workbook. Do not transfer the XML rule across source eras. Receipt:
    `quality/qualifications/mbs-workbook-date-source-doc-review-20260929.json`.
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

- [x] Write failing golden, property, malformed-input, schema-drift,
  determinism, decimal/currency, date, formula-error, duplicate, and lineage
  tests for each MBS table.
  XML candidate tests cover every field, all six destinations, exact decimal
  overflow/scale rejection, explicit dates, duplicate item occurrences,
  receipt mismatch, bounded batching and deterministic Parquet round trips.
  Workbook tests retain legacy annotations, formulas, errors and unsupported
  date semantics; historical change-event and publication suites cover their
  respective synthetic contracts. The combined affected set passes 144 tests
  on current main. This is fixture and candidate-code evidence; real-source
  qualification remains separate.
- [x] Confirm the intended failure before implementation. The XML table tests
  originally failed because `mbs_silver` was absent; historical change-event
  projection tests likewise failed collection before their module existed.
- [~] Implement streaming source-faithful MBS service, hierarchy, description,
  fee/benefit, participant, and legacy annotation tables.
  XML candidates use the existing 9 MB bounded parser and at most 4,096 rows
  per Arrow batch; this is bounded parsing plus batch output, not unbounded
  input streaming or complete real-corpus qualification.
- [~] Add explicit schema-era mappings and historical/current change events
  without overwriting source values.
  XML candidate mappings now require complete exact field coverage for a
  selected Silver table and bind distinct caller-declared eras by digest.
  Complete mappings may now preserve explicit historical/current native-name
  changes while requiring the stable Silver target denominator in exact order,
  unique native identities on each side, and content-bound mapping evidence.
  Deterministic observed-change reports retain both complete native cohorts,
  exact values and receipt identities; presence on only one side remains
  `unknown`, never inferred addition or cessation. The legacy P7 workbook now
  has an exhaustive, digest-bound mapping from its qualified header profile to
  exact-name XML fields, with annotations and declining-list membership kept
  source-only. Deterministic synthetic-fixture comparison candidates bind
  workbook row addresses and receipts to literal XML item keys without
  asserting semantic equivalence. Independently qualified real-source
  execution remains pending.

### Schema-era change-event review fixes

- [x] Bind every event ID to the mapping digest, both schema eras, both source
  revisions, B1/B2 identities, and selection scope so identical native values
  in different comparisons cannot collide. (Hosted review fix; exact-head
  validation recorded in evidence.)
- [~] Emit field-level lineage, coverage denominators, quality findings, and
  promotion candidates.
  Aggregate candidate qualification now binds all six XML Silver tables, the
  complete 40-field and source-row denominators, per-table lineage digests,
  conversion-quality counts, B1/B2 identities and explicit candidate-only
  blockers (`e6abca6`). XML field-addressed lineage now maps all 40 native
  paths to exact Silver table/field/type destinations and records per-field
  state, conversion and occurrence denominators without copying source values.
  Real-workbook field lineage and real-source execution remain pending. The
  public v4 identity was subsequently verified at revision
  `ba82cd1d0f9b0f28514df431b8da3a6c207d76fa` by run `36348699885`; no
  promotion is inferred.
  The hosted P7 qualification command now includes the deterministic
  value-free column-lineage report alongside existing metadata profiles. Its
  four-sheet result still requires an exact-main source run before this
  subtask can close; date semantics remain unselected.

## Aggregate qualification review fixes

- [x] Build deterministic workbook column-addressed lineage over the existing
  qualified header mapping and value producer. Preserve every sheet, header,
  unlabelled cell, B1/B2 identity and conversion denominator without copying
  values or selecting date semantics. Synthetic acceptance is not real-source
  qualification, federation admission or public publication.
  Implemented `684344b`; 93 affected workbook tests pass with 100% new-module
  statement/branch coverage; 47 harness inventory tests and Ruff, formatting,
  ty and BasedPyright pass. Full/hosted validation remains separate.

- [x] Constrain field-lineage native states and conversion statuses to
  separate versioned vocabularies so digest-valid serialized reports cannot
  assign undefined semantics. (Hosted review fix; focused revalidation and
  exact-head checks recorded in evidence.)
- [x] Register the new qualification module in the governed unit lane so every
  primary Test-Goblin profile collects an explicitly assigned test module.
  Format the new module and tests with the repository-pinned formatter after
  the first exact-head routine lane exposed the missing format gate; exercise
  every serialized evidence-drift gate and the no-quality blocker branch.
  (`59f5aa9`, `4a326ee`, `07a53f3`; changed module 97% branch coverage,
  Ruff and BasedPyright pass.)
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
- [x] Cover the PBS v3 temporal `<effective>/<date>`,
  `<supply-only>/<date>`, and `<non-effective>/<date>` structures in date-slot
  candidates. The official v3.1.9 guide specifies these effectivity states and
  the mapping specification specifies XSD `YYYY-MM-DD`; this change maps the
  native date slots only, with conversion still opt-in and no current-status
  inference. An intended synthetic regression failed because all three rows
  were previously `unmapped`; after the fix the four PBS date/historical suites
  pass (103), the date module has 99% branch-aware coverage (24 tests), and
  Ruff, `ty`, BasedPyright and context validation pass. Full local Test-Goblin:
  5,114 passed, 2 failed, 1 skipped, 96.72% coverage; both failures are stable
  release-reproducibility tests unable to find required `uv 0.11.29` (local
  candidates are 0.12.19). An automated review finding then tightened the
  mapping to exact documented element ancestry, with a negative unknown-wrapper
  test; 166 focused PBS/historical tests pass. Exact-main PBS requalification
  remains pending; no source payload was acquired locally and no dataset was
  published.
- [x] Add value-free reference-kind and diagnostic histograms to each prepared
  reference shard receipt, then fail closed unless every histogram reconciles
  with the shard row count and uses only controlled labels. Focused shard and
  aggregate suites pass (152 tests); Ruff, format and production-source `ty`
  checks pass. No source literal or resource identifier is emitted. The exact-
  main run already in progress predates this receipt enhancement; requalify on
  the next main commit before relying on full-corpus reference histograms.

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
- [x] Optimize measured redundant projection/serialization work with exact
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
  The post-merge exact-main run `34749693403` completed all five structural/
  storage projections and all Parquet round-trips on `8ccc450f`, which descends
  from both optimization merges. This supplies the planned production-path
  checkpoint without another full-suite repetition. Its receipt remains
  structural/storage candidate evidence; semantic/date qualification remains
  a separate M-109 task. No timeout-recovery claim or limit change is made.

- [x] Reconcile the reviewed checkpoint/optimization run and retain its exact
  failure before further diagnostics. Run `33379551308` at `6550c15` failed
  `public-before/transport-connect` after consuming its one retry; no source
  file or projection was reached. Receipt: issue #341 comment `5476646551`.
  A local same-guarded metadata-only check passed; original Actions cause is
  unknown. Correct separately reproduced loss of OS DNS preference without
  extra attempts or policy relaxation (`8a701ac`; 184 focused passes, static
  checks pass, automated review found no blocker). Delivered in PR #401,
  merged `2543720` with 38 successful checks. Later metadata recovery and
  the separately observed instrumented corpus run are recorded in Phase 5.
  This checkpoint did not change the timeout, acquire local raw PBS files or
  publish data; it did not establish the original transport failure cause.

- [x] Write failing tests for schedules, items, presentations, restrictions,
  prices, effective dates, AMT references, ATC codes, namespaces, schema drift,
  and source-native identity. The focused PBS acceptance set covers native
  field preservation, structural families, entity lineage, date-slot behavior,
  namespace/root drift, historical-member identity, and batch/Parquet bounds;
  162 affected tests pass on current main. Fixtures do not establish the
  approved real-corpus denominator or semantic/date qualification.
- [x] Confirm the intended failure before implementation. The documented PBS
  v3 temporal regression failed with the effective, supply-only, and
  non-effective date rows all unmapped; the candidate mapping fix is covered
  by the focused PBS date and historical suites.
- [x] Implement bounded PBS v3 source-faithful tables. PR #460 merged as
  `5b7af3b6`; the table schema and qualifier retain source-native candidate
  status, exact source identity, and rebuildable Parquet boundaries.
- [x] Keep PBS funding/formulary, ARTG regulatory, AMT terminology, and ATC
  classification assertions independent in the source-faithful storage and
  lineage layer. PR #460 records funding/formulary as source structure,
  terminology and classification as reference-only, and regulatory as not
  asserted.
- [x] Implement and fixture-qualify the loss-aware bridge from `PbsV3Record`
  to the existing canonical medicine model. PR #498 merged as `5ed2f9f8`.
  The receipt-bound projector accepts both governed PBS v3 source identities,
  rejects a mismatched jurisdiction or payload digest, preserves source and
  restriction effective dates, and emits funding assertions only. AMT and ATC
  remain source references rather than terminology or classification
  assertions; regulatory remains unasserted. This covers a bounded fixture,
  not the approved real-corpus denominator. The existing `project_pbs_xml`
  minimal-fixture path remains separate.
- Hosted run `33549535561` now records a passed PBS aggregate receipt at
  `pbs-aggregate-receipt-20260904.json`; it is structural-storage-candidate
  evidence only and does not close this Silver checkpoint.
- [~] Phase Verification & Checkpoint: PBS Silver is complete for the approved
  denominator without restricted terminology payload publication. The exact-
  main run `34749693403` at `8ccc450f` completed all five structural/storage
  projections over 7,730,684 XML elements and 18,208,758 native fields, with
  common native digest, complete reference windows and verified Parquet
  round-trips. Durable receipt: issue #341 comment `5653049805`, report SHA-256
  `216aec6b96ac439b418d02997e71ac4b04c2ff126d6eb1e537b6e12f0dce5713`.
  This resolves the previous incomplete-run/structural-denominator blocker,
  not PBS Silver acceptance: the receipt says
  `structural_storage_candidate_only`, `domain_semantics_qualified=false`,
  and `date_profile=not-selected`; 2,798 reference rows remain unresolved.
  Source-specific semantic/date mapping and cross-era acceptance remain open.
- [x] Add value-free PBS date-role and conversion-status counters to the
  historical date-projection receipt and fail-closed aggregate. Focused
  historical qualification and aggregate tests pass; details and limits are
  in `docs/qualification/pbs-public-qualification.md`. These counters are
  diagnostics only and do not select a profile or qualify source-era grammar.
  Exact-main hosted requalification remains pending merge of PR #566.

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
- [~] Write failing JSON/Arrow schema, semantic, property, negative-control,
  confidence, review-state, temporal, contradiction, and rights tests for nodes
  and edges. MBS service/benefit synthetic-candidate schema, evidence,
  determinism, tamper, no-inference, Arrow and Parquet tests now pass. PBS
  source-document/native-entity and exact source-containment candidate tests
  also pass with complete nested Silver-field, B1/B2, row/path, schema-era,
  rights, retrieval, review, temporal and negative-control evidence. Medicine
  identity, adjudication, cross-source relations and real-source controls remain
  pending.
- [~] Confirm the intended failure before implementation.
  Both the MBS and PBS Gold graph modules were absent before their bounded
  implementations; the PBS test collection failed with `ModuleNotFoundError`
  before current implementation `f36f56f` (earlier pre-rebase identities
  `4b5731b`, `379c744`, and `0bfad02`). The bounded Australian provenance
  supplement likewise first failed collection because its module was absent.
- [~] Generate stable node/edge tables for MBS, PBS, medicines, restrictions,
  source documents, organizations, and terminology references.
  MBS now emits source-record-scoped service and benefit evidence nodes plus
  only same-record explicit edges from synthetic Silver candidates. Those MBS
  edges now also preserve method, confidence, review, valid/retrieval time,
  rights, sensitivity, history, negative-control and comparison controls. PBS now
  emits source-document and native-entity nodes for schedule, item,
  presentation, restriction, AMT-reference, classification and unmapped source
  structure, plus only exact XML parent/child containment edges from synthetic
  Silver. A separate synthetic-receipt projection now emits exact source
  documents, explicitly non-canonical source-declared organization labels, and
  only document-to-declared-authority provenance edges with B1/B2, time,
  rights, sensitivity and review controls. Canonical organizations, canonical
  medicines, resolved terminology and cross-source relationships remain.
  Frozen full at `eb56007`: 4,341 passed, two failed, one optional pyiceberg
  skip, 96.75% coverage. Both failures are unchanged stable-v1 release
  reproducibility checks requiring pinned uv 0.11.29 while the local candidates
  are uv 0.12.7; no toolchain pin or gate was weakened. Later full-harness lanes
  were not reached after pytest failed. Exact-head hosted checks remain
  authoritative.
- [~] Implement official/source-explicit and deterministic mappings first;
  isolate lexical, ontology-assisted, embedding, and NLP candidates.
  The first MBS projection is deterministic and source-explicit; no lexical,
  ontology, embedding, NLP, terminology or admission path is present.
  The first PBS projection is likewise source-explicit structural containment;
  it records no asserted funding, formulary, regulatory, medicine-identity or
  terminology-equivalence dimension and performs no inference or admission.
- [~] Add adjudication queues, calibrated thresholds, conflict/supersession, and
  review receipts before any candidate promotion. A generic Gold-edge adapter
  now creates deterministic, full-edge-digest-bound `pending_review` cases for
  explicit PBS controls and the legacy/current MBS edge contract, and can
  remove cases only when caller-supplied append-only `AdjudicationEvent`
  records already exist. It creates no reviewer identity, adjudication,
  threshold, receipt, authority, admission or promotion; those controls remain
  pending. The queue now retains `needs_information` cases and removes a case
  only for a complete, unambiguous supersession chain ending in accepted,
  rejected, or superseded. Conflicting roots, branches, cycles, and missing
  predecessors fail closed as pending. The regression failed against the old
  behavior, then all 38 adjacent Gold graph tests passed. Full Test-Goblin:
  5,264 passed, 2 environment-only release reproducibility failures, 1
  optional PyIceberg skip, 96.71% coverage; rerunning only those two tests via
  `uv 0.11.29` passed both. This fixes queue-state derivation only; reviewer
  authority, receipts, calibration, candidate promotion, and Gold acceptance
  remain pending.
- [ ] Phase Verification & Checkpoint: every edge is evidence-bearing and no
  candidate class can masquerade as an authoritative link.

### Gold review chronology control (2026-10-04)

- [x] Require each adjudication supersession chain to be strictly chronological
  before it can remove a case from the pending Gold-edge queue. A terminal
  decision dated before or at its predecessor must remain pending. Regression
  confirmed the existing implementation incorrectly cleared this case. The
  focused queue suites pass (18 tests); contract, routine, formatting, and
  typing checks pass. Full Test-Goblin completed with 5,520 passed, 2 failed,
  and 1 optional PyIceberg skip at 96.75% coverage. Both failures are the
  stable-release clean-clone reproducibility tests, which require pinned
  `uv 0.11.29`; this host supplies `uv 0.12.22`. No release pin or gate was
  weakened. This closes only chronology validation; human reviewer authority,
  receipts, calibration, promotion, real-source controls, and canonical
  cross-source relationships remain unresolved. PR #735 passed all 39 hosted
  checks and merged as `001ded0d3ff3429fa499671f91074209ca0d8106`.

## Phase 5: Historical comparisons and publication (AC-06, AC-07)

### Federated producer v4 acceptance

- [~] Define and execute an exact-main M-112 qualification over the approved
  live producer denominator. Require each admitted Bronze/Silver/Gold/Platinum
  object to bind producer, dataset, immutable revision, path, SHA-256, byte
  count, source/acquisition identity, B0/B1/B2 stratum where applicable,
  source receipt, rights authorization, lineage, and anonymous public readback.
  Independently admit the byte-closed v4 contract and run downstream consumer
  compatibility canaries against the same pinned identities. Synthetic
  inventories and fixtures remain implementation evidence only. Do not infer
  producer coverage from MBS-only publication, archive objects, local outputs,
  or the presence of v4 schema code; do not acquire or publish PBS/API or
  restricted terminology payloads before their separate authority gates pass.
  A metadata-only, path-level proposal now inventories 1,736 Australian raw
  payload candidates plus 23 existing projections across five repositories.
  The shared reimbursement-atlas payload paths are included; the global source
  catalogue and New Zealand health appropriations are excluded from the
  proposed producer set. The maintainer approved this exact candidate
  denominator of 1,736 raw paths plus 23 existing projections across those
  five repositories; the decision is recorded in
  `quality/qualifications/australian-m112-denominator-decision-20260930.json`.
  This does not establish per-object source or rights membership, and no v4
  admission is inferred. A metadata-only audit mapped all 1,736 raw candidate paths to
  pinned source manifests or the exact nested MBS receipt. A subsequent anonymous
  API tree readback at two identical scans found all 1,759 frozen raw/projection
  paths present across the five approved producer datasets (zero missing);
  repository root manifests are not complete tree inventories. Of 1,634
  comparable tree SHA-256 values, all match their manifest digests; 102
  candidate paths lack a comparable tree digest. In the current MBS source
  archive revision, the exact August 2026 MBS XML digest path is present in the
  tree and referenced by the nested run manifest with matching SHA-256 and byte
  count, although it is omitted from the root manifest. The current nested run
  reports admission `accepted` but reviewer status `unreviewed` and has no
  persisted `landed` predecessor. The successful hosted release receipt for
  run 37066153375 separately confirms `data_acquired: true`, anonymous digest
  verification, eight verified objects, preservation of 52 prior paths, and
  removal of temporary source bytes. The bundle manifest's `data_acquired:
  false` is an intentional stage-manifest invariant, not a failed acquisition;
  the attempt receipt's distinct ID/unknown rights are intermediate because
  `_release_receipt` normalizes the final receipt to the approved source version.
  This reconciles hosted acquisition identity and receipt evidence but does not
  close the missing landed predecessor, projection lineage, or M-112 acceptance.
  See `quality/qualifications/australian-m112-mbs-hosted-receipt-20261003.json`.
  The
  previously reconciled two accepted but unreviewed records remain distinct
  append-only acquisition events for the same raw source identity; their
  source-Parquet projection digests differ and still require separate lineage.
  Projection lineage and v4 admission remain open. See
  `quality/qualifications/australian-m112-public-tree-readback-20261003.json`.
  Upstream terms remain
  unresolved for `au-pbs-historical-xml` and all 1,707 `au_pbs`
  reimbursement-atlas payloads; for the exact PBS source archive, Decision
  0009 and its hosted receipt establish maintainer publication authority and
  historic digest verification, but not a broader source licence.
  See `quality/qualifications/australian-m112-object-inventory-20260930.json`,
  `quality/qualifications/australian-m112-source-rights-lineage-crosswalk-20260930.json`,
  and `quality/qualifications/australian-m112-manifest-join-audit-20260930.json`.
- [x] Reconcile the 20 MBS/PBS utilisation raw-object digests against each
  exact current public manifest and its prior hosted anonymous all-object
  verification receipt. The pinned MBS revision remains `dee9a5b...` with
  14/14 joined candidate objects and 28/28 manifest objects verified; PBS
  remains `9f1d53c...` with 6/6 joined candidates and 12/12 manifest objects
  verified. Both receipts record temporary-byte cleanup. The exact manifests
  and source verifier commits are bound in
  `quality/qualifications/australian-m112-utilisation-digest-reconciliation-20261004.json`.
  No new source payload was downloaded or decoded. This does not add rights
  state to the sidecars, broaden source rights, complete the 1,759-object
  denominator, admit v4 objects, or pass consumer canaries.
- [x] Bind two additional approved raw source-archive candidates to existing
  hosted digest evidence: the MBS August XML is present in the exact nested
  manifest and was verified at the same current revision by successful run
  `37066153375`; the PBS April XML's current tree LFS SHA-256 matches the
  digest from successful anonymous verification in run `33290449753`. This
  adds digest evidence only. The MBS landed predecessor/reviewer and projection
  lineage remain missing; the PBS source-rights ledger still says redistribution
  is unknown. See
  `quality/qualifications/australian-m112-source-archive-digest-reconciliation-20261004.json`.
  Together with the 20 utilization objects, 22/1,736 raw paths now have these
  per-object digest joins; all 23 projection paths and 1,714 raw paths remain
  outside this subset, so M-112 stays open.
- [ ] Phase Verification & Checkpoint: record the exact producer/object
  denominator, accepted and missing identities, per-layer receipts, consumer
  canary results, and remaining rights/publication boundaries. Leave M-112
  blocked until every approved live producer object is independently verified.

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
- [x] Add a bounded offline Arrow projection of validated native comparisons:
  one envelope retains both snapshots, lineage, denominators, outcomes and
  abstention reasons even with no differences; bounded difference batches
  preserve literal field states and occurrences. Canonical versioned digests
  link the tables without becoming source-verification receipts. Verify
  deterministic Parquet round-trips and copied-model rejection. Reuse PyArrow;
  no new matching stack, data acquisition, publication or Gold promotion.
  Implemented agent `b745c42`, warning-disclosure fix `fd0f360`; integrated
  `e1298b2` and `04e6b4e`. The warning regression failed before correction.
  Root post-fix integration passes 221 tests with both new modules at 100%
  coverage; automated reciprocal verification passes 20 projection tests and
  an independently computed digest/correspondence probe. No maintainer approval
  or qualified real-source comparison is implied; full/hosted checks follow.
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
- [~] Version the broader MBS metadata separation: preserve source release
  revision and immutable B1/B2 identities while adding independently named
  schema/profile identities to native bindings, Silver and federated products.
  Existing parser/Bronze/Silver `schema_era` values still carry historical
  catalog labels; do not reinterpret them or rewrite published Parquet/receipts
  silently. The content-addressed native cohort binding merged in PR #626;
  this follow-up pairs it with existing v4 federation profile bindings through
  a second declared-only sidecar. PR #628 merged as
  `a089cc15b7f9ab60f13232ca1f233bcc6df1f890` after all 39 hosted checks passed;
  its B1 lineage-digest review correction is covered by 116 focused/adjacent
  tests. The opt-in Silver declaration and both federation sidecars preserve
  legacy v4 products without relabelling releases. Exact-source schema
  qualification, real-source compatibility evidence, product export/adoption,
  and any profile migration remain open; no real cross-release qualification
  or MBS acceptance is claimed.
- [x] Add an opt-in, versioned MBS schema-profile declaration wrapper around
  existing Silver batches. Bind exact source revision and B1/B2 identities;
  retain every default native value and legacy metadata key unchanged. New
  namespaced metadata is explicitly declared, never qualified, and cannot
  select a date profile. Test all tables, duplicate/batch boundaries, copied
  model rejection and Parquet round-trip/default-output compatibility.
  Implemented `f24b166` (agent `9187132`): 33 focused and 246 broader tests
  passed; independent automated review passed 19 selected regressions.
  Delivered in PR #403 (`44a603d`), reviewed `39a61f1`; all 38 hosted checks
  passed and the reviewed/merged trees match. This is an opt-in declaration,
  not independent schema qualification or a rewrite of published artifacts.
- [x] Define a versioned federation profile-declaration consumer before
  publishing these optional outputs. Federation v4 does not accept the native
  comparison `historical` cohort; reject rather than silently mapping it to
  `legacy` or `current` until a compatible versioned contract exists.
  The v1 read-side binding retains v4 `schema_era` as the source release,
  carries the declared comparison profile and exact B1/B2 identities in a
  separate immutable sidecar, and content-binds the already validated v4
  document. It accepts only the existing v4 cohorts and grants no admission,
  qualification, rights or publication authority. Synthetic contract,
  identity, immutable-model, bounds and non-mapping tests pass.
  PR #423 review fix requires the exact embedded federation v4 schema digest,
  rather than accepting a merely well-shaped alternate contract identity.
- [x] Implement the offline read-side prerequisite for already-decoded MBS
  batches: bounded flat declaration JSON with duplicate-key rejection, exact
  caller-supplied receipt/profile/schema/metadata and every row's B1/B2 lineage.
  Reject oversized inputs before row materialization; validate empty batches
  without claiming coverage. Return only immutable declared metadata, without
  mutating values, inferring dates or granting qualification/admission. Reuse
  existing Pydantic/PyArrow contracts; federation v4 evolution stays separate.
  Implemented agent `ff8ce70`, integrated `18e8576`. Initial missing-module
  red, 93 affected agent tests and two automated 39-test verification runs pass;
  the integrated 221-test check covers both new modules at 100%. Limits are
  40 KiB declaration, 4,096 rows, 16 MiB batch and 256 KiB/64 metadata entries.
  Decoding, authenticity, source completeness and admission remain separate.
- [x] Add allowlisted PBS transport cause codes (`11a065a`, original
  `1b26737`) with eight-object explicit-cause traversal, cycle protection and
  separate first-retry/terminal fields. No exception text, IP, hostname,
  credentials, retry-policy or request-count changes. 163 affected tests and
  15 reciprocal review tests passed. Existing hosted failure remains unknown;
  a bounded metadata-only hosted diagnostic is the next acquisition unblocker.
- [x] Implement a separate exact-main Actions PBS public-metadata diagnostic:
  one fixed public revision metadata request, existing bounded retry/transport
  guards, no manifest/receipt/archive/member retrieval and no projection. Emit
  explicitly scoped success/failure/interruption receipts with
  `corpus_qualified=false`; independently review before one hosted observation.
  Implemented `11c3c15` (agent `83885d0`): 175 affected tests passed. An exact
  metadata URL hook rejects archive/CDN redirects before transport; generic
  corpus success cannot become metadata verification. PR #403 merged as
  `44a603d`; run `33392287024` succeeded on that exact head without retry.
  Durable issue #341 receipt `5478488604` has verified SHA-256
  `b9ec3878abd1ab62d1c8b28cfd158fd4d00cc086c3b47cb444d47faee6737b9a`.
  It explicitly records no source-file reads, publication or corpus
  qualification; earlier connection failure cause remains unproven.
- [x] Observe one instrumented full PBS qualification after metadata recovery:
  Actions run `33393205281`, exact `44a603d`, existing pinned public archive
  only. Preserve bounded progress/failure receipts and the 55-minute deadline;
  no public dataset writes or local raw downloads. Do not label a processed
  prefix as qualification or redispatch without new evidence.
  The run timed out at 55 minutes on 2026-08-31. Durable issue #341 receipt
  `5479193015` has verified SHA-256
  `c08f79325d0cac2c16f2e1c30c9f9bac0c559f9a62c32a20cbaaed3382592d44`.
  Last checkpoint: projection qualification, entities, 6,448 batches and
  6,602,752 rows, elapsed 3,307,398 ms. Status is incomplete, not qualified.
  Generic failure-stage `unavailable` does not erase that observed progress;
  earlier projection counts/digests were not durably retained in this receipt.
- [x] Profile the observed entity-projection path with bounded synthetic
  fixtures before optimizing extraction, Parquet round-trip or row accounting.
  Preserve exact rows, ordered digests, lineage and all five final projection
  validations. A prefix cannot be resumed or treated as independently complete;
  no unchanged redispatch or budget increase. Other projection phases must not
  be guessed as the blocker. No real source bytes are downloaded locally.
  One instrumented 100/1,000-item synthetic command passed native-denominator,
  ordered-digest and Parquet equality checks. The 1,000-item case produced
  3,001 entity rows in 1.418274 s: iterator 0.910293 s, Parquet 0.111921 s,
  residual accounting 0.396060 s. Profiling overhead is included; this is not
  a throughput benchmark or prediction that the 55-minute corpus limit fits.
- [x] Test a columnar lineage precheck and selective native-field materialization
  for entity qualification, preserving every nested identity/parent/occurrence,
  independent ordered native digest and Parquet equality. The possible saving
  is bounded by accounting work in that observation; iterator work still
  dominates and requires separate evidence before changing the producer.
  Nested accounting now flattens Arrow list/struct columns without entity-row
  dictionaries. A single temporary Arrow stream replays the independently
  checked entity projection into reference and date qualification, replacing
  four entity builds with one; it is automatically deleted and is not a dataset
  destination. The existing maximum 4,096-row bound reduces Parquet setup while
  8 MiB encoded-byte limits remain authoritative. A 1,000-item synthetic full
  qualifier preserved all five counts and reduced observed CPU from 3.419859 s
  to 2.081080 s (one bounded comparison, not a corpus throughput prediction).
  Focused projection/hosted tests: 141 passed; Ruff and BasedPyright passed.
- [x] Deliver the reviewed optimization through hosted checks, then dispatch one
  exact merged-main PBS qualification run. Accept only a complete durable receipt
  with all five projection denominators/digests and anonymous public pin checks;
  do not infer success from progress, extend the timeout or publish any bytes.
  PR #407 merged as `d58da9b`; all hosted checks passed. Exact run
  `33496451984` timed out at 55 minutes and remains incomplete. Its durable
  receipt records `references`, zero output batches/rows and 2,302,255 ms at
  the last checkpoint, proving the entity projection completed but the blocking
  reference index had not yielded output. No timeout increase or duplicate run.
- [x] Replace reference-index full entity-row materialization with selective
  Arrow columns and flattened native attribute fields. Preserve item/AMT/ATC
  literal contracts, source order, missing/empty states, duplicate occurrence
  counts, distinct resource counts, ambiguity diagnostics, identity checks and
  exact index entry/byte limits. Re-run the exact merged-main qualifier only
  after focused parity, full validation, review and hosted checks pass.
  PR #408 merged as `757dc41`; all protected hosted checks passed. Exact run
  `33502075161` then reached reference output: 120 batches and 163,700 rows at
  3,307,650 ms before the unchanged 55-minute timeout. Receipt:
  issue #341 comment `5493802123`. This is incomplete progress, not a
  qualification result.
- [x] Replace reference-output nested-row reconstruction with Arrow batch
  reuse and exact columnar diagnostics. Retain governed JSON encoded-byte
  limits using byte-equivalent `orjson`, exact output flush boundaries,
  item/AMT/ATC diagnostics, lineage, metadata-aware Parquet equality and native
  digests. One 1,000-item synthetic output-only comparison produced 10,001 rows
  and six equal batches: baseline CPU 0.741650 s, candidate 0.657760 s. This
  bounded observation is not a corpus forecast; hosted validation remains.
  PR #416 merged as `ccf7570`; exact run `33509616416` timed out at the
  unchanged 55-minute limit. Its durable receipt (issue #341 comment
  `5494894668`, verified SHA-256
  `0feb584f31457ea61318cd701825f0273eb472ac3cfe753b7de1176336d0a204`)
  records only six batches and 8,358 rows at 3,307,188 ms. This regressed the
  earlier hosted prefix despite the small synthetic result and is incomplete,
  not qualification. No retry or publication occurred.
- [x] Disaggregate hosted qualification with one anonymous preparation job
  that verifies the pinned public source and computes the entity denominator
  and complete global literal index exactly once. It emits retention-one-day,
  same-run-only derived inputs marked `evidence_truth=false`: one global index
  artifact and 16 digest-bound reference partitions, each worker receiving its assigned
  Arrow partition, the complete global index and exact manifest identity.
  Four bounded phase workers independently stream the pinned public source and
  complete before the reference matrix starts, enforcing global `max-parallel: 4`.
  Only the final aggregate writes durable issue evidence; it fails closed with
  exact missing/failed shard IDs, exact hosted pins and schemas, gap-free ordered
  windows, denominators, declared counter types, digests and Parquet equality.
  These transient Actions artifacts are not reusable data or publication;
  reusable data remains public-Hugging-Face-only under its separate publication
  gate. Preparation outputs expose their exact attempt identity so rerun-failed
  consumers reuse the successful prep; attempt-specific receipts aggregate by
  deterministic latest success and reject conflicting successes. The changes
  were reviewed and merged before dispatch; exact-main run `36417477472` passed
  all 31 jobs on workflow commit `95d9583d77ceb71d979af9b5c8e394efe6712dfd`,
  an ancestor of current main. Its durable aggregate is issue #341 comment
  `5870245890`, SHA-256
  `5e886c6a6b9abb0e035a75d242182c14d875f68d1e640cf2b84b770786633eca`; it used
  pinned dataset revision `31ec854ef9fc82f30a0dbe743fdf50a2e5bd24a7` and recorded
  five round-trip-verified projections, 16 contiguous reference windows, and
  7,730,684 element rows with 18,208,758 native fields. The result remains a
  structural candidate only; it does not qualify domain semantics or complete
  source-rights, M-109, or M-112 gates.
  Exact merged-main run `33509616416` at `ccf7570` falsified that synthetic
  forecast: after the same 55-minute limit it had emitted only 8,358 reference
  rows in six batches, versus 163,700 rows in 120 batches at `757dc41`.
  Receipt: issue #341 comment `5494894668`. The deep nested Arrow
  `Table.from_batches(...).combine_chunks()` reconstruction and a second full
  native-field flatten on the output pass are therefore removed. Output now
  appends diagnostics to each already-bounded input batch and yields bounded
  zero-copy slices; the complete literal index, ordered rows, global
  diagnostics, exact JSON byte checks, lineage, digest and Parquet table
  equality remain mandatory. A deterministic half-open `start_row`/`stop_row`
  API completes the global index, validates an optional total-row denominator,
  scans the complete output identity, and annotates only the selected window.
  Concatenated synthetic windows equal the full table and retain duplicates
  spanning windows. On one 1,000-item synthetic case the replacement emitted
  10,005 equal ordered rows in 4.978997 s versus 8.700892 s for the pre-#416
  row-reconstruction baseline in sequential local observations; this is not a
  corpus forecast. Focused reference/historical tests: 53 passed; Ruff and
  source BasedPyright passed. Exact-main run `36417477472` later passed every
  phase, index, eight pair-preparation, sixteen reference-shard, and aggregate
  job; all five projection outputs passed metadata-aware Parquet round-trip and
  the slice-aware receipt binds sixteen contiguous windows. This validates the
  implementation only as `structural_storage_candidate_only`: domain semantics
  are unqualified and 2,798 reference rows remain unresolved. No timeout increase
  or public publication occurred.
  Review fix `e2de222` closes two P1 fail-closed gaps: only `(0, None)` may
  request unbounded full output, while every explicit window must satisfy
  `0 <= start < stop <= total`; empty and open-ended nonzero windows now fail.
  Diagnostic Python values are sized first, then each bounded native slice gets
  its own Arrow arrays, so a 4,096-row input cannot allocate an over-budget
  diagnostic array before its row/8 MiB boundaries are enforced. Allocation-
  length regression coverage forces byte-bound splitting and proves the largest
  diagnostic allocation equals the largest bounded output batch. Broader
  affected validation: 267 passed; Ruff, format, source BasedPyright, native
  context and diff checks passed. Hosted exact-head revalidation remains.
  The first merged sharded workflow (`9d3a984`, run `33526575517`) failed in
  monolithic preparation after 30m15s, before reference shards could start.
  The diagnostic split (`cbf81a8`, run `33537778788`) then proved the native,
  domain, entities and dates jobs succeed independently, while the entity
  material job failed with fixed `resource/disk-full` evidence. Its design
  wrote a complete reusable entity stream plus all 16 partitions in one job,
  amplifying local disk even though no raw source bytes were retained.
  The next candidate removes that shared spool entirely: one job streams the
  bounded global literal index directly, and four independently retryable jobs
  each re-read the exact pinned public source and retain only one contiguous
  quarter (four of 16 final partitions). Phase jobs run first at maximum four;
  index plus group preparation then runs at one plus three, so every active
  wave has true concurrency at most four. Assembly accepts only digest-valid,
  identical successful retries, rejects divergent successes, and requires the
  index plus exact groups 0..3 and partitions 0..15. Hard links avoid a second
  local copy during assembly. Checkpoints now distinguish workspace and temp
  free space and retain an allowlisted `enospc` code without exception text.
  No raw artifact, timeout increase, dispatch or publication is included.
  Review fix: preparation still waits for the phase wave to finish, but runs
  under `always()` even when an independent phase fails; a phase failure can no
  longer suppress all preparation diagnostics. Exact aggregate coverage still
  fails closed unless every required phase, index, group and reference passes.
  Hosted Codecov then measured 85.61644% patch coverage at `25ee9b9`, with ten
  uncovered changed lines and eleven partial branches confined to the new
  partition-group contracts. Focused negative tests now exercise index/group
  schema drift, pre-existing outputs, uninitialized writers, denominator and
  written-projection drift, malformed containers/partitions, binding drift and
  validation-time projection drift. The affected module reaches 96% branch
  coverage locally and all ten hosted annotations are executed; no exclusion,
  threshold or coverage configuration changed.
  Exact-head review found the outer hosted index report carried the workflow
  commit while its inner deterministic node receipt did not. Assembly read the
  inner receipt and could therefore write a null commit that every downstream
  prepared worker correctly rejects. The hosted index now binds the exact
  commit into the inner node before its wrapper digest is written. Assembly
  requires the inner/outer commit plus every node's commit, dataset and revision
  to agree, and writes that identity into the manifest. A full synthetic hosted
  index plus two groups now passes real assembly and downstream prepared-shard
  qualification; a missing inner commit fails closed.
- [x] Shorten the hosted critical path after the successful disaggregated run:
  start the four phase workers, global reference index and four reference-group
  workers independently, retain `fail-fast: false` for each matrix, and keep
  assembly/reference qualification behind only their actual prepared-input
  dependencies. The aggregate remains an `always()` fail-closed completeness
  gate, so partial failures retain their own receipts and GitHub can rerun failed
  jobs without discarding successful siblings. Implemented `6ffe169`; the
  workflow contract failed before the dependency change, then the complete 121
  PBS hosted-qualification tests, Ruff, format, actionlint and Conductor context
  validation passed. This raises possible first-wave hosted concurrency from
  four to nine to reduce elapsed time; runner availability still provides the
  external queue bound. No timeout, source, receipt, publication or qualification
  semantics changed. Hosted unit review exposed one older preparation test
  pinned to the former three-group throttle; review fix `2f42a11` makes the
  existing end-to-end DAG contract require no `needs: qualify` dependency and
  the new four-group limit. Both PBS workflow suites now pass 135 tests, with
  Ruff, format and actionlint green. PR #435 merged as `fabb7c8` from exact
  reviewed head `a4f8d55` after all 37 hosted checks passed and no review
  threads remained unresolved. Merge-receipt review adds the
  canonical PR and exact Test-Goblin run URLs required for durable hosted
  traceability; it changes no completion claim.
- [x] Further isolate the hosted PBS preparation failure domain after the first
  successful run showed each four-shard group occupied about 30 minutes. Replace
  four groups of four with eight independently retryable groups of two and allow
  all eight preparation children to run concurrently when hosted capacity is
  available. Preserve `fail-fast: false`, attempt-bound artifacts, exact sixteen-
  shard assembly, and the final fail-closed aggregate. Implemented `c10dd41`;
  the two workflow contracts failed before the DAG change, then both complete
  PBS hosted/preparation suites passed (136 tests), including exact expansion
  of eight pair receipts to gap-free partitions 0..15, with Ruff, format,
  actionlint and diff checks green. This changes scheduling and retry scope only:
  it does not change source retrieval, qualification semantics, receipts,
  publication, timeouts or human gates. Rebased implementation `751d3d0`
  supersedes `c10dd41`. Exact-main run `36417477472` then completed all 31 jobs
  successfully in 69m04s wall time, including all eight two-shard preparation
  groups, sixteen reference workers, and the aggregate. This closes the
  engineering elapsed-time observation for the structural candidate path; it
  does not change the unresolved semantic, rights, M-109, or M-112 gates.
- [x] Correct the unanchored coverage ellipsis exclusion, which could suppress
  functions containing variadic tuple type hints. Preserve the pinned coverage
  library's exact stub exclusion and the 91% threshold. Three regression
  signatures failed before correction; recompute coverage without that blind
  spot. Previously recorded percentages remain historical configured results.
  PR #402 merged as `e75ef68`; reviewed `98a350d`, all 38 hosted checks
  succeeded, review threads resolved and reviewed/merged trees identical.
  This closes the four code tasks above, not real-source qualification.

- [x] Write failing tests for additions, cessations, renumbering, fee/benefit/
  restriction changes, schema-era drift, source failures, missing periods, and
  current-versus-legacy labels. Synthetic regression coverage explicitly
  compares fee, benefit, and restriction values; preserves MBS source and
  selected-row denominators; and treats literal item turnover as observation
  only. Existing tests cover additions/cessations, schema drift, incomplete or
  missing periods, and cohort-role constraints.
- [x] Confirm the intended failure before implementation. The new MBS event
  projection tests failed collection because its module did not exist.
- [x] Build deterministic change/event and comparison tables with explicit
  denominators and uncertainty. The existing native comparison Arrow
  projection retains scoped row denominators, completeness and abstention
  reasons. A new bounded MBS event projection records full source, omitted,
  selected-key, observed-row and unmatched-key counts for both cohorts; links
  rows to the exact report digest; preserves source identities and observation
  dates; and fixes absence meaning to `unknown`. Focused changed modules pass
  100% branch coverage; the affected suite passes 197 tests. The full local
  Goblin profile reports 5,536 passed, two known local uv-pin failures, one
  optional PyIceberg skip, and 96.74% coverage. Review correction preserves
  each cohort's temporal role in the Arrow envelope. PR #741 merged as
  `da81000` after all required hosted checks passed, including 100% Codecov
  patch coverage and Linux/macOS/Windows consumer lanes. No real-source
  qualification, admission, publication, or rights decision is implied.
- [x] Revalidate historical-change pages, including nested snapshot and
  comparison models, at API and JSON adapter boundaries. A deliberately
  `model_construct`-built invalid page previously serialized as HTTP 200 with
  malformed nested objects; it now fails closed with HTTP 422. The transport
  payload helper and service JSON method use the same reconstruction check.
  Focused historical suites pass (164 tests); changed production modules pass
  BasedPyright, and Ruff/format/ty pass. Full Goblin reports 5,520 passed,
  2 failed, 1 optional PyIceberg skip, 96.75% coverage; the two failures are
  existing release reproducibility checks requiring uv 0.11.29 while this host
  provides 0.12.22. This synthetic API hardening does not qualify real source
  periods, change Gold denominators, resolve rights, or satisfy M-109/M-112.
  PR #737 merged at `d88aaef73faf46622dd2705783ee8e9703c32d2e`; all 38 hosted
  checks passed, including 100% Codecov patch coverage and Linux/macOS/Windows
  consumer lanes. Its review finding about serialization-warning leakage was
  fixed and the thread resolved before merge.
- [ ] Publish Silver, Gold, lineage, coverage, promotions, and v4 identities to
  public Hugging Face through the hosted data-plane workflow.
- [ ] Verify token-free clean-room regeneration and remove only verified
  transient local outputs.
- [ ] Phase Verification & Checkpoint: old-versus-new analysis is reproducible,
  public, and cannot be mistaken for complete current coverage.

## Phase 6: Integrated qualification (AC-08)

- [x] Repair aggregate MBS Silver denominator review findings at `b073f10`:
  require each serialized table's exact contract-derived field count, require
  only known conversion statuses, and require quality counts to sum to the
  complete field-occurrence denominator. Focused qualification, MBS, and
  harness tests pass (79 tests; changed module 95% coverage), with Ruff and
  BasedPyright clean. The broader Australian source-contract run also passed
  all semantic assertions but recorded one unrelated Hypothesis 200 ms timing
  flake under combined coverage load; no deadline or test was weakened.
- [x] Profile the persistent local `PERF-QUERY` failure by separating connection
  lifecycle, cohort-validity SQL, page SQL and conclusion construction. Static
  audit finds repeated keys/assertion/coverage queries for overlapping cohort
  and page pairs, but does not establish the timing cause. Consider bounded
  request-local result reuse only after profiling and parity tests for paging,
  coverage, absent states and validity; do not relax the 250 ms threshold or
  treat green Linux checks as a local performance qualification.
  One synthetic profiling observation at `44a603d` (Python 3.14.6, DuckDB
  1.5.5, macOS arm64) measured 569.402 ms total: two assertion SQL fetches
  441.023 ms, key fetches 50.168 ms, coverage fetches 9.827 ms, connection
  open/close 61.136 ms, conclusion construction 0.475 ms. Inclusive helper
  timing overlaps these costs. This supports request-local reuse but is not
  a p95 result or proof that reuse alone meets the 250 ms budget.
  Implemented a four-query request-local reuse slice: retain both cohort and
  keyset page SQL, build cohort assertions/coverage/conclusions once, and select
  page conclusions from that sorted cohort. No cross-request cache, dependency
  change, threshold relaxation or query-plan receipt change. Red call-count
  regression observed the original duplicate reads; 81 focused query/product
  contract tests pass, including traversal, exhausted pages and fresh reads.
  Automated subagent verification found no blockers; this is not a second
  accountable reviewer or maintainer approval. Full at `d6cf860` passed
  coverage, including the unchanged 250 ms fixture criterion, then failed the
  local mutation-score baseline (83.511111% versus 83.688889%). No changed
  query file is a mutation target; five suspicious outcomes are not evidence
  of a query regression. Preserve that failed full result and the separate
  authoritative Linux checks. Delivered in PR #405: wording-corrected head
  `f3a9c6e`, merged `02654f5`, 38 successful checks and identical trees.
  The P1 automated-verification versus reviewer-authority wording is corrected.
  A fixture pass is not full-corpus performance qualification.
  Subsequent medallion full at `e4987a6` passed 3,799 tests (one optional
  pyiceberg skip), 96.48% coverage and the fixture performance check, then
  failed the same local mutation-score gate: 1,880 killed, 363 survived,
  two untested and five suspicious of 2,250. Later local lanes were not
  reached; no baseline changes or whole-run retries.
- [ ] Run focused, property, metamorphic, mutation, performance, coverage,
  Ruff, `ty`, BasedPyright, security, rights, provenance, regeneration, and full
  Test-Goblin lanes where supported.
- [ ] Run Conductor review, repair findings, open scoped pull requests, wait for
  hosted checks, merge, and reconcile all evidence.

## M-109 exact public MBS candidate denominator follow-up (2026-09-28)

- [x] Extend the exact-main public MBS candidate report with a bounded
  declared-profile compatibility comparison over the same digest-verified July
  2025 v3 bytes. The check compares every batch's typed values, columns, and
  pre-existing metadata for all six tables; it reports only table/field
  denominators and receipt digests. This is `declared_only` compatibility
  evidence, not schema-profile qualification, source-era semantics, M-109
  acceptance, or publication. Focused profile/qualifier tests (92) and strict
  local checks pass. The full local profile had 5,263 passed, one optional
  skip, and two release reproducibility failures because the default Mac
  environment lacked pinned uv 0.11.29. The exact-version tool was then run
  from an isolated cache and both failed reproducibility tests passed (2); the
  full profile was not repeated. PR #650 merged as
  `b1d6146b4a09b1b1814e821d11510dc35f05e6e8` after all protected checks passed.
  Exact-main run [36632407007](https://github.com/edithatogo/global-medicines-atlas/actions/runs/36632407007)
  verified all six tables at 5,989 rows each and 64 projected columns/383,296
  field occurrences total. Every batch preserved array values and legacy
  metadata. The aggregate is `declared_only`, contains no source values, and
  records no publication. This does not qualify source semantics or M-109.

- [x] Add an Actions-only qualification for the exact anonymously published
  July 2025 MBS XML. It pins the public revision, bounds and digest-checks the
  bytes, processes them in memory with the six-table Silver candidate, and
  retains only an aggregate candidate report. It does not publish derived
  data, persist raw source bytes, promote Silver, or claim M-109 acceptance.
- [x] Add regressions for exact byte/digest identity, candidate-only blockers,
  no publication, bounded source transport and the exact-main read-only job;
  include the new tests in the Test-Goblin unit profile. Focused tests: 15
  passed; Ruff, `ty`, BasedPyright, context, and `actionlint` passed. The first
  hosted routine result found formatting only; its two file-format findings
  have been corrected and the formatter check now passes locally. Automated
  review also identified source-versus-derived output identity, incomplete
  transformation binding, and the unenforced redirect cap; the receipt now
  distinguishes identity-preserving source restore from the separately hashed
  candidate report, binds the exact Git commit, and passes the redirect bound.
  Nineteen focused tests pass after these fixes.
- [x] Merge the reviewed workflow and dispatch it on its exact main commit.
  PR #555 merged as `548d6e1` after every protected lane passed and all three
  review threads were resolved. Exact-main hosted run `36336688622` completed
  successfully; its aggregate artifact records all 5,989 rows across six
  tables and all 40 contracted fields (239,560 field occurrences). One field
  conversion is `invalid`; the report correctly retains
  `quality_findings_present`, `real_source_era_unqualified`, and
  `public_v4_identity_unverified` blockers. No derived data was published.
- [x] Add value-free field/status counts and source-ordinal diagnostics to the
  hosted aggregate; the content-bound candidate report now covers diagnostics
  as well as table qualification. A synthetic invalid-date regression confirms
  field and ordinal are reported while the source value is omitted. Focused
  tests: 20 passed; affected MBS tests: 158 passed; Ruff, `ty`, BasedPyright,
  context and `actionlint` passed.
- [x] Merge the diagnostics improvement and rerun on exact `main`; hosted run
  `36337277773` identified one invalid value at `benefits.Benefit85`, source
  ordinal 36, without retaining source text or identifiers in its report. The
  official MBS XML field description defines this amount as numeric with
  format `1 to 5.2`; the compact notation's fractional-scale interpretation
  remains unresolved;
  source-local inspection remains limited to the hosted
  runner. The exact native value remains unreported here.
- [x] Add a fail-closed maximum five-digit integer-width check in the MBS
  Silver projection, preserving source text as `invalid`; do not constrain
  fractional precision because the official page's compact `1 to 5.2` notation
  does not establish a scale interpretation for this archived file. Synthetic
  checks cover oversized integer text under every date profile, and verify
  blank values and representability states remain distinct. Focused MBS tests:
  79 passed; broader affected MBS tests: 106 passed; Ruff, `ty`, BasedPyright,
  context and diff validation passed. PR #557 merged as `f133c82`; exact-main
  run `36339405937` repeated the 5,989-row/40-field denominator and retained
  exactly one invalid `benefits.Benefit85` at ordinal 36. Thus the amount-width
  guard did not resolve the finding.
- [x] Add a value-free invalid-amount reason diagnostic distinguishing a
  strict numeric grammar mismatch from a numeric value outside the integer-
  width contract. PR #558 merged as `486e5ca`; exact-main run `36339904431` classified
  the single `benefits.Benefit85` finding at source ordinal 36 as a
  `strict_numeric_grammar_mismatch`. The underlying spelling is unknown and may
  be numerically interpretable outside the candidate grammar. The raw value
  and source record identifiers remain absent from the report. Retain the
  `quality_findings_present` blocker and source-faithful
  invalid value. Remaining independent gates include source-era qualification,
  public v4 identity/admission, M-107, and M-109 acceptance.
- [x] Compare the pinned MBS archive object with the official July 2025 V3
  release using bounded anonymous hash-only streaming. PR #560 merged as
  `6983504`; exact-main run `36343032231` confirmed the official and pinned
  archive objects have the same 8,194,522-byte length and SHA-256
  `db873768c5795222455033e2bad28586f19bbf2a10c7d58f06a0671d9111a556`.
  The report now clears only `real_source_era_unqualified`; one invalid
  Benefit85 conversion and `public_v4_identity_unverified` remain.
- [x] Probe the one value-free Benefit85 strict-grammar mismatch without
  coercion or disclosure. Exact-main run `36344055256` classified the sole
  mismatch as decimal text with surrounding XML whitespace; no value or
  identifier was disclosed. The diagnostic is complete.
- [x] Normalize only XML Schema decimal whitespace at the MBS typed-projection
  boundary, while preserving parser-native text unchanged and rejecting
  internal/non-XML whitespace, alternate decimal spellings, and amounts
  outside the documented width. The MBS candidate schema now declares this
  policy as v1.1. PR #562 merged as `a02daa3` after the review correction,
  114 affected tests and all protected checks passed. Exact-main run
  `36345410208` requalified the same 5,989 records, 40 fields, and 239,560
  occurrences with zero quality findings. PR #563 and hosted run
  `36348699885` then anonymously verified the six derived tables at public v4
  revision `ba82cd1d0f9b0f28514df431b8da3a6c207d76fa`. The normalization and
  candidate publication tasks are complete; embedded qualification remains
  candidate-only and M-107, cross-source M-109, federation, and Stable v1 remain
  independent.
- [x] Build and publish a deterministic, source-faithful six-table MBS Silver
  v4 package to the authorized public MBS archive through GitHub Actions only.
  Bind it to the pinned July 2025 B2 digest, official release identity,
  maintainer authorization, exact transform commit, and anonymous per-object
  size/digest verification. The deterministic package builder and protected
  Actions publication workflow are implemented in PR #563. Mocked hosted
  transaction tests cover successful append/readback/receipt/cleanup and
  fail-closed source, privacy, collision, revision, inventory, and digest
  conditions. The package builder has 100% branch-aware coverage; the combined
  builder/publisher focused set has 99%. Ruff, BasedPyright, actionlint, and
  zizmor pass. PR #563 merged as `decdeca1` after all protected checks passed
  and its import-path review thread was resolved. Hosted run `36348699885`
  anonymously verified all nine objects at dataset revision
  `ba82cd1d0f9b0f28514df431b8da3a6c207d76fa`; the durable receipt is on issue
  #340 and binds manifest SHA-256
  `bbdb1bdac49fc1a7f8399ca02cf52a9b0e3a1fbc31e472e3957f1d278ab39a59`.
  Forty pre-existing dataset paths were preserved. Full local Test-Goblin
  completed with 5,088 passed, one
  skipped, and five failures (one temporary typing-dependency contract, now
  reverted; four unrelated stable-receipt/datahouse checks). No raw source
  content entered logs, and hosted temporary bytes were removed after the
  verification receipt was recorded. The public v4 identity blocker is
  cleared. Embedded qualification remains candidate-only; M-107, complete
  cross-source M-109 acceptance, federation acceptance, and Stable v1 remain
  independent.
- [x] Reconcile the exact-main PBS value-free date and reference diagnostics.
  Run `36354464731` on merge `b3dbd889` passed all five structural/storage
  projections, 16 ordered reference windows, matching native digests and
  Parquet round-trips for 7,730,684 elements and 18,208,758 native fields.
  Controlled histograms reconcile: 2,798 unique item XML identifiers and
  2,798 unresolved AMT references; date roles include 2,798 PBS effectivity
  dates. The date conversion profile remained unselected, so these are not
  source-era qualification or semantic acceptance. The content-bound safe
  aggregate is on issue #341, SHA-256
  `5f6b04781beea329b48ce5add10a565b886a16f54b79e2371aa377d60959d555`.
- [x] Qualify the documented `pbs-iso-date-candidate-v1` date grammar on the
  pinned corpus as an explicit opt-in candidate, preserving source-native
  literals, with no interval/status inference and with
  `source_date_era_qualification=not-established`; reconcile candidate status
  counts before any separate source-era or M-109 acceptance claim. Exact-main
  run `36372245263` passed all five projections and 16 ordered reference
  windows with matching native digests and Parquet round-trips for 7,730,684
  rows. The dates projection reports 2,799 converted (2,798 PBS effective
  dates and one schedule date), one missing field, and 7,727,884 unmapped;
  no ambiguous or duplicate literals. This validates the candidate transform
  and its counters only; source-era semantics and domain qualification remain
  unestablished.
- [x] Add an opt-in exact-main `pbs-iso-date-candidate-v1` run with date profile
  bound consistently across projection and reference shards. PR #568 merged as
  `eddcf896`; protected CI, Codecov, and review passed. Focused tests passed;
  the full-profile macOS limitation is recorded in `evidence.jsonl`. Exact-main
  run `36372245263` passed; see the value-free aggregate recorded above and
  `evidence.jsonl`. This remains candidate-only and does not establish
  source-era semantics.
- [x] Qualify the documented ASCII date grammar for the exact pinned PBS V3
  member only, using profile `pbs-v3-pinned-2026-04-01-v1`. The public B1
  receipt and immutable manifest bind the sole source member to this release
  and V3 schema era; other releases, date semantics, AMT resolution and M-109
  acceptance remain outside this narrow qualification. Exact-main run
  `36417477472` passed all five projections and 16 reference windows across
  7,730,684 elements and 18,208,758 native fields; all Parquet round-trips
  verified and the source-native digest remained
  `890c607f0e8c9de95c37770610fdc51fd241ea97210ef5ea61d7ad22fd228a25`.
  The ASCII profile converted 2,799 dates and left one date field missing;
  7,727,884 rows remain unmapped. The aggregate explicitly remains
  `structural_storage_candidate_only`, with 2,798 unresolved AMT references,
  domain semantics unqualified, and publication not performed. The compact,
  value-free hosted aggregate is committed alongside this track as
  `pbs-qualification-receipt-20260928.json`.
- [x] Diagnose M-107's authorized Health.gov workbook download timeouts with a
  separate exact-main, HEAD-only Actions probe. The workstation metadata check
  confirmed all three URLs return the expected XLSX headers, while bounded
  CKAN searches found no matching mirror. PR #569 merged as `fa924f0d` after
  all protected checks passed. Review's slow-response finding was fixed with a
  per-request wall-clock deadline; an unrelated brittle substring assertion
  in a synthetic privacy test was narrowed to exact emitted string values.
  Focused regressions and static/routine checks pass. Exact-main HEAD run
  `36376037675` timed out on all three direct workbook URLs at the 15-second
  deadline, without redirects or body reads. Because its bounded receipt omits
  exception details, this follow-up adds safe timeout-stage labels for
  connection, response, pool, and wall-clock failures. Focused and routine
  validation passes. Classified run `36377031967` reported `wall_clock` for
  all three URLs. Its per-operation timeout matched the 15-second hard limit,
  so the outer deadline may have masked the HTTP phase. The follow-up sets the
  general operation timeout to 7.5 seconds and the connect timeout to at most
  5 seconds beneath the same 15-second cap. Local focused and routine
  validation passes. PR #571 merged as `58cb9e8c` after all protected checks
  passed. Exact-main run `36377888606` classified all three requests as `read`
  timeouts after connection setup, with no response headers. The receipt
  confirms no redirects and no source bytes read. This locates the observed
  delay to response-read/header delivery on the hosted route, but does not
  identify the network or publisher cause and does not satisfy workbook
  acquisition, M-107, or federation acceptance.

## PBS public API rights preflight (2026-09-29)

- [x] Refresh the official PBS public API metadata without requesting data
  payloads. Current docs state no-login public access, current plus 12 months
  of schedules, monthly refresh, and a shared 20-second request interval.
  The API data-model version is 3.7.8; release notes date the 3.7.8 release to
  2026-05-20.
- [x] Preserve the rights boundary: the public-access and local-download
  instructions do not themselves grant this project long-term internal raw
  retention or redistribution rights. The source-rights ledger still records
  reuse and publication as unknown, and no API data request was made.
- [x] Prepare a provider request to the official HPP.Support address asking
  for the applicable reuse terms, internal retention, attribution, derivative
  and redistribution permissions, without requesting embargo access or
  credentials: `pbs-public-api-terms-request.md`. It was subsequently sent and
  automatically acknowledged; substantive provider clarification remains
  pending and rights remain unknown.
- [x] Reconcile the preflight's machine-readable contact status with the sent
  message and automatic acknowledgement in
  `provider-outreach-receipts-20260929.json`. The corrected receipt records
  delivery only; it does not promote rights or authorize acquisition.
- [ ] Obtain provider clarification and a separate source-specific maintainer
  rights decision before any `au-pbs-api` acquisition. PBS source-era/domain
  qualification, unresolved AMT references, M-109, Australian federation and
  Stable v1 remain open.

## Evidence-ledger review repair (2026-09-29)

- [x] Restore append-only ordering for the PBS rights-request send-receipt reconciliation after PR #603 review identified it had been inserted before the prior ledger tail. The record is now appended after the prior tail; the full 205-record JSONL parsed at that checkpoint. Focused tests (3 passed), routine harness, context/ecosystem validation, and `git diff --check` pass. Exact-head hosted revalidation remains pending. The repair changes no source-rights or acceptance state.

## PBS public API rights source review (2026-09-29)

- [x] Review the official PBS API overview and FAQ. The public API is available without identity requirements and its documentation expressly describes downloading schedule data to local storage for a user’s own systems/databases; the API contains effective schedules for the most recent 12 months. The documentation does not specify a retention duration or external redistribution licence. Do not apply authenticated HPP portal terms to the distinct public API. This clarifies the documented local-copy operation but makes no legal conclusion or maintainer rights decision.
- [~] Keep API acquisition pending a source-specific maintainer decision defining permitted internal retention; seek provider clarification for retention duration and external redistribution. No payload request or acquisition was made.

- [x] Reconcile the current API data-model document update date. The official
  API overview lists the v3.7.8 data-model PDF as updated August 2026; the
  machine-readable access preflight now records its exact public URL and month
  separately from the May 2026 API release-note date. This is documentation
  freshness evidence only; no API payload was requested and source rights,
  current API semantics, and M-109 remain unresolved.

## Exact P7 real-source field-lineage follow-up (2026-09-29)

- [x] Qualify the pinned July 2024 P7 workbook's complete value-free field
  lineage on exact `main`. PR #607 supplied the candidate-only lineage and PR
  #608 sanitized its hosted artifact before retention; both merged and all
  required checks passed. Run `36473432952` verified four sheets, 13,742 cells,
  and 99 fields in the durable receipt
  `quality/qualifications/mbs-p7-workbook-field-lineage-20260929.json`.
  The date profile remains unset and semantic promotion remains false. Focused
  tests: 81 passed; the one full local profile had two existing pinned-uv
  reproducibility failures, one optional skip, and 96.71% coverage. This does
  not establish the distinct aggregate-patient denominator or complete M-107.

## MBS v4 current-head candidate identity reconciliation (2026-09-29)

- [x] Re-read the public MBS v4 manifest, qualification, B1 receipt, exact
  publication receipt, and current dataset tree. The original anonymous
  publication receipt's nine objects, including all six Parquet LFS SHA-256
  identities and byte counts, still match at the publication revision and
  current dataset head. No table or source payload bytes were fetched.
- [x] Update the Actions-only aggregate qualifier to verify that public identity
  and compare the current candidate's deterministic source, table, field,
  lineage, and quality denominators with the public candidate. Resolve only the
  stale `public_v4_identity_unverified` aggregate blocker after all metadata,
  receipt, LFS, and candidate-only checks pass. The embedded published
  qualification and candidate-only status remain unchanged.
  Focused qualification tests: 30 passed, including review-driven coverage that
  binds the manifest's B1 receipt digest to the canonical fetched receipt;
  Ruff, format, `ty`, BasedPyright, and context validation passed. The updated
  live exact-main readback remains pending. Full Test-Goblin:
  5,230 passed, 2 failed, 1 skipped, 96.72%; both failures are the existing
  clean-clone release reproducibility checks requiring pinned `uv` 0.11.29,
  unavailable locally (the installed version is 0.12.19).
- [x] PR #633 merged through protected CI as `0b062f947d2e641a862ff7d9d8e81439c5718efd`; all required checks passed. Exact-main workflow run `36594992662` passed on that commit. The aggregate confirms the canonical B1 receipt digest, nine public objects, six Parquet LFS identities, and matching six-table denominator; `resolved_blockers` includes `public_v4_identity_unverified`, `current_blockers` is empty, and `promotion_status=candidate_only`. Publication was false and source bytes were not retained. This does not establish M-109 acceptance, federation acceptance, or Stable v1 approval.

## M-109 exact MBS XML v3 field semantics (2026-10-05)

- [x] Qualify official field meanings and candidate destination semantics for
  the exact July 2025 MBS XML v3 era. The field crosswalk covers all 40 native
  fields contracted by Silver and binds to the exact source digest, 5,989
  source records and 239,560 field occurrences. Exact-era date parsing remains
  supported by the separate hosted date receipt. Add a regression that checks
  the semantic document against the adapter's native field denominator and
  preserves explicit non-transfer boundaries. This closes field-meaning
  evidence for this era only; it does not admit Silver or complete M-109.
- [ ] Repeat native field meaning, temporal semantics and candidate
  transformation qualification independently for the P7 workbook, each
  approved later MBS era, each required PBS historical era, and current PBS API
  only after its access/retention/redistribution gates are resolved.

## M-109 source-era denominator reconciliation (2026-10-05)

- [x] Publish a source-era register that distinguishes exact MBS/PBS profile
  evidence, historical XML schema families, fixture-only coverage, and current
  PBS API rights state. Reconcile the M-109 kickoff denominator verbatim and
  preserve its incompleteness: later-approved MBS snapshots and governed PBS
  v3 releases are not yet enumerated as exact source identities. Do not mark
  M-109 accepted from this inventory.
- [ ] Enumerate the approved exact-source identities and acquire the pending
  maintainer/provider rights decisions before any PBS public API payload
  request. Continue semantic qualification era by era after these are explicit.


## M-112 public producer metadata discovery (2026-09-30)

- [x] Join every candidate raw payload path to its exact pinned dataset
  manifest using metadata only. All 1,736 paths map when the nested MBS
  acquisition manifest and durable hosted receipt are included; 1,735 appear
  in root manifests, and the current MBS root manifest omits the August 2026 XML. Of 1,634 available tree
  SHA-256 comparisons, all match manifest checksums; 102 candidate paths have
  no comparable tree digest. The August XML's exact authorization and previous
  anonymous hosted verification are confirmed. A later exact-revision readback
  reconciles its two append-only B1 acquisition events to the same raw source
  identity; the distinct source-Parquet projections still require lineage, and
  no v4 admission is made. The
  PBS archive's exact maintainer authorization and historic anonymous
  verification are confirmed; broader source terms and the shared
  reimbursement-atlas rights remain open.
  Audit: `quality/qualifications/australian-m112-manifest-join-audit-20260930.json`;
  updated crosswalk:
  `quality/qualifications/australian-m112-source-rights-lineage-crosswalk-20260930.json`.
- [x] Reconcile the two August MBS B1 records as distinct append-only
  acquisition events using the exact current public revision. Both records
  bind source `au-mbs`, effective date 2026-08-01, the same raw XML SHA-256 and
  size, the same rights reference, and the same `raw-acquisition-v1`
  transformation. Separate hosted receipts bind each acquisition and decision
  ID to its own immutable public revision. Preserve both events; do not
  collapse or supersede either. Their source-Parquet LFS digests differ and
  remain separate projection identities requiring lineage. The staged release
  manifest's `data_acquired=false` is an intentional contract invariant; the
  hosted transaction receipt separately records successful acquisition.
  Current tree metadata confirms the raw XML path and byte size, but exposes
  only a Git blob SHA-1, not a comparable tree SHA-256. The root manifest still
  omits that path, while both nested manifests and historic hosted receipts
  bind it. This reconciles source identity only; source rights, reviewer
  status, full-denominator per-object rights, projection lineage, anonymous
  readback for the full denominator, v4 admission, and consumer canaries remain
  open. Receipt:
  `quality/qualifications/australian-m112-mbs-b1-event-reconciliation-20261001.json`.
- [x] Join available per-object MBS/PBS receipt sidecars to raw manifests and
  existing authorization records using exact source ID, category, path, digest,
  size, and hostname metadata. All 20 MBS/PBS utilisation receipts match their
  manifest rows and the declared bounds in their existing authorization
  records. All eight MBS source candidates map to exact receipt, legacy
  authorization, or hosted-publication identities; the August XML remains
  omitted from the root manifest and is represented by two distinct,
  unreviewed B1 acquisition events with separate public transaction receipts.
  The one PBS source object matches its B1 receipt exactly. Decision 0009 and
  issue #340 also establish maintainer authorization and historic anonymous
  verification for the same archive digest, which matches the current pinned
  object. The earlier source-rights ledger still has upstream terms as unknown;
  this does not establish broader source licensing or v4 admission. See
  `quality/qualifications/australian-m112-receipt-sidecar-join-audit-20260930.json`
  and `quality/qualifications/australian-m112-source-archive-receipt-join-audit-20260930.json`.

- [x] Apply the maintainer's direction to keep Australian M-112 limited to
  Australian MBS/PBS producer evidence; track New Zealand health appropriations
  separately. This resolves the jurisdiction boundary only, not the exact
  producer/object denominator or any source-rights decision.
- [x] Map six Australia-related public repository candidates at exact observed
  revisions: the GMA source catalogue, MBS/PBS source archives, both utilisation
  archives, and reimbursement-atlas. None names the required federation v4
  contract. Reimbursement-atlas has a v1 federation manifest and 1,707 raw PBS
  manifest entries; MBS Silver remains candidate-only; utilisation coverage
  includes a partial harvest; Australian source catalogue rows remain marked
  unapproved for public-derived release. Candidate identities and tree digests
  are in `quality/qualifications/australian-m112-scope-assessment-20260930.json`.
- [x] Read back live collection alignment after the scope decision. `Policy AUS`
  remains private and empty; the public Health Economics collection includes
  both Australian source archives, reimbursement-atlas, and the separately
  scoped New Zealand funding dataset. The current registry has no entries for
  the GMA source catalogue or four Australian source/utilisation archives.
  A five-dataset Policy AUS membership and cautious collection/item notes are
  prepared in the scope assessment. No public collection or registry changes
  were made.
- [x] Capture a paginated, public-metadata-only discovery of candidate
  Hugging Face datasets whose names match the GMA, Australian MBS/PBS, or
  reimbursement-atlas filters, then review owner-visible metadata for adjacent
  producers. The receipt now pins 15 candidate dataset revisions and complete
  tree inventories for 2,930 file paths, including New Zealand health
  appropriations. A stable authenticated double scan records 81 visible owner
  datasets (76 public and 5 private with identities pseudonymized) and 10
  collections. No payload bytes or source values were read. This is discovery,
  not an approved producer denominator. Receipt:
  `quality/qualifications/federation-v4-public-producer-discovery-20260930.json`;
  complete owner snapshot: `quality/qualifications/hf-estate-20260930.json`.
- [x] Compare the current authenticated-visible owner estate and live
  Health Economics collection with the pinned public dataset-estate registry.
  The registry has 52 entries, matching 50 public and 2 private current
  datasets; 26 public and 3 private visible datasets are missing. The collection
  also includes the New Zealand funding dataset, so its placement in the
  Australian M-112 denominator requires explicit scope classification. No
  private identities were copied into the comparison, no rights were inferred,
  and no registry mutation was made.
- [x] Approve the exact producer/object denominator for qualification only:
  1,736 raw source payload paths plus 23 existing projections across five
  Australian MBS/PBS candidate repositories. See
  `quality/qualifications/australian-m112-denominator-decision-20260930.json`.
- [x] Refresh the authenticated-visible candidate metadata immediately before
  considering the prepared public collection/registry update. The Oct 1
  Brisbane readback confirmed a stable double scan of 81 datasets (76 public,
  5 private) and 10 collections; all five proposed producer heads and the
  dataset-estate-registry revision still match the pinned proposal. Policy AUS
  remains private and empty. No source bytes were read and no external
  mutation occurred. See
  `quality/qualifications/australian-m112-public-metadata-readback-20261001.json`.
- [x] Reconcile the owner estate and collection memberships in the public
  dataset-estate registry, and make `Policy AUS` public with scoped dataset
  notes. The sole maintainer approved the metadata-only transition; hosted run
  `36816927372` published registry revision
  `4802d56a340646043fc91bed218c1e8a958f42c2` and the exact approved 5-member
  Policy AUS / 6-member HEOR state. The corrected anonymous detail-endpoint
  scan is stable across two reads and confirms all approved notes. Durable
  receipt and readback are recorded in the public federation track at
  `quality/qualifications/hf-public-metadata-publication-receipt-20261001.json`
  and `quality/qualifications/hf-public-metadata-readback-20261001.json`.
  This closes only metadata visibility and registry consistency; it does not
  establish per-object rights, v4 admission, lineage, or M-112 acceptance.
- [ ] Independently bind the approved denominator's per-object source
  membership, rights, v4 contract, lineage, and anonymous public readback, then
  run consumer compatibility canaries against those pinned identities. M-112
  remains blocked; denominator approval, public visibility, and metadata
  inventory are not object-admission evidence.
- [x] Reconcile the previously stale CMS Part D rights review, disposition,
  publication queue, and producer-discovery governance join to the explicit
  2026-08-27 exact-inventory decision and anonymous receipt at pinned revision
  `abcff8ebd1f624c4bbb0a87d903b184388c98254`. This is limited to 30 formulary
  releases and 3 spending resources; the later public dataset head is not claimed
  to have a matching raw digest receipt.

- [x] Review correction: scope the credential boundary accurately. The GitHub receipt was read with the existing authenticated `gh` session; Hugging Face metadata reads were anonymous; no credential material was inspected or logged. See `quality/qualifications/australian-m112-mbs-hosted-receipt-20261003.json`.

## M-112 approved-denominator current-state reconciliation (2026-10-04)

- [x] Correct the pre-decision crosswalk's stale claim that the candidate
  denominator was still unapproved. The exact five-producer denominator
  (1,736 raw paths plus 23 existing projections) was approved on 2026-09-30;
  preserve the older crosswalk unchanged and record the correction in
  `quality/qualifications/australian-m112-current-state-reconciliation-20261004.json`.
- [x] Reconcile public registry state after the approved metadata publication:
  Policy AUS is public with five members and Health Economics has six members.
  Neither membership implies rights or v4 admission.
- [x] Reconcile the latest anonymous two-scan tree receipt: all 1,759 approved
  candidate paths are present at their pinned revisions. This is metadata
  path-presence evidence; full-denominator anonymous object-digest readback,
  current-tree digest comparison, source rights, per-object lineage, v4
  admission, and compatibility canaries remain open.
- [ ] Complete the remaining per-object rights, B1/B2 lineage, anonymous
  payload-digest readback, v4 admission, and consumer canary gates. M-112
  remains blocked until every approved object satisfies its independent gates.

## Source archive digest reconciliation (2026-10-04)

- [x] Bind two Australian raw source-archive candidates (MBS August XML and
  PBS April ZIP) to exact current manifests and existing hosted anonymous
  digest receipts. Together with the companion utilization reconciliation,
  22 of 1,736 raw paths have per-object digest joins; this does not complete
  full-denominator readback, rights, lineage, v4 admission, or canaries.
  See `quality/qualifications/australian-m112-source-archive-digest-reconciliation-20261004.json`.
- [x] Address review finding by linking the exact source/file/destination MBS
  authorization receipt alongside Decision 0009 and fingerprinting the public
  receipt body. This does not extend authorization to other sources.

## Current-tree object identity and eligible digest follow-up (2026-10-04)

- [x] Reconcile the approved 1,759 paths against anonymous tree metadata at
  all five pinned revisions. Git blob IDs and byte counts match for all paths;
  available current LFS SHA-256 metadata matches 1,645 paths (1,634 raw and
  11 projections). These metadata matches do not replace anonymous byte reads
  for non-LFS objects.
- [x] Reuse 24 existing hosted verification records and hash four additional
  rights-permitted MBS source objects at the current pinned revision. Their
  9,055,125 bytes were streamed into SHA-256 without source-value inspection or
  file persistence. One duplicate August path is linked by its identical Git
  blob ID to the hosted-verified path and is not counted as a separate byte
  hash. See
  `quality/qualifications/australian-m112-current-tree-object-identity-reconciliation-20261004.json`.
- [x] Bind the aggregate tree-identity counts to the 1,759 path-level metadata
  observations and all 39 anonymous metadata response-page SHA-256 receipts.
  This preserves the exact pinned-revision object IDs, byte counts, available
  LFS digests, and mismatches without retaining source payloads.
- [x] Correct the supplemental metadata inventory to use the authoritative
  current revisions in the public-tree readback. The earlier supplemental scan
  used the older candidate-inventory revision for the MBS source archive; the
  corrected per-path inventory now binds every row to the current revision and
  the test enforces this distinction.
- [x] Defer all 1,707 reimbursement-atlas raw candidates and 12 projections
  from M-112 admission while source-specific rights and lineage are unresolved.
  Keep all 1,719 paths inside the maintainer-approved denominator and record
  their future re-entry trigger in
  `quality/qualifications/australian-m112-deferred-source-candidates-20261004.json`.
- [x] Defer 34 candidate paths with distinct source-rights or B1/projection
  lineage gaps: both August MBS raw path aliases and ten projections, the PBS
  archive raw object and projection, and 20 utilisation objects. The later
  six-path reconciliation records the remaining MBS raw candidates separately;
  neither record makes an admission or new licensing claim.
  See `quality/qualifications/australian-m112-additional-deferred-source-candidates-20261004.json`.
- [x] Reconcile the six remaining MBS raw candidates to their exact current
  tree identities, existing receipt/authorization joins, prior or current
  anonymous digest evidence, and missing B1/rights/v4 fields. Defer all six in
  the future-source register without changing the approved denominator. The
  four July 2026 sidecars lack rights/reuse/authorization/acquisition fields;
  the July 2025 v4 receipt reference is absent locally; and P7 date semantics
  remain unqualified. Re-entry triggers preserve these gaps explicitly.
- [x] Explicitly defer the 92 raw and 12 projection candidates without direct
  SHA-256 metadata into the future-source register, bound to their exact
  current paths, revision, Git blob identities, and byte counts. The register
  retains the existing source-rights and B1/B2 re-entry trigger; no bytes were
  read and no digest, rights, lineage, v4 admission, or canary result is
  inferred. Contract test verifies all 104 paths against the pinned public
  inventory. The remaining MBS August admission history, utilisation rights,
  projection lineage, exact v4 admission, and consumer canaries remain open.
  See
  `quality/qualifications/australian-m112-unhashed-deferred-candidates-20261004.json`.
- [x] Correct the MBS B1 chronology without retroactively rewriting the
  August acquisition. On the exact authorized main commit, the hosted workflow
  anonymously verified the raw archive object, then appended a new acquisition,
  B2 external-reference manifest, and ordered `landed` then superseding
  `accepted` records in a second metadata commit. The five B1/B2 metadata
  objects passed anonymous digest verification before temporary source bytes
  were removed. Reconciled the public metadata into the local Bronze ledger,
  the MBS source receipt, landing and publication queues, and maturity audit.
  The bounded Bronze qualification remains 14/14 mandatory dimensions with no
  blockers; the receipt-backed cohort is 29 sources. MBS source-record
  projection lineage, v4 admission, M-112 federation, and Stable v1 approval
  remain separate gates. See
  `quality/qualifications/australian-mbs-bronze-source-receipt-20261004.json`
  and `quality/qualifications/bronze-maturity.json`.
- [x] Join the new MBS raw B1/B2 lifecycle to both approved August M-112 raw
  archive aliases by source ID, version, exact SHA-256, and byte count. Both
  aliases still resolve to one producer object at their pinned revision; the
  producer's prior accepted records remain unchanged. This reconciles source
  identity and the local landed-to-accepted chronology only. Producer source-
  Parquet lineage, v4 admission, consumer canaries, and M-112 acceptance remain
  open. See
  `quality/qualifications/australian-m112-mbs-lifecycle-crosswalk-20261004.json`.
- [x] Restore the July 2025 MBS v4 candidate's source-receipt metadata from
  the anonymous pinned producer revision and verify its raw object identity,
  canonical receipt digest, and manifest/source/qualification joins. The
  value-free qualification remains `candidate_only` and still reports
  `public_v4_identity_unverified`; the local M-112 acquisition event, reuse
  disposition, v4 admission, canaries, and federation acceptance remain open.
  No source payload was read. See
  `quality/qualifications/australian-m112-2025-mbs-v4-receipt-readback-20261004.json`.
- [x] Verify the July 2025 v4 candidate identity against the live anonymous
  dataset tree and immutable publication receipt. All nine expected object
  sizes/digests and the current manifest metadata match the receipt; a newer
  append-only dataset head does not invalidate the pinned publication receipt.
  Supersede only `public_v4_identity_unverified`; retain candidate-only status
  and the separate M-112 admission/canary gates. No payload bytes or values
  were read. See
  `quality/qualifications/australian-m112-live-public-v4-metadata-readback-20261004.json`
  and the digest-bound current-state addendum.
- [x] Apply the maintainer's exact-scope rights approval to all 14 MBS-
  utilisation raw objects in the pinned archive manifest. Official data.gov.au
  metadata identifies the two represented datasets as CC BY 3.0 Australia;
  the decision binds both metadata response hashes, the existing publication
  authorization, archive revision, manifest digest, and 14/14 receipt-sidecar
  joins. Preserve the candidate denominator and historic hash-bound readbacks.
  The objects remain deferred because per-object B1 rights/reuse fields,
  complete B1/B2 lineage, v4 review, and consumer canaries remain open. The
  third source ID in the broader authorization has no object in this cohort.
  See `quality/qualifications/australian-mbs-utilisation-exact-scope-rights-decision-20261004.json`
  and `quality/qualifications/australian-m112-utilisation-rights-reconciliation-20261004.json`.

- [x] Prepare append-only per-object rights metadata for the exact 14 approved
  MBS-utilisation objects, bound to raw identities and historical receipt
  digests. This local preparation does not publish metadata or complete
  acquisition lineage, v4 admission, or consumer canaries.

- [x] Bind the prepared 14-object rights supplement to an exact metadata-add
  contract with pinned parent, content-addressed path, preservation, CAS and
  anonymous readback controls. Hosted runner implementation and execution
  remain separate next steps; this contract performs no publication.

- [x] Implement offline validation for the exact MBS-utilisation rights append
  contract, approval, cohort identities and controls. This validator performs
  no I/O and supplies no hosted publication or admission evidence.

- [x] Implement hosted-only orchestration for the exact rights append, reusing
  the anonymous Hub transport protocol and server-enforced CAS. Persist intent,
  acknowledgement and all-object verification in order; propagate failures
  without rollback or automatic retries. Workflow wiring and actual dispatch
  remain separate; no publication is performed during this implementation.

- [x] Wire the exact MBS rights executor into the protected Actions environment,
  reuse the existing bounded anonymous transport and durable receipt store,
  and dispatch on the reviewed main commit. Verify all existing objects plus
  the one addition, then reconcile the hosted receipt without claiming v4
  admission, acquisition lineage completion or consumer canaries.
  Hosted run `37192560767` at reviewed commit `d4004200bd4f9bf837cb21b88223b9cc3f912ea3`
  verified all 31 objects at publication revision `87d63977f546dc5cc7c4f5371e37e77a7dfc0ddf`,
  preserved all 30 baseline objects and durably recorded cleanup. See
  `quality/qualifications/australian-mbs-utilisation-rights-publication-receipt-20261004.json`.

- [x] Reconcile every approved M-112 path individually against current-tree
  identity, anonymous digest receipts, rights, B1/B2 lineage, v4 admission,
  consumer canaries, and its preserved deferral group. The 1,759-row ledger
  confirms all pinned tree identities and sizes, 28 object-level anonymous
  digest readbacks, and exact-scope rights evidence for the 14 MBS-utilisation
  objects. No path has complete B1/B2 lineage, v4 admission, or canary proof;
  all 1,759 remain deferred without changing the approved denominator. The
  smallest rights-cleared cohort cannot advance because its canonical source
  receipt, storage receipt, and admission-history fields remain incomplete.
  See `quality/qualifications/australian-m112-per-object-gate-reconciliation-20261005.json`.

- [x] Restore the exact 14 historical harvest sidecars anonymously and join
  their source IDs, categories, dates, URLs and raw identities to the pinned
  B2 references and published per-object rights supplement. Preserve their
  original bytes, retrieval times and source-native period labels; do not
  infer publication/effective dates or invent acquisition/admission IDs.
  Identity linkage is complete; native event selection/import and admission
  lifecycle metadata remain open. See
  `quality/qualifications/australian-mbs-utilisation-acquisition-crosswalk-20261004.json`.

- [x] Import 14 receipt-derived historical acquisition events using the existing
  native schema and deterministic identity function. Preserve source clocks
  and unknown fields; distinguish imported repository IDs from producer IDs.
  Admission histories, full lifecycle and external publication remain open.
  See `quality/qualifications/australian-mbs-utilisation-acquisition-import-20261004.json`.

- [x] Reconcile SourceReceipt and storage evidence for all 14 imported MBS
  events against the pinned public archive inventory and native contracts;
  identify unsupported fields without fabricating transformations, replication
  controls or admission evidence.
  See `quality/qualifications/australian-mbs-utilisation-lifecycle-reconciliation-20261004.json`.

- [x] Define a closed historical raw-reference import profile and materialize
  all 14 exact MBS receipt/event/raw/rights joins without claiming native
  transformed receipts, replication controls, payload validation or admission.
  See `quality/qualifications/australian-mbs-utilisation-raw-reference-import-20261004.json`.

- [x] Package the 14 historical raw-reference imports, acquisition events and
  closed profile schema into one exact lifecycle metadata bundle, and pin its
  append-only Actions publication contract to the verified dataset parent.
  Contract preparation alone does not publish or admit evidence.
  See `quality/qualifications/australian-mbs-utilisation-lifecycle-append-contract-20261004.json`.

- [x] Implement exact offline lifecycle validation and reuse the guarded
  hosted append protocol through a protected Actions runner. Verify hosted
  publication independently before claiming publication or cache cleanup.
  Hosted run `37200047657` at `a8751ed711c9f34bf92547b1a3314c5b8b3b9c56`
  verified all 32 objects at `f1c75a0465d8cc22841c498274360753d0aab365`,
  preserved all 31 baseline objects and durably recorded cleanup. See
  `quality/qualifications/australian-mbs-utilisation-lifecycle-publication-receipt-20261004.json`.

- [x] Preflight the exact 14-object MBS validation cohort against current
  archive resource bounds. Record current quarantine decisions for oversized
  archives while retaining all raw evidence and other candidates; do not
  infer payload validity or processing acceptance from object metadata.
  See `quality/qualifications/australian-mbs-utilisation-validation-preflight-20261004.json`.

- [x] Implement file-backed ZIP member verification with existing archive
  limits, exact compressed identity checks and streamed CRC/digest checks.
  Validate using synthetic archives before integrating hosted MBS validation;
  this implementation alone does not validate or admit any source object.

- [x] Integrate exact-cohort hosted validation with isolated bounded readers,
  per-object failure outcomes and durable public-safe receipts. Verify CSV
  shape and XLSX package structure separately from archive integrity and
  admission; retain both preflight resource holds.
  Hosted run `37207295524` at `fb9df741d028611068cd4dc560204ea887fe3033`
  recorded 10 structural-profile passes, two workbook profile failures and
  both prior ZIP resource holds. All 12 downloaded objects matched their
  pinned digest; 15 durable receipts were independently read back. No object
  was admitted. See
  `quality/qualifications/australian-mbs-utilisation-payload-validation-receipt-20261004.json`.

- [x] Classify the March and June 2016 demographics workbook profile failures
  through bounded hosted diagnostics before selecting any recovery or
  source-specific processing-admission step. Preserve raw evidence and limits.
  Hosted run `37226168808` identified `archive_expanded_byte_limit` for
  both exact workbooks under the existing 128 MiB XLSX profile. Three native
  receipts were independently read back; no other object was retested and
  later package/worksheet checks remain unqualified. See
  `quality/qualifications/australian-mbs-workbook-diagnostic-receipt-20261005.json`.

- [x] Prepare a bounded streaming workbook validation profile before any
  recovery or processing admission of the two resource-blocked workbooks.
  Preserve existing guards, raw references, ten prior profile passes and both
  oversized ZIP holds.

  Prepared `docs/qualification/australian-mbs-streaming-workbook-profile.md`;
  no runtime limits changed and no source recovery run performed.

- [x] Implement and test the separate streaming workbook profile, then qualify
  only the two pinned workbooks through hosted receipts before any admission.

  Hosted run `37243073339` at `02026bcc58652a874532f73d194f68bfcc1b6eac`
  verified both exact workbook identities and streaming structural profiles.
  Three native receipts were independently read back; both verified cache
  files were removed after durable outcomes. Twelve cohort objects now have
  structural evidence; two oversized ZIP holds remain, with zero admissions.
  See `quality/qualifications/australian-mbs-workbook-streaming-receipt-20261005.json`.

- [x] Define source-specific utilisation semantic validation and admission
  requirements from approved source documentation and native evidence; keep
  the two oversized ZIP holds and wider M-112 gates separate.

  The metadata-only requirements receipt joins all 14 exact objects to
  current official resource documentation and records four schema queries
  with zero returned data rows. It preserves signed service adjustments,
  source-specific cut-offs and catalogue schema eras without selecting native
  payload mappings or granting admission. See
  `quality/qualifications/australian-mbs-utilisation-semantic-requirements-20261005.json`.

- [x] Implement protected hosted native-header inventory for the four already
  structurally verified standalone CSVs. Bind exact source identities and
  record header metadata only before selecting any semantic conversion.
  Exact-main run `37410581626` inventoried four existing public CSVs. All four
  anonymous digests matched; each had eight headers, matched a reviewed
  catalogue schema candidate, and had zero unexpected fields. The Q1 and Q2
  demographics headers match the Q3 schema candidate rather than their own
  resource's schema; this establishes header shape only, not semantic mapping.
  Durable per-object and summary receipts were independently read back from
  issue #340; hosted temporary caches were removed after receipts were
  recorded. No source was
  added, and no semantic validation, admission, or licensing conclusion
  changed. See
  `quality/qualifications/australian-mbs-utilisation-header-inventory-20261006.json`
  and the cross-resource schema reconciliation in
  `quality/qualifications/australian-mbs-utilisation-header-schema-reconciliation-20261006.json`.

- [x] Implement and execute bounded, source-value diagnostics for only these
  four exact-reference standalone CSVs. Synthetic tests cover strict UTF-8/BOM
  handling, rectangular rows, exact decimal observation (including signed
  service totals), missing-cell counts, and digest-bound results. Exact-main
  run `37416203337` at `22ef98006b6002aa5b3b9778b68b54ea4a7f97df` observed
  1,463,030 rows across the four pinned CSVs; all rows were rectangular and no
  cells were empty. Q2 demographics has 4,728 `Services` values outside the
  strict decimal token profile; their lexical forms remain unclassified and
  must not be treated as zero or silently coerced. Four object receipts and a
  summary receipt were independently read back from issue #340; all exact
  digests verified and caches were removed after durable receipts. No raw row
  values were published, no source was added, and no semantic mappings,
  processing admission, or Silver publication occurred. See
  `quality/qualifications/australian-mbs-utilisation-value-observation-20261006.json`.

- [x] Classify invalid numeric tokens into disjoint aggregate lexical
  categories in the isolated exact-main observer. Run `37417959155` at
  `a44e18d8ced37019391fef2212262e50da64bc47` verified all four source digests
  and found all 4,728 Q2 demographics `Services` failures in the separator
  category; the other three CSVs had zero invalid `Services` tokens, and all
  `Benefit` values matched the strict decimal profile. Five receipts were
  independently read back and caches removed after receipt. No token values,
  mappings, admissions, or Silver rows were published. See
  `quality/qualifications/australian-mbs-utilisation-invalid-token-category-observation-20261006.json`.

- [x] Refine the Q2 `Services` separator bucket into aggregate-only lexical
  punctuation-pattern classes. Exact-main run `37419485884` at
  `e1eae264d7380c600e2a337ac9ac7d4bc84415a9` classified all 4,728 invalid Q2
  `Services` tokens as matching a comma-triplet pattern; all other separator
  and invalid-token categories were zero. Four exact-source receipts and the
  summary were independently read back; digests verified and temporary files
  removed after receipts. This is a lexical pattern only, not a semantic
  grouping interpretation or permission to normalize. No new source, mapping,
  admission, or Silver output. See
  `quality/qualifications/australian-mbs-utilisation-separator-pattern-observation-20261006.json`.

- [x] Prepare a synthetic-only, explicit-policy exact numeric parser for
  candidate MBS profiles. A caller must supply the representation policy;
  grouping is disabled by default, signed values and decimal scale are
  preserved, malformed grouping and exponent forms are rejected, and errors
  never echo tokens. Twenty-five synthetic tests pass with 100% statement and
  branch coverage. No source bytes were read and no source profile, row mapping,
  transformation, admission, or Silver output was selected. See
  `quality/qualifications/australian-mbs-utilisation-numeric-policy-20261006.json`.

- [x] Define synthetic candidate row mappings for the existing demographics
  and group CSV shapes from reviewed documentation. Preserve source-native
  identifiers and period/category tokens; keep each field's semantic role and
  row grain explicitly qualified or unresolved. Do not read source rows,
  normalize numeric values, admit data, or publish Silver in this step. The
  resulting contract maps only candidate roles and marks the demographics and
  group grain as unverified. It records each unresolved period, category,
  numeric, suppression, and identifier rule explicitly. No source bytes or
  rows were read. See
  `quality/qualifications/australian-mbs-utilisation-candidate-row-mappings-20261006.json`.

- [x] Extend the protected four-CSV observer contract with aggregate-only
  non-measure token-shape counts and candidate-grain duplicate-record counts.
  Candidate keys are held only as bounded in-memory digests; processing fails
  closed after one million unique keys. No raw token or key is emitted, and
  the proposed grain remains explicitly unverified. Synthetic observer tests
  pass with 100% statement and branch coverage. Exact-main execution is still
  pending; no source bytes were read locally.

- [x] Run the candidate-shape observer on exact main for the same four pinned
  CSV references. Independently verify the per-object and summary receipts,
  confirm the new aggregate fields contain no tokens, and remove staged bytes
  only after digest-bound receipts. Exact run `37427434385` at
  `07eb1bb8202e4abae4512605ca3e8537fafe66ef` verified all four digests and
  five receipts. The 1,463,030 rows were rectangular, with no empty cells or
  repeated candidate keys. Q2 `Services` retained 4,728 comma-triplet lexical
  failures. The row grain and source semantics remain unverified; no admission
  was granted. See
  `quality/qualifications/australian-mbs-utilisation-candidate-shape-observation-20261006.json`.

- [x] Implement a candidate processing-period observer bound to the four
  exact resource IDs and the saved official resource-description digests.
  Require a four-digit 2016 year token and recognize only English full or
  three-letter month names, without trimming or rewriting the source token.
  The per-resource allowed month sets reflect the documented Q1, through-May
  Q2, July Q3, and year-to-date-through-July group bounds; they impose no
  minimum-period or completeness claim. Aggregate output records recognized,
  invalid, mismatched, and out-of-window counts, with no raw tokens or row
  transforms. The observer tests pass with 100% statement and branch coverage;
  no source bytes were read locally.

- [x] Run the candidate processing-period observer on exact main for the same
  four CSVs and independently read back its five receipts. Confirm the month
  spellings and resource-specific bounds only through aggregate outcomes.
  Exact run `37431102764` at `3fa9fd1d6326e816c4540b49a2dd11a8bf9fcb27`
  recognized all 1,463,030 candidate periods, with no year or month parse
  failures. Q2 contradicts its saved “current through May” description:
  190,050 rows classify to June. Five receipts were independently verified,
  digests matched, and temporary bytes were removed after receipt. The
  discrepancy remains open; no cutoff override, period semantic acceptance,
  admission, or Silver output. See
  `quality/qualifications/australian-mbs-utilisation-processing-period-observation-20261006.json`.

- [~] Resolve the Q2 source-description/payload cutoff conflict before
  accepting period semantics or admitting the Q2 object. Do not add sources or
  silently widen the captured May cutoff to make the observer pass.
