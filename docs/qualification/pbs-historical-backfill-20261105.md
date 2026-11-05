# PBS historical backfill proposal — 5 November 2026

The maintainer requested assessment of the DataPlace PBS search and the longest
available file history. This is a scoped resumption of utilisation discovery and
backfill preparation, not general federation, licence approval or publication.

## Relevance and historical scope

| Source family | Located scope | Relevance |
| --- | --- | --- |
| Services Australia PBS Item Report | Historical ZIPs labelled 1992–2014; 2015; July 2016 YTD | PBS/RPBS item service counts and benefits by state/territory |
| Services Australia PBS Patient Category Report | Historical ZIPs labelled 1992–2014; 2015; July 2016 YTD | Service counts and benefits by patient category |
| Services Australia PBS ATC Report | Historical ZIPs labelled 1992–2014; 2015; July 2016 YTD | Service counts and benefits by ATC classification |
| PBS Date of Supply | Six annual CSVs labelled 2020–21 through 2025–26; current summary labelled July 2022–August 2026 | Dispensing utilisation; retain supply-period meaning |
| PBS Date of Processing | ZIP labelled January 2018 YTD | Historical processing series; exact contents uninspected |
| PBS expenditure | 13 spreadsheet attachments discovered across annual pages | Prescription and expenditure reports; preserve each page's period |

