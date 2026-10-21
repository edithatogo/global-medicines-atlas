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
  run `33310284274`, with unsupported values explicitly retained. Exact-main
  requalification on `02ea12284c86c97c7c4151db58e19fa4d7bcf5c1` passed in run
  `38165126564`: all 13,742 cells across four sheets were reconciled to 99
  observed columns, with 97 headers and four unlabelled cells. The value-free
  report retains 36 unrepresentable numeric outcomes and 1,280 date-shaped
  cells without selecting date semantics; `semantic_promotion` remains false.
  See `quality/qualifications/mbs-p7-workbook-field-lineage-20261011.json`.
  This closes exact-main storage/header/lineage requalification only; broader
  value harmonisation and source-era date qualification remain open.

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
- [x] Re-run the value-free P7 storage, header, field-lineage, and conversion
  outcome profiler on current main. Hosted run `38165126564` verified source
  digest `2f1cbc2d2dcbb93be86f42c8dbbe9f5f9e8fb550cad38b6ee54d0e9bdd2e27b8`,
  recorded all four sheet and 13,742 cell denominators, and retained 99
  column-lineage records. The field-lineage report digest is
  `709273b2ce5da48e2efa36dfbfeac1221dc72b6de241eafbdcbaa7fe8bbf9a5b`.
  No cell values were retained; 36 values remain unrepresentable, the date
  profile remains unset, semantic promotion is false, and no product was
  published. Durable aggregate receipt:
  `quality/qualifications/mbs-p7-workbook-field-lineage-20261011.json`.

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
  XML candidates use two-pass bounded streaming: full-document structural,
  schema, identity, denominator, and receipt preflight precedes row output;
  record subtrees are detached and Silver output stays within 4,096 rows per
  Arrow batch. Broader real-corpus and other table-family qualification remain
  open.
- [x] Replace tree-retained MBS XML Silver conversion with the bounded stream
  and verify it under parser, schema-drift, provenance-identity, and full
  Test-Goblin checks (`35da943a`; PR #966 merged as `56511d48`; evidence in
  `evidence.jsonl`).
- [x] Add a synthetic sibling-stream regression proving completed direct-root
  `Data` subtrees are released during the event pass; document the parser and
  Arrow buffer bounds. The sibling-retention assertion is bounded by the
  configured parser chunk and minimum synthetic record size. Focused tests
  (35), adjacent MBS/Gold tests (75), routine checks, strict typing, and diff
  validation passed on 2026-10-12. PR #1035 merged as `6bae816e` with all 40
  hosted check rows passing (29 required), including the E2E lane and Linux,
  macOS, and Windows consumers. This test-only follow-up does not close the
  broader real-corpus qualification above.
