# Plan: Australian health source consolidation

## Phase 1: Freeze the donor denominator (AC-01, AC-06)

- [x] Write failing tests for a complete two-repository inventory and ensure an
  omitted tracked file, function, workflow, or data artifact fails. (`7b830ea`)
- [x] Confirm the intended failure before implementation. (`7b830ea`)
- [x] Generate the machine-readable inventory from the two pinned commits,
  including paths, modes, sizes, digests, languages, functions, data roles,
  implementation state, and disposition. (`7b830ea`)
- [x] Characterize the invalid PBS parser, guessed MBS tag, processor path/type
  bug, zero-byte artifacts, and green-with-no-data scheduled workflow.
  (`7b830ea`)
- [x] Preserve complete donor Git histories and Apache-2.0 code provenance
  without modifying the dirty local donor checkout. (`c85c049`)
- [x] Review Fixes for concurrent donor inventory integration (`c85c049`, `0b9fe16`)
  - [x] Extend the canonical inventory merged by PR #349 instead of retaining
    a second inventory module, generator, manifest, or test authority.
  - [x] Bind Git object identities, reachable history roots/counts, Apache-2.0
    licence digests, and the invalid fenced parser's declarations.
  - [x] Validate the canonical qualification with a committed JSON Schema.
  - [x] Exercise undecodable Python, unrecoverable fenced syntax, history and
    licence drift; focused inventory coverage reaches 99%.