[DataPlace search](https://www.dataplace.gov.au/search/?q=pbs&sort=0)
contains 44 results. Portfolio Budget Statements are an unrelated expansion of
PBS. Restricted PBS claims/AIHW collections are relevant conceptually but are
not open aggregate downloads and are excluded. The open opioid and antimicrobial
Atlas 2015 products are useful derived geographic rates for 2013–14, not a
replacement for these historical series. Ex-manufacturer prices are price data,
not utilisation.

The three legacy catalogue records are
[Item](https://data.gov.au/data/dataset/14b536d4-eb6a-485d-bf87-2e6e77ddbac1),
[Patient Category](https://data.gov.au/data/dataset/ecb895fa-e512-4f96-bd66-38ee055f5784)
and [ATC](https://data.gov.au/data/dataset/13ef77a2-acfe-4016-a9a3-cfe6c3850a13).
Their metadata advertises CC BY (`cc-by`); this records the publisher label,
not a maintainer licensing conclusion or a release grant.

## Frozen candidate inventory and checks

[Candidate inventory](../../quality/qualifications/australian-pbs-historical-backfill-candidates-20261105.json)
binds 42 exact URLs: 20 legacy resources and 22 PBS-site resources. All 42
returned HTTP 200 to HEAD on 5 November 2026, with zero payload bytes read.
HEAD does not prove a valid ZIP/workbook/CSV, its member periods, completeness,
fixity or coverage. Earliest **located advertised** utilisation history is 1992;
no claim is made that every year, item or measure is present or that no earlier
series exists. Preserve CSV and Excel as separate representations, avoiding
double-counting observations. Do not join processing and supply series without
source-era qualifications. The 2016–2020 transition remains a coverage question.

The official [annual index](https://www.pbs.gov.au/statistics/expenditure-prescriptions/pbs-expenditure-and-prescriptions)
also links PDF/DOC reports for 2002–03, 2003–04 and 2004–05 and annual pages back
to 2005–06. Those document resources are outside the 42-file executable candidate
cohort. Older pages may contain additional attachments not matched by the
spreadsheet-name filter. The current cohort is therefore not the complete
historical PBS document denominator.

## Implementation and remaining execution gates

`--backfill-all` previously retained a two-page expenditure limit. It now checks
up to 64 index-linked pages; default rolling discovery still checks two. The
link matcher now includes historical `expenditure-and-prescriptions` and the
publisher's `pb-expenditure` spelling. A regression verifies both rolling and
historical selection. Existing discovery still skips failed annual pages;
absence from its result cannot establish historical completeness.

The existing publication grant permits named PBS-site sources only. It does not
permit these additional data.gov.au legacy families. No grant was edited, source
payload downloaded, scheduled job changed or workflow dispatched in this work.
The current source archive and frozen federation denominator remain unchanged.

The latest recorded scheduled harvest
[38791779376](https://github.com/edithatogo/global-medicines-atlas/actions/runs/38791779376)
failed on 15 October 2026: `Workbook payload exceeds 33554432 byte limit`.
The current summary HEAD advertises a workbook larger than that limit. Do not
raise archive limits or bypass validation without qualifying bounded processing.
Exact source rights, immutable append behavior for changing filenames, safe
archive/member inventory, per-file digest receipts, hosted-only publication,
anonymous readback and cleanup must pass before backfill completion.

Next execution packet: acquire and inspect all authorized candidates on the
hosted runner, retain failed files, inspect historical ZIP member coverage and
record missing periods. Publish additional legacy objects only after explicit
exact-cohort approval. Stop at the acquisition/publication gate or the workbook
safety blocker, with no Stable v1 or semantic promotion.

## Ownership and validation

Chat `01a1aa8f-ba44-78f1-a79b-e14bd3e07236` owns this scoped discovery fix,
candidate inventory and report in the standard Git worktree
`/Volumes/PortableSSD/GitHub/gma-pbs-historical-backfill`, branch
`codex/pbs-utilisation-historical-backfill`. Managed-worktree creation did not
accept the available arguments; the standard Git fallback is not app-managed.
The original `codex/61-fda-status-history` checkout was preserved. Native scope:
read-only public metadata and workflow history; no authentication renewal or
native writer operation. Next operation: protected technical PR, followed by
maintainer decision on the exact additional publication cohort.

Python 3.15.1 was selected through this worktree's `.venv/bin/python`, a read-only
reference to the retained qualified environment; environment contents were not
changed. Test cache remains worktree-local. `tests/test_australian_harvesting.py`:
76 passed; one expected duplicate-ZIP-member fixture warning. Focused lint passed;
format initially identified one new line wrapping issue, subsequently corrected.
No broad profile was run for this bounded discovery change.

## Additional maintainer links — 5 November 2026

The repeated Item and Medicare Statistics links resolve to the same respective
catalogues. A fresh CKAN search filtered to `organization:servicesaustralia`
returns five PBS matches: the three legacy reports, Medicare Statistics and DHS
Annual Reports. The three legacy reports are already in the 42-file candidate
inventory; none of this establishes that their payloads have been archived.

[Additional catalogue metadata](../../quality/qualifications/australian-utilisation-additional-catalogues-20261105.json)
records the exact resource identities and URLs from the three additional named
catalogues, without acquiring payloads:

- Medicare Statistics: 227 resources, including 100 with PBS in their names.
  Listed PBS resources range from July–December 2015 ATC data to September 2026
  item data. These 100 resources are outside the 42-file inventory. Existing
  M-106 documentation assessed an August 2026 MBS resource as metadata only;
  that is not acquisition evidence for this catalogue's PBS resources.
- Medicare Benefits Schedule Statistics: one legacy Health.gov landing-page
  reference, not one acquired statistical data file. MBS source-family work
  exists separately and does not establish complete capture of this link.
- DHS Annual Reports: 28 resources, including report PDF/ZIPs and section ZIPs.
  Relevant health activity context; no exact catalogue acquisition evidence was
  located in this bounded repository check. Keep separate from item utilisation.

The AIHW search opened in the internal browser but rendered no result entries
in the observed search-results region. Its full result set remains unverified;
no blanket claim of inclusion is made. Open derived tables need individual
identity/rights checks; restricted claims/linkage collections remain excluded.
The unfiltered data.gov.au search is discovery, not a fixed dataset or proof
that every result is relevant or included. Additional acquisition/publication
scope remains pending; the prior 20-file publication question is unanswered.

## Publication execution approved — 5 November 2026

The maintainer explicitly approved including and publishing additional legacy
files and relevant Medicare Statistics data to the existing HF archive, completing
historical backfill as far as possible, resolving the workbook blocker and checking
AIHW results. This supersedes the pending-publication statements above. The grant
now names the three legacy families and the PBS subset of Medicare Statistics;
MBS/enrolment records are not relabelled as medicines or added to the PBS archive.
The frozen additional cohort contains 120 resources (20 legacy, 100 PBS statistics).

Full official annual-page discovery now inventories all linked spreadsheets,
PDF/DOC reports and ZIPs, preserving URL identities and annual-page paths. The
metadata-only discovery receipt contains 505 candidates: 376 annual-report files,
9 DOS/DOP/reference files and the 120 additional resources. Index-linked reports
start in 2002–03; legacy ZIP labels start in 1992. Payload/member qualification is
pending the hosted run; these counts are discovery, not acquired coverage.

Large raw workbooks use a separate metadata-only archive validation profile:
256 MiB compressed, 4 GiB declared uncompressed, the existing 20,000-member and
8 MiB metadata-member limits, required OOXML roots and duplicate-member rejection.
No worksheets are inflated or parsed by this profile. Default analytical limits
remain 32 MiB/128 MiB. Downloads read at most 256 MiB plus one sentinel byte.
Historical ZIP member names, sizes and CRC metadata are recorded without extraction.
This is raw preservation, not a semantic or exhaustive archive-integrity assessment.

Each payload is stored under a SHA-256 version directory. Previously archived
paths and source receipts are retained; unchanged versioned objects are skipped.
The existing HF parent and its revision-pinned manifest must be read successfully
before publication; no fallback dataset creation occurs. Per-file transport or
validation failures are retained as partial coverage rather than erasing successes.

AIHW's own search again rendered no result entries. An official-domain search
located the monthly PBS report, medicines overview, environmental weekly PBS
series, mental-health prescribing and restricted PBS data-collection metadata.
The monthly data page states historical monthly tables from May 2002 to January
2015, and revisions caused by late/updated claims and resident-population estimates.
Its download list is JavaScript-populated and remained empty in the observed page;
its script request did not yield the application bundle. This is a concrete
unresolved download-discovery limitation, not proof that no tables exist.
Reference: https://www.aihw.gov.au/reports/medicines/pbs-monthly-data/data
AIHW derived rates and restricted record-level collections remain distinct from
Services Australia aggregate counts; no restricted data were requested or published.

Focused validation: 111 harvesting/context tests initially passed and one new
annual-path test failed because its fixture linked the same absolute URL twice.
The fixture was corrected to distinct annual URLs; the failure-only rerun passed.
Ruff and the two changed Python modules' BasedPyright checks passed before final
formatting. Hosted protected checks and actual backfill remain pending.

### AIHW download discovery recovered through publisher API

The earlier dynamic-list limitation is superseded by the
[read-only API receipt](../../quality/qualifications/aihw-pbs-monthly-resource-discovery-20261105.json).
The publisher's `dataOrResource.js` exposes
`POST /api/search/all-downloadable-resources`. Using the monthly page's component
attributes returned four resources: ATC1 and ATC2 ZIPs for January 2015 onwards,
and ATC1 and ATC2 workbooks for May 2002–January 2015. The initial query's
`filterByItemNodeGUIDs` array produced HTTP 400; using the required string type
returned four results. Each exact-file HEAD returned HTTP 403. This qualifies
metadata discovery, not GET availability, payload fixity or publication. AIHW
source files are outside this approved PBS/Medicare publication-host cohort.

Final-head Codecov patch coverage reported 82.35% against 90.01%, despite all
38 other checks passing. Added focused negative tests for the uncovered annual
page-failure behavior and the raw profile's payload/expansion limits; no gate or
limit was weakened. Reuse the unchanged successful behavioral checks locally;
protected CI runs on the updated head.