- [x] Prove exact existing-source B2-to-Silver row-value parity for the
  already-qualified July 2025 MBS XML and the pinned v4 services Parquet.
  The hosted check binds the existing B1 receipt and both immutable public
  object revisions, compares all rows and fields, and emits a value-free
  receipt. PR [#929](https://github.com/edithatogo/global-medicines-atlas/pull/929)
  merged at `f9c56d32af3ad76d347ff1a25a9e5fcfd96c90e2`; the exact-head hosted
  receipt verified 5,989 rows × 17 fields. No rights, admission, publication,
  or promotion decision changed.
- [x] Re-run the exact parity verifier on current main after the bounded
  streaming-parser replacement. Commit `9c37ecb1589e03de7e63bbed4fc62f8cdf2713a8`
  reproduced all 5,989 rows × 17 fields from the same exact source and Silver
  revisions. Its value-free receipt is byte-for-byte identical to
  `quality/qualifications/mbs-source-silver-parity-2025-07-v3.json`
  (SHA-256 `009deabf772e91fedd7642f2b8f0e5a524abb76401620f8e93a8f3bd20189ded`).
  The pinned public objects were read in memory only; no source bytes were
  retained locally. No source identity, rights, admission, promotion, or
  publication decision changed. See the append-only current-main revalidation
  evidence row.
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
  The exact-main P7 workbook run below closes the real-workbook structural
  lineage subtask. Exact-source execution of the six-table XML aggregate
  candidate qualification passed on exact-main run `38199208744` at
  `46eda6025cfb12f861a5dd5d478fc320e56fc47e`: all six tables have 5,989 rows,
  their declared 40 fields account for 239,560 field occurrences, the official
  July 2025 release digest matches the pinned archive, and the nine-object
  public v4 identity is verified. This is candidate-only qualification; the
  workflow retained no source values or source bytes and made no publication.
  The public v4 identity was subsequently verified at revision
  `ba82cd1d0f9b0f28514df431b8da3a6c207d76fa` by run `36348699885`; no
  promotion is inferred.
  The hosted P7 qualification command now includes the deterministic
  value-free column-lineage report alongside existing metadata profiles.
  Exact-main run `38165126564` on `02ea12284c86c97c7c4151db58e19fa4d7bcf5c1`
  verifies the pinned 87,727-byte workbook (`2f1cbc2d…e27b8`): four sheets,
  13,742 cell positions and 99 column-lineage records, of which 97 are mapped
  and two `AV` columns are explicitly unmapped. The 7,643-byte compressed
  artifact ZIP has SHA-256
  `2652330da3465777b013776f5446e8467d1bfefe3a4422865ea22fb052077db5`;
  its checked-in 43,647-byte JSON member at
  `quality/qualifications/mbs-p7-workbook-field-lineage-20261011.json` has SHA-256
  `335a737fec71abc6f502d65417a6a2b40b9ff20933e710abe02fc92453274f74`;
  field lineage is candidate-only, the date profile is unset, Parquet roundtrip
  is verified, domain mapping is not qualified, and publication is false.
  The hosted workflow retained only the aggregate summary and did not retain
  the source workbook. This closes structural lineage observation for that
  exact workbook only; no date convention, Silver promotion, or source-coverage
  claim follows.
  - [x] Execute and reconcile the exact-main P7 workbook lineage qualifier.
    The workflow asserts the requested commit equals `GITHUB_SHA` on `main`;
    its exact-head job passed and the JSON member is bound to the exact source
    digest above. Its 99 column-lineage records include 97 mapped fields and
    two unmapped columns. Archive and member sizes/digests are recorded
    separately. Cell values and raw workbook bytes are absent from the member.
    No source was added; XML source qualification is recorded separately
    below.
  - [x] Requalify the existing pinned July 2025 MBS XML and published v4
    Silver identity together on exact main. Run `38199208744` verified the
    source SHA-256 and byte count against the official release, all six table
    denominators (5,989 rows each; 40 fields; 239,560 field occurrences), and
    all nine objects at public v4 revision
    `44b25bfd87e44998c7c1da4c3930ad4447e9246f`. The value-free aggregate report
    has no current blockers, but retains `candidate_only`; publication is
    false and source bytes were not retained. This does not establish M-109
    acceptance, rights clearance, broader source coverage, or promotion.

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
- [x] Stream PBS native-field Silver rows from the existing receipt-bound XML
  inventory. Preflight the complete XML with the no-tree safety validator
  before exposing rows, preserve the established depth-first slot order and
  B1/B2 identities, and release completed direct-root children during the
  bounded event pass. This retains the parser chunk and largest direct-root
  subtree; a single large wrapper can still approach the document limit.
  Synthetic sibling, late-tail text-limit, malformed-input, row/Parquet parity,
  and batch-bound tests pass. Full Test-Goblin passed on macOS with 6,264 tests,
  355 gremlin checks, and 96.87% coverage; Darwin mutation observations are
  advisory and Linux CI remains authoritative. Hosted qualification remains
  pending. No source bytes were read or acquired. Evidence is appended in the
  track log.
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
  explicit PBS controls and the legacy/current MBS edge contract. The prior
  implementation removed cases for terminal caller-supplied event chains
  without verifying reviewer authority; PR #1020 removed that route. Every case
  now remains pending until an independent authority verifier exists. This
  adapter creates no reviewer identity, adjudication, threshold, receipt,
  authority, admission or promotion. Earlier queue-state qualification had 9
  focused Gold-review tests and 38 adjacent Gold-review/MBS/PBS graph tests.
  The focused Gold/API/synthetic MBS-PBS E2E suite passes (25). The full local
  Test-Goblin invocation recorded 6,222 passed, 3 optional skips, and 2
  failures in stable-v1 reproducibility tests because the environment resolved
  uv 0.13.0 while the release contract requires uv 0.11.29; both failing tests
  passed on isolated rerun with the pinned version. Coverage was 96.89%.
  Reviewer authority, receipts, calibration, candidate promotion, and Gold
  acceptance remain pending.
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

### Gold review portable projection E2E (2026-10-10)

- [x] Exercise the pending-only review queue from Parquet-projected MBS and
  PBS Gold edges in the Bronze-to-Platinum synthetic E2E paths. Reconstruct
  each source edge from its separate evidence and controls columns; verify
  edge identity, exact full-content digest equality with each pre-projection
  edge, `pending_review`, and no promotion.
  Focused MBS/PBS E2E tests pass (2); Test-Goblin E2E passes (54); routine
  Test-Goblin checks pass. This closes projection-to-queue integration
  coverage only; adjudication authority, promotion, real-source controls, and
  the Gold phase checkpoint remain pending.

### Gold review append-only ledger E2E (2026-10-10)

- [x] Carry both MBS and PBS Parquet-derived Gold review cases through the
  append-only adjudication ledger and regenerate the pending queue from its
  readback. A supplied synthetic `needs_information` event keeps its case
  pending; a later chronological accepted event supersedes it and clears only
  that case. The same pending cases and post-adjudication state are now
  queryable through the bounded `gold-review-queue` CLI. Other PBS cases stay
  pending, no reviewer rationale is emitted, and no case or event performs
  promotion. The caller-supplied ledger is byte/event bounded and its serialized
  sequence must satisfy append-only supersession and chronology before it can
  affect the queue. This verifies persistence and queue mechanics only; the synthetic
  reviewer is not an authority grant or substantive review. Real reviewer
  authority, receipts, calibration, promotion, real-source controls, and the
  Gold phase checkpoint remain pending.

### Gold review ledger append/read boundary hardening (2026-10-17)

- [x] Keep adjudication JSONL readable and within its declared bounds after
  appends. Failing-first tests showed that appending could exceed the reader's
  byte/event limits, join onto a valid final record without a newline, and
  split legal U+0085/U+2028/U+2029 rationale text as if it were physical JSONL
  delimiters. Physical CR, LF, and CRLF boundaries are now parsed consistently;
  appends preserve old bytes, insert a missing record separator, and reject
  writes that would make the ledger unreadable by either bound. Focused review,
  API, and matching journeys pass (49); routine, Ruff, `ty`, BasedPyright, and
  diff checks pass. Commit `1a3bf114`. No adjudications, reviewer authority,
  promotion, source, licensing conclusion, or publication were created.
- [x] Replace the hand-indexed physical-line scanner with the standard byte
  splitter, which preserves the same CR/LF/CRLF and Unicode behavior while
  reducing custom parser logic. The affected 49-test selection and routine
  checks pass on the updated implementation. A local full profile completed
  with 6,469 passed, 3 skipped, and 4 failures (one Hypothesis timing/flaky,
  installed-browser E2E, and two stable-v1 subprocess/toolchain reproducibility).
  All four failed cases passed in a targeted rerun with pinned `uv 0.11.29`;
  this does not convert the full profile into a green run. Hosted mutation
  attempts 1–4 on head `8fababb5` each received runner shutdown near
  2,329/2,398 mutants; no mutation verdict was produced and the cause remains
  unresolved. The updated head requires fresh hosted checks.
- [x] Re-run the changed-source full profile on head `9a309008` with pinned
  `uv 0.11.29`: 6,472 passed, 3 skipped, one Hypothesis timing failure,
  96.89% coverage. The failing Unicode round-trip case passed alone on retry
  (1 passed); preserve the full-profile timing failure as recorded. All 40
  hosted checks passed on final PR head `a7b2d944`, including
  Linux-authoritative mutation, coverage, consumer, security, and context
  lanes. PR #1092 merged as `49c5cc118a06e762d3be08b48fa597454ace59eb`;
  the merge tree matches the exact checked head.

### Gold review CLI authority boundary (2026-10-11)

- [x] Mark the `gold-review-queue` CLI response with
  `adjudication_authority_verified: false`, including when a caller-supplied
  synthetic accepted event removes its case from the pending queue. The
  response remains candidate-only and performs no promotion. The intended
  regression failed before the field was added; focused review/API/graph tests
  pass (89), and full Test-Goblin passes with 6,189 tests and 96.89% coverage.
  (`edb622bd`; PR #968 merged as `1bc43c17`; evidence in `evidence.jsonl`.)
  This verifies output labelling only; no reviewer identity or authority is
  created or inferred, and real adjudication remains pending.
- [x] Assert the authority boundary through both synthetic MBS and PBS
  Bronze-to-Platinum review-queue journeys, before and after caller-supplied
  `needs_information` and accepted events. Every CLI readback remains
  `adjudication_authority_verified: false`, candidate-only, and
  `promotion_performed: false`; the accepted event removes only its case from
  the queue. Caller-supplied reviewer identity and rationale are not emitted
  by the CLI. Focused journeys pass (2), governed E2E passes (56), and routine
  checks pass. Test-only follow-up; no reviewer authority or source state is
  established. PR #970 merged as `efd60390e9734dca079e1f893d1a7b99041190b1`
  after all required checks, including `codecov/patch`, passed on exact head
  `9f1f0a999d436fa6bdb66bfa684f85799221dc8c`.
  Automated review found that the intermediate `needs_information` response
  also needed an explicit candidate-only assertion. Added it; the focused
  journeys, governed E2E lane, and routine checks pass again. The review
  conversation was resolved against corrected commit `8aee112f`; hosted checks
  passed on the final head before merge.
- [x] Require independent authority verification for every event in a terminal
  adjudication chain before it can remove a Gold edge from the review queue.
  The review CLI has no trusted authority verifier, so caller-supplied terminal
  events leave all cases pending; a future trusted verifier must identify every
  event in the chain. Focused Gold review/Platinum API/synthetic MBS-PBS
  Bronze-to-Platinum tests pass (25), routine checks and typing pass. The full
  pinned local profile first reached 96.90% coverage with 6,223 passed,
  3 skipped and one stale CLI expectation failure; after correcting the stale
  assertion, the affected tests passed. PR #1018 merged at exact head
  `9eb933facc132c3efb5a91dc761f007ef54454bd` as
  `adc2c297056e996fb75b52f3293af65a0a5450bb`; all 40 reported hosted check
  rows passed. No reviewer identity, authority, adjudication, promotion,
  source, licensing conclusion, or publication is created or inferred.
- [x] Remove caller-asserted event IDs as a route to clear Gold review cases.
  No independent authority verifier exists, so the review-queue library now
  keeps every case pending regardless of caller-supplied terminal events. A
  failing-first regression confirmed that arbitrary event IDs could previously
  make a case disappear. Focused Gold/API/synthetic MBS-PBS E2E passed (25).
  Full local Test-Goblin passed 6,222 tests and 96.89% coverage apart from two
  existing stable-v1 toolchain tests that passed on rerun with pinned uv
  0.11.29; 3 optional integrations were skipped. PR #1020 merged at exact head
  `bc90b25e4fe98244e9f0813fc7e7cd999e3a8389` as
  `dda9bae85026f91d9f43c321aced1532d0011960`; all 40 hosted check rows passed.
  This does not create reviewer authority, adjudication, promotion, source,
  licensing conclusion, or publication.

### Platinum PBS edge readback coverage (2026-10-09)

- [x] Exercise the existing PBS Gold candidate through both the Platinum edge
  API and CLI, asserting synthetic-only qualification, source identity,
  containment-only relation, non-inference control, and identical readback.
  The first assertion exposed a schema-shape difference: PBS stores
  `inferred=false` in the edge controls object, while MBS exposes it as a
  top-level Arrow column. The test now checks the PBS contract at its declared
  location. The five adjacent Gold graph/review and Platinum edge suites pass
  (50 tests); `ruff`, `ty`, and the routine harness pass. No source or
  production behavior changed. Full track acceptance remains open.

### Gold edge loopback HTTP E2E (2026-10-11)

- [x] Carry the actual synthetic MBS and PBS Gold Parquet edge outputs through
  `/api/v1/edges` over an ephemeral loopback HTTP server, then compare the
  returned pages with the in-process API and CLI readbacks. Assert each source
  identity and synthetic-only qualification. The full medallion/Atlas E2E
  selection passes (7) and routine checks pass. No source, rights conclusion,
  production behavior, or acceptance gate changed. PR #981 merged as
  `595d44591741ac72a3c5138f80aad0c8e29b3600` after all 38 reported checks
  passed; merge tree `97ba84bffbd30c2e650711ca5dd7976711f8fcab` matches the
  qualified head tree.

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
- [x] Bind the maintainer's exact six-object July 2025 MBS v3 authorization
  to the candidate v4 consumer qualification. The authorization artifact
  enumerates each pinned path, SHA-256, and byte count, and explicitly excludes
  publication, production admission, new rights conclusions, Gold review,
  M-112 acceptance, and source expansion. The refreshed exact-main run
  [39049481566](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39049481566)
  passed on `c68c6d4dbb0600ea464f2d98e716fd7b47fe4326`; its 5,107-byte aggregate
  receipt is retained at
  `quality/qualifications/australian-mbs-gold-candidate-consumers-20261018.json`
  (SHA-256 `a4adf65fed0439fd1c17001fbc2d6ee63a5af81601f505d1248bc9486aceb80c`).
  It binds the exact authorization digest and all six table identities,
  per-table lineage digests, scoped admission, source receipt, manifest, and
  semantic manifest. API, CLI, Atlas, and Chromium matched the same ordered
  edge-ID digest across all 5,989 edges. The receipt remains candidate-only
  and `not_reviewed`, retains no source payload bytes, and records no public
  publication. This closes only exact-six candidate qualification and canary
  traversal; it closes no M-110 review, M-112 admission, federation, rights,
  or release gate.
- [x] Require a positive-row real-candidate date filter in the exact-six scalar
  canary. Exact-main run
  [39074277060](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39074277060)
  passed on `7f1cdf457a93d4fa03a38aebca72febfdf029191`; DuckDB and Polars
  agree on 1,000 selected rows within the 1,000-row query limit. The updated
  aggregate receipt
  `quality/qualifications/australian-mbs-gold-candidate-consumers-20261018.json`
  has SHA-256 `6350063e40ce7a715bf676192605a3a7b9d0afb45ff1a6100985b1d565142220`.
  Source values and payload bytes were not retained; candidate-only scope and
  the exact-six authorization remain bound. No consumer admission, M-110
  review/acceptance, M-112 acceptance, rights conclusion, source expansion, or
  publication was performed.
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
- [x] Run focused, property, metamorphic, mutation, performance, coverage,
  Ruff, `ty`, BasedPyright, security, rights, provenance, regeneration, and full
  Test-Goblin lanes where supported. The focused B0-to-Platinum change passed
  24 affected tests and its focused E2E. PR #1005 passed all 38 hosted check
  rows. PR #1006 passed all 38 hosted check rows across 37 contexts after a
  documentation-only reconciliation; its mutation and Gremlins execution
  steps were skipped by the workflow's non-heavy-change rules, so those lane
  results are reused from #1005. The source/test tree is unchanged from the
  qualified PR #1005 tree; the intervening changes are documentation only.
  Hosted lanes across these two PRs include Python 3.14 unit,
  integration, E2E, smoke, property, edge, routine, strict, package, coverage,
  mutation, Gremlins, dependency, regeneration and profiling; representative
  performance; Linux/macOS/Windows consumers; security/context, recovery,
  operational, archive and table-format checks. Automated rights/provenance
  controls are test evidence only: this does not decide rights, admit or
  publish source data, or close real-source, representative-user, or release
  gates.
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
- [x] Enumerate currently pinned exact MBS identities and the one observed
  PBS v3 archive member from anonymous manifest metadata. Record the source
  rights, semantic-qualification and completeness boundaries separately in
  `quality/qualifications/australian-m109-source-era-identities-20261017.json`;
  this is not a complete expected denominator and makes no admission claim.
- [ ] Reconcile the complete approved MBS/PBS source-era denominator and obtain
  the pending PBS maintainer/provider rights decisions before any PBS public
  API payload request. Continue semantic qualification era by era only after
  exact identity and authority are established.

### M-109 P7 workbook source-owner clarification follow-up (2026-10-17)

- [x] Reply to MBS Online's locator request. The first reply supplied the
  official July 2024 downloads page, but it does not list the P7 workbook and
  therefore was only contextual. A second value-free follow-up supplied the
  exact pinned donor-archive path, commit, and digest, explicitly stating that
  this does not prove Department publication or authorship. The response and
  both follow-ups are preserved in
  `quality/qualifications/mbs-workbook-date-source-owner-clarification-20261017.json`.
- [ ] Keep P7 date conversion disabled and await source-owner clarification of
  the donor copy's official provenance and, if confirmed, its date convention.
  Neither the contextual downloads page nor the donor archive locator proves
  official provenance, date convention, field semantics, or transformation.

## M-109 latest MBS archive metadata reconciliation (2026-10-17)

- [x] Refresh the known-object inventory to the current M-108 append receipt:
  revision `da83cad9116e2f9a5b927be7b080e9a5e5ea6998`, root manifest digest
  `68e6bb97ee43117b860ff1c57e625a00075c734e933d08b3cd67de673432d055`, and
  212 manifest objects. The MBS schedule/P7 subset contains 86 distinct
  payload digests across 90 manifest paths, including four 2025 paths that
  the previous M-109 identity snapshot had listed as missing.
- [x] Keep exact manifest-path aliases and duplicate payload digests visible;
  bind the M-109 record to M-108's append and anonymous cleanup receipts. This
  is metadata reconciliation only and does not establish every path's official
  provenance, complete the expected historical denominator, or change rights,
  qualification, or admission.
- [ ] Continue M-109 source-era denominator, source-owner, semantic, temporal,
  transformation, PBS rights, and Silver admission gates. M-109 remains
  blocked.

## M-109 August 2026 MBS field semantics and date grammar (2026-10-17)

- [x] Bind the exact August 2026 MBS XML v3 candidate to the Department's
  published native-field guide and release page as candidate documentation.
  The crosswalk covers all 40 native fields and preserves source-specific
  conditional absence. The current guide declares the `DD.MM.YYYY` grammar,
  but its 2022 update date and missing release-linked field-semantic history
  do not qualify all field meanings for August 2026. The semantics status
  record keeps those mappings provisional and blocks their acceptance pending
  version-linked evidence.
- [x] Select `mbs-dmy` only in the August 2026 hosted candidate qualifier and
  retain date values and invalid/unsupported status counts in memory/aggregate
  output only. Local focused tests (135), Ruff, `ty`, BasedPyright, context,
  and diff checks passed. Exact-main validation of the selected grammar is
  pending; no source values were read locally.
- [x] Preserve the prior exact-main no-date field-presence diagnostic as a
  separate, explicitly unqualified baseline report. Its 40 aggregate field
  diagnostics show zero source/native-presence mismatches; they do not validate
  the newly selected date grammar. The report contains no source values.
- [x] Run the updated qualifier on exact main `a087acdf` (workflow
  `39029209737`, artifact `12100055332`, artifact digest
  `sha256:982a5e5846a75dfd717a3ca7ad65f3a9906c96f2239944be06aafe270172fbb6`).
  The aggregate DMY profile (`8e8d14f88baabc10a172fd2ec3947f8a89947828d64fb0237398dc230896763e`)
  confirms 6,046 rows in each of 40 fields, matched source/native presence,
  zero invalid or unsupported conversions, and observed DMY conversion counts.
  The report's `field_semantics_accepted: true` interpretation is superseded:
  the historical artifact and its digest remain unchanged, while the corrected
  qualifier defaults field-semantic acceptance to false and retains the
  version-history blocker. No values or bytes were retained. Historical eras,
  public admission, and the complete M-109 denominator remain open.
- [x] Merge the semantic-acceptance correction in PR #1110 at
  `764ee7c757c60243e8963e7482883728b768dc74`, tested exact head
  `2e90182c7b1e6bd0655ce02f55e1646a3dc13a91`. All 39 required hosted
  contexts passed, including Codecov patch and Linux/macOS/Windows consumer
  checks; the review finding is resolved. The historical profile bytes remain
  preserved and explicitly superseded only for its prior field-semantic
  acceptance interpretation.
- [x] Reconcile the corrected candidate against exact current main
  `b5b4d3ce6e3400e0fdb84ab2b56854776c4878e6` using hosted run `39032003723`.
  The pinned 2026-08 XML identity matched; 40 fields across 6,046 rows each
  have zero source-presence/projected-state mismatches. The report keeps
  `field_semantics_accepted: false` and records no source values or bytes. The
  six-table lineage and the proposed M-108 output prefix are recorded in
  `docs/qualification/australian-m108-derived-products-20261017.md`; no
  Parquet output, derived-rights approval, v4 admission, or publication exists.
- [ ] First compare the exact archived July 2026 XML (the edition released
  2026-05-28 and referenced by the August page) with the August 2026 XML using
  a bounded, aggregate-only read in the existing exact-main qualifier. Verify
  both official endpoints against their pinned sidecar digests/sizes; emit no
  record identifiers or values and create no Parquet products or publication.
  This can document release structure/content chronology but cannot establish
  semantic continuity by itself. After that comparison, obtain versioned
  schema/change history or source-owner clarification for field meanings and
  temporal semantics. Do not rerun completed workflows `39029209737` or
  `39032003723`; do not generate or publish the proposed derived outputs until
  output-specific rights and admission gates are separately resolved. M-105's
  D-006-07 chronology disposition remains blocked; the bounded pre-archive
  record search is complete and must not be restarted absent newly surfaced
  pre-archive evidence.


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
- [x] Complete anonymous SHA-256 identity readback for all 1,759 frozen raw
  and projection paths. The 92 raw PBS gaps and 12 projection gaps are bound
  to same-path digests at immutable revisions; this closes identity only.
- [ ] Complete the remaining per-object rights, B1/B2 lineage, v4 admission,
  and consumer canary gates. M-112 remains blocked until each eligible object
  satisfies its independent gates.

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
  Current-main revalidation run `38944324136` at
  `8ba21a12f74c6336901abfe6b13cd6d2caae9a91` retested only these two pinned
  workbooks. Both again passed the same bounded profile, three receipts were
  read back, and both hosted cache files were removed. The two ZIP holds and
  zero-admission state are unchanged; see
  `quality/qualifications/australian-mbs-workbook-streaming-receipt-20261017.json`.

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

## Source-neutral aggregate measure contract (2026-10-11)

- [x] Define a candidate-only typed aggregate measure contract that keeps
  service counts distinct from distinct-patient counts, preserves suppressed,
  unreported, and unavailable states as unknown, binds source and receipt
  digests, requires explicit period/time semantics, and excludes patient-level
  identifiers. A deterministic Arrow schema and Parquet round-trip are tested
  entirely with synthetic values. The contract performs no source acquisition,
  semantic qualification, admission, or publication; M-106 remains blocked on
  its separate source-specific denominator and rights evidence.
- [x] Register the contract tests in Test-Goblin and run focused, routine, and
  full local validation. The focused measure/source-review/E2E set passes 27
  tests; routine and pinned Test-Goblin checks pass. The full local run passes
  the pytest, package, mutation, Gremlins, randomized-order, provenance,
  security, and dependency lanes. Four existing optional Hugging Face typing
  warnings and an unavailable PyPI package audit are retained as limitations.
- [x] Close hosted patch-coverage findings for missing invalid-state controls:
  missing source-defined time evidence, incomplete observed values, a typed
  value on a non-observed state, missing suppression marker, and native values
  on unreported/unavailable states. Seven new parameterized cases bring the
  focused measure/source-review/E2E set to 27; the new module reaches 100%
  statement and branch coverage locally. Exact-head PR #943 later passed all
  39 reported checks and merged as `6201cac4d1e7df98528e9cf581834549a87bc248`.

### Aggregate measure review corrections (2026-10-11)

- [x] Reconcile observed native integer counts under an explicit representation
  policy while retaining the exact token, and reject typed counts outside the
  Arrow `int64` range before projection. Grouped values require policy evidence;
  malformed groups and unqualified separators fail closed. Synthetic tests
  cover positive, malformed, missing-policy-evidence, and range-boundary cases.
- [x] Re-run the focused measure, source-review, and medallion E2E tests plus
  lint, formatting, `ty`, BasedPyright, and the pinned full Test-Goblin profile.
  Focused tests pass (31); all local gates pass. Full profile: 6,144 passed,
  96.94% coverage, 353 Gremlins passed; Darwin mutation is advisory, and the
  optional PyPI audit is skipped because this project is not published there.
  Exact-head PR #943 passed all 39 reported checks including Codecov and
  Linux/macOS/Windows consumers, all four review threads were reconciled, and
  the change merged as `6201cac4d1e7df98528e9cf581834549a87bc248`.

## M-109 July 2025 MBS six-table value parity (2026-10-12)

- [x] Extend the existing exact-source parity qualification from the services
  table to all six pinned July 2025 MBS Silver table candidates. Bind each
  Parquet identity and the candidate manifest digest, compare every generated
  source-faithful field and row value, and emit a value-free receipt with no
  rights, admission, publication, or promotion claims. The model and JSON
  Schema require each of the six tables exactly once and in deterministic
  order. Final local focused/integration checks pass (17 parity tests; 52
  parity plus MBS Silver tests), as do targeted `ty`, BasedPyright, Ruff, and
  formatting checks. PR #1052 passed required exact-head checks and merged as
  `2666e6e026867be99d85f1e32bc9b381afe50efc`. Exact-main Test-Goblin run
  `38908829291` passed; its value-free six-table parity receipt was downloaded
  and validated against both the Pydantic model and Draft 2020-12 JSON Schema.
  All six tables report 5,989 rows and the expected source-to-Silver value
  parity. Rights, production admission, publication, and production promotion
  remain false. The full local profile on the pre-cardinality-guard tree had 6,276
  passed, 3 skipped, and 7 failures; most were existing performance/browser
  checks under severe host load, with one Hypothesis first-call timeout. The
  isolated Bronze recovery retry also timed out while spawning `git
  rev-parse`, without reaching its digest assertion. Do not weaken those
  limits; protected hosted lanes must validate the final tree. This closes
  only source-to-candidate value parity for one era; M-109's other eras,
  semantics, rights, and denominator requirements remain open.

- [x] Refresh the exact MBS August raw-path root-manifest state with an
  anonymous metadata-only readback at dataset revision
  `1e4971c35c0ef45026168a8e2498d1bd57a3c324`. The root manifest lists the
  matching SHA-256 and byte count under the historical
  `Downloads-20260801` alias, but does not list the approved content-addressed
  path. This confirms the path-level manifest gap without reading source bytes,
  changing rights, changing the denominator, or admitting the object. See
  `quality/qualifications/australian-m112-root-manifest-readback-20261005.json`.

- [x] Prepare the exact August 2026 MBS root-manifest append as a local,
  metadata-only candidate. The protected main-only workflow binds the current
  anonymous manifest revision and digest, the exact existing raw-object blob
  identity, its historical alias, and the existing MBS publication and source
  receipt evidence; compare-and-swap writes only `manifest.json`. Focused
  publisher tests cover stale-head rejection, ambiguous-commit idempotency, and
  anonymous-readback failure. No source payload is read or uploaded, and no
  rights, admission, denominator, or M-112 acceptance state changes.

- [x] Execute the exact-main metadata-only append and reconcile its durable
  anonymous receipt. PR #1067 merged at `320112b821e861c19f4065f550273119ac219831`
  after all 39 required checks passed on head
  `3a8b6b83fcd8d417c590c204a602277f1e2f784a`. Hosted run
  `38939963456` appended the existing content-addressed August MBS XML identity
  to the root manifest using compare-and-swap; the public dataset advanced from
  `44b25bfd87e44998c7c1da4c3930ad4447e9246f` to
  `3d2d528439bddf6f42e8e700c88917f0960a9f38`. Anonymous readback verified the
  manifest digest, the added path and unchanged historical alias, each bound to
  SHA-256 `c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565`
  and 8,293,331 bytes. File count increased from 27 to 28; no other manifest
  rows, rights, admission, or denominator changed, and no source payload bytes
  were read or uploaded. Durable receipt:
  https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-6221047682 .
  This closes only the root-manifest identity gap; M-112's approved denominator,
  object-level lineage, rights/admission, and consumer-canary acceptance remain
  open.

## M-112 August MBS root-manifest current-state refresh (2026-10-17)

- [x] Reconcile the August MBS content-addressed path and preserved historical
  alias against the exact hosted append receipt, the frozen 1,759-path ledger,
  and the latest anonymous public root-manifest readback. The append receipt
  records the historical `3d2d528...` revision; the current archive head is
  `da83cad9116e2f9a5b927be7b080e9a5e5ea6998`, with 212 root objects and
  manifest SHA-256
  `68e6bb97ee43117b860ff1c57e625a00075c734e933d08b3cd67de673432d055`. Both
  August paths remain present with the same declared SHA-256 and byte count.
  This refreshes manifest membership only; the alias's prior object-level
  anonymous digest state is preserved, and both paths remain deferred because
  per-object rights, complete B1/B2 lineage, v4 admission, and consumer canaries
  remain incomplete. See
  `quality/qualifications/australian-m112-root-manifest-path-readback-20261017.json`.

## M-112 historical imported B1-to-B2 reference reconciliation (2026-10-17)

- [x] Build deterministic B2 external-reference rows for the selected 14
  historical MBS utilisation objects from their imported acquisition events.
  The generator verifies both import manifests, per-record and event digests,
  B1 acquisition/content identity, successful retrieval, and the immutable
  public revision locator. It writes
  `quality/bronze/imported-raw-evidence/australian-mbs-utilisation-20261017.json`
  and the hash-bound qualification
  `quality/qualifications/australian-mbs-utilisation-b2-reference-reconciliation-20261017.json`.
  This is a 14-object subset of the approved 1,759-path denominator. It reads
  no source payload bytes or values and creates no native source receipt,
  payload-storage receipt, replication qualification, or admission history.
  The final focused 25-test selection passes; 231 broader affected tests passed
  before the final scope annotation was added, which was covered by the final
  focused selection. The local full profile completed with 6,394 passed,
  7 failed, 3 skipped and 96.89% coverage. Failures were outside this B2 path:
  product query performance budgets, the local uv 0.13.1 versus required
  0.11.29 release-build mismatch, one product-security runner, and one PBS
  UTF-8 composed-size assertion. M-112 rights, complete B1/B2 lifecycle,
  admission, v4 admission, and consumer canaries remain open.

### M-110 real-Silver admission gate recheck (opened 2026-10-05; reconciled 2026-10-17)

- [x] Qualify Gold relationships over the admitted real MBS Silver tables for
  the exact July 2025 v3 source era. PR #1072 records the scoped admission and
  qualifies a value-free candidate graph from all six exact-revision objects,
  with 5,989 same-source-record service-benefit edges, typed nodes, provenance,
  and negative controls. This closes only the MBS graph-input qualification;
  the candidate remains `not_reviewed`, without consumer acceptance or
  promotion. The PBS 2026-04 v3 aggregate remains
  `structural_storage_candidate_only`, `domain_semantics_qualified=false`,
  and `date_profile=not-selected`; it is not included in this qualification.
- [ ] Complete the remaining M-110 acceptance work after applicable
  source-era Silver semantics and rights are accepted for each exact input
  revision. The exact July 2025 MBS v3 same-record Gold edge review is recorded
  as candidate-only, and its consumer canaries are complete. Qualify PBS
  separately after its prerequisites. Keep MBS/PBS cross-source or clinical
  interpretations excluded unless separately supported and approved.

### M-110 exact-era MBS candidate revalidation (2026-10-17)

- [x] Revalidate the exact July 2025 MBS v3 public candidate identity and six
  table digests at current main using the read-only hosted qualifier. Run
  `38947544328` resolved the stale `public_v4_identity_unverified` finding;
  the current public revision and all six object identities match. This
  confirms candidate identity and declared schema compatibility only.
- [x] Bind the existing Decision 0009 and exact-source publication
  authorization basis into an immutable Silver admission receipt against the
  verified six-object revision. The parity receipt's `rights_conclusion=false`
  means that receipt made no independent conclusion; it does not negate the
  maintainer authority. Its `production_admission=false` remains unchanged.
  `quality/qualifications/australian-mbs-silver-admission-20261017.json`
  scopes admission to July 2025 MBS v3 graph qualification input only and
  binds the exact six-table semantic manifest. It makes no new rights
  conclusion, does not promote the public candidate, and does not accept M-109,
  M-110 Gold, or M-112.
- [x] Qualify the M-110 graph against admitted real tables after the prior
  admission gate passes. Preserve MBS-only scope and the existing M-109/M-112
  boundaries. The earlier assessment snapshots remain historical.
- [x] Build a value-free M-110 graph candidate from all six exact-revision
  admitted Silver object identities. The qualification
  `quality/qualifications/australian-mbs-gold-real-silver-qualification-20261017.json`
  binds the exact admission and semantic manifest, verifies all six public
  Parquet digests, and qualifies 5,989 source-record service-benefit edges
  (11,978 nodes) from the real July 2025 tables. Cross-record, forged-digest,
  and unpermitted-rights negative controls reject. The graph is candidate schema
  v3. `confidence` is null and `confidence_calibration` is
  `not_applicable_source_record` because the relation is explicit within one
  source record; it is not a scored or uncalibrated similarity match. At
  qualification time review state was `not_reviewed`; the later maintainer
  disposition is recorded below without rewriting this immutable receipt. The
  report records exact hashes for the graph
  builder, qualifier, and three
  schemas; its readback rejects stale implementation fingerprints. No public
  dataset mutation or graph publication occurred.
- [x] Record the maintainer's bounded disposition: accept the exact July 2025
  MBS v3 edge set as a candidate for consumer-canary use. Exact-main run
  `39045806438` traversed all 5,989 candidate edges through API, CLI, Atlas,
  and Chromium with identical ordered edge-ID digests and complete six-table
  lineage; receipt SHA-256 is
  `8d1db8c5fa9376a9f786078114e7bb7682decb8709fde6bf7992113065d8488f`.
  The retained current receipt was refreshed on exact main by run
  [39049481566](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39049481566)
  at `c68c6d4dbb0600ea464f2d98e716fd7b47fe4326`; its SHA-256 is
  `a4adf65fed0439fd1c17001fbc2d6ee63a5af81601f505d1248bc9486aceb80c`.
  This refresh repeats the four-surface canary only. It leaves each edge
  `not_reviewed`, preserves null confidence with calibration marked
  `not_applicable_source_record`, and makes no M-110, M-109, M-112,
  production-admission, rights,
  source-coverage, or publication claim.
- [x] Complete the maintainer's M-110 Gold graph review for the exact July 2025
  MBS v3 same-record edge set. The maintainer accepted all 5,989
  `source_record_has_benefit` edges as reviewed candidates, bound to graph
  digest `44c6c4f2d3dee80e49efac7bc14cc8965958b476a0e73c3758214645c7f7b27b`
  and ordered edge-ID digest
  `7a2ba8a0b31dca32101172bde49f6dc17d3ef6d873afb4760651f2a22c3a502d`.
  Receipt: `quality/qualifications/australian-mbs-gold-same-record-review-20261018.json`.
  It accepts only the source-explicit same-record service-benefit relationship;
  the pre-review graph and canary remain immutable historical evidence with
  `review_state=not_reviewed`. Confidence remains null with calibration
  `not_applicable_source_record`. No payable-benefit, clinical, cross-era,
  product-admission, rights, or federation claim is made.
  `quality/qualifications/australian-m110-mbs-july-2025-real-gold-assessment-20261018.json`
  records this bounded review. Broader M-110 acceptance, product admission,
  other MBS/PBS eras, and M-112 remain open; no second reviewer is assigned.
  A separate technical review verified that the admitted-table builder pairs
  `services` and `benefits` only on matching source-record ID, ordinal, source
  digest, and receipt digest; the exact qualification reports all 5,989 edges
  bound to that shared record identity and passes cross-record, forged-digest,
  and unpermitted-rights controls. This verifies row pairing and provenance
  mechanics only. It does not establish a positive or payable benefit, clinical
  meaning, or cross-era equivalence. The edge model and consumer contract keep
  the pre-review `review_state=not_reviewed`; the later maintainer disposition
  below records review of the bounded candidate edge set only, not M-110
  acceptance.
- [x] Correct the MBS XML numeric-width transform so the three EMSN numeric
  fields use their official seven-integer-digit limit while ScheduleFee and
  Benefit75/85/100 retain five digits. Boundary tests failed before the fix and
  pass after it. Focused MBS plus admission-assessment tests: 65 passed; the
  full profile: 6,362 passed, three skipped, two local reproducibility tests
  failed only because spawned processes found uv 0.13.1 instead of required
  0.11.29; those two tests passed when rerun with pinned uv first on PATH.
  Coverage 96.87%; current-source impact remains unqualified.
- [x] Re-run the read-only exact-main source qualifier after the field-width
  fix. Run `38953649119` succeeded at exact main
  `8c0090db41bb4ad2a4de20090a5e0895fffd91ec`; its value-free report is
  `quality/qualifications/australian-mbs-silver-candidate-qualification-20261017-8c0090db.json`
  (artifact `12070470185`, SHA-256
  `536f607f9f16cef42d6455858ce534af82186ced3ade2eb4c6839b2baf767232`). All
  5,989 rows and six object identities match the accepted candidate; the
  field-specific fix changed no values or object digests, so no republication
  was needed.
- [x] Qualify the M-110 graph against the admitted exact-era input. The
  value-free qualification
  `quality/qualifications/australian-mbs-gold-real-silver-qualification-20261017.json`
  was rebuilt from the exact six pinned public Parquet objects. Its graph
  digest is `a52ad5ca22c0c8edda528a5a02276751198a142ab62e35fbf942dff730e3a7d4`;
  all five implementation/schema fingerprints are checked by `--check` and the
  assessment test. This remains a candidate with review and consumer
  acceptance pending.
- [x] Remove the admission verifier's dependency on the full Git object
  history. GitHub Actions checks out one commit, so the original `git show`
  lookup for the public manifest's historical Decision 0009 failed on PR
  #1072. Preserve the exact historical decision bytes and verify their pinned
  SHA-256, producer commit, manifest paths and hashes, and current source
  authorization bytes without invoking Git. Source-only and byte-tamper tests
  pass; the final 63-test affected selection and routine profile pass. A full
  local profile completed with 6,385 passed, 3 skipped, and 96.85% coverage,
  but its two failures were stale generated admission/Gold snapshots captured
  before the final schema label and fingerprints were regenerated. The
  corrected verifier and projection changes subsequently merged in PR #1072
  after exact-head hosted checks passed; see the 2026-10-17 reconciliation.
- [x] Preserve exact M-110 admission and semantic bindings in each admitted
  Gold Arrow projection. The review found that equal row bodies from two
  different admission manifests produced byte-equal projected tables because
  Arrow metadata dropped those graph-level identities. Real v3 node and edge
  schemas now carry the admission, semantic-manifest, and graph SHA-256 values;
  Parquet round trips preserve them, while synthetic v2 schema metadata remains
  unchanged. The graph module's focused branch coverage is 100%; the affected
  five-module selection passes 71 tests. The full local profile completed with
  6,394 passed, 3 skipped, 96.89% coverage, and one unrelated PERF-QUERY timing
  overrun (392.588 ms against 250 ms); that same performance test passed alone.

  The corrected verifier and projection changes subsequently merged in PR
  #1072 after exact-head hosted checks passed; see the 2026-10-17 reconciliation.

### M-110 implementation hosted-check reconciliation (2026-10-17)

- [x] Reconcile the two implementation follow-ups above against PR #1072's
  exact head `a6a5b6a15bdeb577d222e6bb686aa47da7d11660`. The Python 3.14 unit,
  routine, integration, and E2E checks, Codecov patch check, consumer platform
  checks, and all other reported required checks passed. PR #1072 merged as
  `b6eccdf89726458ec5476ec1a3bda7832b8a6a98`; the resulting implementation is
  present on current main. This closes the shallow-checkout verifier and Arrow
  provenance-binding implementation tasks only. M-110 Gold review and consumer
  acceptance remain open; no clinical interpretation or review decision is
  inferred from CI.

### M-110 source-neutral scalar consumer bridge (2026-10-17)

- [x] Add a deterministic candidate-only contract-typed Arrow projection over
  the admitted-real-Silver Gold graph. Preserve the serialized typed value,
  native value and state, conversion status, source record ordinal,
  source/receipt/acquisition IDs, graph/admission/semantic digests, rights,
  both graph and B1 sensitivity assertions, receipt clocks, and the graph's
  day-level snapshot validity. Restore exact `decimal128(38,9)`, `date32`, and
  string values only from the existing field contracts and source-era typed
  values; retain native text beside each typed value. Reject incompatible
  field-table mappings, malformed scalars, and source/receipt mismatches.
  This candidate projection makes no v4 admission or product-trust claim.
- [x] Preserve exact decimal filters through the bounded Platinum query and
  Benefits API surfaces; add an explicit tagged ISO date filter for `date32`
  columns. DuckDB and Polars compare Decimal/date values natively, while JSON
  results remain lossless strings. The OpenAPI schema is unchanged.
- [~] Qualify the exact projection as an existing Platinum product resource
  only after independent v4 `ReceiptClosure`, `TrustedAdmissionProfile`, and
  deployment trust accept the exact artifact. The current M-110 assessment
  still scopes Silver admission to graph input; consumer acceptance and graph
  review remain open. No source was added and no public object was written.

### M-110 synthetic scalar consumer path verification (2026-10-17)

- [x] Exercise the candidate scalar projection through Parquet and the
  read-only Benefits API using exact synthetic v4 receipt-byte closure,
  independently configured `TrustedAdmissionProfile`, distribution binding,
  and anonymous object read. Verify exact decimal and tagged ISO date filters,
  and preserve `candidate_only`, `consumer_admission=not_performed`, synthetic
  cohort, and `review_state=not_declared`. Explicitly unknown effective date
  passes the evidence validator; an omitted effective-date field still fails.
- [x] Run projection, Benefits API, identity API, and Platinum evidence tests
  (83 passed). This qualifies the synthetic exact-artifact consumer route only;
  it does not qualify the real M-110 artifact, establish consumer admission,
  or record a Gold review. Required full local Test-Goblin also ran: 6,480
  passed, 3 skipped, and 3 failed at 96.89% coverage. Both Stable v1
  reproducibility failures were due to the shell exposing `uv 0.13.1` instead
  of pinned `0.11.29`; both passed on isolated rerun with pinned uv first on
  `PATH`. The product-security abuse-control test failed once in the full
  profile and passed on isolated rerun. Preserve the initial full-profile
  result; this is not recorded as a clean full local profile.
- [x] Close the follow-up Codecov patch-coverage gap with public-validator tests
  for complete and nested mapping envelopes carrying `effective_date: null`,
  rejection when the field is omitted, and rejection when another required
  state is null. The focused evidence suite now has 10 passing tests; Ruff,
  formatting, diff checks, and Test-Goblin routine pass. The initial Codecov
  patch result (75.00% against 90.01%) is retained. The added mapping-branch
  coverage passed Codecov on final head `d4c018d2`. PR #1099 merged as
  `ff7076fa`; all 40 reported check rows passed, including Codecov patch,
  full hosted Test-Goblin, and Linux/macOS/Windows consumer lanes. The merge
  tree `9d5fbd07` matches both the qualified head and current main.

### M-110 exact synthetic scalar path across product surfaces (2026-10-17)

- [x] Exercise the same exact synthetic scalar Parquet through the actual
  operator trust, contract, semantic-manifest, schema, and admission
  configuration loader, then query it through CLI, API, and Atlas. Replace only
  network transport and the clock; no product handler or trust loader is
  mocked. Exact decimal and tagged-date cases return equal CLI/API rows and
  object identities. Atlas previously omitted confidence, uncertainty, and
  review state; the implementation and tests now add these values alongside
  coverage and the exact object identity. The fixture grants no real
  publication or rights authority and changes no source. This adds a bounded
  Atlas evidence-display behavior. PR #1101 merged as `2987e07d` (tree
  `498390ca`); all required hosted checks passed for head `a31ee05a`, including
  Codecov and Linux/macOS/Windows consumer lanes. The merged tree matches
  current main. This verifies the synthetic cross-surface route only; exact
  real M-110 consumer acceptance remains open.

### M-110 real scalar engine canary (2026-10-18)

- [x] Extend the protected exact-main candidate workflow to build a temporary
  contract-typed scalar projection from the same six digest-verified July 2025
  MBS v3 Silver tables, bind it to the existing B1 receipt and Gold graph, and
  exercise exact Decimal and date predicates in DuckDB and Polars. Retain only
  the aggregate receipt and remove both candidate Parquet files in the
  workflow's always-run cleanup. Exact-main run
  [39055455167](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39055455167)
  passed on `82a6fce4807151bee277c9a96a88dc0c5db17504`: both engines returned
  360 rows for `Benefit100 > 10.00` and 0 rows for
  `BenefitStartDate >= 2025-08-01`, with each query capped at 1,000 rows.
  The refreshed aggregate receipt is
  `quality/qualifications/australian-mbs-gold-candidate-consumers-20261018.json`
  (2,357 bytes; SHA-256
  `ce2634a5061d27b017f733020b04f1084646bc51c4c7a4c29369b662fab7107a`).
  The same run traversed all 5,989 edges across API, CLI, Atlas, and Chromium.
  The exact receipt test now pins this artifact and asserts both scalar query
  outcomes and candidate/admission boundaries; 63 affected tests and the
  routine validation pass.
  This direct adapter canary does not enter the trusted product resolver or
  establish product admission; edge review, M-110 acceptance, M-112, rights,
  publication, and source coverage remain unchanged.

### M-110 candidate Gold edges in Atlas (2026-10-17)

- [x] Add an optional read-only `/gold/edges` Atlas page over the existing
  qualified edge table. Reuse bounded deterministic selection; expose filters
  and pages of at most 1,000 edges, preserving edge identity, endpoints, kind,
  source-record provenance, qualification, confidence, review state, and
  source controls. Empty results explicitly state that absence is not negative
  evidence. Label candidate scope and exclude clinical-equivalence, regulatory,
  and funding inferences. The MBS v3 maintainer disposition remains
  candidate-only; no additional source, source bytes, admission, or publication
  was introduced. Focused Atlas/API/CLI tests pass locally; full profile and
  exact-head hosted checks remain pending. The local full Test-Goblin main
  suite reached 100%, but its later randomized Hypothesis stage failed when
  `test_round_trip_preserves_arbitrary_source_native_labels` exceeded its
  200 ms deadline (252.73 ms on the first call); the isolated case passed in
  5.17 seconds. Retain the full profile as non-clean. The small follow-up that
  avoids a second edge-table scan for non-paginated API/CLI calls has focused
  tests and routine/strict checks; protected CI must qualify the exact final
  head.
- [x] Complete a real, local, candidate-only consumer journey for the exact
  admitted MBS v3 graph. Generate a bounded Parquet edge projection from the
  six already-pinned Silver tables, load all 5,989 edges within the existing
  file bounds, and traverse them through CLI, API, and Atlas in pages of at
  most 1,000. Verify each page preserves the admission, semantic-manifest, and
  graph digests and that all edges remain `not_reviewed`. The real graph was
  traversed by following Atlas-rendered next links through offsets 0, 1000,
  2000, 3000, 4000, and 5000; all 5,989 unique Atlas edge IDs matched API and
  CLI output. PR #1106 merged as `13f1a02717c6100dd56e896517781b8383c26981`;
  its exact head passed all required hosted checks, including Codecov patch and
  Linux/macOS/Windows consumers. No source was added and no public dataset was
  written. This completes the candidate-only technical consumer journey, not
  independent Gold review, M-110 acceptance, product admission, or publication.

- [x] Make the real MBS v3 candidate journey reproducible in a protected,
  main-only `workflow_dispatch` qualification. Require exact commit identity,
  verify the six pinned public Silver objects, traverse API/CLI/Atlas through
  their real pagination paths, and retain only an aggregate receipt. Keep the
  temporary derived Parquet out of artifacts and clean it on success or
  failure. PR #1112 merged at `ed518ae06e821bc35efd3ad53c95b03af7a0c24b`;
  exact-main run `39033590329` passed and retained one 763-byte aggregate
  receipt. It binds all 5,989 edges, pinned admission/semantic/graph digests,
  six page offsets, and the matching ordered edge-ID digest across API, CLI,
  and rendered Atlas response. This remains candidate-only, `not_reviewed`, and
  unpublished.
- [x] Extend the exact-main MBS candidate qualification through a real
  Chromium session against the loopback Atlas route. Follow each rendered
  continuation link and compare the browser's ordered edge IDs and review
  states with the authoritative candidate table; retain only aggregate counts,
  offsets, and digests. Keep the temporary Parquet out of artifacts and clean
  it on success or failure. Do not infer Gold review, product admission,
  licensing, source coverage, or publication. On base main
  `ed518ae06e821bc35efd3ad53c95b03af7a0c24b`, local Chromium checks cover the
  positive two-page fixture and refusals for malformed rows, bindings,
  review-state changes, pagination drift, missing assets, non-success pages,
  and off-host requests. A loopback 503 response with valid page markup was
  reproduced and refused. The response matcher binds each continuation to an
  HTTP 200 main-frame response at the exact expected URL, rejecting iframe or
  unrelated responses. The focused set passes (52 tests; 95.44% combined
  coverage), and Test-Goblin E2E passes (114 tests). Ruff, `ty`, BasedPyright,
  actionlint, pedantic zizmor, context, and ecosystem checks pass. Exact-main
  browser qualification passed on merge `2cf0fe0d` in exact-main run
  `39039867923`; its aggregate receipt binds the six-object authorization and
  matching browser/API/Atlas/CLI edge digests across all 5,989 edges and six
  pages. This remains candidate-only, `not_reviewed`, and unpublished.
- [x] Bind the exact six authorized MBS v4 Silver tables to their source
  receipt, current manifest, exact source-era report, scoped admission,
  semantic manifest, and per-table source-lineage digests in the aggregate
  consumer receipt. Preserve candidate-only status and every M-112 rights,
  admission, promotion, and federation boundary; no new source or public write.
  Exact-main run [39045806438](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39045806438)
  passed on `1182ab71a44c9e72fce6031ec244848e6919f096`; artifact
  `12105656905` (`australian-mbs-gold-candidate-consumers-39045806438-1`,
  2,207 bytes) is retained as
  `quality/qualifications/australian-mbs-gold-candidate-consumers-20261018.json`
  with SHA-256
  `8d1db8c5fa9376a9f786078114e7bb7682decb8709fde6bf7992113065d8488f`.
  It binds all six table identities and per-table source-lineage digests to
  the B1 source-receipt object, manifest, exact source-era report, scoped
  admission, and semantic manifest. The API, CLI, Atlas, and Chromium browser
  returned the same ordered edge-ID digest across all 5,989 candidate edges
  and six pages. The report contains no edge IDs or source values and records
  no retained source bytes or public publication. M-110 review and M-111
  admitted-product acceptance remain open.

### M-112 B0 source identity and Bronze denominator reconciliation (2026-10-17)

- [x] Add the imported MBS demographics source identity to the B0 catalogue
  and landing queue so its historical B1/B2 references resolve to a known
  source. Keep the queue `rights_blocked` with `evidence_scope=none`: the
  existing maintainer decision covers only 10 demographics and 4
  group-statistics objects in the exact 14-object archive manifest. The new
  source row does not qualify a distinct-patient denominator, current
  coverage, native receipts, storage receipts, or admission. The catalogue
  now has 176 sources; the approved bounded Bronze scope remains 42, and the
  full public universe is 159 with 117 deferred. A separate B0 identity for
  the four group-statistics objects resolves all 14 approved imported source
  identities across demographics and group statistics; this adds no receipt,
  admission, or distinct-patient denominator evidence. M-112's approved 1,759-path
  denominator is unchanged. Focused tests, rights-generator checks, B0
  byte-for-byte regeneration, Ruff, BasedPyright, and diff checks pass. The
  full local profile was not repeated while the shared validation run was
  active.
- [x] Add the separate `au-data-gov-mbs-group` B0 identity for the four
  group-statistics references in the same exact 14-object authorization. A
  source-event digest audit and regression now verify 10 demographics and 4
  group-statistics identities resolve to B0; queue rights remain blocked and
  source evidence remains `none`. Reconcile catalogue-derived Bronze and Stable
  projections to 176 catalogue rows, 159 public Bronze sources, 117 deferred,
  29 direct-receipt sources, and 130 without a direct receipt. The 42-source
  bounded cohort and 1,759-path M-112 denominator are unchanged. No source
  payload bytes were read, acquired, admitted, or published.


## M-112 B0 identity pull request closeout (2026-10-17)

- [x] Merge PR #1077 after all 29 required protected contexts passed on exact
  head `a5aac47f2e4948bde14515e848419388686eeb0e` and the lineage review thread
  was resolved. Merge commit `68fc74506809a436de9ab245b674e802d53279f2` has
  the exact tested tree. Rebind Bronze maturity to current main; the 176-row
  catalogue, 159-source public universe, 117 deferred sources, 42-source
  bounded scope, and 1,759-path M-112 denominator remain unchanged. M-112
  rights, native lifecycle, admission, canaries, and federation acceptance
  remain open.


## PR #1079 review correction (2026-10-17)

- [x] Correct the two newly recorded Git tree identifiers as `*_tree_oid`, record `git_object_format: sha1`, and validate both JSONL rows and exact Git trees; focused receipt validation and `git diff --check` pass. Fix commit `24246a1f`.

## Bronze maturity rebind after PR #1079 (2026-10-17)

- [x] Verify PR #1079 merged at `50a0655269bc79f22cf9577a11118f7928892d37`
  with its exact tested tree; rebind the Bronze maturity report and M5 status
  to that source commit. The 176-catalogue, 159-public, 117-deferred,
  42-bounded, 29-direct-receipt, and 1,759-path M-112 counts remain unchanged.
  The 224 focused maturity/contract tests, measured-coverage check, and context
  validation pass. M-112 admission and federation acceptance remain blocked.

## M-106 patient-denominator source metadata refresh (2026-10-17)

- [x] Recheck official public metadata and both existing source-owner inquiry
  threads without acquiring source content. The Department's current annual
  statistics page lists patient measures for 2009-10 to 2025-26 by state and
  territory; this is a stronger aggregate-denominator lead, but no count
  definition, cross-item deduplication, coverage, suppression, exact workbook
  identity; the existing annual-series authorization is separately established.
  The Services Australia item-report page returned HTTP 503, and the narrow GP non-referred bulk-billing product
  does not represent the full MBS denominator. The Department thread contains
  only an automatic receipt and Services Australia has no inbound reply.
  Details are preserved in
  `quality/qualifications/australian-mbs-m106-source-metadata-recheck-20261017.json`.
- [ ] Obtain substantive source-owner clarification of the annual patient-count
  definition and exact workbook identity before acquisition. Use the existing
  annual-series authorization for this category; require a new rights decision
  only if the exact object or use falls outside its approved scope.
  Keep M-106 blocked; do not treat public-page metadata, item counts, or the
  dashboard percentage as the required distinct-patient denominator.


## M-107 targeted historical schedule page harvesting (2026-10-17)

- [x] Add a bounded workflow-dispatch path for exact official MBS Downloads
  page IDs when historical releases are absent from the newest-release index.
  Record one metadata-only attempt for every selected page, including a safe
  exception class on fetch failure; restrict requests to canonical dated page
  IDs and 24 pages per run. The existing monthly discovery remains the default.
  The implementation passed its focused and broader local tests, hosted
  protected checks, and Codecov on exact head `0c2bd5ad3a3583234434224effff892e8c0fb99c`; PR #1084 merged as
  `17a853b6259b8494c207afd44e1100992fc0bf51` with the exact tested tree.
- [x] Run the authorized exact-main harvest for `Downloads-250101`,
  `Downloads-250301`, and `Downloads-251101` with `max_releases=0` at merge
  commit `17a853b6259b8494c207afd44e1100992fc0bf51`. Run
  [38993834387](https://github.com/edithatogo/global-medicines-atlas/actions/runs/38993834387)
  recorded one XML for January, one for March, and two distinct November
  revisions with zero archive-identity conflicts. The public immutable
  revision is `52ad5c31cfe101c487a4c7a9c382540642e6110a`; its public manifest
  readback binds all four paths, byte sizes, and SHA-256 digests. The final
  [receipt](https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-6228342987)
  records all three pages complete, anonymous digest verification for the
  40-object cumulative archive, and verified temporary-byte cleanup.
- [~] Reconcile the full expected MBS/PBS period and source denominator.
  These four exact MBS objects add historical snapshot coverage but do not
  qualify the timed-out Health.gov workbook families, historical PBS schemas,
  or a complete M-107 series. Keep M-107 blocked until the remaining
  source-specific evidence is reconciled.

## PR #1084 patch coverage and source-identity correction (2026-10-17)

- [x] Address Codecov's exact-head patch-coverage finding on `36f38f1`: add
  regressions for negative recent-release limits and more than 24 exact pages.
  Review then identified that distinct URLs with the same archive path must
  make the targeted page incomplete; only identical URLs are deduplicated.
  The workflow now fails before staging on an ambiguous collision, with
  regressions for both collision and exact-duplicate cases. The affected
  The affected 119-test set passes; local coverage executes all 58 changed
  statements in `australian_harvesting.py` (98% total module coverage), and
  Ruff, BasedPyright, context validation, diff checks, Codecov, and all
  protected checks passed before merge. This correction preserves the exact
  source identity of the subsequently acquired MBS objects; it does not close
  the remaining M-107 source-family and denominator gaps.

## M-107 official historical index reconciliation (2026-10-17)

- [x] Reconcile the official MBS Downloads index, its linked release pages,
  and the distinct Previous Downloads file list as metadata only. The current
  Downloads index exposes 55 pages and 531 links (417 distinct resource URLs),
  including 82 distinct MBS-XML resource URLs across 41 page IDs. Exact
  comparison with B1 receipt source URLs at MBS archive revision
  `52ad5c31cfe101c487a4c7a9c382540642e6110a` matches 10 and leaves 72 without
  a current receipt. The Previous Downloads page lists 105 historical PDFs
  for 1974–2010; its XML link is a site-wide RSS feed and is excluded from the
  historical file count. The current harvest authorization does not establish
  rights for those historical PDF/Word products. No source payload was
  acquired. See
  `quality/qualifications/australian-mbs-official-index-reconciliation-20261017.json`
  and `docs/qualification/australian-mbs-pbs-m107-snapshots.md`.
- [x] Apply the review correction that separates the Previous Downloads
  page's 105 historical PDF files from its site-wide RSS feed link. The RSS
  XML is now classified as a feed and excluded from historical file totals;
  the qualification regression test asserts this distinction.
- [x] Extend and qualify the bounded exact-page selector for observed
  historical IDs such as `Downloads-200701a` and `Downloads-2023-11`. Preserve
  each exact ID as the page identity; never infer a release date from a suffix.
  Reject full URLs, paths, queries, fragments, control characters, and encoded
  path separators before any fetch. The 24-page limit and pre-staging failure
  for a page with no supported XML or an archive-path collision remain
  fail-closed. Focused tests (76), the broader affected harness (84), local
  full profile (6,461 passed, 3 optional skips; the two local uv-version
  failures were rerun successfully with the pinned official uv), 98% affected
  module coverage, `ty`, BasedPyright, Ruff, context validation, and JSON/diff
  checks pass. See the append-only evidence entry and the pinned-tool
  reproducibility reference recorded there.
- [~] Harvest eligible authorized monthly-schedule XML pages in exact main
  cohorts of at most 24 and reconcile exact B1 receipts, source identities, and
  supersession chronology. Two hosted cohorts of 24 and eight pages completed
  at exact main `832814cfd1b6859b511fc6c5134b8a45a3383096`, adding immutable
  dataset revisions `18cfdaa7ba826f0de8b2a3cd0960a55f7364a398` and
  `51da37714b2ea3ac3b0376d28769595e8c6e9c14`; both receipts report anonymous
  digest verification and cleanup. Exact URL reconciliation of the current
  index initially matched 78 of 82 XML links. The four unmatched URLs from
  `Downloads-210615` were subsequently acquired after the collision-safe
  identity fix merged; the current archive now matches all 82 URLs. M-107
  remains blocked pending the full MBS/PBS period, source-era, utilisation, and
  rights reconciliation. The post-merge qualification test passes (3 tests),
  the broader harvesting/index set passes (78 tests), and context, JSON/JSONL,
  and diff validation pass.

## M-107 collision-safe source identity (2026-10-17)

- [x] Preserve distinct official XML URLs that share an exact or
  case-insensitive archive filename. The targeted page harvester now assigns
  every member of a colliding group a deterministic
  `source-url-sha256/<full URL digest>/<original filename>` path, while keeping
  ordinary archive paths unchanged and deduplicating only identical URLs.
  Regressions prove exact and case-only collision handling, input-order
  independence, staging of separate payload and receipt paths, and
  page-completeness behavior. Focused tests (74 harvesting plus 3 index
  qualification; 77 total), adjacent publication/workflow tests (11),
  BasedPyright, `ty`, Ruff, formatting, context validation, and diff checks
  pass. Full Test-Goblin completed with 6,461 passed, 3 skipped,
  and 3 failures at 96.88% total coverage. The three failed tests were rerun
  individually with the pinned `uv 0.11.29` and all passed (3 passed); do not
  treat the full profile itself as uninterrupted green. PR
  [#1087](https://github.com/edithatogo/global-medicines-atlas/pull/1087)
  merged at `c374cff2c0225beaf170887dd54dbfe0ccb77022` after all required
  exact-head checks passed. The four distinct URLs on `Downloads-210615` now
  have collision-safe receipt-backed identities. M-107 remains blocked on its
  wider source denominator and other historical MBS/PBS gaps.
- [x] Close the PR's Codecov patch-coverage finding. At exact PR head
  `a7da966aea77c73cb845e39ab5af9bb07d21144e`, Codecov reported 89.28% against
  the 90.01% target and identified the remaining-conflict fail-closed branch at
  lines 527–528. Added a regression that forces a collision after URL-hash
  disambiguation, invokes the CLI, and verifies the conflict is reported and
  refused before staging or receipt writes. The production implementation did
  not change. The updated focused set (78), broader release harness (11),
  typing, lint, and formatting checks pass; exact-head Codecov patch coverage
  and all other required checks passed before merge.

## M-107 collision-page hosted receipt reconciliation (2026-10-17)

- [x] Run only the deferred `Downloads-210615` page under the existing
  monthly-schedule authorization at exact main commit
  `c374cff2c0225beaf170887dd54dbfe0ccb77022`. Hosted run
  [39000296702](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39000296702)
  found four XML resources with zero identity conflicts. Its publication
  receipt reports anonymous digest verification for 212 files; the final
  cleanup receipt confirms temporary hosted source bytes were removed.
- [x] Read back the exact revision's public manifest and the four new B1
  receipt sidecars as metadata, then reconcile all 82 official current-index
  MBS-XML URLs against 87 sidecars: 82 exact URL matches, zero unmatched URLs.
  The 212-file manifest SHA-256 is
  `68e6bb97ee43117b860ff1c57e625a00075c734e933d08b3cd67de673432d055` at
  revision `da83cad9116e2f9a5b927be7b080e9a5e5ea6998`. Raw XML payloads were not
  fetched during this metadata reconciliation. The M-107 qualification and
  snapshot document now record the current manifest and receipts.
- [~] Continue the broader M-107 reconciliation: the present MBS-XML index
  match does not establish the full historical MBS/PBS expected-period
  denominator, source-era semantics, utilization-family coverage, source
  rights, or admission.

## M-112 historical receipt-to-gate crosswalk (2026-10-17)

- [x] Crosswalk all 14 historical utilisation `SourceReceipt` projections to
  their exact immutable B2 identities and approved per-object rows in the
  unchanged 1,759-path denominator. The deterministic value-free report binds
  the gate reconciliation, historical receipt inventory, acquisition import,
  and every sidecar digest; all 14 are explicitly historical and satisfy none
  of the live-source, independent-storage, complete B1/B2, v4-admission, or
  consumer-canary gates. No source bytes or values were read, acquired, or
  published. On `origin/main` `764ee7c757c60243e8963e7482883728b768dc74`,
  the focused 18 tests and broader 55-test M-112 suite passed; changed-module
  branch coverage was 98.70%, and Ruff, `ty`, BasedPyright, context validation,
  deterministic `--check`, formatting, and diff checks passed. The report is
  `quality/qualifications/australian-m112-historical-receipt-gate-crosswalk-20261017.json`.
- [~] Continue per-object lineage, independent storage/readback, rights,
  admission, and consumer-canary evidence under the existing approved
  denominator. This historical metadata crosswalk does not complete M-112 or
  promote any deferred object.

## M-109 July/August 2026 MBS predecessor comparison implementation (2026-10-17)

- [x] Implement the bounded exact-main comparator at
  `scripts/compare_mbs_source_eras.py` and add it to the existing August
  candidate workflow. It verifies both July/August harvest sidecars, pinned
  archive objects, and current official endpoints in GitHub Actions memory;
  emits only aggregate field presence and change counts; and produces an
  `incomplete` aggregate artifact before failing the workflow on endpoint,
  identity, or structure errors. July's recorded `monthly_schedule_xml`
  authorization and the August exact-release approval are separately bound.
  It creates no Silver output, public mutation, or semantic promotion. Focused
  comparator/source-era tests (25), actionlint, Ruff, `ty`, BasedPyright,
  context/ecosystem, and routine Test-Goblin passed. Harvest sidecars are parsed
  through a typed JSON boundary and checked against their pinned content digest.
- [x] Run the comparator from exact current `main` commit
  `f6cccb0beb66d5a1322149f33dc61820eea05166`. Run
  [39047005443](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39047005443)
  completed successfully and matched both archived releases to their exact
  official bytes. The value-free report is preserved at
  `quality/qualifications/australian-m109-july-august-predecessor-comparison-20261018.json`
  (artifact 12105683236; downloaded report SHA-256
  `73ef383cd36ca2703ddd70344b572f8904b67b8d85a1f6420036fa76e4d4954b`). It
  records 6,045 matched records, one added record, no removed records, and
  aggregate field changes only. This establishes structural/content comparison
  for these two exact releases, not semantic continuity or M-109 acceptance.
- [ ] Obtain release-linked schema/change history or source-owner clarification
  for the 2022-03-04 to 2026-05-28 field guide gap. Keep M-109 blocked until
  required source-era meaning and transformation evidence is accepted.

### Comparator transport-failure review correction (2026-10-17)

- [x] Correct review finding [discussion_r4302792284](https://github.com/edithatogo/global-medicines-atlas/pull/1114#discussion_r4302792284): DNS `OSError` and `DestinationPolicyError` now produce a value-free `incomplete` artifact with a safe failure class and a nonzero exit. Add CLI regressions for HTTP, DNS, and rejected-redirect failures. Focused tests (25), Ruff, `ty`, BasedPyright, routine Test-Goblin, and `git diff --check` pass. No retry, endpoint change, or destination-policy weakening was introduced. Exact-head hosted revalidation remains pending.
## M-107 primary Downloads page inventory (2026-10-18)

- [x] Compare the live official Downloads landing-page resources to the pinned
  public archive manifest and the exact source-specific authorization. Record
  the two item-lookup files labeled `20261101`, re-use item map, and historical
  information PDF as metadata-only source candidates. None has a matching B1
  source-URL receipt or archive path at revision `da83cad`; the existing
  authorization categories do not cover these files. No source payload was
  requested or read, and no rights or publication decision was inferred.
- [~] Keep any acquisition of these four candidates blocked pending an exact
  source-specific rights and publication decision. Continue independent MBS,
  PBS, and utilisation denominator work; these links do not establish period
  completeness or M-107 acceptance.

### Official MBS field-guide semantic-history comparison (2026-10-18)

- [x] Compare the official November 2013 and February 2022 XML field guides and bind their exact public URLs and downloaded PDF SHA-256 digests in `quality/qualifications/australian-mbs-field-guide-semantic-history-20261018.json`. `ItemChange` retains the same one-character mandatory shape while its wording broadens from item-number change to change to the item. The linked February 2022 PDF conflicts with the current help-page `EMSNCap` legend and its own conditional rule. These are documentary observations only; no release meanings are assigned.
- [x] Re-run the aggregate July/August source comparator on exact main `4b8ea386b20b1f9b034e5d8cf80ca3e05430bb4c`; hosted run `39048554153` succeeded and the aggregate report SHA-256 is `09b1263b8724b4cce187bbaef9a2fec033c579c2aeaa94b503faecc7b672c210`.
- [ ] Obtain a versioned source-owner clarification or release-linked schema/change record establishing field meanings and effective dates for each required source era. The 2022-03-04 to 2026-05-28 gap and source-era denominator remain open; M-109 remains blocked.

### Official March 2026 release correction (2026-10-18)

- [x] Record the official March 2026 page's corrected XML revision, its release/effective dates, and its stated EMSN-cap correction for 12 items. Preserve the page's wording that columns Y, AB, and AC changed without mapping those labels to XML tags. This narrows one release-specific correction record but does not resolve the conflicting field guide, qualify other eras, or change M-109 acceptance. See `quality/qualifications/australian-mbs-release-corrections-20261018.json`.
- [ ] Obtain release-linked schema/change history or source-owner clarification establishing field meanings and effective dates across the required source-era denominator. M-109 remains blocked.

## M-109 official PBS archive index reconciliation (2026-10-18)

- [x] Inventory the official PBS schedule archive's 24 linked year pages from
  2003 through 2026 without fetching the listed data files. The pages expose
  316 XML/API-CSV links across 197 schedule dates: 88 XML links with no
  version label (April 2007–August 2017), 105 V3 and 105 down-converted V2
  links (September 2017–May 2026), and 18 API CSV links (April 2025–September
  2026). This is an official-page link inventory, not an approved corpus
  denominator or a schema qualification. See
  `quality/qualifications/australian-pbs-schedule-index-metadata-20261018.json`
  and `docs/qualification/pbs-schedule-index-metadata-20261018.md`.
- [~] Keep historical XML reuse and current PBS API retention/redistribution
  blocked pending source-specific clarification and the maintainer rights
  decision. Reconcile the 2006–2014 source-era identities outside this
  schedule archive before declaring the PBS denominator complete; do not infer
  source absence from a missing archive-page link.
- [x] Reconcile official schema and API documentation metadata. The PBS XML
  Schema v2.1 document records schema milestones from December 2006, before
  the archive index's first XML link in April 2007; the current API information
  page documents a rolling most-recent-12-month schedule window. These facts
  narrow the source-era questions but do not identify every schedule release,
  assign schemas to every file, or establish reuse rights. Exact URLs and
  limitations are in the metadata qualification.
- [~] M-109 remains blocked on the complete approved source-era denominator,
  field semantics, lineage and source-specific rights/admission evidence.

## M-107 PBS official schedule-link crosswalk (2026-10-18)

- [x] Enumerate all 316 schedule-data links across the 197 periods exposed by
  the 24 official PBS archive year pages. Bind each link to its source-family
  rights-ledger record and enumerate the acceptance evidence still required.
  The value-free report is
  `quality/qualifications/australian-pbs-m107-link-crosswalk-20261018.json`.
- [x] Match one April 2026 XML V3 link by effective date, displayed version
  label, and archive filename to the known public object. Preserve the exact
  identity boundary: this does not prove source-URL-to-receipt lineage. The
  object remains deferred with unknown upstream redistribution terms and
  incomplete B1/B2 lineage.
- [~] Leave the other 315 archive-identity mappings unresolved. This is not
  evidence that those periods or source objects are absent. No source payload
  was requested or read, no rights decision changed, and M-107 remains blocked
  on the complete approved denominator, source-specific rights, receipt
  lineage, and source-era qualification.
- [x] Register the focused crosswalk regression test in Test-Goblin. The
  focused and affected qualification/ledger tests passed (82 tests); the
  routine Test-Goblin profile, context, ecosystem, Ruff, formatting, and diff
  checks passed.

## M-107 2011–2019 historical MBS PDF link reconciliation (2026-10-18)

- [x] Reconcile the nine preserved official-page observations by PDF link
  occurrence and exact URL identity. The pages contain 119 PDF link
  appearances but 113 distinct URLs; six repeated appearances span five URLs.
  The earlier hand-count of 120 was one too high because the 2012 page has 24
  PDF links, not 25. See
  `quality/qualifications/australian-mbs-m107-historical-pdf-crosswalk-20261018.json`.
- [x] Compare displayed labels with filename month tokens without assigning
  effective dates. Eight date-like labels differ from filename tokens, one
  cannot be compared, and 110 match. Repeated URLs with multiple labels remain
  unresolved source-identity questions.
- [~] Keep all historical PDF rights and acquisition open. The existing
  authorization does not cover historical PDFs; no PDF or software payload was
  requested or read. This nine-page metadata slice does not complete the
  pre-2010/2020+ format denominator or M-107.
- [x] Validate the report and documentation with 66 focused and affected tests;
  Test-Goblin routine, context, and ecosystem checks; Ruff, formatting, and
  diff checks all passed.

## M-107 Previous Downloads PDF links, 1974–2010 (2026-10-18)

- [x] Reconcile the official Previous Downloads page's 105 PDF link identities
  against the preserved 2026-10-17 metadata observation. Each URL is distinct;
  25 displayed label/filename month tokens match and 80 cannot be compared.
  The row-level crosswalk is
  `quality/qualifications/australian-mbs-m107-previous-downloads-crosswalk-20261018.json`.
- [x] Cross-check against the 2011–2019 page inventory: the two observations
  have disjoint URL sets, totaling 224 PDF link appearances across 218 URLs.
  This is a metadata denominator for observed PDF listings only, not an
  expected schedule period denominator.
- [~] Keep acquisition, source-specific rights, and effective-date semantics
  open. Existing authorization does not cover these historical PDFs; no
  payload was requested or read. M-107 remains blocked.
- [x] Validate both PDF inventories and the documentation with 69 focused and
  affected tests; Test-Goblin routine, context, ecosystem, Ruff, formatting,
  and diff checks passed. Protected hosted checks remain required for the
  amended PR head.
- [x] Resolve the Python 3.14 strict-profile failure on the first expanded
  PR head by typing JSON-loaded previous-download records and comparison keys.
  Post-rebase validation passed 69 affected tests and strict/routine
  Test-Goblin checks; the strict profile reports zero errors and four existing
  optional-import warnings.

## M-112 exact-six MBS v4 candidate qualification and consumer canary (2026-10-18)

- [x] Reconfirm the maintainer's candidate-use authorization for the exact six
  July 2025 MBS v3 Silver Parquet identities in
  `quality/qualifications/australian-mbs-v4-candidate-use-authorization-20261017.json`.
  Its scope is candidate v4 qualification and consumer canaries only; it grants
  no publication, production admission, rights conclusion, M-110 review, or
  M-112 acceptance.
- [x] Requalify the pinned public candidate on exact current `main` with hosted
  run [39061440432](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39061440432)
  at `08fdcbdf230c34c874b7df3abbf3491c5b12b35a`. The aggregate report SHA-256
  is `460f1ea97503bb694fa7ba3e82339164196c7efc69e62bda169e6a8817529ffe`;
  it verified the July 2025 source digest, all six table digests, the pinned
  manifest, and all nine expected public objects at current revision
  `da83cad9116e2f9a5b927be7b080e9a5e5ea6998`. There were no current technical
  blockers. The report is aggregate-only; source bytes were not retained and
  publication was not performed.
- [x] Run the exact-main consumer canary at
  [39061576513](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39061576513)
  on the same commit. The aggregate receipt SHA-256 is
  `496c5bbfa9f7d3bf8c9630f8fd212612d49684542b042167097260b185fd4d0e`; all
  5,989 edges traversed API, CLI, Atlas, and Chromium with the same ordered
  edge-ID digest, bound to the six-table lineage. Temporary Parquet was
  removed by the workflow. This remains a candidate canary with
  `review_state=not_reviewed` and does not accept M-110 or M-112.
- [x] Keep the separately recorded maintainer disposition limited to accepting
  this MBS v3 edge set as reviewed candidate edges. M-110 overall acceptance,
  product admission, and M-112 federation acceptance remain open.

## M-109 current-index MBS XML release-page chronology (2026-10-18)

- [x] Reconcile the 82 current Downloads-index MBS XML links to their official
  page rows across 41 pages and anonymously re-read the 87 matching B1 receipt
  sidecars from current archive revision
  `42d73b6facac016f14a335d36d83f1a3b630add8`. Every URL matched one official
  row; all sidecar digests, source URLs, archive paths, and payload digests
  matched. The report stores response hashes and explicit date phrases only;
  HTML bodies and XML payloads were not retained or requested. It does not
  infer effective dates or complete the historical denominator, source-era
  semantics, rights, or M-109. See
  `quality/qualifications/australian-mbs-current-release-page-chronology-20261018.json`.
- [~] Continue with the complete approved MBS/PBS historical denominator,
  source-owner field-history clarification, source-era semantics, and
  source-specific rights/admission evidence.

## M-109 chronology qualification review corrections (2026-10-18)

- [x] Preserve each expected official XML link as unresolved when its page
  fails or exceeds the bounded response limit; fail the current-index claim if
  any page link is absent, ambiguous, or unobserved.
- [x] Require every indexed resource to bind its nonempty receipt list to
  exact current-revision sidecars. Count missing and unindexed resource
  receipts explicitly and fail the report status closed.
- [x] Stream official pages and public JSON metadata with a 2 MB cap and
  64 KiB chunks, stopping at the first chunk that exceeds the cap.
- [x] Add regressions for failed-page denominator preservation, oversized
  stream stopping, and missing/empty resource receipt mappings. The updated
  metadata-only report still observes 41 pages, 82 exact official XML rows,
  82 exact current resource receipt bindings, and 87 verified sidecars.
  Focused tests: 11 passed; broader affected tests: 27 passed; Test-Goblin
  routine, Ruff, `ty`, BasedPyright, context/ecosystem, and diff checks passed.
- [~] These report-integrity corrections do not complete the historical
  denominator, source-era semantics, rights, admission, or M-109.


## M-109 official August no-further-change claim reconciliation (2026-10-18)

- [x] Bind the August release-page statement and exact July/August aggregate
  report by input digests. The page states one new item and no further XML
  changes from the release published on 28 May; the comparison reports 6,045
  matched, one added, zero removed, and 5,445 changed records. Preserve this as
  `unresolved_observed_delta`; do not infer the named item identity or whether
  change-indicator differences are snapshot-relative.
- [x] Add a reproducible, value-free qualification, four focused negative and
  boundary tests, and a Test-Goblin unit-lane registration regression. The
  report does not emit the item code, source identifiers, or source values and
  leaves field semantics and M-109 blocked. The full Test-Goblin unit lane was
  interrupted at 39% because it exceeded the bounded affected-test scope; no
  test failure was observed or represented as a pass.
- [~] Await authoritative clarification of the release-note/comparison delta
  and field-flag temporal scope, as well as the complete approved source-era
  denominator, source-specific rights, and admission evidence.

### M-109 reconciliation provenance review fixes (2026-10-18)

- [x] Bind each parsed evidence object to the exact bytes whose SHA-256 is
  recorded; reject caller-supplied objects that differ from those bytes.
- [x] Record the actual paths passed to the CLI, including supported input
  overrides, and add regressions for both provenance boundaries.
- [x] Re-run the focused reconciliation and Test-Goblin harness tests (64
  passed), Ruff, formatting, `ty`, BasedPyright on changed files, report
  regeneration, and `git diff --check`.
- [~] Push the review correction to PR #1160 and wait for protected checks on
  its new exact head. No M-109 semantics, rights, admission, or acceptance
  status changes.

## M-112 raw B2 candidate adapter (2026-10-18)

- [x] Add a source-scoped v4.1 MBS raw-B2 adapter over the existing receipt
  closure and independent admission primitives. Require exact Bronze/B2/raw
  identity, the raw-B2 v2 field-lineage exception, and publication,
  verification, authorization, discovery, input-lineage, v1/v3 conformance,
  recovery-checksum, and cache-cleanup receipt roles. Keep results
  `candidate_only`; expose no reader admission record.
- [x] Prove synthetic closure and independent identity binding with four
  coherent substitutions, missing receipt bytes, a missing conformance role,
  and an unauthorized layer. Independent review also passed twelve additional
  negative controls against trust fields and receipt roles.
- [x] Focused federation/MBS/harness tests (196), Ruff format/lint, `ty`,
  BasedPyright, and diff checks pass.
- [x] Project context and ecosystem validation pass on the updated track
  ledger and plan.
- [x] Run the required full production profile on this exact frozen change
  under the existing host guard with pinned uv 0.11.29 in parent and child
  PATH. The run completed with 6,877 passed, 3 skipped, and one failure at
  96.89% coverage: the pre-existing product-release fixture measured query
  p95 275.915 ms against its 250 ms budget. The exact test passed when rerun
  alone under the same guard (1 passed, 1 existing deprecation warning). Record
  the full-profile result as a host-sensitive timing miss, not a pass. The
  adapter's focused checks and exact-head hosted checks passed. Next, bind real
  receipts and independent trust expectations for the six raw MBS paths. No
  real contract, admission, remote read, or consumer canary is created by this
  adapter increment; M-112 remains blocked for all 1,759 approved paths.

## M-112 six-path metadata reconciliation (2026-10-18)

- [x] Independently read and hash the pinned metadata for the six MBS raw
  candidate paths without fetching any source payload. The qualification
  records 29 bounded anonymous metadata readbacks: the July root manifest,
  all 16 July metadata additions, four July path receipt sidecars, the
  historical and current August source manifests, and five August lifecycle
  records, plus the August lifecycle root manifest. All 29 status/digest
  checks passed. Each July path joined through
  its sidecar, B1 acquisition, B1 source receipt, B2 reference, and landed
  admission. The five August lifecycle records joined to one payload identity
  and also byte-match their preserved repository copies. None of the five
  lifecycle paths is listed in that revision's 21-entry root manifest; their
  direct reads do not supply a v4 discovery role. Review correction: only 27
  of the 29 readbacks had an expected SHA-256 and qualify as digest matches;
  the current and older August source-manifest reads are status-only because
  no expected digest was recorded for either. Their observed digests remain
  diagnostic metadata, not verified matches.
- [x] Preserve the two August path identities over one payload digest and the
  older B2 external locator revision `abdf414cdea0127d3edda6f8af402d1a01139623`
  separately from the path readback at `40891976f77ee5e7688edceed25c9ac98a77547e`.
  The lifecycle metadata readback at `1e4971c35c0ef45026168a8e2498d1bd57a3c324`
  is bound to `edithatogo/australian-mbs-source-archive`; an initial request
  under the global-atlas dataset name returned 401 and is retained only as a
  superseded locator error.
- [x] Confirm the July root manifest is 228 files with the recorded SHA-256.
  Reconcile the older per-object B1 acquisition summary's 2,533-byte claim to
  the independently fetched 2,534-byte metadata file and its matching digest;
  keep the one-byte summary discrepancy explicit.
- [x] Add the bounded metadata-only reader, exact-dataset locator regression,
  and compact hash-bound qualification at
  `quality/qualifications/australian-m112-raw-b2-metadata-reconciliation-20261018.json`.
  Focused adjacent tests pass (99); no source bytes were fetched, no rights or
  issuer claim was added, and the six path rows remain deferred.
- [~] The MBS raw B1/B2 receipts are not a v4.1 raw-B2 contract/closure. The
  independently configured v4 roles for publication, verification, exact
  authorization, discovery, input lineage, v1/v3 conformance, recovery
  checksum, and cache cleanup remain unbound; no M-112 admission or reader
  canary was attempted. Preserve the 1,759 denominator and all six deferrals.

### M-112 metadata digest accounting review correction (2026-10-18)

- [x] Keep a successful anonymous manifest read without an expected digest as
  a status-only observation. The qualification now records 27 digest matches
  and two status-only reads across 29 metadata requests, retaining observed
  hashes without claiming either was verified against an expected identity.
  All six path candidates and the 1,759-object denominator are unchanged.

### M-112 retained per-object join expansion (2026-10-18)

- [x] Build a separate retained-evidence overlay over the frozen 1,759-object
  denominator, preserving every object ID and the baseline inventory. Four July
  MBS raw paths now have exact same-path, byte-count, SHA-256, and B1/B2-role
  joins, using retained metadata only. This raises exact digest/path matches
  from 22 to 26; it raises complete B1/B2 lineage paths from two to six. The
  previously bound August same-content alias remains a separate path-identity
  binding, not an independent acquisition: 27 path identities are bound across
  26 exact digest/path matches.
- [x] Classify the six retained candidates explicitly: four verified new joins,
  one already-joined canonical August path, one already-bound same-content alias,
  zero unmatched, and zero incompatible-role records. Ten existing non-LFS or
  alias bindings reduce the prior 102 raw tree-SHA gaps to 92 raw paths without
  direct or alias SHA evidence; twelve projection paths remain separately
  unbound. This is an identity-evidence distinction, not a rights or admission
  result.
- [x] Keep all 1,759 objects deferred; B1/B2-complete raw lineage is 6, exact
  source/release rights remain 2, v4 admissions remain 0, and consumer canaries
  remain 0 at this 2026-10-18 checkpoint. The current 2026-10-21 readback below
  records seven admissions and seven canaries. No source payload bytes or new
  sources were used, and no rights
  conclusion was added. The source-owner-reserved PBS/M107 crosswalks and July
  derivative were not changed.
- [x] Save the reproducible overlay at
  `quality/qualifications/australian-m112-per-object-gate-reconciliation-20261018-retained-joins.json`,
  generated by `scripts/reconcile_m112_retained_evidence_joins.py`; cover it with
  `tests/test_australian_m112_retained_evidence_joins.py` and register the test
  in the routine unit lane. Focused adjacent tests and routine validation pass.

### M-112 retained-join accounting review correction (2026-10-18)

- [x] Correct the previous increment's terminology: the 22 prior exact
  raw-path matches comprise digest/path evidence and do not all prove B1/B2
  receipt lineage. The four new July joins increase digest/path matches from
  22 to 26 and complete B1/B2 lineage paths from 2 to 6. Keep the previously
  bound August alias separately identified; it is not a new acquisition.
- [x] Remove the obsolete “B1 binding incomplete” wording from the four July
  per-object rights states while leaving exact per-object authorization and
  reuse disposition unresolved. Rights remain a separate gate.

### M-112 approved object inventory freeze (2026-10-18)

- [x] Freeze the exact approved denominator as 1,759 `(dataset, path)` members:
  1,736 raw source paths and 23 existing projections across the five approved
  Australian candidate producers. Bind the freeze to the 2026-09-30 approval
  record and the exact approved inventory artifact. Preserve each original
  approval-time revision alongside its current reconciliation revision.
- [x] Verify the complete approved member set against the 2026-10-18 per-object
  reconciliation: all 1,759 dataset/path identities match, with no additions,
  removals, or duplicates. Eighteen producer revision observations have advanced
  since approval; revision movement is recorded separately and does not change
  frozen path membership.
- [x] Save the lock receipt at
  `quality/qualifications/australian-m112-frozen-object-inventory-20261018.json`.
  The retained-evidence join generator now fails closed if a later inventory
  overlay changes the frozen path set. This is a scope freeze only: no source
  payload bytes were read, and rights, admission, release, and canary gates
  remain separate.

### M-112 exact-six candidate consumer canary readback (2026-10-18)

- [x] Re-run the bounded exact-main candidate workflow at
  [39105652146](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39105652146)
  (attempt 2) after the six July 2025 MBS v3 Silver objects passed candidate
  lineage qualification. It traversed all 5,989 source-record edges through
  API, CLI, Atlas, and Chromium; each consumer produced the same ordered
  edge-ID digest. DuckDB and Polars also matched on bounded date and decimal
  queries. The aggregate-only receipt is
  `quality/qualifications/australian-mbs-gold-candidate-consumers-20261018-rerun-39105652146.json`.
- [x] Keep this result scoped to the six authorized candidate Silver tables and
  their Gold candidate consumers. The initial browser attempt failed to load
  the stylesheet; the failed job retry passed all steps. The receipt remains
  `candidate_only` and `review_state=not_reviewed`; no admission, rights
  conclusion, publication, source retention, or M-112 acceptance occurred.
- [x] At this 2026-10-18 checkpoint, keep per-object federation-reader canaries
  blocked until an eligible object receives v4 admission. The then-current
  overlay reported zero M-112 consumer canaries. This dated status is superseded
  by the 2026-10-21 current readback below; the 1,752 remaining objects remain
  deferred pending their own qualification.

### M-112 complete frozen-object identity readback (2026-10-18)

- [x] Stream the 12 previously unbound projection objects at their frozen
  public revision and verify their byte counts and SHA-256 digests without
  local persistence or value inspection.
- [x] Stream the 92 previously unbound PBS raw objects anonymously at their
  exact immutable revision, without local persistence or value inspection.
  Every recorded 64-character filename digest matches the streamed SHA-256.
- [x] Bind both readback receipts into the retained per-object overlay. All
  1,759 paths now carry direct SHA-256 evidence or the existing verified alias
  binding; raw and projection identity gaps are zero. There are 118 exact raw
  digest/path matches (119 path identities including the existing alias), of
  which six have complete B1/B2 lineage; the 92 PBS hash reads do not create
  lineage. The approved denominator and all deferrals are unchanged. This adds
  no rights or admission conclusion; PBS B1/B2 lineage and source-owner
  crosswalks remain open and unchanged.
- [x] Verify with the focused join tests, the full 80-test M-112 suite, Ruff,
  and exact frozen-membership and per-object identity assertions.

### M-112 producer receipt projection joins (2026-10-19)

- [x] Join the 1,706 pinned-revision B1/B2 raw projection matches against the
  existing producer's immutable source-download metadata. Exact digest, byte
  count, source version, locator, and source ID match for 1,705 objects. The
  remaining MBS XML object has a path-specific receipt matching its path,
  digest, and size; its URL differs from the parallel reimbursement-atlas B1
  projection locator. The object's existing MBS B1/B2 lifecycle evidence
  remains complete.
- [x] Preserve evidence strength: historical download rows are producer
  projections, not native receipt artifacts or admission histories. The
  receipt matches add no complete lineages; the total remains 6. No rights,
  source admissions, release decisions, new sources, or denominator changes
  were made.
- [~] Locate persisted landed-admission histories for the 1,703 incomplete
  B1/B2 projection matches. Their acquisition/B2 projection records and source
  receipt rows do not supply a landed event. A bounded search of the pinned
  producer's tracked path history (536 commits across fetched refs), its
  current source tree, and all current Actions artifact pages found no
  joinable landed-admission records. This narrows the retained-evidence search
  without proving that no other existing record exists. Continue only from
  existing evidence; do not synthesize admission history.

### M-112 exact path versus complete lineage accounting correction (2026-10-19)

- [x] Correct the projected-join qualification: 26 is the exact raw digest/path
  match set, not a complete receipt-join count. Five of those 26 have complete
  lineage; six complete lineages exist across the full inventory. The 1,703
  projection matches without persisted landed-admission history remain open.
- [x] Verify the correction with the focused regression test, BasedPyright,
  Ruff, formatting, and diff checks. No lineage was added; all 1,759 deferrals
  and the frozen denominator remain unchanged.

### M-112 historical MBS utilisation B1/B2 lineage (2026-10-19)

- [x] Join the 14 already-frozen MBS utilisation raw paths to their historical
  source receipts, acquisition events, immutable B2 references, and exact
  anonymous digest/byte-count readback at the pinned archive revision.
- [x] Add current `landed`, reviewer-unreviewed records and external-reference
  B2 manifests for those exact objects. The earlier historical import records
  remain unchanged. Complete B1/B2 lineages now total 20 across 1,736 raw
  paths; 19 of the 26 exact raw digest/path matches have complete lineage.
- [x] Preserve separate gates: all 1,759 objects remain deferred; the new
  records do not accept data for processing, change rights, add v4 admissions,
  or run consumer canaries. No new source was added and no source values were
  inspected.
- [~] Continue the remaining B1/B2 lineage work. Current overlay evidence
  leaves 1,716 raw paths incomplete, including PBS/M107 owner-managed work and
  the separately reserved July derivative. These remain outside this MBS
  increment.

- [x] Recheck the Windows consumer failure introduced by the new hashed
  admission paths. The clean-clone test now uses `RUNNER_TEMP` with a short
  prefix. PR #1174 merged at `c94ae241`; final-head hosted Windows and all other
  protected checks passed. The local release-reproduction test still cannot
  complete because available `uv` is 0.13.1 while the committed toolchain pins
  0.11.29.

- [x] Correct review finding #4307864545: the reconciler now validates the
  current B2-manifest and landed-admission SHA-256 values against both the
  per-object qualification and its `output_bindings` map. Two regression cases
  reject stale artifact and stale output-binding hashes; focused tests, Ruff,
  formatting, and BasedPyright pass. Broader suite and hosted rerun pending.

### M-112 P7 archive-boundary B1/B2 lineage (2026-10-19)

- [x] Re-stream the already-inventory July 2024 P7 archive object at its pinned
  public Hugging Face revision; verify HTTP 200, 87,727 bytes, and the exact
  frozen SHA-256 without saving or inspecting payload values.
- [x] Bind the historical archive receipt, its acquisition event, an
  external-reference-only B2 manifest, and a current landed/unreviewed
  admission record to the frozen P7 path, digest, and byte count. Keep the
  retrieval explicitly scoped to the archive boundary.
- [x] Preserve the known limits: original source-origin acquisition and source
  date semantics remain unverified; no rights conclusion, processing
  acceptance, v4 admission, canary, new source, or inventory change.
- [x] Reconcile the per-object overlay and Bronze receipt-cohort projections.
  Complete raw B1/B2 lineages now total 21 of 1,736; 1,715 remain incomplete.
  The July 2025 derivative, PBS/M107 work, and 1,707 reimbursement-atlas rows
  remain with their existing owner lanes.
- [x] Focused lineage/Bronze/receipt tests passed (75) after deterministic
  receipt-cohort regeneration. Routine checks, BasedPyright, context,
  ecosystem, and diff checks pass. Full local Test-Goblin completed with 6,918
  passed, 3 skipped, and 11 failures. One stale receipt-cohort projection was
  regenerated and its affected tests passed. The remaining failures are two
  stable-v1 reproduction tests requiring pinned `uv` 0.11.29 (local 0.13.1),
  three Gold/browser consumer tests, the PBS and coverage browser E2E tests,
  two scalar Chromium tests, and one Platinum browser test. Hosted PR checks
  are still required for this increment.

### M-112 August MBS Bronze projection lineage (2026-10-19)

- [x] Rebuild the four frozen August 2026 MBS `source.parquet` and `p7.parquet`
  projections from the exact pinned raw B2 stream and each run's public source
  receipt. All four output byte counts and SHA-256 values reproduce exactly and
  match the run manifests, M-108 metadata readback, and frozen tree inventory.
  Preserve both run-specific receipts, acquisitions, and accepted/unreviewed
  admission events; no event was collapsed or rewritten.
- [x] Bind the four output rows to the existing complete raw B1/B2 lineage and
  source transformation implementation. Raw source bytes were streamed and
  parsed in memory, then discarded; no source values or Parquet outputs were
  persisted. Rights, v4 admission, and release gates remain unchanged.
- [x] Reconcile the retained overlay and verify the exact four changed
  projection members. The frozen 1,759-object denominator is unchanged; 22 raw
  and 10 projection B1/B2 lineages are complete (32 total), 1,714 raw and 13
  projection lineages remain incomplete, all objects remain deferred, and v4
  admissions and M-112 federation-reader canaries were zero at this 2026-10-19
  checkpoint. See the current 2026-10-21 readback below.
- [~] Continue B1/B2 lineage work for remaining objects. The 1,707
  reimbursement-atlas raw rows and 12 medallion projections lack persisted
  landed-admission/source-receipt joins; PBS/M107 owner-managed objects remain
  in their separate lane.

- [~] Audit remaining lineage candidates against the pinned producer history.
  The 1,714 incomplete raw lineages are PBS objects: 1,707 reimbursement-atlas
  payloads, six PBS-utilisation objects, and one PBS-source object. The remaining
  13 incomplete projections are 12 reimbursement-atlas medallion tables and one
  PBS source Parquet. The pinned producer revision exposes B1/B2 metadata
  projections, but its existing retained Actions artifact contains no exact
  per-object landed-admission or B2 receipt records for this inventory. The
  source-owner lane remains unchanged; 32 of 1,759 objects have complete lineage.
  See the `m112_remaining_lineage_owner_lane_audit` evidence record.

### M-112 July Silver review correction (2026-10-19)

- [x] Address review findings #4308597850 and #4308597853. The reconciler now
  compares current-tree expected and observed Git blob, LFS digest, and byte
  count against each frozen object identity, validates both Silver qualification
  reports, and requires exact table-lineage equality with the manifest-bound
  public qualification. Four targeted tests and the 15-test focused suite pass;
  Ruff, formatting, BasedPyright, Test-Goblin routine, and repository metadata
  checks pass. All 39 hosted PR checks passed and PR #1177 merged as
  `25b6ee301bef156f4ac1f5757735a9ca65e5c948`.
- [x] The maintainer directed completion of B1/B2 lineage. A current,
  unreviewed record set was created from the exact pinned producer projections
  and frozen object identities; it does not rewrite producer history or change
  owner-held PBS/M107 crosswalks or the reserved July derivative. See the
  `m112_pbs_projected_b1_b2_lineage_expansion` evidence record.

- [x] Hosted verification and merge for PR #1177: all 39 reported checks passed
  on head `720292151d000530df3f568220e6fae56b7869aa`; both review conversations
  were resolved after their findings were fixed. The squash merge is
  `25b6ee301bef156f4ac1f5757735a9ca65e5c948`.


### M-112 PBS projected B1/B2 lineage expansion (2026-10-19)

- [x] Bind 1,703 exact frozen PBS raw paths to the pinned source receipt, B1
  acquisition projection, B2 immutable reference, and newly recorded local
  `landed` decision with `reviewer_status=unreviewed`. The 1,703 paths map to
  1,702 unique acquisition events, preserving the same-content alias as a
  separate path identity. The local decision is recorded at
  `2026-10-18T21:34:05Z`; it is not represented as historical producer
  admission evidence.
- [x] Regenerate the qualification and cumulative per-object overlay. The
  current inventory now has 1,725 complete raw lineages and 10 complete
  projection lineages (1,735/1,759 total); 11 raw and 13 projection lineages
  remain incomplete. All objects remain deferred, rights remain unresolved
  where previously unresolved, and v4 admissions and consumer canaries were
  zero at this 2026-10-19 checkpoint. The current 2026-10-21 readback below
  records seven admissions and seven canaries. No source was added, no source-
  owner work was changed, and no source payload bytes or values were read for
  this metadata join.
- [x] Verify the focused tests (4 passed), the complete M-112 affected suite
  (103 passed), Ruff, formatting, BasedPyright, and diff checks. Test-Goblin
  full ran 6,945 tests with 2 unrelated stable-v1 reproducibility failures
  because this host provides `uv 0.13.1` while the pinned build requires
  `uv 0.11.29`; 3 optional integration tests were skipped. The new lineage
  tests passed in both focused and full runs. Hosted protected checks remain
  required on the pull request.
- [~] Continue lineage qualification for the final 24 objects, then proceed
  through eligible v4 admission and consumer canaries only after their separate
  gates pass. Keep PBS/M107 crosswalks and the reserved July derivative in the
  source owner's lane.

### M-112 PBS projected-lineage merge and PBS utilisation lineage (2026-10-19)

- [x] Reconcile PR #1179's hosted result: all 38 reported checks passed on
  head `81aa031a3d10f722fb7565578204991c8768d0e9`; squash merge
  `ffbeff0ccd05724adb48994cccf0afafe13cc7cb` is on current `main`.
- [x] Read back all six PBS utilisation receipt sidecars anonymously at the
  frozen revision. Their exact receipt digests, source/category fields,
  payload digests, and byte counts match the retained audit and frozen raw
  object identities. Only 4,226 bytes of receipt metadata were read; no
  payload bytes or values were read.
- [x] Create six local historical B1 acquisition events with
  `rights_state=unknown`, exact pinned external-reference B2 manifests, and
  unreviewed `landed` records. The new records do not change rights,
  processing/public admission, the denominator, or consumer-canary status.
- [x] Reconcile the cumulative 1,759-object gate report: 1,731 raw and 10
  projection B1/B2 lineages are complete (1,741 total); five raw and 13
  projection lineages remain incomplete. All 1,759 objects remain deferred;
  v4 admissions and consumer canaries were zero at this 2026-10-19 checkpoint.
  The later 2026-10-21 readback below records seven admissions and seven
  canaries.
- [x] Verify 3 focused tests and 106 M-112 tests, Ruff, formatting, `ty`,
  BasedPyright, Test-Goblin routine and repository checks. Test-Goblin full
  completed with exit code 0 under pinned `uv 0.11.29`; coverage was 97.92%
  lines and 93.43% branches. The Darwin mutation lane is advisory; protected
  Linux CI remains authoritative for the mutation baseline.
- [x] Rerun Test-Goblin full after tightening per-object authorization-scope
  validation. The exact final code again exited 0; pytest and all harness
  stages passed, including 364 gremlins tests (1,034 of 1,118 zapped with
  cache reuse), format/lint, package probes, Scalene, and security checks.
- [x] Address the two automated review findings on PR #1180: require the
  linked admission state to be exactly `landed`, and refresh the cumulative
  report purpose, observation timestamp, and per-run byte counters. The
  report now records zero projection/source-payload bytes and 4,226 bytes of
  receipt-sidecar metadata for this increment. Focused tests (4), the full
  M-112 affected suite (107), Ruff, `ty`, and BasedPyright pass.
- [x] Run the pinned full profile for the review correction. Under
  `uv 0.11.29`, pytest completed with 6,950 passed and three skipped; one unrelated
  Hypothesis property case fails because reversing inputs changes the Brier
  score by one floating-point rounding unit. Both Stable v1 reproducibility
  tests pass under the pinned runtime. Hosted checks for the corrected PR head
  remain required.
## M-112 PBS archive PDF B1/B2 lineage (2026-10-19)

- [x] Stream all five already-inventoried PBS archive PDF variants from their
  exact Internet Archive replay URLs. Each streamed SHA-256 and byte count
  matches both the frozen inventory and its producer archive-variant receipt.
  No payload bytes were persisted or values inspected.
- [x] Add retrieval-timed local B1 acquisition events, reference-only B2
  manifests, and unreviewed `landed` admissions for those five frozen paths.
  Rights remain unknown; the producer receipt still records
  `blocked_pending_explicit_permission`; no processing, v4 admission, or
  consumer canary follows from this lineage.
- [x] Regenerate the cumulative overlay without changing the 1,759-object
  denominator. Raw lineage is now complete for 1,736 paths; all 1,759 remain
  deferred, and the 13 unresolved objects are projections.
- [x] Focused tests (3), the full M-112 affected suite (110), Ruff, `ty`, and
  BasedPyright pass. The full profile completed with 6,950 passed and three
  skipped; four unrelated failures remain in an order-sensitive matching
  property, a browser scalar-filter canary, and two Stable v1 reproducibility
  checks.
- [~] Continue lineage reconciliation for the remaining 13 projections.
  Preserve separate rights, v4 admission, and canary gates; PBS/M107
  crosswalks and the reserved July derivative remain with their owner.

## M-112 v4.1 contract-role qualification (2026-10-19)

- [x] Qualify the mandatory v4.1 contract roles against the all 16 rights/lineage/readback-qualified MBS raw path identities (14 utilisation paths and two August release aliases) with approved exact-scope rights, complete B1/B2 lineage, and anonymous digest evidence. The role matrix binds each object identity and evidence references; the two August paths are distinct path identities for one source payload. It records v2 as not applicable only for raw B2 under v4.1.
  Qualification: `quality/qualifications/australian-m112-v4-contract-role-evidence-qualification-20261019.json` (SHA-256 `39e06d16e71693417042f16c7cba0e82aa949a8e0d0e53ab0a38e3e68af8f2b1`). This is a gap assessment only: no contract was emitted, no admission or canary was performed, and the 1,759 denominator and zero-admission count are unchanged.
- [~] Obtain exact v4 publication and clean-room verification receipts, v1/v3 lineage, discovery, recovery/cache evidence, and consumer canaries before admitting any object.

## M-112 July 2025 MBS Silver rights attestation (2026-10-19)

- [x] Record the maintainer's attestation that an exact written permission or
  other applicable rights instrument covers public release of the six exact
  July 2025 MBS v3 Silver outputs. Per maintainer instruction, the instrument
  was not located or independently inspected. Bind the attestation to all six
  object paths and SHA-256 digests in
  `quality/qualifications/australian-mbs-v4-public-release-rights-attestation-20261019.json`.
  The current 1,759-object reconciliation records the six exact projection
  rights states in
  `quality/qualifications/australian-m112-per-object-gate-reconciliation-20261019-july-mbs-silver-rights-attested.json`.
  Public release is authorized by the attestation; no release was performed,
  and the separate v4 admission and canary gates remain closed.
- [x] Resolve the CMS HCPCS Level II reference-only rights state for the exact
  July 2026 file through the bounded CMS public-use rights decision. The
  approved record excludes ADA CDT material and leaves processing, v4
  admission, canary, derived-table rights, and external publication closed.
  The CMS Part D authorization does not apply, and this record is outside the
  frozen M-112 denominator. See the later exact-file disposition below.

## M-112 rights and release evidence preflight (2026-10-19)

- [x] Reconcile the current per-object rights states against the frozen 1,759
  object inventory. Sixteen objects have existing positive rights metadata
  (two exact MBS source-release paths and 14 exact-scope MBS utilisation files);
  the six July 2025 Silver projections remain without a projection-rights
  conclusion. The full state counts and pinned inputs are in
  `quality/qualifications/australian-m112-rights-release-preflight-20261019.json`.
- [x] Compare the six-table candidate authorization and the July 2025 raw
  receipt with the official July release page and current MBS Online copyright
  page. The source receipt says `permitted`; the linked approval record covers
  the exact August 2026 XML, while the six-table decision allows candidate
  qualification and canaries but excludes public release and any new rights
  conclusion. No source-specific written permission for the July 2025 source or
  derivative release was found in the reviewed records. No legal conclusion
  or public-release authorization is recorded by this preflight.
- [x] Reconcile the separate CMS HCPCS reference-only Bronze records with the
  official CMS public-use and HCPCS rights documentation. CMS describes
  Level II HCPCS as public domain, while D codes are maintained by ADA; the
  exact referenced file's code composition was not inspected. Keep its
  `rights_state=unknown` and `reviewer_status=unreviewed`. The CMS Part D
  authorization does not apply to this HCPCS object, which is outside the M-112
  frozen denominator.
- [x] Resolve the exact six MBS Silver-table rights and release disposition
  through the maintainer's bounded attestation of applicable written
  permission. The instrument was not located at the maintainer's direction;
  this records the attestation, not independent review. No release was
  performed. See the later MBS Silver attestation and current reconciliation.

## CMS HCPCS exact-file rights disposition (2026-10-19)

- [x] Bind the exact July 2026 CMS HCPCS external-reference object to its
  existing B1 acquisition, B2 manifest, and landed admission. Preserve the
  official CMS public-use, source-maintenance, and rights references without
  acquiring or inspecting the source payload.
- [x] Sole maintainer accepted the CMS public-use/public-domain basis for
  this exact July 2026 file; the rights decision records
  `rights_state=permitted` and `reviewer_status=approved`. The CMS rights
  decision is bounded to the official file and excludes separately licensed
  ADA CDT material. The payload was not opened or inspected. B2 remains
  `external_reference_only`; no processing, v4 admission, canary, derived-table
  rights conclusion, or external publication was authorized. The M-112
  denominator and all 1,759 deferrals remain unchanged. See
  `quality/qualifications/cms-hcpcs-rights-review-20261019.json`.

## M-112 effective rights reconciliation (2026-10-19)

- [x] Supersede the historical rights preflight with a current effective-state
  reconciliation. It binds the frozen 1,759-object inventory, the six-object
  cumulative lineage overlay, the exact six-object July MBS Silver attestation,
  the four August Bronze projections, and the approved exact-file CMS HCPCS
  decision. The six-object rights attestation is applied as a scoped override
  over the cumulative overlay. It preserves historical acquisition rights and
  admission records. See
  `quality/qualifications/australian-m112-current-rights-reconciliation-20261019.json`.
- [x] Supersede the prior 22/1,737 rights snapshot after joining the existing
  PBS utilisation publication authorization to all six frozen raw PBS objects.
  Exact path, digest, byte count, source, category, and source-domain checks
  pass; the grant excludes unlicensed vocabulary redistribution, whose presence
  remains unreviewed and blocks full-object release. The current snapshot has
  28 objects with positive scoped rights evidence and 1,731 unresolved. Rights
  evidence leaves all 1,759 objects deferred, zero v4 admissions, zero canaries,
  and zero external publications unchanged at this 2026-10-19 checkpoint. The
  later 2026-10-21 readback below records seven admissions and seven canaries;
  the no-publication state remains current. CMS remains external-reference-only;
  no processing or derived rights are inferred.
- [ ] Resolve the four exact August 2026 MBS Bronze projection rights and
  derived-output authority independently. Their B1/B2 and transformation
  lineage is complete in the cumulative overlay, but the source authorization
  does not conclude rights for these projections. Do not extend the July
  Silver attestation to them.
- [ ] Continue the remaining source-specific rights lane for the unresolved
  PBS and reimbursement-atlas objects. Identity or lineage alone does not
  establish reuse authority.
- Reconciliation implementation commit: `27007a797753c4ae9d8a53a81dede6c76a5a1369`.

## M-112 rights-release preflight refresh (2026-10-20)

- [x] Supersede the pre-decision October 19 rights-release preflight with a
  digest-bound snapshot of current effective rights evidence. Preserve the
  historical preflight unchanged. The exact six July 2025 MBS Silver objects
  carry the maintainer-attested bounded release permission; no release was
  performed. The exact July 2026 CMS HCPCS reference is permitted/reviewed,
  while its acquisition-time `unknown` state remains historical and no
  payload-processing, derived-rights, admission, canary, or publication
  authority is inferred. See
  `quality/qualifications/australian-m112-rights-release-preflight-20261020.json`.
- [x] Reassert the frozen denominator (1,759), current rights counts (28 with
  scoped positive rights evidence, 1,731 unresolved), zero v4 admissions, zero
  canaries, and zero external publications at this 2026-10-20 checkpoint. The
  later 2026-10-21 readback below records seven admissions and seven canaries;
  no external publication occurred. PBS utilization's scoped grant
  still excludes unlicensed vocabulary; full-object release remains blocked
  pending exclusion review.
- [ ] Resolve derived-output rights for the four exact August 2026 MBS Bronze
  Parquet projections. Their complete lineage does not establish rights, and
  the source authorization records no derived-output authority. Keep this
  separate from the July Silver attestation.
- [ ] Continue the remaining source-specific rights work for the unresolved
  MBS, PBS, and reimbursement-atlas objects. No source coverage was added.

## M-112 raw B2 v1 conformance candidate (2026-10-19)

- [x] Build a deterministic v1 conformance manifest for the exact 16-object
  MBS raw-B2 cohort already selected by the v4.1 role assessment. Bind each
  artifact to its source acquisition identity, exact path/revision/digest,
  exact-scope rights evidence, B1/B2 lineage evidence, and anonymous digest
  readback. The manifest keeps all artifacts `candidate` and all Silver
  promotions `blocked` on remaining v4 roles.
- [x] Validate all bound local evidence digests and the immutable v1 schema
  (`4c1ee81b026c64cf8f962d602cd64441a4a023c132346349c8b27dab0981f10e`); the
  focused selection passed (14 tests), the broader federation/M-112 selection
  passed (422 tests), and the follow-up harness/new qualification selection
  passed (72 tests). Test-Goblin routine, Ruff, formatting, BasedPyright, `ty`,
  context, ecosystem, and diff checks passed. No source payload bytes or
  values were read. The manifest is
  `quality/qualifications/australian-m112-v1-conformance-20261019.json`
  (SHA-256
  `826f7380ecb925d9c51dad826307f2d94348ed9ac44320ef70f8faff25709842`).
- [~] Bind this manifest as the exact `/lineage/v1_conformance` receipt in
  live v4.1 contracts only after its durable commit URL is established. This
  closes the local v1 schema-conformance candidate for these paths; it does
  not by itself satisfy the v4 receipt role, v3 replay, publication, clean-room
  verification, discovery, recovery/cache, consumer canaries, or admission.

## M-110 exact-main candidate consumer canary refresh (2026-10-19)

- [x] After validating the exact MBS Gold graph qualification, dispatch the
  bounded hosted consumer traversal against current `main` commit
  `cdc870b9c2fb42a13d5ed79e8f09f7f53ba10a3f`. Run
  [39262766723](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39262766723)
  passed all 5,989 candidate edges through API, CLI, Atlas, and Chromium; the
  four ordered edge-ID digests match. DuckDB and Polars also matched for the
  bounded date and decimal queries. The aggregate receipt is
  `quality/qualifications/australian-mbs-gold-candidate-consumers-20261019-39262766723.json`
  (SHA-256
  `b5197a7b9cb9c2b67efa73f740e1bc1717f5ef03b454f5dd50a008d0e77e9b26`).
- [x] Preserve scope: this is the authorized MBS Gold candidate canary only.
  It creates no M-112 v4 admission and does not change the M-112 per-object
  consumer-canary count, which remains zero while exact v4 contract roles are
  incomplete. The earlier candidate graph review and M-109/M-110/M-112 gates
  remain separate.

## M-110 relationship screening and match-behavior diagnostic (2026-10-19)

- [x] Screen current relationship classes against source and lineage evidence.
  The exact July 2025 MBS v3 `source_record_has_benefit` relation qualifies
  only as source-explicit within-record evidence (5,989 edges); confidence is
  not applicable, valid time is unselected, and the edge review state in the
  immutable graph qualification is `not_reviewed`. PBS
  `source_contains_entity` qualifies only as a structural contract on
  synthetic Silver. Cross-source/cross-record semantic relations do not
  qualify. See
  `quality/qualifications/australian-gold-relationship-screening-20261019.json`.
- [x] Assess current candidate-generator behavior against the six labeled
  synthetic cases, using the generator itself rather than supplied
  predictions. At lexical threshold 0.65 the result is precision 0.50, recall
  0.50, recall@5 0.50, coverage 0.67, selective risk 0.50, two false
  positives and two false negatives. A 0.99 cutoff yields zero false positives
  only at 0.33 coverage and 0.50 recall. These six self-authored cases cannot
  establish calibration or select a production threshold. Report:
  `quality/qualifications/matching-behavior-synthetic-20261019.json`.
- [ ] Complete PBS real admitted Silver screening, representative
  human-adjudicated held-out labels, per-method/source calibration, and exact
  candidate review before any scored relationship promotion. Synthetic graph
  parity and this diagnostic do not close M-110.
- [x] Focused matcher/graph/review selection: 98 passed. Broader affected MBS,
  PBS, matcher, and M-110 selection: 106 passed. Test-Goblin routine,
  deterministic report regeneration, Ruff, Ruff format, `ty`, BasedPyright,
  and `git diff --check` passed. No threshold was promoted.

## M-112 durable v1 candidate receipt readback (2026-10-19)

- [x] Read back the merged v1 candidate manifest anonymously from the exact
  main commit `290cc219217821404cf25bcfc58761821389d614`; its digest is
  `826f7380ecb925d9c51dad826307f2d94348ed9ac44320ef70f8faff25709842`.
  It covers 16 raw-B2 path identities and keeps all 16 promotions blocked.
- [x] Refresh the role assessment with the stable receipt identity and
  `candidate_receipt_available_unbound` state for those objects. This records
  durable candidate evidence only; no live v4 contracts were created or bound,
  and admission and consumer-canary counts remain zero.
- [ ] Bind the receipt into exact v4.1 contracts only as their other required
  publication, verification, rights, discovery, recovery/cache, lineage, and
  consumer evidence becomes available. Do not promote based on this receipt
  alone. Full details are recorded in `evidence.jsonl` and
  `quality/qualifications/australian-m112-v4-contract-role-evidence-qualification-20261019.json`.

## M-112 hosted publication and clean-room receipt reconciliation (2026-10-20)

- [x] Reconcile the 14 exact MBS utilisation raw-B2 candidates against the
  existing hosted 28-object manifest at pinned revision
  `dee9a5b0580dfe394474dc26b372559462e157e7`. All 14 match by dataset,
  revision, path, byte count, and SHA-256 in
  `quality/qualifications/australian-m112-utilisation-digest-reconciliation-20261004.json`.
- [x] Verify the historical GitHub Actions harvest run `36333396964` completed
  successfully at workflow commit `979f806fcf92267f9595eb78a88707e4ec2e503c`.
  Its durable issue receipts report all 28 manifest objects anonymously
  digest-verified; the restore calls used `hf_hub_download(token=False)`, and
  the follow-up receipt records temporary hosted-runner materialization cleanup.
  Current metadata readback confirms the exact pinned Hub revision remains
  public and ungated.
- [x] Refresh the role assessment with the exact per-object publication and
  token-free clean-room restore receipts as `candidate_receipt_available_unbound`
  for these 14 objects. The two August objects remain without this receipt
  binding. This does not create a v4 contract, change rights, admit objects, or
  qualify any consumer canary. The 1,759 denominator, zero admissions, and
  zero canaries are the 2026-10-20 checkpoint state, superseded by the
  2026-10-21 current readback below.
- [x] Validate the deterministic refresh: focused selection 14 passed; broader
  federation and admission selection 195 passed; Test-Goblin routine, Ruff,
  `ty`, context/ecosystem validation, and `git diff --check` passed. Qualification
  is `quality/qualifications/australian-m112-v4-contract-role-evidence-qualification-20261020.json`
  (SHA-256
  `3d3893c921fcb9a650948377d609779a0987b68b406a29373a5a2061d57fdb93`).
- [ ] Complete authority and source semantics, v4 discovery, v3 replay,
  recovery/cache, and exact contract binding before considering admission.
  M-112 consumer-reader canaries remain gated on an admitted object.

## M-110 exact-main candidate consumer canary refresh (2026-10-19, post-merge)

- [x] Revalidate the exact MBS Gold qualification on merged `main` and run
  hosted workflow [39271490764](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39271490764)
  at commit `47e0afbd5a3ea59e16531237ec08403b0d317d04`. All 5,989 candidate
  edges passed through API, CLI, Atlas, and Chromium with identical ordered
  edge-ID digests; bounded DuckDB/Polars date and decimal queries agreed.
  The aggregate-only receipt is
  `quality/qualifications/australian-mbs-gold-candidate-consumers-20261019-39271490764.json`
  (SHA-256
  `c9fda86d8ac0da31821233469350e6c7f88dd2f53481de1950fb51510cfd294d`).
  No public dataset mutation or source-payload retention occurred. This is
  M-110 candidate evidence only; M-112 admissions and M-112 consumer canaries
  remain zero.

## M-112 admitted-object consumer canary preparation (2026-10-20)

- [x] Build the exact v4.1 contract for the July 2016 MBS Group raw B2
  object and verify all external receipt roles plus independent admission.
  The contract pins public revision
  `dee9a5b0580dfe394474dc26b372559462e157e7`, path
  `raw/mbs/utilisation/group/mbs-group-2016hr-july.xlsx`, 6,857,437 bytes,
  and SHA-256
  `9f2f28b69f58a0aa05a0b56b09515651b1e0b50a634234ce7f6f6c8426373285`.
  Its contract SHA-256 is
  `b95056d6ab657f5b280870dc2ac7dcb1578019224e843d423a99e2880f451d7e`.
  Receipt closure verified 12 role bindings and 10 unique receipt payloads;
  one exact object is technically admitted. The source-native workbook layout
  remains unqualified and no values or rows are interpreted.
- [x] Prepare a default-branch-only, 15-minute hosted workflow to revalidate
  that exact admission, exercise `bind_consumer_contract` and
  `FederatedReader` on the live public object, verify stream digest/size and
  reader cache cleanup, and retain an aggregate-only canary receipt.
- [x] Run and verify the exact-main canary after the workflow and qualification
  merged. The exact July 2016 Group workbook canary passed in run `39300224557`;
  its receipt and the later current 7/7 reconciliation are recorded below.

## M-112 consumer canary cache-expiry correction (2026-10-20)

- [x] Record hosted canary run
  [39298714672](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39298714672)
  against merged main `fee2f3078b6c482ffce007d70f26bed5ad8fee62`. It reached the
  admitted-object consumer check but failed its final combined assertion. The
  contract cache expiry was 15 minutes after the v3 replay, before this run;
  the production reader therefore correctly retained no expired cache entry.
  This failed attempt is not a passing canary and the count remains zero.
- [x] Correct the canary to derive expected cache occupancy from the exact
  admitted expiry timestamp at the observation point. It now accepts a retained
  exact-object cache only while its admission is live, requires zero retained
  bytes after expiry, and always checks that closing the reader clears cache.
  Focused cache-boundary tests cover both live and expired receipts.
- [x] Merge the correction and rerun on exact `main`. Run `39300224557` passed
  the exact-object reader and cleanup checks; the aggregate receipt is recorded
  below. The current M-112 readback now counts seven unique admitted objects
  and seven canaries.

## M-112 July 2016 admitted-object consumer canary passed (2026-10-20)

- [x] Run hosted canary
  [39300224557](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39300224557)
  on exact merged `main` commit
  `500344931252ce65768b55fb2f3e07191470344c`. The production contract binder
  and `FederatedReader` accepted the admitted contract and exercised the exact
  public July 2016 raw B2 object. Both remote and consumer-stream SHA-256 and
  byte count matched the pinned identity. The admitted cache expiry had passed,
  so the reader retained zero bytes; close also left zero cache bytes.
- [x] Read back and retain the metadata-only workflow receipt at
  `quality/qualifications/australian-m112-v4-july2016-consumer-canary-20261020-39300224557.json`
  (SHA-256 `af870552004e50ab5174fc535c9e5bbefe59f6edc4d03c830ce40129adf22b6a`).
  The exact object now has one v4 admission and one consumer canary. The overall
  approved denominator remains 1,759; the remaining 1,758 paths are not
  implied complete. Native workbook layout remains unqualified and no rows or
  values were interpreted.

## M-112 CMS reference-only effective rights readback (2026-10-20)

- [x] Reconcile the exact approved CMS HCPCS rights decision into the current
  reference-only readback fields, while retaining acquisition-time `unknown`
  and the superseded landed admission's `unreviewed` status as history. Keep
  source bytes external-reference-only and keep processing, derived rights,
  canaries, and publication unauthorized.
- [x] Verify the regenerated qualification and overlay bind the current rights
  review, decision, and superseding landed admission to the exact CMS file.
  Focused checks (40 tests after merging the concurrent replay update), routine
  profile, and all 39 hosted checks passed on PR #1208 before merge.
- [x] Make the effective admission state explicit in the current readback and
  fail closed unless the latest admission is approved, is for the exact CMS
  acquisition/content, and supersedes the original landed admission. The new
  report labels the superseded `unreviewed` admission and acquisition-time
  `unknown` separately from the effective `permitted` / `approved` state. The
  append-only current snapshot is
  `quality/qualifications/australian-m112-rights-release-preflight-20261020-3.json`;
  it preserves the prior `-2` snapshot unchanged. This clarifies the existing
  exact-file decision only; external publication, processing, derived-table
  rights, v4 admission, and canaries remain unauthorized.

## M-112 second raw-object v3 replay preparation (2026-10-20)

- [x] Generalize the metadata-only replay planner and hosted executor to one
  exact raw MBS B2 path at a time. The target must uniquely match the frozen
  role report and pass exact-rights, anonymous-digest, B1/B2, publication, and
  restore checks. Reject paths outside the MBS raw-B2 prefix and any identity
  already present in a v4 contract. Preserve the existing July workbook replay
  plan identity.
- [x] Validate the exact candidate
  `raw/mbs/utilisation/group/mbs-group-2016-july.csv` at public revision
  `dee9a5b0580dfe394474dc26b372559462e157e7` (12,291,303 bytes,
  SHA-256 `62ad118d94cd565a051164aa645eff1fef84a5beb74d501e3dc64344fcf16d3b`).
  Official metadata supports its July 2016 YTD temporal description; native
  schema layout remains unqualified. The replay does not interpret rows or
  source values.
- [x] Focused replay tests (13), broader admission/consumer/replay tests (131),
  Test-Goblin routine, Ruff, `ty`, BasedPyright, actionlint, and the existing
  workbook replay plan check passed.
- [~] Merge and run the bounded default-branch replay for this CSV. Read back
  its exact run receipt and verify the digest, byte count, token-free fetch,
  and temporary-byte cleanup before binding the new v3 role into a v4 contract.
  The M-112 count is one admitted object and one consumer canary out of 1,759;
  this candidate is not admitted by replay evidence alone.

## M-112 July 2016 CSV admitted-object consumer canary (2026-10-20)

- [x] Merge PR [#1212](https://github.com/edithatogo/global-medicines-atlas/pull/1212)
  with all required hosted checks passing. The workflow now selects one exact
  qualified object while remaining constrained to an exact merged-main commit.
- [x] Run hosted canary
  [39317542644](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39317542644)
  on merge commit `8932efd261ff6e4956dfc013702a5db19281ca63`. The production
  binder and `FederatedReader` read the exact admitted July 2016 CSV; remote and
  streamed digest and byte count match. Cache bytes were zero after read and
  close. No source values or rows were interpreted or retained.
- [x] Read back the metadata-only receipt at
  `quality/qualifications/australian-m112-v4-group2016-csv-consumer-canary-20261020-39317542644.json`
  (SHA-256
  `c129eb177924a1a2096c2bfd0ea9fac3585fedd9c53cb2a6c8fcbcf4ddcb7b1c`).
  M-112 now has two admitted objects and two `FederatedReader` canaries out of
  1,759 approved paths. This does not qualify API, CLI, Atlas, browser product
  consumers, source-native CSV semantics, or the remaining denominator.

## M-110 and M-112 bounded consumer canary refresh (2026-10-20)

- [x] Requalify the admitted July 2016 MBS raw B2 object through the pinned
  `FederatedReader` on exact `main` commit
  `7dbf14db2403485cabbe699858579cf7c7567012`. Hosted canary run
  [39306554319](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39306554319)
  passed; remote and streamed digests matched, no source values were
  interpreted or retained, and reader cache usage was zero after read and
  close. Receipt:
  `quality/qualifications/australian-m112-v4-july2016-consumer-canary-20261020-39306554319.json`
  (SHA-256
  `62aa052690bf3092aaf658d747654bc14316807e005e72f063ec11b158df4f18`).
  The M-112 total remains one admitted object and one admitted-object canary;
  the other 1,758 denominator entries are not implied complete.
- [x] After checking the exact MBS Gold candidate qualification, run hosted
  workflow [39306778440](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39306778440)
  on the same exact `main` commit. API, CLI, Atlas, and Chromium traversed all
  5,989 candidate edges with identical ordered edge-ID digests. The aggregate
  receipt is
  `quality/qualifications/australian-mbs-gold-candidate-consumers-20261020-39306778440.json`
  (SHA-256
  `4b9b4141a877d86aad7cb92fdc4e4d82ae012503e750418e5fb7ce2dccdf98af`).
- [x] Keep the evidence scopes distinct: the MBS Gold traversal remains
  candidate-only with `review_state=not_reviewed`; it does not establish M-110
  acceptance, semantic calibration, M-112 admission, or increase the M-112
  admitted-object canary count. No public dataset was mutated and no source
  bytes were retained.
## M-112 PBS publication and current admission/canary readback (2026-10-20)

- [x] Reconcile the exact April 2026 PBS source ZIP to Decision 0009, its
  publication-intent record, the hosted anonymous digest receipt, and the
  current pinned path/digest/size. Record exact-object publication authority
  separately from the still-unknown upstream licence and preserve the
  acquisition-time `unknown` state.
- [x] Keep the exact PBS Bronze Parquet projection
  `bronze/2026-04-01/pbs-v3-source.parquet` unresolved; source permission does
  not imply derivative rights. No rights conclusion, v4 admission, or release
  is made for the projection.
- [x] Reconcile the successful exact-main July 2016 MBS workbook and CSV
  canary receipts. They bind two distinct rights-cleared raw B2 objects and
  contracts, so current counts are two admitted objects, two canaried objects,
  and 1,757 deferred objects. Source values and native layouts remain
  unqualified. Rights remain 32 resolved and 1,727 unresolved across the frozen
  1,759-object inventory.
- [x] Refresh the effective-rights report and preflight with exact hashes and
  both canary run receipts; preserve all other deferrals, keep inventory
  membership unchanged, and add no sources or datasets.
- [x] Focused rights/preflight tests passed (9); Ruff, format, ty, BasedPyright,
  and diff checks passed. Full profile: 7,010 passed, 3 skipped, 3 failed. Two
  failures require pinned uv 0.11.29; both passed in the pinned-toolchain rerun
  after verifying the official release archive digest. One unrelated Chromium
  end-to-end timeout passed when isolated. Coverage was 96.90%.
- [ ] Resolve the exact PBS Bronze projection's own rights and continue the
  remaining source-specific rights review.

- [x] After integrating main commit `5b4d6626` (PR #1211), rerun the
  rights/preflight and July 2016 admission/role suites together: 28 passed.
  Routine profile, Ruff, format, ty, BasedPyright, and diff checks passed on the
  integrated tree.

## M-110 reviewed-candidate consumer canary (2026-10-20)

- [x] Bind the exact maintainer disposition at
  `quality/qualifications/australian-mbs-gold-same-record-review-20261018.json`
  to the 5,989 source-explicit July 2025 MBS `source_record_has_benefit`
  edges and their reviewed edge-ID digest. The disposition is
  `accepted_candidate_only`; it does not establish overall M-110 acceptance,
  payability, clinical equivalence, or production admission.
- [x] Require the hosted consumer qualifier to verify that review receipt and
  exact edge digest, then compare the complete ordered traversal through API,
  CLI, Atlas, and Chromium. Preserve the underlying graph's immutable
  `review_state=not_reviewed` and report review separately.
- [x] Run the bounded traversal on exact `main` commit
  `386b6bd292e6a657dc01d17c8355d9fa13d35bfa` (hosted run
  [39322203034](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39322203034))
  and read back the metadata-only receipt at
  `quality/qualifications/australian-mbs-gold-reviewed-candidate-consumers-20261020-39322203034.json`
  (SHA-256 `8b5d1a6b1537981cac50af6843a0dc52a7a3d1d1203f9850740b0c5552cf96a1`).
  API, CLI, Atlas, and Chromium each returned the same ordered 5,989-edge
  reviewed-candidate set (edge-ID SHA-256
  `7a2ba8a0b31dca32101172bde49f6dc17d3ef6d873afb4760651f2a22c3a502d`).
  This records four surface canary checks for one candidate relationship set;
  it does not change the graph's immutable `review_state=not_reviewed`, accept
  M-110 overall, establish clinical/payability/equivalence, or count as an
  M-112 admitted-object canary. Earlier candidate traversals remain historical
  and are not relabeled.

## M-112 July 2025 MBS Silver current public metadata readback (2026-10-20)

- [x] Read the anonymous current Hugging Face tree for
  `edithatogo/australian-mbs-source-archive`. At revision
  `42d73b6facac016f14a335d36d83f1a3b630add8`, all six exact July 2025 v3
  Silver Parquet paths have the same LFS SHA-256 digests and byte counts as
  the maintainer rights attestation. Record the metadata readback in
  `quality/qualifications/australian-mbs-v4-current-public-tree-readback-20261020.json`.
- [x] Reconcile that readback into the M-112 rights report and preflight. The
  readback confirms current public metadata identity; the hosted receipt remains
  the evidence of anonymous payload-byte verification at the publication
  revision. No payload bytes or source values were read in this step.
- [x] Preserve all boundaries: no new external publication, no new rights
  conclusion, no v4 admission or promotion, no object-membership change. The six
  objects remain a public candidate, not an accepted M-112 product. Frozen M-112
  rights counts remain 32 resolved and 1,727 unresolved.
- [x] Focused rights/preflight tests passed (9); Ruff, Ruff format, ty,
  BasedPyright, routine Test-Goblin, and diff checks passed.

## M-112 historical 1993–2015 raw B2 v4 role qualification (2026-10-20)

- [x] Select `raw/mbs/utilisation/group/mbs-demographics-historical-1993-2015.zip`
  from the frozen 1,759-path denominator. Exact-scope rights, B1/B2 lineage,
  anonymous digest readback, official source period, publication/restore,
  discovery, and v1 conformance evidence were already available; only the v3
  replay/cache role was missing. Native source layout remains unqualified.
- [x] Run the bounded hosted replay on exact `main`
  `3df35dbd1475557122faa3025b915e37cf202a55`:
  [39324097024](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39324097024).
  Anonymous byte count and SHA-256 matched the frozen identity; the workflow
  rebuilt only the append-only registration and removed temporary source bytes.
- [x] Read back the aggregate-only receipt
  `quality/qualifications/australian-m112-v3-replay-execution-20261020-39324097024.json`
  (SHA-256 `d0b13510173001f20d4809d6389acd123465d55cb85091d8356c98104eb28731`)
  and deterministic plan
  `quality/qualifications/australian-m112-v3-replay-plan-20261020-39324097024.json`
  (SHA-256 `1b1e68b33666b3d334e604534c50ab5ab912ae0c023d53764b0cd123a48fc7bf`).
  The role qualifier now validates all three replay receipts. The current
  admitted-object count remains two; replay alone does not admit the new object.
- [x] Focused role/replay/contract tests passed (35), and the affected M-112
  suite passed (172). The new contract path is
  restricted to the exact public identity, rights decision, and bound role
  evidence for this archive. Test-Goblin full completed with 7,017 passed,
  3 skipped, and 2 failed at the existing Stable v1 clean-clone toolchain
  checks because local uv is 0.13.1 while those checks require pinned uv
  0.11.29; coverage was 96.89%. Context/registry, ecosystem validation,
  Test-Goblin routine, Ruff, formatting, ty, BasedPyright (0 errors), and
  diff checks passed.
- [x] Build the per-object v4.1 raw-B2 contract against the merged role receipt,
  verify the full external receipt closure, then record admission only if the
  exact object and every required role validate. Keep native archive semantics
  unqualified and all other denominator paths deferred.

## M-110 screened-relationship consumer canary refresh (2026-10-20)

- [x] After screening identified `source_record_has_benefit` as the only
  evidence-qualified candidate class, rerun the bounded exact-main consumer
  check on `e02e0b0dccf0893954125a2780c2a2b3436b6574`. Hosted run
  [39326767284](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39326767284)
  passed 5,989 candidate edges through API, CLI, Atlas, and Chromium with
  matching ordered edge-ID digests. Bounded DuckDB/Polars date and decimal
  queries also matched. Aggregate receipt:
  `quality/qualifications/australian-mbs-gold-candidate-consumers-20261020-39326767284.json` (SHA-256 `0f8aa73bfa745610a70ce6ba4190fdcb1fef0ae7be5aa1c87a5b17640cbdca00`).
- [x] This is one four-surface M-110 screened-candidate canary. It does not
  accept M-110 overall, calibrate match scoring, promote cross-source
  relationships, or count as an M-112 admitted-object canary.

## M-112 historical 1993–2015 raw B2 v4 admission and canary preparation (2026-10-20)

- [x] Bind candidate roles to merged exact-main evidence commit
  `060114c0a9d1d6f8122f0829f24257861ae30e75`; create the exact raw-B2
  v4.1 contract with SHA-256
  `992eb2ce2d93891f51423284df2d718bc7d44af6511cc09c11c33a578588210b`.
- [x] Independently verify the contract’s 12 receipt roles against 10
  unique public receipts. The exact 1993–2015 object is admitted; native
  archive layout remains unqualified. Recorded admission qualification:
  `quality/qualifications/australian-m112-v4-historical-1993-2015-admission-qualification-20261020.json`.
- [x] Refresh current role reconciliation: three v4 admissions, two
  admitted-object canaries, approved denominator unchanged at 1,759.
- [x] Extend the hosted bounded `FederatedReader` canary workflow to
  accept this exact admitted path; focused admission/role tests passed (23),
  broader affected suite passed (176), and routine Test-Goblin, Ruff,
  formatting, role check, and diff checks passed.
- [x] After this contract and workflow change merged, run the exact-main
  hosted canary for this object, read back its aggregate receipt, then
  refresh role qualification to count the third canary.

## M-112 historical 1993–2015 admitted-object consumer canary (2026-10-20)

- [x] Run the bounded hosted `FederatedReader` canary on exact `main`
  commit `3149a5533ecb1b721d9deda66311d4abc94ee3d1`; workflow run
  [39330593204](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39330593204)
  passed for the exact 1993–2015 archive. Remote digest and streamed
  digest matched; reader cache was zero after read and close; no source
  values were interpreted or retained. Aggregate receipt:
  `quality/qualifications/australian-m112-v4-historical-1993-2015-consumer-canary-20261020-39330593204.json`
  (SHA-256 `b10a7f795014e0b6ebc975330062bb9e20dd13d66996a09b1a5a69c4b438803f`).
- [x] Reconcile current M-112 qualification: 3 admitted objects and 3
  per-object consumer canaries of 1,759 approved paths; the remaining
  1,756 paths remain deferred. Native source archive layout remains
  unqualified. The separate M-110 candidate consumer canary is not counted
  as an M-112 admission canary.
- [x] Focused admission/role tests passed (24); broader M-110/M-112 suite
  passed (177); role reconciliation, Test-Goblin routine, Ruff, formatting,
  and diff checks passed.

## M-112 exact raw PBS rights reconciliation (2026-10-20)

- [x] Bind the active owner-attested raw PBS redistribution permission at
  `edithatogo/reimbursement-atlas` revision
  `a93516ed416118bc51c1db2b71ab540fa4d0fe52` to exactly 1,708 frozen,
  lineaged raw objects: 1,707 reimbursement-atlas objects and one already
  landed PBS XML-V3 archive object. The permission snapshot digest is
  `0817123492cfe20858f86b3ec14c92539081a647b17dd6933d2d2ff8c266d098`.
- [x] Preserve the permission's limits: it is an owner attestation, not an
  independently verified publisher licence; historical acquisition rights
  remain unchanged; no public release, project-wide publication, v4 admission,
  canary, payload-byte read, or source-value inspection is authorized by this
  reconciliation. The PBS Bronze projection, 12 reimbursement-atlas derived
  projections, and all other unresolved objects retain their own rights gates.
- [x] Refresh current rights and release-preflight reports. Frozen membership
  remains 1,759; effective rights are 1,740 resolved and 19 unresolved. All
  1,756 deferrals, three existing admissions, and three admitted-object
  canaries remain unchanged.
- [x] Focused rights and preflight tests passed (11); broader M-112/M-110
  rights, role, and graph tests passed (54). Updated post-canary verification
  is recorded below with the corresponding PR evidence.
- [ ] Resolve rights for the remaining derived and source-specific objects;
  do not infer derived rights from this raw-source permission.

## M-112 Reimbursement Atlas medallion rights-ledger readback (2026-10-20)

- [x] Freeze the current upstream rights-ledger comparison for the 12 exact
  Reimbursement Atlas medallion projection identities. At upstream revision
  `a93516ed416118bc51c1db2b71ab540fa4d0fe52`, none of the 184 current
  checksum-bound decisions match an exact path/digest pair, and none of the
  19 standing-scope paths covers these outputs. The current licensing policy
  requires source-specific approved evidence for derived-output publication.
  Readback: `quality/qualifications/australian-m112-reimbursement-atlas-medallion-rights-ledger-readback-20261020.json`
  (SHA-256 `20f1d99b97ff5e91a75d1c36413176061db451def6fbd19bb644ebf58c4827db`).
- [x] Record the maintainer-attested public redistribution rights basis for
  these exact 12 path/digest/byte-count identities, at maintainer direction
  without locating the instrument. The qualification explicitly preserves
  admission, consumer-canary, and release-execution gates:
  `quality/qualifications/australian-reimbursement-atlas-medallion-rights-attestation-20261020.json`.
  Reconciliation binds complete B1/B2 lineage and unchanged frozen membership;
  no projection values or source payload bytes were inspected.
- [ ] Resolve rights for the exact PBS Bronze source projection. Its raw-source
  redistribution permission and lineage do not grant derived-output rights.

## M-112 Reimbursement Atlas projection rights attestation (2026-10-20)

- [x] Apply the maintainer's statement that exact written permission or another
  applicable rights instrument exists to the 12 exact Reimbursement Atlas
  medallion projection identities. Per instruction, the instrument was not
  located or independently reviewed. The attestation is limited to these
  frozen paths, digests, and byte counts; public release execution, v4
  admission, and consumer canaries remain false. The reconciled rights count is
  1,752 resolved and 7 unresolved, with all 1,759 frozen identities and the
  three existing admissions/canaries unchanged. Current report:
  `quality/qualifications/australian-m112-current-rights-reconciliation-20261020-2.json`.
  Current preflight:
  `quality/qualifications/australian-m112-rights-release-preflight-20261020-2.json`.
- [ ] Resolve source-specific rights for the PBS Bronze projection, separately
  from its raw archive permission.

## M-112 PBS Bronze projection rights terms readback (2026-10-20)

- [x] Compare the exact `bronze/2026-04-01/pbs-v3-source.parquet` identity
  with current official PBS API documentation and the raw-source permission.
  Official docs describe public access and download/local storage; they do not
  record an express redistribution grant for this derived output. The exact
  API `_meta` copyright notice has not been read back. The raw permission is
  limited to raw objects. Rights remain unresolved; no release, processing, or
  admission authority is inferred. Readback:
  `quality/qualifications/australian-m112-pbs-bronze-projection-rights-source-terms-readback-20261020.json`
  (SHA-256 `6d9f380ab3ce60a66c166de118afac613ab1a76927b487aa153aedef5aea31b6`).
- [ ] Obtain an object-bound applicable rights basis for this projection; do
  not infer its rights from the raw archive permission or lineage.

## M-112 Q3 2016 demographics raw B2 replay role qualification (2026-10-20)

- [x] Run exact-main bounded v3 replay for the Q3 2016 demographics CSV on
  `1ebee786331c2e63d0a4d9501894ad657006ea9d`: hosted run
  [39344611967](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39344611967) passed anonymous digest verification, rebuilt only its append-only
  B2 registration, and removed temporary source bytes. Exact object digest is
  `bc6ad85e41bd2394f4dc0b3550c0657eb7389f444c9300d72105a41530e08e1c`
  (7,680,041 bytes).
- [x] Retain and reconcile the deterministic plan, aggregate receipt, and
  readback manifest. The current M-112 role report binds 4 of 16 candidate v3
  replay/cache roles, with 14 publication/restore roles, 3 existing v4
  admissions, and 3 existing admitted-object canaries. This replay creates no
  v4 admission or canary.
- [x] Build and independently verify the exact Q3 raw-B2 v4.1 contract after
  the role-evidence merge, then run its admitted-object canary on exact `main`.
  The exact-main qualification is recorded at
  `quality/qualifications/australian-m112-v4-demographics-q3-july-admission-qualification-20261020-39356792827.json`.
  Native source layout remains unqualified and outside this raw-B2 admission.

## MBS August projections outside the frozen M-112 inventory (2026-10-20)

- [x] Record the maintainer's attestation for the exact four already-public
  August 2026 MBS Bronze Parquet outputs identified by product IDs
  `d78170f1944e8c209833b86193d403b12553a3932579dc571ff10f8485a6483b` and
  `f9f9af5a152ea74c25a617102e3cf271054ef78867ed0eb84fb69822b6767d63`. The
  permission instrument was not located or independently reviewed, as directed.
  The attestation binds each exact path, digest, byte count, dataset, and public
  revision. It does not add the outputs to frozen M-112 inventory, perform new
  publication, inspect source/Parquet bytes, authorize v4 admission, or authorize
  consumer canaries. The scoped readback is
  `quality/qualifications/australian-mbs-public-august-projection-scope-exception-20261020.json`;
  attestation is
  `quality/qualifications/australian-mbs-august-outside-m112-projection-rights-attestation-20261020.json`.

## M-112 Q3 HR contract candidate and consumer-canary readiness (2026-10-21)

- [x] Merge the Q3 2016 July HR v3 replay evidence in PR [#1241](https://github.com/edithatogo/global-medicines-atlas/pull/1241) at exact main commit `6dc3f707382f65659b511c98e55412ecbdb0d6b2`. Hosted run [39431880718](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39431880718) passed anonymous digest verification for the exact 7,316,301-byte object (`7c0591665008e1b423cf8aa6f5dfe0d78499914ae67ef34dc566c4b0a1736152`) and removed temporary source bytes.
- [x] Pre-canary baseline: six admitted objects had six passed admitted-object consumer canaries in the role qualification (SHA-256 `6b02c5cf5e93a15a753f573ff6e3da5c8d76183270c4be53c4ddef51fbc1679a`). This supersedes still-earlier plan snapshots that said zero or three; the Q3 HR admission and canary were pending at this checkpoint.
- [x] Add Q3 HR as an exact target in the v4.1 contract builder and bounded consumer-canary workflow. Generate and validate the candidate contract bound to the merged replay receipt. Contract SHA-256: `f65f1da3d4b9018e61a1ba31a5de1ceeb9bfa732da363a142c88bc7260eca469`. Native workbook schema remains unqualified; admission and consumer-canary completion is recorded in the following section.
- [x] Focused tests passed (20); broader affected admission/role/reconciliation tests passed (49). Ruff, formatting, `ty`, BasedPyright, actionlint, contract `--check`, and `git diff --check` passed. The local full Test-Goblin profile completed with 7,015 passed and 3 skipped but failed 31 tests because this workstation lacks Playwright Chromium and has uv 0.13.1 while reproducibility tests require 0.11.29. These environment failures do not pass the full profile; protected hosted checks remain required for the scoped PR.
- [x] Merge the scoped target-support and contract PR, verify the contract on exact `main`, then run the bounded hosted v4 admission/consumer workflow for the Q3 HR path. Read back and validate the metadata-only hosted receipt before incrementing admission/canary counts or marking this item complete. Do not infer native schema qualification or cross-source relationship calibration from this raw-B2 reader canary. Completion evidence is recorded below.
- [x] Preserve the historical rights-preflight snapshots. The first unit lane exposed that the plan digest was stale after this update; retain the prior snapshot byte-for-byte and bind the final plan bytes in the new current preflight revision `quality/qualifications/australian-m112-rights-release-preflight-20261021-3.json`, without changing rights, denominator, admission, or canary state.

## M-112 Q3 HR exact-main v4 admission and consumer canary (2026-10-21)

- [x] PR [#1243](https://github.com/edithatogo/global-medicines-atlas/pull/1243) merged by squash at exact main commit `0f95edc35778b848072602c4aed5c59d6c9564a6` after all required checks passed. The PR pins the merged evidence commit for reproducible Q3 HR contract regeneration.
- [x] Exact-main hosted workflow [39444235017](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39444235017) passed the Q3 HR contract verification, v4.1 admission, and bounded `FederatedReader` consumer canary. It verified remote and consumer-stream digest matches, zero reader-cache bytes after read/close, and no public dataset mutation, source-value inclusion, or retained source bytes. Its metadata-only receipt is `quality/qualifications/australian-m112-v4-july2016-admission-qualification-20261021-39444235017.json` (SHA-256 `81497c806bd307688e11113e25160de2afbf5164579a877bf5b4d00bc70eab9e`). Native workbook schema remains unqualified.
- [x] Reconcile the current role qualification to seven exact admitted objects and seven passed consumer canaries, preserving the approved 1,759-object denominator and recording 1,752 remaining deferrals. The role report SHA-256 is `d57fbdb0d1803e52593c4ffe19b0286cf60ea0ab1a036ad19f4e81ff630d790d`; current rights reconciliation SHA-256 is `22fd38ddc616c85743ef71898bfaefebcf983dfb868851b7f1dc24d93a3a6400`.
- [x] Refresh the current rights-release preflight as `quality/qualifications/australian-m112-rights-release-preflight-20261021-5.json`, preserving revision 20261021-4 byte-for-byte as its predecessor. The exact-main workflow completed at `2026-10-20T14:59:44Z`; the current reconciliation uses that actual receipt time, not local midnight labeled UTC.
- [x] Pin the Q3 HR receipt to dataset revision `dee9a5b0580dfe394474dc26b372559462e157e7` in current-rights reconciliation and reject receipts that change admission and canary revisions together.
- [x] Validate the updated qualification with 58 focused contract/admission, role, current-rights, and preflight tests; Ruff, formatting, and `git diff --check` pass. Do not count this raw-B2 reader canary as native schema qualification or relationship calibration.

## M-112 current qualification readback (2026-10-21)

The latest preflight binds the current rights reconciliation and role report:
all 1,759 frozen objects have resolved rights, seven exact objects are admitted
and canaried, and 1,752 remain deferred. The July HR workbook reader canary does
not itself qualify native layout or relationship semantics; separate physical
layout evidence now qualifies the exact pinned workbook structure only. No
source or dataset was added and no external publication was performed. Current receipts:
`quality/qualifications/australian-m112-rights-release-preflight-20261021-7.json`,
`quality/qualifications/australian-m112-current-rights-reconciliation-20261021.json`,
and `quality/qualifications/australian-m112-v4-contract-role-evidence-qualification-20261020.json`.
The latest local candidate-role refresh is
`quality/qualifications/australian-m112-v4-contract-role-evidence-qualification-20261021.json`
(SHA-256 `67fb4cd0ccf3073fd472c3b5677b4b6452b55047fff0791a3720eb14914369dd`);
it retains seven admissions, seven canaries, and 1,752 deferrals. The bound
preflight still references the 20261020 role-report input. This refresh does
not itself perform the pending Q1 HR admission or canary.

## M-112 lineage and next bounded v4 cohort (2026-10-21)

- [x] Bind the July 2025 MBS XML (`db873768…11a556`, 8,194,522 bytes) and
  July 2024 P7 workbook (`2f1cbc2d…e27b8`, 87,727 bytes) to their existing
  receipt, acquisition, external-reference B2 manifest, and landed unreviewed
  admission. Their lineage reports preserve the approved inventory revision
  and path membership. P7's archive retrieval lineage does not establish its
  original source-origin acquisition or qualify workbook date semantics.
- [x] Qualify the next bounded cohort from the frozen inventory. The v4 role
  report binds seven exact objects, eligibility, admissions, and passed
  `FederatedReader` consumer canaries; seven remain admitted and canaried while
  1,752 objects remain deferred. The exact Q1 HR workbook's physical layout is
  qualified by the separate 2026-10-21 layout report; native field/formula
  semantics and relationship semantics remain unqualified.
- [x] Reconcile the current evidence without changing inventory membership,
  adding sources, mutating the public dataset, or publishing. The reviewed
  lineage overlay reports 22 complete raw B1/B2 lineages, 118 exact raw
  digest/path joins (119 including the separately identified same-content
  alias), and zero raw/projection objects without direct or alias SHA-256
  evidence.
- [x] Record the bounded completion in this track's append-only evidence
  ledger under `m112_mbs_lineage_and_next_bounded_cohort`.

## M-110 bounded MBS candidate content screen (2026-10-21)

- [x] Re-read the six exact, already-authorized July 2025 MBS v4 candidate
  Parquet objects at immutable revision `42d73b6facac016f14a335d36d83f1a3b630add8`,
  verify each byte count and SHA-256, and screen all 35,934 rows in memory.
  The bounded sensitive-field-name, email-like-value, and exact-digest screen
  found no patterns across 1,040,085 bytes. The aggregate-only receipt is
  `quality/qualifications/australian-mbs-v4-bounded-content-screen-20261021.json`
  (SHA-256 `83ae8b29ad197495c6cb929165bf2560eaaf22f13ffbb8c7410f8a26ce2d6e5e`).
- [x] Complete the bounded content screen and classify detected indicators
  across the six exact July 2025 MBS v4 candidate tables and six exact PBS
  utilisation objects. The current disposition reports 35,934 screened MBS
  rows, 1,314,870 ATC-shaped PBS values, 136 terminology-marker occurrences,
  zero UMLS-CUI matches, and zero email-like values; all observed indicators
  have field/context classification. Receipt:
  `quality/qualifications/australian-restricted-content-screen-disposition-20261021.json`
  (SHA-256 `81fc11f9d4b1a07de3ff7ebbc3d5bf444b6eaabeed0acfc9fed794db53c3d184`).
- [ ] Retain the residual boundary: the configured detectors are not
  exhaustive, ATC membership is unverified, and the rights instruments were
  not independently reviewed. This closes the bounded screen only; it does not
  clear broader restricted content or authorize release.
- [ ] Calibrate the actual matcher on representative, human-adjudicated,
  case-disjoint held-out labels from the existing source scope. The available
  400/400 generated matcher cases are synthetic-only and produce poor holdout
  calibration; no confidence or production threshold is selected.

## M-112 next bounded cohort preparation (2026-10-21)

- [x] Confirm the two exact July 2026 MBS Basic Service Description sidecars
  already have reviewed B1/B2 bindings. The reviewed lineage overlay binds the
  CSV (`07563bb…3eb5b6`, 135,983 bytes) and XML (`b71f1f…be9f4a3`, 615,386
  bytes) to their source receipts, acquisitions, external-reference B2
  manifests, and landed unreviewed admissions. This does not admit either
  object or qualify its source semantics.
- [x] Replay the next eligible exact object, the Q1 2016 HR workbook, through
  hosted run [39533443472](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39533443472)
  on exact `main` `de76083a0da67414c803c7a74de00162fe5dfbad`. Anonymous digest
  and byte-count verification passed for SHA-256
  `d44522cbd1847e73ee69cb5374c207296133254cd82be61e751f78db1a456d4d`
  (21,966,140 bytes); the workflow read no source values and removed its
  temporary bytes. The candidate-only receipt is
  `quality/qualifications/australian-m112-v3-replay-execution-20261021-39533443472.json`.
- [x] Bind that replay and cleanup evidence in successor manifest
  `quality/qualifications/australian-m112-v3-replay-readbacks-20261021.json`
  and role qualification
  `quality/qualifications/australian-m112-v4-contract-role-evidence-qualification-20261021.json`.
  V3 replay candidates rise from seven to eight of 16; admission remains
  seven, canaries seven, and 1,752 objects remain deferred.
- [x] Add exact Q1 HR identity support to the v4 raw-B2 contract builder and
  consumer-canary target set. The contract construction test verifies its
  pinned identity and pending-consumer state. This creates no admission or
  canary. The workbook's physical layout is qualified separately; native field
  semantics and formulas remain unqualified.
- [~] Complete exact-head v4 admission and consumer canary for this candidate
  after the support changes and candidate contract are available on `main`.
  The row remains open until hosted admission and canary readback are recorded.


## M-110 PBS utilisation identifier-shape screen (2026-10-21)

- [x] Re-screen all six exact, already-authorized PBS utilisation objects at
  immutable revision `9f1d53cd50eea251b326da42a96f3ac72ebce97a` in memory.
  Original byte counts and SHA-256 digests matched the pinned lineage for all
  191,047,619 bytes. The aggregate-only qualification is
  `quality/qualifications/australian-pbs-utilisation-identifier-shape-screen-20261021.json`
  (SHA-256 `fa8b25d1bd312d097b9f72cf97e418af61e4aa33f7b4c55a40a7dcad20cafc71`).
  The scan found 1,314,870 ATC-shaped strings, 928,410 six-to-eighteen-digit
  numeric candidates, and 136 explicit terminology markers; the exact UMLS CUI
  text pattern occurred zero times. No source values or files were retained.
- [ ] Complete the vocabulary-membership review and determine excluded versus
  cleared fields. The pattern counts are candidate indicators: numeric or
  ATC-shaped strings cannot be assigned to a licensed vocabulary from shape
  alone, and the existing approved scope contains no complete vocabulary
  dictionary or source-owner field contract. The maintainer's exact six-object
  rights attestation includes all vocabulary, but the instrument was not
  independently reviewed. Full-content classification remains open; this scan
  itself authorizes no admission or release.


## M-110 PBS field-level pattern localization (2026-10-21)

- [x] Attribute the previously observed pattern totals to file and column
  positions in a second in-memory pass over the same six pinned PBS objects.
  Forty-one field positions contained at least one pattern; the summary
  workbook's column position 2 contains ATC-shaped strings across five sheets,
  the item-drug map contains ATC-shaped strings at column position 3, the two
  DOS CSVs contain numeric candidates in seven columns each, and the expenditure
  workbooks contain explicit terminology-marker text. The aggregate report
  stores column positions and opaque label hashes, not labels or values:
  `quality/qualifications/australian-pbs-utilisation-field-pattern-screen-20261021.json`.
- [ ] Human/source-contract review must map these positions to exact fields and
  determine vocabulary membership and rights disposition. Opaque label hashes
  cannot substitute for field meaning. The existing exact six-object rights
  attestation covers all contents, including vocabulary, with the instrument
  not independently reviewed; no admission or publication follows.


## M-112 Q1 HR local role binding (2026-10-21)

- [x] Build and validate the exact v4.1 raw-B2 contract for the replayed Q1
  2016 HR object. The canonical contract is
  `quality/qualifications/australian-m112-v4-demographics-q1-marchhr-raw-b2-contract.json`
  (SHA-256 `5a8f97b0e36ad1e90110166e3fd66fda6ee7f12fd572232c5ba3cb0e8584d9a5`);
  it binds the pinned 21,966,140-byte object and its exact digest, source,
  acquisition and lineage roles. Schema and semantic checks pass. Native
  physical workbook layout is qualified by the exact-object layout report.
  Workbook metadata qualifies the processing-month basis, and the formula/cache
  comparison qualifies text-literal storage behavior. Age category meaning,
  `Benefits ($)` meaning, and a typed transform remain unqualified.
- [~] Complete anonymous receipt closure and exact-main admission/canary. The
  local closure attempt found that the Q1 replay receipt URL at pinned main
  `de76083a0da67414c803c7a74de00162fe5dfbad` returns HTTP 404. The contract is
  now bound to local evidence commit `de77e8e2b7f88994c1b99919c475d085fc9b39a7`,
  which contains that receipt, but this commit is not publicly available while
  the no-push/no-PR rule is active. Admission and canary remain 7 each; the
  1,752 deferrals and 1,759 denominator are unchanged.


## M-112 Q1 HR physical workbook layout qualification (2026-10-21)

- [x] Bind the native physical layout of the exact Q1 2016 HR workbook to its
  replayed source digest and byte count. The in-memory read verified the exact
  21,966,140-byte object, two sheets, primary sheet `MBS Demographics 2016
  Qtr1` with declared range `A1:H545077`, and a separate `Metadata` sheet. Its
  primary header row is row 3 with eight fields. No source records or values
  were emitted or retained. The aggregate inventory is
  `quality/qualifications/australian-mbs-demographics-q1hr-workbook-layout-candidate-20261021.json`.
- [x] Compare header shape with the already-reviewed Q1 demographics CSV schema
  in the existing inventory. The workbook has four distinct header labels
  (`Month`, `Item_Number`, `Age_Range`, `Benefits ($)`) versus the CSV schema
  (`Month of Processing`, `Item Number`, `Age Range`, `Benefit`). This qualifies
  a physical layout difference; it does not map those fields or assert semantic
  equivalence. The workbook contains 171,477 formula cells; formulas were not
  evaluated.
- [x] Qualify the source-reported month interpretation and stored formula
  behavior. The metadata sheet defines `Month` by service processing date
  rather than service date; the formula/cache comparison finds every observed
  `Age_Range` output is a text literal equal to its cached string. The reports
  are `australian-mbs-demographics-q1hr-metadata-semantics-20261021.json`
  (SHA-256 `927269591afa38f5393615510a0ae5dc8ce8a6b99040759de92f7bdeeb465bd5`)
  and `australian-mbs-demographics-q1hr-formula-literal-analysis-20261021.json`
  (SHA-256 `f324ae679840bd57fb7e7d566f9a18fdf7a90a4614289cce865b2086be97fa3e`).
- [ ] Resolve `Age_Range` category meaning, `Benefits ($)` calculation,
  unmatched rows, and any source-era mapping before a loss-aware typed
  projection. These reports do not establish CSV equivalence or a valid
  transformation. Exact-main admission and the reader canary remain separately
  open.


## M-112 Q1 HR formula and existing-CSV comparison (2026-10-21)

- [x] Verify both existing Q1 objects at the same pinned revision and compare
  workbook formula structure without emitting formula text or cell values. The
  workbook contains 171,477 formula cells, all in `Age_Range`; 171,346 have
  formula text with one normalized syntax shape, and 131 shared-formula cells
  have no local formula text. No formula results were evaluated. Aggregate
  profile: `quality/qualifications/australian-mbs-demographics-q1hr-formula-syntax-profile-20261021.json`
  (SHA-256 `01034f8a4d7f341a342c09f7591262ff13563ec492fea35294d9c83c9200a556`).
- [x] Compare workbook values to the already inventoried Q1 CSV in memory, with
  no row values retained or emitted. Both objects passed their pinned digest
  and byte-count checks. The workbook has 545,074 parsed data rows versus
  545,070 in the CSV; row-order comparison and order-independent full-row
  comparison found zero exact full-row matches. The workbook `Age_Range`
  frequencies had no exact values in common with the CSV; `Benefits ($)` also
  differs substantially under exact numeric canonicalization. Aggregate
  reports: `quality/qualifications/australian-mbs-demographics-q1hr-existing-csv-comparison-20261021.json`
  (SHA-256 `5318d9328e72d64bb12a3157b3a59f7c16edd59cae22a7de5e6540e707684446`)
  and `quality/qualifications/australian-mbs-demographics-q1hr-existing-csv-multiset-comparison-20261021.json`
  (SHA-256 `dc3ac67bb87954227e28775546a26c5a75200c06b500f50a913f5516d35bc2eb`).
- [ ] Resolve field mapping, formula authoring and cached-result meaning, four
  additional workbook rows, and source-era semantics before defining a
  loss-aware typed projection. The comparisons do not establish equivalence or
  explain differences. No admission, canary, Silver projection, or public
  mutation followed; current M-112 counts remain 7 admissions, 7 canaries,
  and 1,752 deferred of 1,759.

- [x] Profile the exact workbook's formula-expression and cached-output
  relationship without retaining or emitting source values. The read-only
  workbook view exposes 171,477 text-literal formulas in `Age_Range`; each of
  the 171,477 cached outputs is a string matching its decoded literal, with no
  formula references or operators. The raw XML profile separately records
  171,346 explicit formula texts and 131 shared-formula cells without local
  text; the library reconstructs those expressions in its workbook view. This
  resolves calculation behavior only. It does not establish the labels' field
  meaning, temporal scope, the four extra workbook rows, or equivalence with
  the CSV, whose `Age Range` values have zero exact frequency overlap. Receipt:
  `quality/qualifications/australian-mbs-demographics-q1hr-formula-literal-analysis-20261021.json`
  (SHA-256 `f324ae679840bd57fb7e7d566f9a18fdf7a90a4614289cce865b2086be97fa3e`).

- [x] Read the metadata sheet of the same exact Q1 HR workbook in memory and
  qualify the source's reporting-period context. It defines `Month` by service
  processing date rather than service date, describes the eligible registered-
  provider Medicare-benefit population and exclusions, states that service
  totals net later-day adjustments, and defines the month-end enrolled-person
  denominator for per-capita measures. It also describes MBS group statistics
  by age range and gender. This source-era evidence does not resolve the
  `Benefits ($)` calculation, exact age-range categories, or equivalence to the
  existing CSV. No source bytes or row values were retained. Receipt:
  `quality/qualifications/australian-mbs-demographics-q1hr-metadata-semantics-20261021.json`
  (SHA-256 `927269591afa38f5393615510a0ae5dc8ce8a6b99040759de92f7bdeeb465bd5`).
- [x] Test whether Unicode, case, whitespace, dash, and numeric canonicalization
  explain the workbook/CSV age-label and record-key differences. Both exact
  pinned objects were reverified in memory; normalized age-label sets still
  had zero overlap and no full record keys joined. This rejects a simple
  formatting-only crosswalk while retaining the semantic mapping as unresolved.
  No source labels or values were emitted or retained. Receipt:
  `quality/qualifications/australian-mbs-demographics-q1hr-label-normalization-20261021.json`
  (SHA-256 `6224cd9c6b479b6d4c5a1ecec43c2e10290b7aab0c363209cd8e8db0d892aaad`).


## M-110 PBS field-header mapping follow-up (2026-10-21)

- [x] Map the existing field-pattern counts to exact headers in the three
  already-screened CSVs. The DOS numeric candidates occur in month, count,
  contribution, cost, and markup fields; ATC-shaped values occur in
  `ATC5_Code`. Resolve `ATC5_CODE` in the five annual summary sheets that hold
  1,304,100 ATC-shaped strings. These are exact field labels, not vocabulary
  rights or relationship qualification. The value-free receipts are
  `quality/qualifications/australian-pbs-utilisation-pattern-field-header-map-20261021.json`
  (SHA-256 `1e6c2e254af3704ab422cfc4a495648441dae9a533907bca4097cfab15cb33a4`) and
  `quality/qualifications/australian-pbs-utilisation-summary-workbook-header-resolution-20261021.json`
  (SHA-256 `f717d2bda385a1dc7080b3493de9430998172146c03b5f8252f21e6f61ae71dd`).
- [x] Classify the observed marker content in the two expenditure workbooks:
  all 136 detected occurrences are contextual or label text, and the separate
  ATC-shaped scan found zero cells in those files. See the exact pinned
  aggregate receipt below. This does not establish ATC vocabulary membership,
  exhaustive detection, independent rights review, admission, or publication.


## M-110 PBS six-object privacy-pattern scan (2026-10-21)

- [x] Run a bounded privacy-pattern scan over all six exact PBS utilisation
  objects at the pinned revision (191,047,619 bytes); each digest and size
  matched. No email-shaped values were found. Six sensitive-looking DOS CSV
  header hits resolve to `PATIENT_CAT`, `PATIENT_CONTRIB`, and
  `PATIENT_NET_CONTRIB`, aggregate category and contribution measures. The
  value-free receipts are `quality/qualifications/australian-pbs-utilisation-private-pattern-screen-20261021.json` (SHA-256 `43c1c2a80adb86bb215dbd2340645fee1ce20d4c17a2a0545c9134c2d4c86f33`) and
  `quality/qualifications/australian-pbs-dos-sensitive-header-context-20261021.json` (SHA-256 `a5046bae17eb24a63e286f0c083ca0a2269c997bc2918b7fe3bf97324ee40654`).
- [ ] Review the workbook narrative-token hits and restricted terminology. This
  bounded detector is not exhaustive and makes no privacy, rights, or vocabulary
  clearance claim. The current aggregate screen still does not classify whether
  these narrative tokens represent individual-level content.


## M-112 current role-report reference reconciliation (2026-10-21)

- [x] Verify the latest candidate-role qualification at
  `quality/qualifications/australian-m112-v4-contract-role-evidence-qualification-20261021.json`
  (SHA-256 `4c73d269e8d69ebea185cf7c62909641147e035fd7c784a46b94bd415fd03f6c`).
  Its readback remains seven v4 admissions, seven consumer canaries, and 1,752
  deferred objects of 1,759.
- [x] Reconcile the registry and current-readback sections in the Bronze,
  federation, Platinum, and Australian benefits plans to identify the newer
  candidate-role report while preserving the report actually bound by preflight
  snapshot 20261021-7. Dated earlier zero-count entries remain historical.
- [x] Preserve the pending Q1 HR admission/canary and all other gates; this
  documentation update does not change inventory, rights, admission, canaries,
  publication, or release state.


## M-110 expenditure-workbook marker context (2026-10-21)

- [x] Re-read the two exact expenditure workbooks at pinned revision
  `9f1d53cd50eea251b326da42a96f3ac72ebce97a`, verifying their original byte
  counts and SHA-256 digests before parsing XLSX text cells in memory.
- [x] Classify all 136 detected ATC marker cells across the two reports as
  contextual/label text; the separate ATC-shaped identifier scan found zero
  cells. The aggregate-only receipt is
  `quality/qualifications/australian-pbs-expenditure-marker-context-screen-20261021.json`
  (SHA-256 `150c92ae5a2e488243b3bb324651ba946593246b548eb17c25694c7f0de149a1`).
  No source values were emitted or persisted locally.
- [x] The focused parser tests passed (2); the report regenerated and passed
  `--check`, Python compilation, line-length review, and `git diff --check`.
  Ruff was unavailable because the locked typing-group tool bootstrap stalled
  while downloading its runtime; no lint pass is claimed.
- [ ] Complete restricted-content classification across all six PBS objects
  and the MBS candidate scope. This marker-context screen does not establish
  vocabulary rights, rights clearance, admission, or release.
- [ ] Calibrate the actual matcher on representative reviewed cross-jurisdiction
  labels. The retained scope still lacks non-synthetic medicine labels for that
  calibration; synthetic graph parity remains insufficient.


## M-112 Q1 HR candidate receipt recovery (2026-10-21)

- [x] Recover the exact replay receipt from unexpired GitHub Actions artifact
  `australian-m112-v3-replay-39533443472-1`; verify its SHA-256
  `c81490ada740101e0aaae38846409aa216d2bf2d69b8a74f94a35812c71858e0` matches
  the locally committed receipt. The run is successful and explicitly records
  no admission, consumer canary, source-value read, or public dataset mutation.
- [x] Regenerate the Q1 HR candidate v4.1 contract with its receipt and B1/B2
  inputs pinned to candidate evidence commit
  `0dbc1d7def66b49c6df5372ca694d78bc7b5008f`; schema and semantic checks pass.
- [ ] Re-run exact remote receipt closure and the consumer canary after the
  candidate evidence commit becomes available on the public repository. Until
  then this contract remains local candidate evidence; source-native workbook
  layout remains unqualified.

## M-112 July BSD sidecar lineage current readback (2026-10-21)

- [x] Reconcile the two exact July BSD sidecars against the retained lineage
  overlay and its pinned metadata readbacks. Both exact paths now bind their
  source receipt, acquisition, external-reference B2 manifest, and landed
  unreviewed admission at the proper content digest and byte count. The source
  receipt and B2 metadata revision is `42d73b6facac016f14a335d36d83f1a3b630add8`;
  the current dataset content revision is `40891976f77ee5e7688edceed25c9ac98a77547e`.
  The metadata-only receipt is
  `quality/qualifications/australian-m112-july-bsd-sidecar-lineage-current-readback-20261021.json`
  (SHA-256 `f2cad69df7473d56a888bbb7616855e09d5116d3036de71c890798ba987639a2`).
- [x] Preserve the earlier rights-preflight snapshot and clarify that its
  statement about two incomplete sidecar bindings is superseded for lineage
  only. Exact rights attestation, processing admission, consumer canary, and
  release remain separate gates; the current 1,759 denominator is unchanged.
- [~] Continue the bounded v4 cohort from the Q1 HR candidate contract. Local
  contract qualification and replay receipt exist, but the exact-main Q1 HR
  admission and canary have not run. The latest hosted canary remains the
  seven-object readback; the candidate evidence commit is not on public main.
- [x] Revalidate the existing exact-object Q1 HR raw-B2 contract against the
  current v4.1 schema and federation semantics with the read-only `--check`
  path. It passes. The check does not close remote receipt roles or qualify
  admission. The contract builder still has no durable merged evidence commit
  binding for this object, and exact-main admission/canary remain open.
- [x] Rebuild the local Q1 HR contract with all 12 schema-defined receipt roles
  bound to candidate evidence commit `c857e3c42cd6ffa7fa9d21d599613c1169ce1f9e`.
  Seven Git-hosted role payloads match their exact local Git commit digests.
  Five externally hosted receipts remain un-fetched, so remote closure and
  eligibility are not established. The exact-object contract still passes
  local schema/semantic validation. Contract SHA-256:
  `5a8f97b0e36ad1e90110166e3fd66fda6ee7f12fd572232c5ba3cb0e8584d9a5`.
- [ ] Attempt exact receipt closure with the read-only `--check --verify`
  path. Closure stops at HTTP 404 for the v3 replay receipt pinned to the local
  candidate commit. No source bytes were read and no admission or canary was
  produced. Public `main` remains `de76083a0da67414c803c7a74de00162fe5dfbad`;
  a durable accessible evidence commit is still required before retrying.

## M-112 Q1 HR benefit-column diagnostic (2026-10-21)

- [x] Compare the pinned workbook `Benefits ($)` cells with the existing CSV
  `Benefit` cells in memory after rechecking both exact object digests and byte
  counts. The value-free report records 545,066 numeric pairs; 19,904 are exact
  numeric matches, and none of the tested fixed scales explains the aggregate
  mismatch. The workbook contains 545,074 data rows while the CSV contains
  545,070. No values were emitted or retained and no Silver projection was
  created. The script SHA-256 is
  `817284f6fb0561e4f5b55c945b25a8c3a1001224afd0ce05d153b1bdf19af588`;
  receipt `quality/qualifications/australian-mbs-demographics-q1hr-benefit-scale-comparison-20261021.json`
  SHA-256 is `465c655dd0bcad42ff31d94826ef857b32de4f491f851ed47c7347687e16c8b5`.
- [ ] Resolve the meaning/calculation of `Benefits ($)`, the age-category
  mapping, and the four-row count difference from source-supported evidence.
  This diagnostic rules out only the tested fixed-scale relationships; it does
  not establish row equivalence, semantic non-equivalence, or a valid transform.
- [ ] Build and qualify a loss-aware Silver projection only after those source
  semantics are established. Exact-main admission and its consumer canary also
  remain gated on durable accessible receipt evidence.

## M-112 Q1 HR age-context candidate comparison (2026-10-21)

- [x] Compare the age labels using only six shared context fields from the
  same two exact objects, after digest and byte-count verification. The
  aggregate-only report finds 11 one-to-one candidate category pairs supported
  by 360,235 unique row contexts; 75,767 repeated/ambiguous contexts are
  excluded. All 436,002 CSV context keys match the workbook with identical
  multiplicities; the workbook has three additional context keys and four
  unmatched row occurrences. This localizes the count delta but does not explain
  those records. The files contain 13 and 11 unique age labels; labels are
  represented only by digests. No values or rows were emitted or retained.
  The initial fail-closed parser recognized none of the 11 candidate pairs.
  Value-free probes established that the nine CSV ranges have balanced outer
  double quotes; removing only that wrapper raised the equal-bound count to 9.
  A further masked probe identified an explicit `>=` lower-bound form and one
  nonnumeric pair. The parser now handles the lower-bound form. The latest
  report counts 10 pairs with equal explicit numeric bounds and one remaining
  nonnumeric pair; after quote normalization, all 11 pairs have equal literal
  labels. This is candidate syntax/literal evidence only. It does not establish
  source-defined age meaning, equivalence of the nonnumeric category, explain
  the four unmatched workbook rows, or authorize a Silver transform. Focused
  tests (18), Ruff, formatting, and report regeneration passed. Current script
  SHA-256: `385acef2c9883610a0ccb8b1fc0fe3e485dc1897c7ec7f89f2e24395251c94f9`;
  report SHA-256:
  `0aecb12f9c1ff28e9529df9509c9898abd5b782e78f5ae73833c05fba4a560a6`.
- [ ] Obtain source-supported category definitions and review whether the
  candidate pairs are semantically equivalent. Shared context and one-to-one
  counts do not establish age-band meaning, row equivalence, or authorization
  to transform Silver data. Explain the four workbook-only row occurrences and
  resolve the `Benefits ($)` calculation before projection qualification.

## M-110 restricted-content screen reconciliation (2026-10-21)

- [x] Reconcile the value-free screens over all six exact PBS utilisation
  objects and all six July 2025 MBS v4 candidate tables. The PBS findings
  localize ATC-shaped values to the existing `ATC5_Code` and `ATC5_CODE`
  fields, numeric shapes to existing period/count/contribution/cost fields,
  and 136 expenditure-workbook markers to contextual or label text. The exact
  UMLS CUI text pattern has zero matches. The MBS bounded screen reports no
  configured field-name, email-like, or exact-digest patterns over 35,934
  candidate rows. No source values were emitted. Consolidated receipt:
  `quality/qualifications/australian-restricted-content-screen-reconciliation-20261021.json`
  (SHA-256 `af14e16f255e4686f09ab25180c62139476edbd0aaf3dd5367a2f39c5e166e5b`).
- [ ] Verify ATC membership against an authoritative reference already in the
  approved inventory. No such dictionary is present in the retained source
  scope. The exact six-object PBS and six-table MBS rights attestations cover
  their stated scopes, but the instruments were not independently reviewed;
  the configured scans are not exhaustive. No new vocabulary source is added,
  and no admission, publication, or release follows from this reconciliation.

- [x] Classify every content indicator reported by the bounded screens against
  the exact field-header evidence and bind both six-object rights attestations
  by path, digest and byte count. The 1,314,870 ATC-shaped occurrences map to
  `ATC5_CODE`/`ATC5_Code`; 928,410 numeric candidates map to existing period,
  prescription, contribution, cost and markup fields; 136 marker occurrences
  are contextual/label text; exact UMLS CUI and email-like patterns are zero.
  The 35,934 MBS candidate rows have no configured-screen findings. The exact
  attestations cover those contents; the instruments remain unreviewed. This
  closes disposition of observed indicators only, not exhaustive detection or
  independent vocabulary membership. Receipt:
  `quality/qualifications/australian-restricted-content-screen-disposition-20261021.json`
  (SHA-256 `81fc11f9d4b1a07de3ff7ebbc3d5bf444b6eaabeed0acfc9fed794db53c3d184`).
## M-110 PBS ATC-shaped field internal consistency (2026-10-21)

- [x] Compare the two already screened and rights-attested PBS fields at the
  pinned revision without emitting or retaining field values. All 980 distinct
  ATC-shaped values in the five summary sheets are present in `ATC5_Code` of
  the item-drug map; the map has 384 additional distinct ATC-shaped values.
  The aggregate report records only counts and digests:
  `quality/qualifications/australian-pbs-utilisation-atc-internal-consistency-20261021.json`
  (SHA-256 `cd041b481f14c18e38e19d89d4178c4f430f89371c2340ddb71996becfa13688`).
  Script SHA-256:
  `2001f783a4350091768adb6a60a96586b34fbabf1fbbb551c3a18a17cd96d731`.
- [ ] Explain the 384 item-map-only values and verify vocabulary membership
  against an authoritative ATC reference already in the approved inventory.
  The repository contains no such dictionary. Cross-file agreement is only
  internal consistency, not vocabulary membership, licensing, or matcher
  calibration. The PBS permission instrument remains maintainer-attested and
  independently unreviewed.

- [ ] Calibrate the actual cross-jurisdiction matcher. The current retained
  source scope contains no real cross-jurisdiction medicine-pair labels. A
  current-head inventory recount at `a038b2667330f668bbe1557297deaf6f1140f338`
  found 18 B1 receipts, all for Australian MBS/PBS sources. The accepted
  same-record MBS edges do not label medicine identity. Calibration remains
  unmeasurable from this frozen source set; do not select a threshold or add
  sources. Updated scope report:
  `quality/qualifications/frontier-real-matcher-label-availability-20261021.json`
  (SHA-256 `8eb8d7ae6bc2b83ae11aec3fd9210b8cd52ee772b9c460aeb3c96d137c7e7973`).

## M-112 Q1 HR physical-layout role binding (2026-10-21)

- [x] Bind the exact Q1 2016 HR workbook layout qualification to its matching
  frozen candidate object in the v4 role report. The report records the
  qualified physical structure while leaving source-field semantics, formula
  semantics, the source contract role, admission, and consumer canary
  unqualified. The cohort remains seven admitted and canaried, with 1,752
  objects deferred. The role report is
  `quality/qualifications/australian-m112-v4-contract-role-evidence-qualification-20261021.json`;
  its physical-layout input is
  `quality/qualifications/australian-mbs-demographics-q1hr-workbook-layout-candidate-20261021.json`.
- [x] Verify exact object identity and fail-closed behavior if the evidence
  scope claims source semantics or admission. Fifteen focused tests, `ty`,
  BasedPyright, Ruff, formatting, role-report `--check`, and `git diff --check`
  passed.
- [x] Close the exact raw-B2 contract roles and hosted receipt closure after
  PR #1247 made the pinned evidence revision accessible. Run 39575404598 at
  main b6e8a8e4f6d633dfea0056104b62972a669c1b3e passed on 2026-10-21 at
  09:14:48 UTC. The Q1 HR receipt is retained in the current reconciliation;
  its byte and streamed digests match and cache bytes after close are zero.
  Unresolved field semantics continue to gate harmonization independently.


## Authorized repository workflow and current preflight (2026-10-21)

- [x] Apply the maintainer's instruction to preserve the absolute email and
  messaging exclusion while permitting authorized technical commits, pushes,
  PR metadata, CI/workflow execution, and green-check merges. Standalone
  comments, outreach, invitations, and requests to send remain prohibited.
  Earlier local-only/no-push notes above record the superseded policy.
- [x] Preserve preflight 20261021-11 unchanged and bind the current plan and
  tests in successor
  `quality/qualifications/australian-m112-rights-release-preflight-20261021-12.json`.
  The first focused run found two stale input digests in the previous snapshot;
  its result was 64 passed and one failed. This refresh changes no rights,
  inventory membership, admission, or canary count: 7/7 and 1,752 deferred.
- [x] Publish the prepared candidate evidence through a technical PR, require
  protected checks before merge, and run the Q1 HR exact-main verification
  and reader canary. Its raw-B2 contract preserves uninterpreted immutable
  bytes; unresolved age-category and benefit semantics continue to gate
  Silver transformation independently.

- [x] Repair review findings before publishing: assign the three new test
  modules to the governed unit inventory; use the shared DTD/entity-rejecting
  XML parser for the PBS expenditure screen; bound source download bytes, ZIP
  expansion, XML members, and shared-string indexes. Negative tests cover
  identity drift, XML DTDs, and expansion bounds. The two exact pinned PBS
  reports still reproduce unchanged with the bounded parser. Routine checks
  and targeted strict typing pass.
- [~] Run focused and broader affected tests, the pinned-toolchain full profile,
  and protected hosted checks against the frozen candidate branch before merge.

## PR 1247 check repairs (2026-10-21)

- [x] Remove one blank evidence-ledger line without changing any JSON record;
  correct malformed quoted age-label equality with a negative regression case.
- [x] Upgrade vulnerable certifi and transitive uv; preserve historical build
  reproducibility with the content-bound patched custom CA bundle. Qualify
  the temporary edgetest uv ceiling override against all three real environments.
- [x] Supply dependency-canary collection dependencies and reject failed or
  missing edgetest status reports even when its process returns zero.
- [x] Preserve preflight -12 unchanged; successor
  `quality/qualifications/australian-m112-rights-release-preflight-20261021-13.json`
  binds the repaired inputs. Counts remain 7 admissions, 7 canaries, 1,752 deferred.
- [x] Require the repaired-head checks and exact main-only Q1 HR canary. PR
  #1247 merged with 40 passing checks and the Q1 HR run passed. The
  first local full attempt was interrupted for confirmed CI failures; no full
  pass is claimed for that attempt. Local receipt verification resolved all
  required remote roles and returned admitted_pending_consumer_canary; this
  is not a hosted admission or hosted canary.

## Eighth admission, Silver semantics and matcher continuation (2026-10-21)

- [x] Retain the exact Q1 HR hosted receipt from run 39575404598, merged main
  b6e8a8e4f6d633dfea0056104b62972a669c1b3e, completed 09:14:48 UTC. The
  role and rights reports now reconcile eight admissions and eight canaries
  over 1,759 frozen objects, with 1,751 deferred. Preflight -14 binds the
  current inputs and preserves -13 unchanged. No new admission was performed
  by this reconciliation; the retained hosted receipt is the evidence.
- [x] Join both exact Q1 objects using full source context plus normalized
  literal age labels. All 545,070 CSV rows have unique workbook counterparts;
  there are no repeated shared full keys and no unmatched CSV rows. The four
  workbook-only rows all have nonnumeric years; two have text in all fields
  and two have only a text year field. This is structural classification,
  not authority to delete or interpret those rows.
- [x] Test the benefit mismatch after correcting row alignment and excluding
  ambiguous keys. All 545,070 pairs are numeric; only 54,693 agree exactly or
  after rounding to two decimal places. A total of 490,365 differ by more than
  0.01. No tested fixed multiplier explains the result. The mismatch is not
  resolved by row order or numeric precision. Aggregate-only receipt:
  `quality/qualifications/australian-mbs-demographics-q1hr-context-measure-diagnostics-20261021.json`.
- [ ] Resolve the source-defined HR benefit measure and nonnumeric age category
  before harmonization. Preserve native labels and the HR benefit field as a
  distinct unresolved measure; do not substitute CSV values or infer payable
  benefit. No Silver projection or semantic-equivalence claim is created.
- [x] Recheck the unchanged 18-receipt, Australian-only retained label scope;
  rerun the actual matcher on the existing 400/400 generated controls. Record
  post-retrieval operating points, scope, input digests and missing real
  labels in
  `quality/qualifications/frontier-frozen-matcher-calibration-20261021.json`.
  The 0.65 control cutoff admits 200/200 generated negatives; 0.9 excludes
  them but misses 100/200 generated positives. These are synthetic controls,
  not real-source operating estimates. No source threshold is selected.
- [ ] Actual cross-jurisdiction medicine calibration remains blocked by zero
  eligible reviewed real pair labels in the frozen scope. The 5,989 reviewed
  same-record MBS edges do not supply those labels. No sources, outreach,
  confidence authority or public releases are added.
- [x] Review scope and negative controls: pin Q1 identity and exact hosted run,
  reject self-consistent identity drift, exclude repeated keys and non-finite
  measures, expose large differences, scope operating points to post-retrieval
  scored cases, and require re-review when retained calibration inputs drift.
- [x] Focused diagnostic and legacy checks passed (30), current preflight checks
  passed (8), the broader bounded contract/matcher selection passed (183),
  routine checks passed and strict typing returned zero errors or warnings.
  A separate wider selection reached local asynchronous timeouts and was
  interrupted with exit 2 after 196 passed and one timeout failure; it is
  not counted as a pass. No repeated local
  full profile is claimed: source-report reconciliation and offline diagnostics
  leave production matching and release/publication behavior unchanged.
- [~] Require complete protected CI on the final PR head before merging.
  Production matching behavior and
  release/publication gates are unchanged; this increment reconciles metadata
  and adds offline diagnostics.

## PR 1248 review corrections (2026-10-21)

- [x] Bind the exact 18-receipt path/digest tree to the independently checked
  original availability-audit revision a038b2667330f668bbe1557297deaf6f1140f338.
  A receipt replacement with unchanged source/jurisdiction counts now fails
  closed and requires renewed label review.
- [x] Make both diagnostic CLIs directly executable using the established
  package/direct-import pattern. Add an actual read-only --check entry point
  for matcher readiness and regression tests for direct execution.
- [x] Preserve published preflight -14 byte-for-byte and bind corrections in
  successor -15. Admission/canary totals remain 8/8 with 1,751 deferred.
- [x] Twenty initial focused review checks and 73 broader affected checks pass;
  strict typing has zero errors/warnings and routine checks pass. Direct CLI
  write/check consistency and read-only check behavior are covered.
- [~] Require fresh protected CI before resolving review threads and merging.
  No standalone review comment is sent.


## Source meaning resolution (2026-10-21)

- [x] Diagnose the exact retained Q1 workbook/CSV benefit discrepancy with
  full-key rounding and truncation controls; keep aggregate evidence only.
- [~] Identify the exact Q1 native nonnumeric data label as `Unknown`.
  Preserve it verbatim without numeric bounds. Its source definition, cause,
  relationship to suppression and CSV semantic equivalence remain unresolved.
  This local observation requires hosted requalification before promotion.
- [ ] Resolve P7 date and numeric conventions using the exact retained
  workbook and its source-era evidence; preserve formula/error states.
- [ ] Establish patient-count population, period and deduplication semantics
  wherever those measures are included. Do not substitute service counts or
  rounded population percentages for distinct patients.
- [ ] Run affected checks, review, protected CI and reconcile the evidence.

This increment uses the frozen existing sources and sends no outreach.


### Hosted source-meaning reproducibility

- [x] Implement aggregate-only Q1 unknown-age and rounding diagnostics with
  exact object identities and main Actions commit guards; synthetic focused
  checks pass. This creates no Silver promotion or benefit interpretation.
- [x] Diagnose PR #1249 unit failure as stale preflight input digests after
  the plan changed. Preserve preflight -15 and bind this increment in -16;
  rights, admission and canary conclusions remain unchanged.
- [~] Verify complete protected CI, merge the reviewed increment and execute
  the read-only main workflow; retain the exact hosted aggregate receipt.


### Exact hosted source-meaning readback (2026-10-21)

- [x] Merge PR #1249 as `6522e7959b2065214e77cd623dbb05c379217b57`
  after all 39 reported checks and 29 required checks passed.
- [x] Execute main workflow run `39590928303`; download the actual aggregate
  artifact and retain its exact bytes. It observes 58 native `Unknown` age
  labels and reproduces all 545,070 full-key numeric comparisons and all
  fourteen rounding/truncation counts. No Silver promotion follows.
- [ ] Resolve the five source-definition requirements in
  `quality/qualifications/silver-source-meaning-resolution-20261021-hosted.json`.
  Hosted diagnostics do not resolve the benefit calculation, unknown-age
  definition, P7 date/value conventions or included patient denominators.


## Approved bounded Silver completion (2026-10-21)

The maintainer authorizes field-level uncertainty treatments and completion of
MBS/PBS qualification and delivery within the existing frozen inventory. This
supersedes whole-layer blocking on missing meanings; it does not establish those
meanings or grant new rights, publication, clinical claims or outreach.

- [x] Implement interpreted/native-unresolved/unavailable field states and
  consumer guards; source/field identity must prevent unqualified pooling.
- [~] Preserve Q1 workbook/CSV measures independently and retain Unknown ages
  in native rows, totals and coverage with unresolved suppression semantics.
- [~] Carry P7 raw dates and numeric/formula/error evidence through typed
  outputs; block temporal claims without source-bound qualified dates.
- [x] Mark unsupported patient denominators/rates unavailable while retaining
  supported service counts independently.
- [ ] Finish MBS families and source eras in the frozen inventory.
- [ ] Finish PBS domain harmonisation with field-level unresolved outcomes.
- [ ] Qualify exact eligible outputs: coverage, identity, lineage, missing/error
  states, lossless decimals and deterministic Parquet rebuilds.
- [ ] Bind output digests to applicable rights/admission evidence; execute
  authorized restore and consumer canaries and complete protected CI.


### Q1 source-native Silver projection implementation (2026-10-21)

- [~] Preserve primary-table rows and all eight native field slots, source
  properties, per-object benefit identities, precision exceptions and native
  age groups. Bind the producer to existing B1 acquisition and B2 manifest
  identities; keep unsupported patient rates unavailable.
- [ ] Complete receipt-bound source-byte extraction and ancillary workbook
  metadata coverage. The primary-table producer alone does not qualify the
  complete workbook or prove source-to-output extraction parity.
- [ ] Qualify exact real-source outputs, independent Parquet restore and
  consumers; retain source meanings as unresolved where evidence is absent.
- [ ] Continue all remaining MBS/PBS families, source eras, exact output roles,
  rights/admission binding and delivery work in the approved goal.


### Q1 complete-source extraction follow-up (2026-10-21)

- [~] Implement receipt-bound CSV/workbook extraction with primary rows, ancillary
  cells, worksheet inventories and fully read ZIP-member fingerprints. Synthetic
  extraction checks pass; real-source parity and deterministic output writing
  remain pending.
- [~] Correct review finding on PR #1252: carry exact object identity into the
  generic benefit semantics so byte-identical path aliases remain distinct.
  Focused regression passes; successor protected CI and merge remain pending.

- [~] Build deterministic candidate primary/ancillary Parquet packages with
  transactional finalization, ZIP/sheet inventories and independent restore
  checks. Local synthetic tests pass; source parity, exact transform binding,
  hosted qualification and delivery remain pending.


### Protected Q1 native Silver qualification (2026-10-22)

- [~] Implement exact-main read-only qualification for the existing Q1 workbook
  and CSV: repeat deterministic package builds, independent source-field parity,
  Parquet restore and DuckDB count/uncertainty checks. Retain only aggregate
  output/manifest fingerprints; remove temporary derivatives on completion.
- [ ] Merge the reviewed qualifier and execute it on its exact main commit;
  retain the actual aggregate receipt before claiming real-source qualification.
- [ ] Continue all remaining frozen MBS/PBS families and exact-output
  rights/admission and federated consumer delivery after Q1 qualification.


### Existing quarterly demographic CSV cohort (2026-10-22)

- [~] Extend native candidate qualification to the three exact frozen Q1 March,
  Q2 May and Q3 July CSVs using retained structural/header receipts and exact
  B1/B2 identities. Preserve separate measure populations and unresolved age
  semantics; no cross-quarter benefit equivalence is inferred.
- [ ] Merge and execute protected exact-main per-object qualification, retain
  actual output digests and restore receipts, then bind applicable output
  admission/rights and authorized delivery.
- [ ] Continue workbook, historical ZIP, other MBS families and broader PBS
  domain/era qualification; the three-CSV cohort does not close those lanes.


### Registered exact-main qualification entry points (2026-10-22)

- [x] Merge native extraction/package PR #1253 as `9edd2a56` after 40
  checks, then qualifier PR #1256 as `db057e20` after 39 reported checks
  and complete required-check coverage. PR #1254 was superseded following
  a stale head and failed reopen; its corrected files are on main.
- [x] Retain the exact P7 current-main aggregate in PR #1257, merged as
  `de299e3e`: 13,742 cells, four formulas, two errors, 36 representability
  exceptions and 1,280 unqualified date cells. This is storage/profile proof;
  typed-value package restore and date meaning remain unqualified.
- [~] Expose the reviewed Q1-pair and quarterly-CSV native qualifiers through
  registered workflow 391616583, retaining the legacy diagnostics default,
  mutually exclusive modes, exact-main guards and aggregate-only artifacts.
  The separate new Q1 workflow is present on main but returned HTTP 404 from
  dispatch and is absent from the Actions registry; no source run is claimed.
- [ ] Complete protected CI, merge, dispatch native modes on exact main and
  retain actual source-to-output parity/restore receipts before qualification.

The interrupted local full profiles for commits `269a6e33` and `044a07c5`
no longer had live process handles after the intentional turn interruption.
Their logs lack terminal summaries; no full pass is claimed. A fresh full
profile applies to this changed workflow behavior after the code is frozen.


### Source-native MBS group CSV candidate (2026-10-22)

- [~] Preserve the separate July 2016 group CSV family: native group, subgroup,
  item, state and period strings, service counts, benefit tokens and complete
  header/record coverage. No age dimension or cross-era hierarchy equivalence.
- [~] Build deterministic candidate Parquet with independent Arrow CSV/native-
  field parity, typed-value/provenance checks and atomic finalization.
- [ ] Bind the exact retained group object (164,543 source records) to a hosted
  qualifier, execute on exact main and retain actual digests/restore evidence;
  complete applicable rights/admission and delivery independently.

PR #1258 merged as `ebd4e300` after all 40 reported checks passed. Exact-main
Q1 run `39627539043` is active and quarterly CSV run `39627746801` is queued;
source qualification remains pending their actual final artifacts.

### Q1 exact-source qualification readback and group hosted route (2026-10-22)

- [x] Retain the aggregate artifact from successful exact-main Q1 run
  `39627539043`: both source objects have complete primary-field parity,
  deterministic rebuild, independent Parquet restore and DuckDB checks.
  Workbook 545,074 rows, 58 literal Unknown ages and 76,287 lossless-decimal
  exceptions remain visible; CSV 545,070 rows. No benefit equivalence,
  patient-rate support, new rights conclusion or output admission follows.
- [~] Add the existing July group CSV qualifier to the registered workflow:
  exact B1/B2/frozen identity, 164,543-row denominator, repeat build,
  independent restore and bounded DuckDB checks; aggregate artifact only.
- [ ] Complete group increment review, full validation, protected CI and
  exact-main hosted execution. Quarterly run `39627746801` remains queued.
- [ ] Continue remaining MBS families and eras, PBS domain harmonisation,
  exact output rights/admission and consumer delivery within frozen scope.

### P7 typed candidate package and exact restore (2026-10-22)

- [~] Extend the existing P7 typed producer into a deterministic transactional
  `cells.parquet` package. Preserve every native cell and its header mapping,
  numeric text, formula/cache/error, source and receipt identity; date profile
  remains unselected and all interpretation states remain native_unresolved.
- [~] Extend the registered hosted workbook qualifier to build twice, compare
  exact package fingerprints and independently restore every native cell and
  typed field. Retain aggregate-only evidence and delete temporary packages.
- [x] Verify synthetic corruption, rehashed Parquet/schema changes, manifest
  drift, file-set/symlink/byte bounds, no overwrite and transactional failure.
  Seventy affected tests pass; package branch coverage is 93.68%; affected
  production typing has zero errors or warnings.
- [ ] Complete full validation, review and protected CI, merge, then execute
  the existing exact-main P7 workflow and retain its aggregate artifact.
- [ ] Continue all remaining frozen MBS/PBS families, exact output admission
  and actual consumer delivery; typed storage does not establish semantics.

### Quarterly CSV source qualification and PBS native values (2026-10-22)

- [x] Retain all three aggregate artifacts from successful exact-main run
  `39627746801`. Complete native-field parity, deterministic rebuild, Parquet
  restore and DuckDB checks cover 545,070 / 567,335 / 186,082 data rows.
  Q2 retains 4,728 service-count conversion exceptions; no rows are dropped.
  Source benefit meanings remain separate, patient rates unavailable, and
  no output admission or rights conclusion follows from these checks.
- [~] Add PBS native value candidates to both ordinary and historical entity
  streams. Preserve all native fields, product/restriction/reference occurrence
  identities and parent/archive/member lineage. Decimal candidates are lossless
  only; currency stays literal; unsupported values and domain meanings remain
  explicitly unresolved. No vocabulary membership or era equivalence inferred.
- [x] Verify 94 affected checks and 100% branch coverage of PBS value handling.
- [ ] Integrate PBS values into real-corpus output qualification and restore,
  complete remaining source family/era mappings and applicable output roles.
- [ ] Complete validation, review, protected CI and exact-main source execution;
  keep remaining MBS/PBS inventory coverage and consumer delivery open.

### Group source proof, PBS values qualification and outbound closure (2026-10-22)

- [x] Retain successful group run `39634190836` at main `889608f2`:
  164,543 data records plus header, 1,316,352 native slots, deterministic
  rebuild, independent native parity and DuckDB checks. No age inference,
  benefit equivalence, output admission or rights conclusion follows.
- [~] Add an explicit PBS values projection to the existing exact-main hosted
  route. Keep the five default structural projections unchanged. Verify full
  native digest/denominators, Parquet equality and controlled conversion-state
  counters; reject rounded candidates or semantic promotion independently.
- [x] Remove legacy workflow comment commands and unused issue-write scopes.
  Retain verification receipts in artifacts before source cleanup where comment
  receipts previously supplied that checkpoint. Confirm 15 comment-capable
  workflows disabled pending comment-free-main reconciliation; preserve all
  unrelated validation routes. The account-level outbound ban remains absolute.
- [x] Merge P7 PR #1260 as `d7bdaeb8` after all 40 hosted checks passed.
  Dispatch exact-main workbook run `39636095527`; result remains pending.
- [ ] Complete PBS increment validation/review/CI and exact-main values run.
  Reconcile the continuing local full profile without claiming its browser
  timeouts as passes; preserve all remaining inventory and delivery work.

### P7 typed source qualification readback (2026-10-22)

- [x] Retain exact-main run `39636095527` at `d7bdaeb8`: deterministic
  typed package rebuild, native-cell parity and typed Parquet restoration pass
  over 13,742 cells / four sheets. Preserve all four formula cells, two source
  error cells, 36 unrepresentable decimal conversions and 1,280 unsupported
  date formats. All 13,742 interpretation states remain native_unresolved;
  date profile is unselected. Output admission/rights/publication remain false.
- [x] Verify 324 affected PBS/workflow checks; 49 workflow-wide outbound
  regression cases pass. Audit all active-state run pages for the 15 disabled
  comment-capable workflows: none running or queued was observed.
- [ ] Finish remaining MBS workbook/archive/family coverage, PBS domain/era
  qualification, reproducible exact output roles and eligible consumer delivery.

### PBS route CI source-binding repair (2026-10-22)

- [x] Resolve hosted unit failures on `d89fbd4f` without restoring outbound
  comments: verify harvest destinations against the actual authorization files
  and invoked runners, and retain the exact historical root-manifest workflow
  snapshot matching the published input digest. The old readback is unchanged;
  the inert text snapshot and binding sidecar make its provenance reviewable.
- [x] Verify 126 affected harvesting, historical binding and outbound checks.
- [~] Retire the known-failing PBS full profile (exit 130), preserve its limits
  and rerun the repaired source tree. No full pass is claimed for the old run.
- [ ] Require repaired-head protected CI and complete exact-main PBS values
  qualification before recording any real-corpus value-projection result.

### Frozen quarterly demographic workbooks (2026-10-22)

- [~] Extend the native candidate route to all three exact demographic
  workbooks. Bind the Q1/Q2 latest streaming success and Q3 structural success
  to the original B1 acquisition and B2 reference, frozen path/revision/digest
  and B1 observed byte count. External-only B2 null byte counts are not zero.
- [x] Verify metadata identity and negative controls: 12 checks pass with
  100% branch coverage. Preserve the June Q2 workbook independently of the
  May Q2 CSV; source periods and benefit meaning are not equated.
- [~] Add protected per-workbook qualification using the existing deterministic
  package and independent native reader. Count actual primary source rows,
  reject empty denominators, preserve ancillary cells and use bounded DuckDB
  counts only after restoration/parity. Aggregate artifacts only.
- [x] Verify 28 cohort/qualifier checks with 97.01% combined branch coverage,
  affected production typing with zero errors/warnings, and workflow lint.
- [ ] Complete broader validation, review/CI and exact-main workbook runs.
  No real Q2/Q3 typed-workbook result is claimed before those runs finish.
- [ ] Continue group workbook, historical archives, remaining MBS source
  families and eras, PBS semantics, exact eligible output roles and delivery.

### PBS values progress boundary correction (2026-10-22)

- [x] Retain failed exact-main run `39641247728` at `c84c4898`: the bounded
  receipt records the 18,208,758-field denominator checkpoint and validation
  failure before the first values batch. No projection result is qualified.
- [x] Reproduce the same failure through the synthetic hosted wrapper with
  progress enabled. Add only fixed `values` to the aggregate phase allowlist;
  keep arbitrary phase labels and source text rejected. All 208 affected
  PBS/workbook checks and production typing pass.
- [~] Retire the superseded main-source full profile (exit 130) for this
  runtime-proven correction and workbook extension. No full pass is claimed.
- [ ] Complete repaired-head CI and rerun native-values qualification on exact
  merged main; retain the successful artifact only after actual verification.

### Frozen group workbook native layout discovery

- [~] Bind the frozen July group workbook to original B1/B2 and structural
  evidence, then inspect its own native layout on exact-main Actions before
  assigning semantic column roles. Implementation passes 20 focused checks
  (95.51% combined branch coverage), 168 broader affected checks, routine and
  strict typing. All ZIP members and native worksheet cells contribute to
  inventories; only bounded first-three-row header candidates are exposed.
  This does not qualify a group workbook Silver output. Hosted layout readback,
  reviewed field mapping, deterministic Parquet and restore remain pending.

### Historical PBS candidate value package and restore

- [~] Produce a complete deterministic PBS native-value Parquet package with
  content-bound manifest/output identity and atomic completion. Implementation
  passes 13 focused checks (96.8% branch-inclusive coverage), 112 broader
  affected checks, routine and strict typing. Restore compares all native slots
  to the separate unharmonised stream and all typed values/lineage/Arrow metadata
  to the producer. Rehashed corruption, semantic promotion and partial builds
  fail closed. Real-source complete-package qualification and applicable output
  rights/admission/delivery remain pending; domain meanings remain unresolved.

- [~] Qualify the complete PBS value package through the existing protected
  exact-main route, retaining the 55-minute step/65-minute job limits. The
  candidate mode writes two independent Parquet serialization files from one
  bounded producer pass, requires identical file digests, then verifies a fresh
  producer reparse and every original field against the restored package.
  This is explicitly not two independent end-to-end pipeline builds. Each
  temporary file is capped at 4 GiB; only aggregate evidence is uploaded and
  temporary derivatives are removed. The hosted wrapper and progress boundary
  pass synthetic checks; real-source execution and runtime fit remain pending.

### Complete quarterly workbook readback and next source-family coverage

- [x] Retain exact successful run 39648296077 for all three frozen demographic
  workbooks. Q3 preserves 186082 native rows, 11 literal Unknown-age rows and
  26193 lossless-decimal exceptions; source parity, two builds, independent
  Parquet restore and DuckDB counts passed. No benefit pooling, patient rate,
  new admission or publication follows.
- [x] Retain group workbook native layout run 39651063652: the primary sheet
  has 164558 physical rows/1316464 cells and Metadata has 228 cells. The actual
  Group/Sub_Group header is independent of demographic and CSV profiles.
- [~] Implement the group workbook native-row producer with separate group
  dimensions, complete cell properties, formulas/cache/errors and lossless
  numeric candidates. Primary-only output explicitly requires separate
  ancillary retention. Complete-source package/restore and hosted typed-output
  qualification remain pending.
- [x] Retain successful PBS native-value run 39648302023 over 18208758 fields
  and 7730684 entities. All entities remain native_unresolved; 7713891 are
  unmapped and none reaches the existing price role. This does not establish
  source absence of prices or domain completion.
- [~] Qualify the new bounded PBS native schema-path inventory route before
  extending domain mappings from the actual source structure. It emits paths,
  counts and presence states only, with a separate 1 MiB inventory bound and
  unchanged summary bound of 48000 bytes; no native values or new source are emitted.
  Read-only schema work has an independent concurrency key; legacy qualifier
  serialization and timeout limits remain intact.
- [~] Observe complete-package run 39654897926, dispatched on exact merged
  main eaee359d after PR1264 passed all 40 protected checks. No completed
  real-source package claim is made until the terminal receipt is verified.


### PBS actual schema inventory and restore recovery (2026-10-22)

- [x] Qualify exact April 2026 native schema inventory in run 39667604237:
  18,208,758 fields, 5,163 paths, 1,971,791 metadata bytes. Both original
  path-count and aggregate-byte limits were exceeded; no truncation or native
  values were emitted. Domain meanings remain unqualified.
- [~] Remove redundant restore scans and native Arrow materialization while
  retaining the existing native digest, exact typed row comparison, complete
  metadata, lineage, file bounds and manifest format. Synthetic differential
  controls pass; actual full-source package timing remains unqualified.
- [ ] Extend explicit source-bound domain profiles from observed paths for
  products, prescribing rules/restrictions, nested amount/pricing structures,
  drug references, vocabulary metadata and historical records. Keep source
  structural roles distinct from qualified payment or clinical meaning.
- [ ] Qualify complete PBS outputs and applicable admission/consumer delivery.


### Exact observed PBS domain profile and group workbook qualification

- [x] Qualify complete group workbook native package in run 39669037532:
  164555 primary rows, 252 ancillary cells, 1316692 total native cells,
  two equal builds, independent field parity, complete restore and DuckDB
  count checks. Retain 23987 benefit decimal exceptions and unresolved meaning.
- [x] Implement separate opt-in PBS structural roles from the exact qualified
  April inventory. Preserve every native field and parent occurrence; typed
  amount candidates retain precision exceptions and absent currency evidence.
- [~] Prepare protected read-only observed-domain-values qualification using
  original B1/B2, independent native digest, exact storage equality and inventory
  role denominators. Local synthetic checks do not qualify the real corpus.
- [ ] Require exact-main hosted observed-profile qualification, then complete
  substantive reference/domain semantics and eligible package delivery.


### Remaining frozen historical MBS archive members (2026-10-22)

- [x] Bind all six frozen historical ZIP archives to their exact acquisition,
  original external-reference B2, source digest and observed byte count.
  Preserve four prior structural passes and two resource holds separately.
- [ ] Inventory every member with streaming integrity and bounded native
  container identification on protected runners. Avoid inferring XLS/OOXML,
  CSV columns or eras from a filename alone.
- [ ] Qualify every eligible member's source-faithful tables, identifiers,
  null/error/precision/date behavior and reproducible outputs; retain explicit
  resource or format holds until actual evidence resolves them.