- [x] Phase Verification & Checkpoint: inventory denominator and regression
  failures are receipt-bound and independently reproducible. (`deed5e4`, PR #350)

## Phase 2: Add the independent MBS source domain (AC-02, AC-03, AC-07)

- [x] Write failing parser, admission, temporal, coverage, and semantic-boundary
  tests for `MBS_XML/Data`, all 40 native fields across the variable 34-to-37
  fields per record, and all 5,989 records. (`4871201`)
- [x] Confirm the intended failure before implementation. (`4871201`)
- [x] Add `au-mbs` source catalogue entries, source profiles, receipts, adapter
  registration, source-health checks, and versioned acquisition surfaces.
  (`4871201`)
- [x] Implement bounded source-faithful MBS XML parsing without Silver
  harmonisation in Bronze. (`4871201`)
- [x] Add a source-native workbook admission/profile and deterministic
  projection for all four P7 workbook sheets while retaining formula/error and
  schema-era information. (`4871201`)
- [x] Prove that MBS outputs cannot satisfy medicine regulatory, PBS funding,
  formulary, terminology, utilization, or clinical assertion contracts.
  (`4871201`)
- [x] Phase Verification & Checkpoint: exact raw digests, record counts, fields,
  dates, and independent-domain semantics pass. (`4871201`)

## Phase 3: Replace the PBS experiment with governed v3 support (AC-04, AC-07)

- [x] Write failing tests for ZIP safety, PBS namespaces, item/product identity,
  restrictions, AMT references, ATC codes, effective dates, malformed XML,
  duplicate members, traversal names, decompression limits, and drift. (`796c93a`)
- [x] Confirm the intended failure before implementation. (`796c93a`)
- [x] Extend the existing `au_pbs` adapter and catalogue/source profile rather
  than creating a second PBS authority. (`796c93a`)
- [x] Implement receipt-bound download, immutable ZIP preservation, member
  manifests, source-native Parquet, and the bounded tag-inspection command.
  (`771ca39`; HF revision `31ec854ef9fc82f30a0dbe743fdf50a2e5bd24a7`)
- [x] Preserve the donor CLI input/output expectations through compatibility
  tests where they are useful; do not preserve its syntax error.
  (`3f4e99a`, `0eaf89e`, `0ead5e2`)
- [x] Phase Verification & Checkpoint: donor intended behavior is covered by a
  valid, safe, typed implementation. (`a51a411`, PR #362; 37 hosted checks passed)

## Review Fixes: PBS v3 archive and record contracts

- [x] Accept the observed official `pbs:root`/Dublin Core validity shape,
  derive archive paths from the validated effective date, and bind hosted
  publication to a private-first exact-commit transaction with anonymous
  digest verification, durable issue receipts, cleanup, and privacy
  containment. (`ffb9614`)
- [x] Apply the maintainer's public-from-outset policy to the exact PBS
  destination while retaining exact-commit binding, atomic exact-sibling
  replacement, anonymous verification, durable receipts, and verified cleanup.
  (`458bbcd`)
- [x] Regenerate the content-bound stable-v1 measured-coverage receipt after
  the official PBS root-shape correction changed the adapter digest.
  (`28c5e33`)
- [x] Reject duplicate PBS item identities, keep restriction text/date pairs
  aligned, and label projected element digests without implying byte-exact
  native XML slicing. (`d9b583e`)
- [x] Regenerate the stable-v1 measured-coverage receipt after the concurrent
  hosted donor-binding correction changed its content-bound inputs. (`52ebf78`)
- [x] Match XML structural limits to the governed PBS archive envelope, require
  the v3 schedule root, bound tag iteration, and preserve absent AMT resources
  as Parquet nulls. (`00a59eb`)
- [x] Regenerate measured coverage after the final reviewed PBS projector
  changed its content-bound source digest. (`108dbc4`)
- [x] Bind hosted PBS publication to structured B1 retrieval, rights, reuse,
  sensitivity, transformation, and admission evidence; record failed hosted
  retrieval attempts append-only. (`5d91648`)
- [x] Replace the impossible private rollback promise with the approved,
  truthful public-from-outset failure policy. (`5d91648`)
- [x] Reconcile the official April 2026 schedule exceeding the former finite
  structural ceiling while retaining the bounded PBS archive envelope and
  regenerating its content-bound coverage receipt. (`4c65dc3`)

## Review Fixes: MBS source-domain phase

- [x] Bind source-batch identities as literals and bind the catalogue download
  surface to the exact versioned July 2025 XML rather than a generic page.
  (`dc6001a`)
- [x] Exercise exact-qualification, hostile-shape, archive-relationship, Git
  failure, and malformed-inventory branches above the 91% coverage floor.
  (`da37c55`)
- [x] Assign every new donor test module to the governed routine unit lane and
  rerun the routine harness with the compatible local Python fallback.
  (`85b6a51`)
- [x] Regenerate the exhaustive Bronze landing queue after catalogue expansion
  and keep parser-only MBS sources `not_yet_implemented` until hosted public
  B1/B2 receipts and anonymous restore verification exist.
- [x] Regenerate every stable-v1 and source-rights projection bound to the
  expanded 174-source catalogue, retaining fail-closed rights states for both
  newly catalogued sources.
- [x] Bind donor inventory validation to caller-supplied pinned repository and
  source URL identities so valid Git bytes cannot be relabelled.
- [x] Regenerate downstream B0, archive, monitoring, prompt reconciliation, and
  academic-protocol projections after the catalogue denominator changed from
  172 to 174 sources.
- [x] Regenerate the strictly offline preregistration rehearsal bundle after
  its embedded academic protocol changed; retain its unsubmitted state.

## Phase 4: Replace the monthly scraper safely (AC-05, AC-06)

- [x] Write failing tests for month ranges, historical URL generation,
  item/participant naming, timeouts, retries, rate limits, 404s, empty output,
  mixed HTML tables, XML P7 filtering, and deterministic projections.
  Partial foundation: `79e16b3` covers bounded historical months/URLs/names,
  six-404 regression, serial rate limits, timeout retries and empty transport
  outcomes. 59 focused tests pass; HTML/P7/admission and live scheduling remain
  pending. `docs/qualification/mbs-monthly-compatibility.md` defines that boundary.
  Extension `1e5c3ec` adds separate typed simple-HTML tables, deterministic
  per-table Parquet and native P7 selection; 57 focused tests pass with 100%
  reported coverage for the two new modules. `1349c93` additionally retains
  the separate donor `mbs/item` profile and locks serialized table shape.
  Live scheduling, complex HTML spans and durable admission receipts remain pending.
- [x] Confirm the intended failure before implementation. (`7230721`, PR #364)
- [x] Reuse GMA HTTP destination, admission, receipt, source-health, and
  catalogue-driven scheduling controls.
  Typed HTML admission now uses the shared content-addressed Bronze decision
  and append-only store; live-only usable-table health uses shared escalation.
  Hosted runner uses the catalogue and a separately approved exact-release
  override. PR #367 (`435527a`) passed 38 hosted checks; run `33296983154`
  acquired and anonymously verified the approved August release.
- [x] Keep old endpoint behavior as a compatibility probe and source-drift
  fixture; use current official MBS releases for production acquisition.
  (`7230721`, `435527a`; historical endpoints remain synthetic probes.)
- [x] Replace heterogeneous `pandas.concat` output with source/table identities
  and explicit schema contracts. (`7230721`, PR #364; typed HTML and native P7)
- [x] Require artifact and receipt evidence before a scheduled run reports data
  acquisition success.
  (`435527a`; public receipt issue #340 comment `5467154799`, 6,046 records.)
- [x] Phase Verification & Checkpoint: the August 2026 no-data run fails closed
  and a valid fixture run emits deterministic, typed products.
  111 focused tests passed; live run `33296983154` separately verified eight
  objects at HF revision `75f9f20a36ddb829dfe0ca88660664570782be02`, preserved
  all 11 prior paths and removed hosted temporary bytes after verification.
  This does not establish live historical participant-count coverage.

## Phase 5: Preserve design intent and prepare archival (AC-01, AC-08, AC-09)

- [x] Map Neo4j, SNOMED CT-AU, AMT, ATC hierarchy, NLP/NER, temporal graph,
  Spark, and Airflow commitments to existing GMA capabilities or successor
  tasks; label each as implemented, preview, rejected, or separately gated.
  (`4c1fae7`; omission-sensitive successor map and existing plan references)
- [x] Verify the exact donor XML, legacy workbook, and both complete Git-history
  receipts from the public Hugging Face data-plane track. (`4d1dae4`)
- [x] Publish compatibility and successor notices in both donor repositories,
  link exact GMA/Hugging Face destinations, and run downstream canaries.
  (graph PR #5 `3993e5e`; scraper PR #4 `009e805`; canonical mapping PR #366
  `4806b7f`; anonymous revision canaries recorded by the coordinating task)
- [x] Prepare non-destructive GitHub archive commands and a rollback checklist;
  stop at the compatibility-archive gate for the exact two repositories.
  (`4c1fae7`; commands documented only, no archive approval or execution)
- [x] Phase Verification & Checkpoint: no donor scope is unaccounted for and no
  archive action has occurred without the final human gate.
  Exact donor denominator and all eight roadmap commitments are mapped;
  implemented behavior and future successor tasks remain distinct. Donor
  notices are merged; final GitHub archive approval remains pending.

## Post-baseline donor drift follow-up (AC-01, AC-06, AC-09)

- [x] Reconcile complete changed-path/blob inventories against independently
  observed current donor heads without overwriting the frozen baseline.
  Graph `3993e5e` changes two documentation files; scraper `009e805` changes
  eight files, including code, workflow and tests despite its commit title.
  Timeout and parsing improvements have GMA equivalents; literal async API
  compatibility remains explicitly legacy-only, not proven parity.
  Implemented `b8938b7` (agent original `9d19e64`): missing-module red,
  malformed-path and copied-model corrections, then 58 focused/inventory
  passes and 100% new-module coverage. Delivered in PR #401 at reviewed
  `f0799c4`, merged `2543720`, 38 successful checks and matching trees.
- [x] Preserve both later donor heads through exact hosted history receipts
  before archival; the existing baseline bundles do not contain these commits.
  No raw-data paths changed in the observed deltas. This is not evidence of
  later history preservation or authorization to archive either repository
  at that checkpoint. Hosted run `34005721959` later preserved and anonymously
  restored both exact heads at public revision `97038008d17a48f620302f04fe6a3156fb8d5d57`;
  see `quality/qualifications/scraper-archival-20260906.json`.
- [x] Prepare a separate append-only history contract for those exact heads.
  Implemented `9ca7eca` and review fix `2ebf0c2`: public target, baseline
  prerequisites, head-addressed bundle/manifest metadata, CAS, unchanged prior
  objects, anonymous digest and clean Git restoration bindings. Retain all
  supplied observations and revalidate copied models and exact boolean flags.
  Pure metadata consistency checks do not authenticate observations or authorize
  publication, cleanup or archive. Seven review regressions failed first;
  84 focused history/delta tests pass, corrected coverage 148 statements and
  46 branches, all covered. The checked-in execution authority envelope is
  exact-head bound and deliberately inert (`publication_authorized=false`);
  it rejects local and non-main execution. Protected hosted checks remain the
  PR delivery gate. PR #410 patch coverage repair exercises exact-head drift,
  every hosted-context short-circuit, and the separately constructed authorized
  success path without changing the checked-in inert contract; the module now
  has 100% statement and branch coverage locally. The exact original two-file
  command was reproduced at `f36f061` with 87 passed; the coverage-repair head
  adds four cases and the same command now reports 91 passed. PR #410 exact
  updated head `e237897` passed all 38 protected checks and auto-merged as
  `6dbb91b`; this delivers only the inert authority envelope, not an append.
- [x] Add the hosted append transaction and obtain exact authorization for the
  two newer histories before dispatch. Do not reuse the old replace-all,
  private-target legacy publisher or its dataset-wide privacy rollback.
  Recover an already-completed append from its authenticated durable receipt;
  do not force an empty new commit or overwrite identical head-addressed paths.

## Phase 6: Integrated qualification (AC-10)

- [x] Run focused tests, Ruff, `ty`, BasedPyright, provenance, rights,
  deterministic regeneration, security, coverage, and compatibility lanes.
  PR #367 head `184a9b4`: 111 focused tests, local type/style/security passed;
  all 38 hosted checks passed, including mutation, Mojo and regeneration.
- [x] Run `uv run python scripts/test_goblin.py full` where platform support
  permits; record Linux-authoritative Mojo/mutmut evidence separately.
  Local: 2,793 passed, three failed, one skipped, 96.42% coverage. Two failures
  require exact Python 3.14.6 rather than local 3.14.7; one exceeds the unchanged
  query latency budget. Later local lanes did not execute after failure.
  Required exact-head hosted lanes passed; no local-all-green claim.
- [x] Run Conductor review, fix findings, open a scoped pull request, wait for
  required hosted checks, merge, and reconcile evidence.
  Three PR #367 review findings fixed and resolved; implementation merged.
  Publication/checkpoint reconciliation merged as PR #368 (`c1f51f6`),
  reviewed head `6aafcdd`; required checks passed. Its recording-time review
  finding was corrected before merge. See `review.md` for the AC audit.
- [x] Keep archive tasks pending until the exact parity/publication package and
  maintainer approval are recorded. Both separate approvals and completed
  archive readbacks are recorded in the scraper and graph archival receipts;
  no further archival action is pending for those exact repositories.


## Scraper archival readiness follow-up (2026-09-06)

- [x] Reconcile the dirty local scraper delta without modifying it; preserve
  the general-group patch and synthetic PBS fixture and adapt useful behavior.
  Implemented `7babb53`; 226 initial canaries and 109 final focused tests pass.
- [x] Record explicit async, complex-table, CSV and participant-coverage
  dispositions plus the live open issue/PR inventory. (`7babb53`)
- [x] Implement and test the exact hosted history append and recovery runner;
  retain disabled publication authority until separately approved.
  `7babb53` plus reviewed synthetic transport/detached-HEAD follow-up; final
  hosted delivery merged in PR #476 (`af24b15`), with 38 checks passing. Full local run: 4,810 passed,
  two pinned-uv environment failures (both passed targeted recovery), one skip.
- [x] Obtain exact history publication approval, dispatch and verify the receipt.
  Approval: issue #339 comment 5556212193; run 34005721959 succeeded.
  Verification: issue #340 comment 5556271994; all 30 objects verified.
- [x] Re-query the donor, resolve open donor work and record scraper archival
  without deleting history or local work. Scraper archived 2026-09-06T02:12:07Z;
  main and both branches retained. Issues #1–#3 and PR #5 closed as superseded.
  Receipt: `quality/qualifications/scraper-archival-20260906.json`.

See [scraper archival readiness](../../../docs/migrations/scraper-archive-readiness.md).


### Review Fixes: immutable history recovery

- [x] Preserve verification/recovery of the acknowledged immutable revision
  after another archive writer advances main; require the exact approved
  contract and record publishing versus verification commit/run identities.
  PR #476 review comment 3942541730; 114 focused tests pass, 100% orchestration
  statement/branch coverage. Current-head preservation remains a final preflight.


### Review Fixes: standalone history restoration

- [x] Rebuild loose Git objects directly from verified bundle PACK streams
  using `unpack-objects --strict`, then bind exact refs, prove ancestry and run
  full strict fsck. This avoids intermittent generated pack-index failures
  without relaxing object verification. 115 focused tests pass, including a
  corrupt-stream rejection; final hosted qualification remains in PR #476.

### Review Fixes: approved archival gate

- [x] Reconcile scraper archival approval in the plan and acceptance review;
  retain graph archival as a separate pending decision. PR #477 comment
  3942668945; no repeated scraper approval is required.

## Graph archival readiness follow-up (2026-09-06)

- [x] Revalidate the exact current graph head against the published restoration
  receipt and current public revision; inventory refs, releases and artifacts.
- [x] Verify successor archive links and run donor/parser/history canaries:
  174 passed; no new code or data delta since preserved baseline scope.
- [x] Resolve issues #2–#4 and close onboarding PR #6 as superseded, retaining
  both branches and discussion history; re-query open work as empty.
- [x] Review, validate and merge the graph readiness record. PR #479 merged
  `067977b0`; all 39 checks passed.
- [x] Obtain graph-only archival approval, repeat final drift preflight, archive
  without deletion, and record before/after evidence. Issue #339 comment
  5556516869; archived 2026-09-06T03:02:52Z. Restored the missing Renovate
  ref to its exact recorded commit before archival; both branches verified.

See [graph archival readiness](../../../docs/migrations/graph-archive-readiness.md).

## M-105 acceptance follow-up

- [x] Bind every pinned donor artifact and later changed path to exact
  behavioral or byte-level evidence. The
  [2026-09-27 gap audit](../../../docs/qualification/australian-donor-parity-gap.md)
  and omission-sensitive matrix classify all 54 baseline blobs and ten later
  changed paths with exact Git identities. The MBS XML parser and governed
  downloader now bind pre-archive exact-corpus and hosted receipts. The three
  graph PBS executable rows also bind function-specific tests and the pinned
  public April 2026 archive. Scraper processor and processor-test rows now
  bind function-specific synthetic replacement checks. Both pinned scraper CI
  blobs now bind protected hosted test/lint execution. The donor's unchanged
  hard-coded demonstration entry point and later async scraper test are
  explicitly excluded with reasons and exact archived-history proof; separate
  synthetic rehearsal and hosted XML release evidence does not replace their
  omitted HTML and async behavior. The pinned scraper module now has a
  function-level legacy-only receipt: `month_range` is adopted with tests,
  while both async HTML callers remain in exact archived history. The pinned
  monthly workflow is now a legacy-only row: its failed HTML scrape and Git
  commit path remain archived, while a separate approved XML release was
  acquired and anonymously verified by a scheduled GMA run. No matrix row is
  pending. Exact history preservation and archive approval are verified
  separately. M-105 remains blocked because its pre-archive parity requirement
  cannot be established retroactively by this post-archive reconciliation.
- [x] Record the maintainer's chronology-exception disposition in
  `conductor/decisions/0006-external-gate-decision-register.md` (D-006-07).
  Keep M-105 blocked without waiving or amending the pre-archive criterion;
  continue M-106–M-112 independently.
- [x] Recheck pre-archive GitHub evidence on 2026-10-18. PRs #349, #364, #476,
  and #477 establish only scoped parser/rehearsal/history-preservation evidence;
  #476 and #477 explicitly leave participant/async parity and full donor
  behavior coverage unclaimed. No pre-archive record for the complete 54-blob,
  ten-path denominator was found in the searched PR/issue evidence. This does
  not claim that the search covered unpreserved external records and does not
  waive the criterion. See the updated M-105 gap audit.
- [x] Query the archived donor repositories' own PR records on 2026-10-18.
  Scraper PR #4 records bounded synthetic request/output tests and limited
  parser/CI changes; graph PR #5 is a successor notice with explicit
  compatibility limits. Neither supplies complete pre-archive parity for the
  full denominator. See the updated M-105 gap audit; D-006-07 remains in force.

## M-107 source-family gap preservation follow-up (2026-09-28)

- [x] Add regressions for filename-derived reporting periods and for a stale
  annual workbook that must not satisfy the currently expected FY. Annual
  workbooks use the latest completed FY; quarterly/YTD workbooks use the latest
  published FY. Missing or stale-period Health.gov families are explicit
  non-fetchable failures; successful resources can produce only a partial
  latest-run manifest.
- [x] Focused tests: `tests/test_australian_harvesting.py` (35 passed); affected
  publication/workflow tests (51 passed); Ruff, `ty`, and BasedPyright passed.
- [x] Merge the reviewed change and dispatch exact-main under the existing
  publication authorization. Run `36330658537` published revision
  `32ce8741be7f0508dca641a3e397759ec492da02`; all 28 objects were anonymously
  verified, latest-run coverage was explicitly `partial`, and temporary
  hosted bytes were removed. Health.gov page discovery returned zero URLs.
  This does not qualify M-107 or the federation gate.

## M-107 direct workbook fallback follow-up (2026-09-28)

- [x] Read the public harvest receipt and confirm Health.gov families were
  marked unavailable without making workbook requests.
- [x] Add exact official current-period quarterly and YTD workbook URLs, plus
  the actual older annual attachment, as bounded discovery fallbacks. Preserve
  filename-derived periods so the older annual workbook cannot satisfy the
  latest annual FY. PR #553 merged as `979f806f`; all protected checks and
  Codecov passed.
- [x] Run exact-main acquisition and record the anonymous receipt. The first
  attempt `36332516760` was cancelled during workbook staging after 14 minutes;
  it had completed two official-download attempts that each returned zero
  bytes before a third was interrupted, and it never reached publication.
  Replacement run `36333396964` published immutable revision
  `dee9a5b0580dfe394474dc26b372559462e157e7`; all 28 objects passed anonymous
  digest verification and temporary bytes were removed. Coverage remains
  `partial`: all three official Health.gov workbook requests timed out with
  zero bytes and the annual-family sentinel remains unavailable. Exact public
  receipt: issue #340 comment `5857784415`; cleanup receipt: `5857784489`.
- [~] Resolve the remaining delivery blocker without changing source identity
  or rights scope: obtain an authorized hosted egress route to the official
  Health.gov workbook files or an agency-provided mirror authorized under the
  existing source contract. Then repeat exact-main acquisition and qualify
  workbook periods, historical denominators, and family coverage. A bounded
  data.gov.au metadata search found no exact mirror. M-107 and the Australian
  federation gate remain blocked until those source payloads and dependent
  acceptance evidence are available.

## M-107 bounded endpoint diagnostic (2026-09-28)

- [x] Run the authorized exact-main HEAD-only diagnostic after introducing
  independent operation and whole-request deadlines. Run `36377888606` on
  `58cb9e8c` classified all three workbook URLs as response-read timeouts after
  connection setup; no headers or source bytes were received and no redirects
  were followed. The durable receipt is issue #340 comment `5863375054`.
- [x] Compare the same metadata-only requests from the workstation. All three
  returned HTTP 200 with the expected XLSX media type and non-zero content
  length, without following redirects or reading bodies. This establishes a
  route-dependent observation, not its root cause. The source authorization
  forbids workstation raw retention and requires GitHub-Actions-only upload;
  no payload GET or local retention was attempted. Machine-readable metadata
  receipt: `quality/qualifications/australian-mbs-workstation-head-availability-20260928.json`.
- [x] Repeat the value-free probe once after the timeout-alignment fix on
  exact main `38566970ff872c38c3312bfb118e5b4ed59777f8`. Run
  `36452243269` classified all three URLs as response-read timeouts; no
  headers or workbook bytes were received and no redirects were followed.
  The issue receipt is `#5874364267`; durable aggregate:
  `quality/qualifications/australian-mbs-workbook-head-preflight-20260929.json`.
- [~] Obtain an authorized reachable delivery path. The corrected probe
  narrows the hosted observation but does not identify a publisher or
  network cause, provide workbook content, or satisfy M-107/federation
  acceptance. Do not repeat the same probe until an endpoint or transport
  condition changes.

## M-107 agency-hosted mirror route (2026-09-28)

- [x] Record the maintainer's selected delivery route: an agency-hosted mirror.
  No mirror is yet identified, and this route choice alone does not authorize
  external contact or qualify a source payload.
- [x] Recheck the current official Health.gov publication metadata. The annual
  State and Territory page describes coverage through FY 2025-26, but its
  linked attachment URL filename ends in FY 2024-25. The attachment bytes were
  not read, so the workbook's actual coverage remains unverified. Metadata-only
  evidence: `quality/qualifications/australian-mbs-agency-mirror-route-20260928.json`.
- [x] Prepare and send the source-owner request for an agency-controlled
  endpoint, workbook period/coverage clarification, historical releases,
  attribution/terms, and machine retrieval requirements:
  `conductor/tracks/australian_health_source_consolidation_20260829/m107-agency-mirror-request.md`.
  Sent to the Department's published general-enquiry address on 2026-09-28;
  an automatic acknowledgement confirms receipt, with substantive response
  pending. Sent and acknowledgement evidence:
  `quality/qualifications/provider-outreach-receipts-20260929.json`.
- [~] Obtain the agency's response and an approved endpoint within the existing
  source authorization. No substantive reply was observed at the time of the
  receipt. Do
  not GET or retain workbook bytes on the workstation.
  If the endpoint uses a domain outside the current authorization, stop for an
  explicit scope update. Then acquire only through the authorized GitHub Actions
  publication workflow and qualify each workbook's exact period, denominator,
  and historical family coverage. M-107 and Australian federation remain open.

## MBS legacy workbook date convention (2026-09-29)

- [x] Prepare a value-free inquiry asking Health.gov to confirm the date
  convention for the exact July 2024 legacy Group P7 workbook. The official XML
  date specification does not establish the separate workbook's convention;
  compatibility evidence found 1,276 cells valid under both orders and four
  valid only under DMY. Sent under the existing MBS contact authorization to
  `enquiries@health.gov.au`; message ID, subject, no-attachment status, and
  message readback are recorded in
  `quality/qualifications/provider-outreach-receipts-20260929.json` and
  `mbs-workbook-date-convention-request.md`.
- [~] Keep the date profile unset and semantic promotion disabled pending
  source-specific documentation or confirmation. No source bytes or cell
  values were sent; no response has yet been observed.

## M-106 item-demographic source discovery (2026-09-29)

- [x] Review official Services Australia item-report metadata and the
  data.gov.au item-demographics catalog record. The published fields include
  item, age range, gender, services, and benefit; no distinct-patient-count
  field is listed, and the catalogued data was last updated in 2016. Mark this
  only as a candidate for item-service counts, not a patient denominator:
  `quality/qualifications/australian-mbs-item-demographic-source-review-20260929.json`.
- [x] Send a value-free source-owner inquiry about a public item-level
  unique-patient measure, coverage, suppression and reuse terms:
  `m106-item-patient-count-inquiry.md`. Sent to the published Services
  Australia statistics contact. The request asks for existing public sources
  only and does not request custom or restricted data; the message readback is
  recorded in `provider-outreach-receipts-20260929.json`.
- [~] Keep M-106 blocked until the source owner confirms whether an item-level
  patient count exists, its public period/denominator, and applicable rights.
  Item service counts must not be relabelled as patients.

## M-106 current item-data metadata preflight (2026-09-30)

- [x] Inspect the newly catalogued Services Australia August 2026 MBS Item
  Data resource using its public metadata page and a CKAN `limit=0` schema
  query. The metadata reports 26,391 records and fields for processing year
  and month, group, subgroup, item, state, services and benefit; the query
  returned zero records. The catalog lists CC BY 3.0 Australia, but no
  project-specific rights decision, source acquisition, or publication
  authority is recorded. Receipt:
  `quality/qualifications/australian-mbs-current-item-data-metadata-20260930.json`.
- [x] Reconcile M-106 documentation and add a digest-bound contract check.
  The new resource provides no distinct-patient field in its published schema,
  and the catalog data dictionary is empty. This narrows it to a current
  item-level statistics candidate; field semantics and patient counts remain
  unqualified. The focused metadata contract tests (2), Stable v1 contract
  tests (43), routine Test-Goblin, context/ecosystem checks, Ruff,
  BasedPyright strict, and diff checks passed.
- [x] Recheck the already-sent patient-count inquiry using a subject-scoped
  Gmail search. It returned the original sent message and no inbound source-
  owner reply; no follow-up was sent. Receipt:
  `quality/qualifications/provider-response-m106-refresh-20260930.json`.
- [~] Keep acquisition and M-106 acceptance blocked pending source-owner
  clarification on a distinct-patient measure and a separate maintainer
  rights decision for this exact resource. No CSV row or source byte was
  retrieved.

## M-106 public patient-statistics metadata recheck (2026-10-16)

- [x] Review the Department's current Medicare statistics collection and
  linked patient-statistics metadata. The collection page lists a 2025–26
  per-patient bulk-billing dashboard and annual GP Non-Referred Attendances
  patient bulk-billing ranges by PHN. The 2024–25 annual report states that
  the Department counts patients for its MBS population-access measure from
  claims in its Enterprise Data Warehouse, but the cited methodology does not
  publish the exact numerator. Record these as metadata-only candidate/source-
  owner evidence in
  `quality/qualifications/australian-mbs-m106-patient-source-metadata-20261016.json`.
  No product payload was downloaded, no count was derived, and no rights or
  acquisition decision was made.
- [~] Keep M-106 blocked. Clarify whether a public or releasable dataset gives
  exact deduplicated distinct-patient counts for the required MBS domain and
  periods, including coverage, suppression, and reuse terms. Obtain a separate
  source-specific maintainer rights decision before any acquisition. GP/NRA
  patient-billing products and rounded population percentages are not a
  denominator for full MBS coverage. A value-free source-owner inquiry was
  sent to the Department's published enquiry address on 2026-10-16 and read
  back under the sent label; its message identity and scope are recorded in
  the qualification JSON. The exact sent text is preserved in
  `m106-department-patient-denominator-inquiry.md`. The annual-report PDF was
  reviewed through the web reader at pages 91–92, but was not saved locally;
  the dashboard/workbook payloads and patient-level data were not acquired.
  Await a substantive reply; no data or attachments were sent, and no source
  rights or acquisition decision was made.

## M-109 PBS current-distribution transition (2026-09-29)

- [x] Reconcile current official PBS distribution metadata with the pinned
  historical XML qualification. The official portal records legacy XML/text
  outputs as discontinued, identifies the public API/API CSV as the current
  route, lists API model 3.7.8 with release notes dated 2026-05-20, and exposes
  the current schedule plus the previous 12 months. Its published XML history
  names G2B XML 1.8 (Dec 2006–Oct 2012), PBS XML 2.8–2.12 (Dec 2012–Aug 2017),
  PBS XML 3.0 onward (from Sep 2017), and an alternate 2.12 distribution
  through Aug 2018. These are documented eras, not a verified acquisition
  denominator. The metadata-only receipt is
  `quality/qualifications/pbs-source-transition-20260929.json`; it contains no
  API payload or source values.
- [x] Keep the 2026-04-01 PBS XML v3 profile scoped to its exact historical
  member. The separate API preflight records public read access and permission
  to download for users' own systems, but no retention duration, external
  redistribution terms, or source-specific maintainer rights decision.
- [~] M-109 current PBS coverage remains blocked until the API source contract,
  retention and publication rights are resolved and a scoped current API
  corpus is authorized and qualified. Do not reuse the XML profile as current
  API semantics or exceed its 12-month published history window.

## M-109 exact-main July 2025 MBS six-table parity evidence (2026-10-16)

- [x] Reconcile the dependent benefits-track exact-main Test-Goblin receipt
  into the M-109 source-era register and federation acceptance summary. Run
  `38908829291` on merge `2666e6e026867be99d85f1e32bc9b381afe50efc`
  validated artifact `12048749308` (SHA-256
  `0743f6039e3da1d5bac05d013f3fd629d22da94df014033cdac66b0bb19ef5b6`).
  Its value-free receipt binds the pinned July 2025 source and Silver manifest,
  verifies source-to-candidate value parity for exactly six canonical tables,
  and reports 5,989 rows per table. This is one source-era parity result only;
  rights, production admission, publication, promotion, other-era semantics,
  the approved source-era denominator, and full M-109 acceptance remain open.
- [x] Preserve the exact 2,843-byte value-free receipt in
  `quality/qualifications/mbs-source-silver-tables-parity-2025-07-v3.json`.
  Its committed digest is
  `0743f6039e3da1d5bac05d013f3fd629d22da94df014033cdac66b0bb19ef5b6`;
  a regression checks this identity and validates the receipt with both the
  Pydantic model and JSON Schema so evidence remains auditable after the
  hosted artifact expires.

## M-109 source-era identity validator generalization (2026-10-17)

- [x] Generalize MBS source-era verification beyond the pinned July 2025
  release. Bind official HTTPS host and URI authority, filename date and
  version, release ID, effective date, schema-era year/month/day/version, and
  comparison chronology. Unversioned releases require the exact effective
  day in their schema-era identity.
  Preserve backward loading and report digests only for the exact legacy July
  2025 identity; other eras must name their schema era explicitly. Tests cover
  the official August 2026 identity shape, missing-era rejection, identity
  contradictions, and a correction released after its effective date.
  The qualification model is now capable of representing additional official
  eras, but no additional source-era schema or semantic profile was read or
  accepted by this change.
- [~] M-109 still requires the complete approved source-era denominator,
  source-specific Silver schema and semantic qualification, admitted real
  source data, and all external rights or admission evidence. The validator
  generalization does not close those gates.

## M-109 August 2026 MBS candidate qualification route (2026-10-17)

- [x] Add a read-only GitHub Actions qualification route for the exact
  authorized August 2026 MBS object. It binds the B1 receipt, immutable B2
  archive identity, and live official release by SHA-256 and byte count, then
  emits aggregate six-table candidate counts and lineage only. The route
  processes source bytes in memory in Actions, retains only a 90-day aggregate
  artifact, and does not publish or admit data.
- [x] Add regression tests for exact source identity, successful candidate
  boundaries, and fail-closed mismatch between the archived and official bytes.
  The report explicitly leaves field semantics, temporal semantics, public v4
  admission, and M-109 acceptance open. Record exact qualification state in
  `docs/qualification/australian-m109-source-era-register.md`.
- [~] Reconcile source structure and diagnostics without advancing field
  meanings, temporal semantics, transformations, or the approved era
  denominator until their exact-era evidence is independently qualified.
- [x] Run the initial candidate workflow on exact `main` commit
  `b566e9980fd14d9d94caa7235002af94f6f53533` (run `39025588261`) and preserve
  the 4,542-byte aggregate report at
  `quality/qualifications/mbs-source-era-candidate-2026-08-01.json`. Archive
  bytes and official bytes matched the approved B1 SHA-256 and byte count.
  The candidate reports 6,046 rows across six tables and remains blocked by
  `public_v4_identity_unverified` and `quality_findings_present`; it does not
  accept field meanings or semantics.
- [x] Implement the per-field presence/state comparison with exact row
  identity checks and no source-value output. Tests show native absence is
  represented as `missing_field` without calling it invalid or optional.
  Also report per-field conversion-status counts so `unsupported_format` is
  distinct from native absence. The report leaves requiredness unaccepted and
  reports mismatches without promoting the candidate. The exact-main profile
  is recorded below; do not repeat it absent changed source bytes or profile
  code.
- [x] Run the updated hosted profile on exact `main` commit
  `b5b4d3ce6e3400e0fdb84ab2b56854776c4878e6` (run `39032003723`) and retain
  its aggregate-only output at
  `quality/qualifications/mbs-source-era-candidate-2026-08-01-run-39032003723.json`.
  All 40 source fields align with projected presence/state across 6,046 rows
  each (zero mismatches); the report remains candidate-only and records no
  source values or bytes. The profile applies the official DMY grammar as a
  candidate and reports no unsupported/invalid date values, but does not
  accept release-specific semantics, requiredness, or temporal meaning.
- [~] Reconcile the field-guide meanings with release-linked version history.
  MBS Online identifies the predecessor as `MBS-XML-20260701.XML`, released
  2026-05-28 and effective 1 July, and says the August file includes item
  73331 with no further changes compared with that May-published edition. The
  exact July/August archive identities and sidecars are verified in current
  metadata. The bounded comparison ran on exact `main` commit
  `0979b7f6c395986636e48aefbeeac8c579d36283` (run `39037457764`) and failed
  closed; its aggregate artifact is `12102413530`. The August sidecar binds
  the original acquisition path while the B2 archive uses a content-addressed
  path. Metadata-only inspection confirms both August paths resolve to the
  same pinned LFS object identity and byte count. The local repair preserves
  both identities, validates each against the pinned digest, and adds static
  failure-stage diagnostics. Exact-main verification of that repair remains
  pending its protected PR and merge. A structural/content comparison cannot
  establish semantic continuity; the field guide's version history after
  2022 remains unverified. The consolidated M-108/M-109 assessment records
  source-archive-only authority, absent derived-output authority, and
  preservation/reversal steps. No further `39029209737`/`39032003723`
  diagnostic run is needed.

## M-107 metadata evidence review fixes (2026-09-28)

- [x] Correct the proposed route/contact evidence timestamps to the recorded
  commit time (`2026-09-28T10:10:14Z`), removing timestamps later than the
  commit that contains those records. The correction is confined to the
  unmerged PR evidence additions.
- [x] Preserve the currently observed publication-page metadata in a minimal
  content-addressed receipt and link it from the route qualification. The
  SHA-256 binds the exact extracted page titles, period statements, dates, and
  attachment URLs; the mutable HTML payload and workbook bytes are not copied.
  M-107 remains blocked because this receipt does not establish workbook
  contents, mirror availability, historical completeness, or acquisition.
- [x] Reconcile PR #579 after merge `4d880652bcbdb692eaa2a90319ac0270810189d0`.
  Its exact head `8bf354e0128e12169f53a296231668e874d82f5f` passed all 37 hosted
  checks, including Codecov patch coverage. The value-free metadata receipt is
  now durable on `main`; the source-owner request was subsequently sent; provider response, an approved
  endpoint, M-107 qualification, and Australian federation remain open.


## MBS metadata append receipt-link review correction (2026-09-29)

- [x] Preserve the append-only ledger and supersede the incorrect PBS receipt
  links in the follow-up with the MBS transaction's CAS intent, acknowledgement,
  and anonymous verification comments `5885053897`, `5885054280`, and
  `5885067299`, as recorded in `docs/qualification/source-metadata-append.md`.
  The public metadata object remains verified at its exact revision, size, and
  digest; no source payload or acceptance claim changed.

## Provider-response readback (2026-09-29)

- [x] Check the existing OpenPrescribing, PBS API, Medicare workbook,
  MBS workbook-date, Services Australia denominator, and Medstat inquiries
  using read-only mailbox searches. The initial sender-address-only check is
  retained in `quality/qualifications/provider-response-check-20260929.json`;
  a review finding showed that sender filters could miss replies from other
  addresses, so it was superseded by the subject-scoped thread check below.
- [~] Keep dependent source acquisition and acceptance gates pending. Do not
  infer approval from automated acknowledgements or repeat unchanged source
  probes. No follow-up messages were sent.

## OpenPrescribing provider response and thread-search correction (2026-09-29)

- [x] Search each outstanding inquiry by its subject rather than only its
  destination address. This found OpenPrescribing's substantive reply in the
  original thread from an observed responder address; record the correction
  and exact message metadata in
  `quality/qualifications/provider-response-thread-check-20260929.json`.
- [x] Reconcile the OpenPrescribing queue reason and next action. The provider
  says increased Cloudflare protections may challenge or block automation and
  that no alternative automated retrieval route can be offered at present.
  Keep the approved scope unchanged and wait for a provider-supported route or
  material access-control change before a bounded retry. Do not bypass
  challenges, crawl unboundedly, or substitute upstream files.
- [x] Regenerate the dependent B0 Source Index JSON, Parquet, schema, dataset
  metadata, and documentation projections from the updated landing queue.
  The queue state counts did not change; the source-specific reason and retry
  evidence now agree across B0 projections.
- [ ] Acquire and qualify only after an authorized, reachable route exists;
  the current response grants no access, credentials, or rights change.

## Provider inquiry refresh after PR #636 (2026-09-29)

- [x] Recheck all six outstanding provider inquiries with read-only,
  subject-scoped searches. OpenPrescribing's substantive response remains the
  only observed provider guidance; PBS and MBS agency inquiries remain at
  automatic acknowledgements, Services Australia has no reply, and the
  Medstat automatic reply remains unbound to its inquiry. Receipt:
  `quality/qualifications/provider-response-thread-refresh-20260929.json`.
- [~] Continue only when a source owner provides substantive guidance or the
  authorized endpoint/transport materially changes. No follow-ups were sent;
  rights, acquisition, and acceptance gates remain unchanged.

## Archived donor notice disposition (2026-10-04)

- [x] Record the maintainer's direction to keep both donor repositories
  archived and defer public successor-notice updates. The prepared wording
  remains local; no donor repository, tag, release, or dataset was mutated.
- [ ] Revisit only after a separate explicit authorization for the public
  notice change. This documentation decision does not change Australian
  federation acceptance or Stable v1 gates.

## M-112 post-denominator evidence reconciliation (2026-10-04)

- [x] Reconcile all 1,759 paths in the maintainer-approved qualification
  denominator between active and future-source ledgers. The denominator remains
  unchanged; all 1,719 previously deferred and 40 newly deferred candidates
  are explicitly registered. This is classification, not admission or rights
  evidence. See
  `quality/qualifications/australian-m112-additional-deferred-source-candidates-20261004.json`.
- [x] Crosswalk the hosted August 2026 MBS raw receipt and its two exact
  producer archive aliases to the current B1/B2 lifecycle. PR #750 completed
  and persisted the local GMA landed-to-accepted lifecycle; PR #751 joined its
  exact source identity to both aliases. The producer archive's historical
  records remain unchanged, and its root-manifest membership and source-Parquet
  projection lineage remain unresolved. PR #751 merged as `d75c905d`. See
  `quality/qualifications/australian-m112-mbs-lifecycle-crosswalk-20261004.json`.
- [x] Restore the anonymous pinned-revision July 2025 v4 source-receipt,
  manifest, and qualification metadata using source-native remote paths and
  separate local restore paths. Exact receipt and manifest hashes agree; the
  upstream qualification remains `candidate_only` with
  `public_v4_identity_unverified`. No source payload bytes were read and no
  admission or rights decision was made. PR #752 merged as
  `077cc68de7f5a20e43d3e9224ece80aef5800391` after all required hosted checks
  passed.
- [x] Preserve the October 3 current-state reconciliation as a dated snapshot.
  Add a later digest-bound M-112 addendum to incorporate the merged August MBS
  lifecycle crosswalk and restored July 2025 candidate receipt, superseding
  only the stale August lifecycle fields. The broader denominator, digest,
  rights, lineage, admission, and canary gates remain open. See
  `quality/qualifications/australian-m112-current-state-addendum-20261004.json`.
- [x] Refresh the July 2025 v4 identity against the live anonymous dataset
  head. All nine objects still match the historical hosted receipt's size and
  digest identities, and the current manifest metadata matches that receipt.
  The live dataset head is
  `1e4971c35c0ef45026168a8e2498d1bd57a3c324`; the immutable publication receipt
  remains pinned to `ba82cd1d0f9b0f28514df431b8da3a6c207d76fa`. This is valid
  for the existing verifier, which checks the historical receipt binding and
  current object identities without requiring head/revision equality. Identity
  is verified and the embedded candidate remains candidate-only; this is not
  M-112 admission or federation acceptance. The refreshed readback used
  metadata endpoints only and did not read source payload bytes or run
  canaries. See
  `quality/qualifications/australian-m112-live-public-v4-metadata-readback-20261004.json`.
- [x] Merge PR #755 (`8aa006d58a5f8809f0b0541a8ca921e84c96ec53`) after all 37
  protected checks passed. The review correction makes the addendum's
  supersession scope explicitly cover both the July v4 identity and August
  MBS lifecycle. M-112 remains blocked on source-specific rights, per-object
  rights and lineage, full-denominator digest readback, admission, and
  consumer canaries; no source values or payload bytes were read.
- [~] Keep M-112 federation acceptance blocked. Remaining gates are
  source-specific rights for historical PBS and reimbursement-atlas PBS
  records; per-object rights, receipts, B1/B2 lineage, and projection lineage
  across the full denominator; the July 2025 v4 metadata/object identity is now
  verified, but exact v4 admission plus consumer canaries remain open. The
  full-denominator anonymous digest gate remains open. The 20
  utilization-publication digest joins are publication receipts only and do
  not establish source rights or admission.

## M-107 historical snapshot coverage reconciliation (2026-10-05)

- [x] Reconcile the current metadata-only public tree inventory with official
  MBS download pages, PBS source-era documentation, source rights ledgers, and
  prior Health.gov workbook receipts. Record exact missing families and
  periods, retrieval state, rights state, and acceptance evidence in
  `docs/qualification/australian-mbs-pbs-m107-snapshots.md`.
- [x] Use the pre-authorized exact-main MBS schedule workflow for independent
  releases. Run `37282662744` added the `2026-11-01` schedule and verified 21
  cumulative objects with cleanup. Run `37282945693` selected nine recent
  release resources, added the `2026-01-01` schedule and two distinct
  `2026-03-01` XML revisions, and verified 27 cumulative objects with cleanup.
  Read back B1 receipts at the exact resulting revisions; do not treat the
  partial recent archive as a full release denominator.
- [x] Preserve the three Health.gov workbook zero-byte timeout findings and
  annual page/attachment period mismatch. Read back the Department inquiry
  thread; only outgoing messages were present. No unchanged workbook retries
  were made.
- [x] Record the PBS schedule schema-era ranges and exact April 2026 v3 object;
  record that older XML rights are unresolved, the API's 12-month route lacks
  retention/redistribution terms, and the separate PBS utilisation tree has
  six metadata-observed raw paths with per-object rights/lineage unresolved.
- [x] Reconcile all 82 distinct MBS-XML URLs listed across 41 current Downloads
  pages to B1 receipts in archive revision `da83cad9116e2f9a5b927be7b080e9a5e5ea6998`.
  The metadata-only readback checked 87 schedule receipt sidecars against the
  212-object manifest, found 82 exact source-URL matches, and found no
  unmatched URL or identity conflict. This closes the present-index link to
  receipt check, including the January/March/November 2025 releases; it does
  not prove a complete historical period denominator. See
  `quality/qualifications/australian-mbs-official-index-reconciliation-20261017.json`
  and `docs/qualification/australian-mbs-pbs-m107-snapshots.md`.
- [~] Keep M-107 blocked. The complete expected historical source/period
  denominator remains unresolved: historical MBS PDF/Word/software formats
  are not fully enumerated or covered by the existing MBS XML authorization;
  four current Downloads resources remain without source-specific rights or
  receipts; PBS schedule/API periods still lack source-specific rights and
  period-by-period receipts; and the Health.gov workbook families remain
  unavailable through the unchanged hosted route. Finish only after the
  expected source/snapshot denominator reconciles to exact source receipts,
  schema era, validity, retrieval, completeness, rights and immutable archive
  identities.

## M-105 recorded-disposition wording alignment (2026-10-17)

- [x] Align the parity-gap audit with D-006-07: the maintainer chose to keep
  M-105 blocked, continue M-106–M-112 independently, and grant no waiver or
  criterion change. The pre-archive sequence remains unsatisfied; no acceptance
  evidence or requirement was altered. The focused text assertions, Conductor
  context validation, and `git diff --check` pass.

## M-109 MBS archive inventory reconciled to latest append (2026-10-17)

- [x] Reconcile the metadata-only MBS source inventory to the latest M-108
  append receipt: revision `da83cad9116e2f9a5b927be7b080e9a5e5ea6998`, root
  manifest SHA-256
  `68e6bb97ee43117b860ff1c57e625a00075c734e933d08b3cd67de673432d055`, 212
  root objects. Record all 86 distinct schedule/P7 payload digests and 90
  manifest paths, keeping duplicate-digest aliases and different path
  identities visible.
- [x] Reconcile the four 2025 paths previously listed as missing: the January,
  March, and two November XML objects are present in the pinned archive
  manifest. Archive visibility alone does not verify official release
  provenance, complete history, semantics, rights beyond recorded scopes, or
  admission.
- [x] Add regression coverage binding M-109's pinned revision, manifest digest
  and object count to the M-108 append receipt and checking exact path/digest/
  byte identities for the four newly observed 2025 paths. Preserve the
  incomplete denominator, PBS rights boundary, and blocked M-109 acceptance.
- [ ] Continue source-era official release matching, field/temporal semantics,
  transformations, source-era denominator reconciliation, PBS-specific rights,
  and admission. The metadata refresh does not close M-109.

## M-112 approved MBS utilisation digest crosswalk (2026-10-17)

- [x] Bind all 14 exact-scope-approved MBS utilisation paths in the unchanged
  1,759-path denominator to the existing hosted anonymous digest-verification
  receipt at revision `dee9a5b0580dfe394474dc26b372559462e157e7`. The object
  paths, SHA-256 values, byte counts, source IDs, and authorization-scope
  matches reconcile to the per-object M-112 ledger and imported acquisition
  events. These 14 objects are already included in the 20-object digest
  reconciliation; full-denominator digest coverage remains incomplete.
- [x] Add a regression tying the rights-approved cohort to those exact digest
  receipt rows. The local reconciliation reads metadata and acquisition-event
  records only; it downloads no source bytes, reads no source values, and does
  not alter rights, lineage, v4 admission, consumer canaries, or M-112 status.

## M-112 July 2026 MBS source-object digest crosswalk (2026-10-17)

- [x] Bind the four July 2026 MBS source objects with existing anonymous
  digest readbacks to their exact rows in the 1,759-path per-object gate ledger.
  The regression verifies the pinned dataset revision, object size, and
  digest-evidence report identity while preserving unresolved exact-object
  rights/B1 binding, incomplete B1/B2 lineage, deferred disposition, and
  absent v4 admission and consumer canaries. No source bytes were downloaded
  and no source values were read. See the
  `m112_july_2026_mbs_digest_gate_crosswalk` evidence record.

## Australian qualification rebase validation (2026-10-17)

- [x] Rebase the consolidated M-109/M-111/M-112 evidence branch onto current
  `main` after PR #1092 merged. Preserve every distinct append-only record
  from both histories, retain the exact PR #1093 merge receipt, and verify
  the focused M-109/M-111/M-112 tests, broader M-112 tests, routine profile,
  typing, and context checks. No acceptance or rights state changed; see
  `australian_qualification_rebase_preservation_validation`.

## PR #1094 Gitleaks history finding disposition (2026-10-17)

- [x] Verify the two historical `generic-api-key` findings are the public
  revision identities recorded in the M-109 metadata readback, then add only
  their exact Gitleaks fingerprints to `.gitleaksignore`. Keep history
  scanning and all other findings fail-closed.
- [x] Add a regression that fixes the allowlist to those two fingerprints and
  documents the disposition without exposing matched values. Focused tests,
  routine Test Goblin, Ruff, diff checks, and a fresh full-history Gitleaks
  scan pass locally. Hosted verification is pending on the updated PR head.
- [x] Verify the updated exact-head hosted leak-detection check and all
  protected checks before merging. PR #1094 head `dde310c8` passed all 39
  checks, including Gitleaks and Codecov patch coverage, and squash-merged as
  `4781e94c`; the merge tree matches the tested head tree.

## M-112 historical canonical receipt projections (2026-10-17)

- [x] Build 14 deterministic historical `SourceReceipt` projections from the
  exact-scope-approved MBS cohort. Bind every projection to its indexed
  historical raw-reference sidecar, acquisition event, B1 harvest receipt,
  data.gov.au catalog metadata snapshot, exact rights decision, per-object
  denominator row, and existing B2 immutable public reference. Read no source
  payload bytes or values, perform no new acquisition, and classify every
  projection as `historical`; none satisfies the live-source gate. Preserve
  unknown sensitivity and review-required publication state.
- [x] Add regeneration/check mode and regressions for canonical serialization,
  all 14 identities, transformation-output identity, and historical/live gate
  separation. Rebind the source-contract fingerprint in the MBS lifecycle
  record and its M-112 dependent identity records; refresh the generated
  Bronze cohort projection without changing the 1,759-object denominator.
- [x] Verify the affected M-112/receipt/Bronze tests (113 passed), context
  validation, Ruff, `ty`, and BasedPyright. The full local Test-Goblin run
  completed with 6,501 passed, 3 skipped, and 3 failures: two release
  reproducibility cases could not find pinned uv 0.11.29 (both pass in an
  isolated rerun using that exact version); one Chromium benefits case passed
  on isolated rerun. Preserve the full-profile result as failed; hosted Linux
  CI remains required.
- [~] Keep M-112 blocked. These projections do not create native/live receipts,
  independent storage or restore evidence, v4 admission histories, consumer
  canaries, or full-denominator reconciliation. M-112 acceptance remains open.

## PR #1102 exact-manifest rights review correction (2026-10-17)

- [x] Close the review finding that a count-only 14-object check could have
  allowed a different cohort to inherit exact-scope permission. Validate the
  maintainer decision's dataset, revision, manifest path/digest, source counts,
  and rights disposition; bind the per-object rights list and receipt-sidecar
  join audit by their exact digests; then compare each source ID/category,
  path, payload digest, and byte count against both the approved rights row and
  manifest-join row before constructing a permitted historical receipt. Also
  bind the per-object gate identity to the same row.
- [x] Add negative tests for changed dataset/revision/manifest identity,
  object path, digest, size, and manifest-join controls. The expanded affected
  suite passed 121 tests; Ruff, BasedPyright, `ty`, context validation, and
  historical generator checks passed.
- [x] Run full Test-Goblin with pinned uv 0.11.29: 6,513 passed, 3 skipped,
  1 failed; coverage was 96.90%. The only failure was the PBS Chromium
  benefits browser timing out during close; its exact isolated rerun passed.
  Keep this recorded as a failed full profile. Hosted checks on the prior PR
  head passed; checks for the corrected head remain pending.
- [~] Keep M-112 blocked. The generated rows are historical projections, not
  native/live acquisition evidence. Independent storage/replication and
  restore proof, v4 admission histories, consumer canaries, and complete
  1,759-object reconciliation remain outstanding.

## PR #1111 Test-Goblin inventory correction (2026-10-17)

- [x] Classify the new M-112 historical receipt gate-crosswalk test module in
  the governed unit lane after the exact-head hosted run failed closed on the
  unassigned test file. Preserve the failed run as evidence; do not interpret
  downstream skipped uploads as separate failures.
- [x] Run the affected module (18 passed), Test-Goblin contracts including
  complete test collection (6,565 collected), and `git diff --check`. Rerun
  protected hosted checks on the corrected exact head before merging.
- [~] M-112 remains blocked pending current/live receipts, independent storage
  and restore evidence, v4 admission, consumer canaries, and full-denominator
  reconciliation.

## M-109 exact-main July/August MBS comparison (2026-10-17)

- [x] Merge PR #1117 after all 39 exact-head required checks passed. The
  squash merge is `0d665975ae504cbe681ae09817bfcff618d66640`.
- [x] Run the bounded exact-main workflow at that commit. Run
  [39043594884](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39043594884)
  completed successfully. Both official source identities matched their
  immutable archive digests and sizes, including the distinct August B1
  receipt path and B2 content-addressed path.
- [x] Read back aggregate-only reports. The July/August comparison report
  artifact `12105111369` records 6,045 matched records, one added record,
  5,445 changed records, no removed records, and aggregate counts for six
  changed native fields. Its report digest is
  `efeea889b3ce805c3a431073de02c78ba3b211157707750e0b3ab5948e2eb3c4`;
  the downloaded JSON artifact SHA-256 is
  `a80cfb25b88eb32a8fe1326c1f907328a37957ef542768d8367e6c39b5f9e6b2`.
  No source values or identifiers were retained, no local source payload was
  downloaded, and publication or admission did not occur.
- [~] Keep M-109 blocked. The separate candidate report remains `candidate_only`
  with release-linked field-semantic history and public v4 identity
  unverified. Structural comparison does not establish meanings, temporal
  semantics, the full MBS/PBS denominator, rights, Silver admission, or
  M-109 acceptance; continue those requirements against authorized evidence.
- [x] Parse the append-only evidence ledger, run Conductor context validation,
  and pass `git diff --check` after recording the hosted result.

## M-107 official historical-page inventory (2026-10-17)

- [x] Record page-level metadata from the Department's 2010–2019 historical
  landing page and the 2011–2019 year-page listings, totaling 120 listed PDF
  links. The 2018 count is from an official search-index excerpt because its
  direct page open timed out. This is metadata-only; no historical file or
  software payload was requested or downloaded.
- [~] Keep M-107 blocked. The official overview also refers to software files,
  the 2010 period and the complete historical MBS/PBS denominator are not
  reconciled, and the existing MBS publication authorization does not cover
  historical PDF/software retention or redistribution. Do not acquire those
  objects until source-specific rights and exact snapshot requirements are
  resolved.

## M-107 primary Downloads page resources (2026-10-18)

- [x] Compare the live official Downloads landing-page rows to the exact
  archive manifest and source-specific authorization. Record four top-level
  resources (two item-lookup files labeled `20261101`, re-use item map,
  historical information PDF) and zero matching source-URL receipts/archive paths at
  revision `da83cad`. This is metadata-only; no linked payload was requested
  or read. See
  `quality/qualifications/australian-mbs-primary-downloads-metadata-20261018.json`.
- [~] Keep the four resources unacquired pending a source-specific rights and
  publication decision. Continue independent expected-period and source-era
  reconciliation; M-107 remains blocked.

## M-107 PBS official schedule archive metadata inventory (2026-10-18)

- [x] Inventory all 24 official PBS schedule year pages linked for 2003–2026.
  The metadata-only read found 316 XML/API-CSV links across 197 schedule dates,
  including 88 version-unspecified XML links, 105 V3 links, 105 down-converted
  V2 links, and 18 API CSV links. No data-file link was followed. The observation
  is recorded at
  `quality/qualifications/australian-pbs-schedule-index-metadata-20261018.json`.
- [~] Keep acquisition and reuse blocked pending source-specific rights and
  retention decisions. Reconcile exact source identities for historical PBS
  eras not represented by these pages; a missing link is not evidence of source
  absence. This inventory does not establish the expected historical period
  denominator or M-107 acceptance.


## M-107 PBS schema-history metadata follow-up (2026-10-18)

- [x] Record the official PBS XML Schema v2.1 document's reported schema
  milestones beginning in December 2006 and the API information page's
  documented rolling 12-month schedule window. These metadata narrow the
  historical source-era gap but do not identify all required snapshots or
  establish source rights; see the value-free index qualification.
- [~] Continue reconciling exact historical schedule identities and receipts.
  M-107 remains blocked; do not infer absent coverage from missing archive-page
  links or the API's documented current window.

## M-112 August 2026 raw-object rights and lifecycle refresh (2026-10-18)

- [x] Refresh the exact 1,759-path M-112 per-object report from its preserved
  October 5 baseline using the current August source receipt, source-specific
  publication authorization, raw B1/B2 lifecycle crosswalk, anonymous digest
  reconciliation, and current public root-manifest readback. Keep the approved
  denominator unchanged and all 1,759 objects deferred pending v4 admission and
  consumer canaries.
- [x] Bind both August raw aliases to the existing `au-mbs` monthly-schedule
  authorization and exact permitted source receipt. The content-addressed XML
  path now records its complete raw B1/B2 chain and existing anonymous digest
  receipt. Keep the alias's direct anonymous digest and B1/B2 lineage gates
  open; shared Git blob identity and root-manifest metadata are not a separate
  payload digest receipt. Producer projection lineage remains unqualified.
- [x] Record the refreshed result in
  `quality/qualifications/australian-m112-per-object-gate-reconciliation-20261018.json`:
  two exact-source-rights rows, one complete raw B1/B2 row, zero v4 admissions,
  and zero consumer canaries. This does not create or expand rights, read or
  upload source bytes, admit objects, or accept M-112.
- [x] Validate the refresh with the focused M-112 tests (9 passed), the broader
  M-112/rights suite (81 passed), Ruff, `ty`, BasedPyright, context validation,
  and `git diff --check`. The full Test-Goblin run recorded 6,665 passed, 3
  skipped, and 2 failures because its subprocess selected uv 0.13.1 instead of
  pinned uv 0.11.29; both failed reproducibility tests passed in isolation with
  the pinned uv. Preserve the full-profile result as failed.

## M-105 hosted donor-history search follow-up (2026-10-18)

- [x] Recheck both donor repositories' complete available PR histories and
  hosted Actions metadata through their exact archive times. The scraper had
  14 pre-archive monthly runs, whose green workflow conclusions do not establish
  data success or GMA parity; the last run remains six 404s with no data commit.
  The graph history showed only two Dependency Graph runs and no functional
  parity workflow. PR #4/#5 (scraper) and #1/#5/#6 (graph) still do not cover
  all 54 baseline blobs and ten later changed paths. Details are in the
  [M-105 parity-gap audit](../../../docs/qualification/australian-donor-parity-gap.md).
- [~] M-105 remains blocked: this search found no full pre-archive parity proof.
  Keep the criterion unchanged and request a maintainer decision only if choosing
  a narrow chronology exception or an explicit criterion change. Continue
  independent M-106–M-112 work.

## M-112 August raw alias B1/B2 identity reconciliation (2026-10-18)

- [x] Bind the August legacy path to the canonical content-addressed raw
  object's existing source receipt and landed-to-accepted B1 lifecycle, its
  immutable B2 reference, exact shared Git blob/digest/size identity, and its
  own anonymous digest readback. Historical producer-archive records are
  preserved; source-Parquet projection lineage remains separately open.
- [x] Update the 1,759-path M-112 gate report to count two raw paths with
  complete shared-payload B1/B2 lineage. Both paths remain deferred; no v4
  admission, consumer canary, rights change, or acceptance is inferred.
- [x] Verify the focused crosswalk (7 passed), broader M-112/rights suite
  (79 passed), routine profile, Ruff, `ty`, BasedPyright, context/ecosystem
  checks, and `git diff --check`.
- [x] Merge PR #1144 after all 39 exact-head required checks passed. The
  verified squash merge is `c538472e4985454a434c22e51aa0f4c5ed47f2a8`.

## M-112 July metadata hosted readback reconciliation (2026-10-18)

- [x] Bind the hosted July lifecycle append to its exact main-branch workflow
  run, contract and authorization digests, anonymous digest verification,
  anonymous metadata readback, parent and final manifest identities, and the
  four approved July MBS raw-object paths. Preserve the parent manifest and
  verify the 16 metadata-only additions; no raw bytes were downloaded,
  retained, or uploaded locally.
- [x] Reject duplicate or widened identities across the frozen 1,759-object
  M-112 report and the contract, hosted object, raw digest, and metadata
  addition cohorts before indexing them. Conflicting duplicate rows are
  rejected regardless of ordering.
- [x] Produce
  `quality/qualifications/australian-m112-per-object-gate-reconciliation-20261018-post-july-readback.json`
  from the preserved prior report. Reconcile four additional exact source
  rights decisions and raw B1/B2 lineages while preserving all 1,759
  deferrals, the approved denominator, zero v4 admissions, and zero consumer
  canaries. Producer projection lineage remains separate and unqualified.
- [x] Address review findings by requiring successful B1 retrieval status and
  binding each B2 external reference to the exact dataset, parent revision, and
  raw object path. Add adversarial cases for failed retrieval and incorrect
  dataset, revision, and path.
- [x] Validate the refresh with 88 focused July-contract tests at 97.25% module
  coverage, 126 broader M-112 tests, Ruff, `ty`, BasedPyright, deterministic
  regeneration, and `git diff --check`. Do not repeat the previously recorded
  full local profile solely for this bounded qualification refresh.
- [x] Merge PR #1150 after all 39 exact-head required checks passed. The
  verified squash merge is `90766f14f49ee810be14d86df4368a02d3ffbdbe`.
- [~] M-112 and Stable v1 remain unaccepted by this raw B1/B2 metadata
  reconciliation; v4 admission, consumer canaries, projection lineage and
  full-denominator qualification remain open.

## M-111 current public MBS archive-head refresh (2026-10-18)

- [x] Refresh the public current-head identity after the July metadata append.
  Bind the public Dataset API main revision and root-manifest digest/count to
  the latest hosted M-112 readback, then recheck the nested July 2025 MBS
  product manifest and all eight product objects at that exact revision.
- [x] Verify six Parquet LFS digests and sizes using public tree metadata, and
  hash only the two small value-free JSON sidecars. No Parquet or source
  payload bytes were read. Preserve the unchanged candidate-only status and
  blocked API, CLI, Atlas and export consumer claims.
- [~] M-111 consumer acceptance remains blocked pending independently admitted
  product rights, full source-era coverage, freshness/cohort and confidence
  evidence, successful per-surface canaries, and public export restore.

## M-109 official release-change metadata crosswalk (2026-10-18)

- [x] Reconcile the official March, July, and August 2026 MBS release-page
  change notes into
  `quality/qualifications/australian-mbs-official-release-change-notes-20261018.json`.
  Preserve release/effective dates and item-level correction scope without
  requesting or reading XML payloads.
- [x] Add content-addressed metadata-only retrieval receipts for all three
  official pages, verify their recorded item/column tokens in the matching
  response, and test URL/status/length/digest binding without retaining page
  bodies. Record unresolved column-to-element and field-guide conflicts; update
  the MBS source-era register while preserving blocked M-109 status; assign the
  regression to the Test-Goblin unit lane.
- [x] Run the focused receipt regression and 110 broader M-109/MBS source-era,
  donor-disposition, and Test-Goblin harness tests; routine formatting, typing,
  context validation, JSON checks, and `git diff --check` pass.
- [~] M-109 still requires source-owner or exact-era schema clarification to
  map the documented changes to XML element semantics, plus the approved
  denominator, rights, and admission evidence. Release-page notes do not
  qualify field meaning or complete source-era semantics.

## M-105 narrow chronology waiver application (2026-10-18)

- [x] Apply the maintainer-approved D-006-10 waiver solely to the requirement
  that complete parity evidence predate either donor archive. The criterion is
  unchanged and no pre-archive complete-parity proof is claimed. The exact
  54-row baseline and ten-row changed-path denominator, final row dispositions,
  donor identities, licenses, archive history, and function-specific evidence
  remain required and bound by the waiver dossier.
- [x] Reconcile Stable v1 from the dossier: M-105 is verified under the narrow
  chronology waiver; M-106–M-113 and the Australian federation gate remain
  blocked. The release-readiness receipt remains blocked and no release or
  source-rights decision is inferred.
- [x] Validate 54 focused donor/Stable contract tests and 65 broader
  documentation/Test-Goblin harness tests; Ruff, formatting, JSON/JSONL,
  and `git diff --check` pass. Exact-head hosted checks are required before
  merge.
