# M-107 Australian MBS/PBS snapshot inventory, 2026-09-28

M-107 remains **blocked**. An anonymously readable public revision proves an
object exists at that revision; it does not prove that every historical period
or source category was acquired. Exact public revisions and receipts below are
immutable archive evidence; the two utilisation follow-up receipts also record
anonymous digest verification and cleanup. No raw source payload was downloaded
during this inventory update.

| Source family | Pinned public evidence | Snapshot and completeness boundary |
| --- | --- | --- |
| MBS schedule/legacy | [`australian-mbs-source-archive` revision `c39dd99`](https://huggingface.co/datasets/edithatogo/australian-mbs-source-archive/tree/c39dd99ab8a6fcf557aeec391e1891b5fa18754f), [donor inventory](../../quality/qualifications/australian-health-donor-inventory.json), and [August release receipt](https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-5467154799) | Exact July 2025 XML and July 2024 four-sheet P7 workbook are retained as legacy; exact August 2026 XML has 6,046 admitted rows. Donor empty notebook/XML placeholders remain historical artifacts, not data coverage. The scheduled run revalidates only the authorized August release. This is not a complete monthly series. |
| MBS utilisation | Baseline [`australian-mbs-utilisation-archive` revision `7f8f6b7`](https://huggingface.co/datasets/edithatogo/australian-mbs-utilisation-archive/tree/7f8f6b7e973a0b5f68d6ddff9dfea6a0db61b697) and [hosted run](https://github.com/edithatogo/global-medicines-atlas/actions/runs/34358783818); [partial revision `32ce874`](https://huggingface.co/datasets/edithatogo/australian-mbs-utilisation-archive/tree/32ce8741be7f0508dca641a3e397759ec492da02) from [run 36330658537](https://github.com/edithatogo/global-medicines-atlas/actions/runs/36330658537) and [receipt](https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-5857370840); latest [partial revision `dee9a5b`](https://huggingface.co/datasets/edithatogo/australian-mbs-utilisation-archive/tree/dee9a5b0580dfe394474dc26b372559462e157e7) from [run 36333396964](https://github.com/edithatogo/global-medicines-atlas/actions/runs/36333396964), [receipt](https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-5857784415), and [cleanup receipt](https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-5857784489); [authorization](../../quality/qualifications/australian-mbs-utilisation-publication-authorization.json) | The baseline contains 14 historical group/demographics raw objects with paired B1 receipts. Both later exact-main revisions contain 28 verified objects and explicitly record `coverage_status=partial`. The latest manifest itself records four failed Health.gov resources and four staged resources under `latest_run_coverage`. The three direct official workbook requests—quarterly June 2025–26, YTD July–June 2025–26, and annual 2009–10 to 2024–25—timed out with zero bytes; the annual-family sentinel also remained unavailable. The annual attachment is older than the latest FY stated in its page title. Historical group/demographics objects are not equivalent to the missing Health.gov workbook families. These receipts prove the partial archive and cleanup, not current workbook acquisition or a complete series. |
| PBS source | [`australian-pbs-source-archive` revision `31ec854`](https://huggingface.co/datasets/edithatogo/australian-pbs-source-archive/tree/31ec854ef9fc82f30a0dbe743fdf50a2e5bd24a7), [historical qualification audit](pbs-public-qualification.md) | Exact 1 April 2026 v3 ZIP, XML member, B1 receipt, and source-faithful Parquet are public. Historical qualification has failed at transport or timed out; published object identity is not a qualified historical series or complete schema-era comparison. |

The exact-main [P7 workbook qualification](../../quality/qualifications/mbs-p7-workbook-field-lineage-20260929.json)
now verifies the pinned July 2024 candidate's four-sheet, 13,742-cell
denominator and 99 value-free field mappings. Its lineage remains
`candidate_only`, and its date profile is unset. This adds structural evidence
for one legacy snapshot; it does not repair the missing Health.gov utilisation
workbook families or establish complete/current M-107 coverage.

The [official quarterly](https://www.health.gov.au/resources/publications/medicare-quarterly-statistics-state-and-territory-june-quarter-2025-26?language=en), [annual](https://www.health.gov.au/resources/publications/medicare-annual-statistics-state-and-territory-2009-10-to-2025-26?language=en), and [year-to-date](https://www.health.gov.au/resources/publications/medicare-statistics-year-to-date-summary-tables-july-to-june-2025-26) pages still advertise the three workbook categories. Page presence is discovery evidence, not byte acquisition or a successful snapshot. The annual page describes patients only at its own aggregate geography/time denominator; no item-level count follows from it.

Next acceptance work is to recover those three authorized workbooks through a supported hosted delivery path, retain failures and attempts as B1 evidence, and independently verify their bytes, schema-era labels, periods, and completeness. PBS historical qualification needs its separate transport recovery and schema-era checks. A complete M-107 claim requires an enumerated expected-period/source inventory, checked against actual receipts; the present public archives establish only the exact objects above.

The hosted utilisation publisher now requires discovery of all five authorized
source/category families before staging. A failed `data.gov.au` package query,
missing workbook category, or inaccessible publication page cannot yield a
`complete` run by silently reducing the selected-resource denominator.

## Read-only delivery preflight, 2026-09-28

A bounded metadata-only `HEAD` request from the maintainer workstation reached
the three exact official workbook URLs with HTTP 200 and the expected Excel
content type. The quarterly workbook returned `Content-Length: 3160065`, the
year-to-date workbook `85783`, and the annual attachment `1058479` bytes. The
annual URL still names the 2009–10 to 2024–25 workbook; its publication page is
titled through 2025–26. No response body was requested, so these headers do
not establish content digests, workbook integrity, or source-byte acquisition.

Metadata-only CKAN `package_search` queries for each of the three exact
filenames returned no matching Medicare package/resources on data.gov.au. This
found no alternate catalogued mirror and confirmed local route availability,
while the prior hosted harvest still timed out on the same file requests. The
current failure is therefore narrowed to the hosted-runner delivery path; this
check does not prove the GitHub Actions route is fixed. Do not repeat the
unchanged harvest. A dedicated manual exact-main Actions workflow now probes
these exact URLs using `HEAD` only, with a 15-second request timeout, no
redirects, no dataset token, and no source-body reads. It records only response
status, bounded content length and an Excel content-type validity flag. Its
hosted result must be observed before another authorized byte-acquisition
attempt. No local workbook bytes were downloaded.

Review hardening wraps each individual request in a 15-second wall-clock
deadline as well as HTTP operation timeouts, so a slow-drip response is retained
as a finite timeout result rather than consuming the whole Actions job. A
synthetic slow-response test and invalid-deadline cases cover that boundary.

The first [exact-head hosted attempt on 2026-09-27](https://github.com/edithatogo/global-medicines-atlas/actions/runs/36321857806)
at `234f4a44a915877ac95c7668b4445fb368417f3b` passed repository/authority
binding and both `data.gov.au` package queries. Its bounded health.gov.au
publication-page discovery returned zero workbook URLs after about 110 seconds;
the job failed before staging, publication, or cleanup. The prior public
utilisation revision is unchanged. A read-only workstation HEAD check returned
HTTP 200 for the annual publication page and its exact linked workbook URL,
`https://www.health.gov.au/sites/default/files/2026-08/medicare-annual-statistics-state-and-territory-2009-10-to-2024-25.xlsx`;
the resolved URL was identical and HEAD reported 1,058,479 bytes. A separate
bounded GET of the page returned its Excel link. The page title ends 2025–26
while the workbook filename ends 2024–25, so the workbook's period is not
qualified from page metadata. This local observation does not explain or
overcome the hosted delivery failure. A [metadata-only Actions diagnostic](../../.github/workflows/mbs-publication-page-diagnostic.yml)
probed only that pinned official publication page with 12- and 30-second
whole-probe deadlines. The [exact-head hosted run on 2026-09-27](https://github.com/edithatogo/global-medicines-atlas/actions/runs/36323531387)
at `d8114f1a243a057b7497ba1e84601b481720d34d` completed successfully as a
diagnostic; its retained artifact reports `wall_clock_timeout` for both attempts
and no publication. Its `workbook_requested=false` field was not independently
supported because the first probe allowed a same-host redirect to a workbook;
the timeout artifact retained no redirect chain. The corrected diagnostic
confines redirects to the same publication-page path and rejects non-HTML
responses before reading their bodies. Its [new exact-head hosted run](https://github.com/edithatogo/global-medicines-atlas/actions/runs/36324451674)
at `a4af1dfe30cd0f43093a541ada0d1198801276dc` again recorded
`wall_clock_timeout` at both 12 and 30 seconds, with no workbook request or
publication. This confirms the annual-page transport failure under the
corrected request boundary.
The annual-page discovery route therefore remains unavailable from that
hosted runner; this does not establish whether the other two pages or a
different authorized transport would succeed.

A read-only `data.gov.au` CKAN package search for the exact phrases
`Medicare annual statistics`, `Medicare quarterly statistics`, and
`Medicare statistics year-to-date` returned zero matching packages on
2026-09-27. This bounded metadata search found no verified mirror for the
three workbooks; it does not prove no alternate official distribution exists.
The exact-main direct-fallback run [36333396964](https://github.com/edithatogo/global-medicines-atlas/actions/runs/36333396964)
later resolved page discovery by selecting the three official file links, but
all three file requests timed out with zero bytes. Its anonymous receipt and
cleanup receipt are linked in the table. Do not repeat this unchanged harvest
merely to reproduce the same file-download timeout. M-107 remains blocked
pending an independently verified, authorized hosted delivery path and
byte-level receipt for each missing workbook.

## M-107 current snapshot and rights reconciliation (2026-10-05)

This is a gap reconciliation, not a complete expected-period denominator. The
latest inventory explicitly enumerating Australian public archive paths is
`quality/qualifications/australian-m112-current-tree-object-inventory-20261004.json`;
it reports metadata and object identities and does not read source payloads.
Where it lists exact objects below, presence and the reported digest/size
match are metadata-readback evidence, not a new source acquisition or a
source-specific rights conclusion.

| Source / missing snapshot | Retrieval and current evidence | Rights status | Acceptance evidence still required |
| --- | --- | --- | --- |
| MBS monthly schedules: missing known official releases `2025-01-01`, `2025-03-01`, and both `2025-11-01` XML revisions | The official pages identify exact files: [January 2025 `MBS-XML-20250101`](https://www.mbsonline.gov.au/internet/mbsonline/publishing.nsf/Content/Downloads-250101); [March 2025 `MBS-XML-20250301`](https://www.mbsonline.gov.au/internet/mbsonline/publishing.nsf/Content/Downloads-250301); and [November 2025 `MBS-XML-20251101.XML` (released 3 October) plus `MBS-XML-20251101 Version 2.XML` (released 28 October)](https://www.mbsonline.gov.au/internet/mbsonline/publishing.nsf/Content/Downloads-251101). The October 5 nine-page exact-main harvest [37282945693](https://github.com/edithatogo/global-medicines-atlas/actions/runs/37282945693) selected nine resources, published revision `44b25bfd87e44998c7c1da4c3930ad4447e9246f`, verified 27 cumulative objects anonymously, and removed temporary bytes. Its exact-revision metadata inventory includes `2026-01-01`, both `2026-03-01` XML revisions, `2026-07-01`, `2026-08-01`, and `2026-11-01`; it contains no object for the three missing page families above. The successful harvest receipt has no per-page failure inventory, so page-level retrieval errors cannot be asserted. | The maintainer's `australian-mbs-harvest-publication-authorization.json` covers `au-mbs`, `mbsonline.gov.au`, and `monthly_schedule_xml`; it records publication authorization and asserted redistribution permission. | These missing releases need exact B1 receipts, publication at an immutable revision, anonymous digest verification, cleanup, and captured supersession order. The two November revisions are separate source snapshots, not one interchangeable file. |
| MBS schedule: acquired recent release revisions | The October 5 nine-page run's exact-revision metadata inventory and source receipt sidecars bind `2026-01-01` (8,215,319 bytes; SHA-256 `352448dc912b3e2125f2acd56b6094da13de7f229022a498c21848a0fcdc2299`), two `2026-03-01` revisions (8,271,294 bytes / `e6ed9cf794a73e0a9d10c6ffca931f29cce899d720fb7377fe4f5d64dc2b9561` and 8,271,558 bytes / `252a06590143428ab49aca79302dc0f1e4e4c2726cf36859d1673e6521e31ded`), plus previously present July/August 2026 snapshots. The first exact-main harvest [37282662744](https://github.com/edithatogo/global-medicines-atlas/actions/runs/37282662744) separately acquired `2026-11-01` and verified the full 21-object cumulative archive; the second run [37282945693](https://github.com/edithatogo/global-medicines-atlas/actions/runs/37282945693) verified all 27 cumulative objects and removed temporary bytes. | Same MBS schedule authorization as above. | These recent exact objects now have hosted receipts and anonymous byte verification. This does not close earlier/later release gaps or the complete official index denominator. |
| MBS schedule: existing legacy/current set | The October 4 exact-tree inventory includes donor July 2025 XML, July 2026 XML, August 2026 XML, July 2024 P7 workbook, and July/August 2026 supplements. The October 5 hosted harvests add January/March/November 2026 XML. July 2025 and July 2024 donor artifacts are covered by `australian-health-legacy-publication-authorization.json`; current XML schedule and supplements are covered by the MBS harvest authorization. These objects do not establish every MBS release: official history is linked back to 1974. | Publication authorization exists for the recorded scopes; no claim that archive membership proves source rights beyond those authorization records. | Build the official release-date denominator across the Downloads index and historical pages, reconcile every effective release with exact object receipts, and retain explicit unavailable/empty states. |
| MBS historical PDF/Word and pre-2020 software/print releases | The official [2010–2019 page](https://www.mbsonline.gov.au/internet/mbsonline/publishing.nsf/Content/MBSOnline-2010) links year-specific 2011–2019 file pages; the official [Previous Downloads page](https://www.mbsonline.gov.au/internet/mbsonline/publishing.nsf/Content/Prev-Downloads) lists individual and bundled historical MBS publications from 1974–2010. The period/resource denominator has not been extracted page-by-page and no such files were acquired by this review. | The current MBS harvest authorization covers XML schedule, Basic Service Description and RVG categories only; the legacy donor authorization covers its exact two donor payloads. Neither authorizes the historical PDF/Word family as a whole. | Enumerate exact files, source dates, bundles and schema/format roles. Resolve source-specific retention and publication rights before acquiring or publishing out-of-scope files; preserve multi-period PDFs as bundled artifacts rather than inventing a single-period identity. |
| MBS utilisation: historical group and demographic snapshots | The current October 4 tree inventory records 14 raw objects: group data for 1993–2015 and July 2016; demographics for 1993–2012, 2016 Q1–Q3; and workbook companions for 2016 Q1–Q3. Latest hosted harvest revision `dee9a5b0580dfe394474dc26b372559462e157e7` contains 28 anonymously verified objects and is explicitly partial. | The source/category authorization covers `au-health-medicare-statistics`, `au-data-gov-mbs-group`, and `au-data-gov-mbs-demographics`, including group/demographics categories. This is publication authorization; period completeness and source-specific reuse terms are not thereby established. | Reconcile the official agency inventories and period labels to these exact paths and receipts; retain absent or failed periods as such. Do not infer coverage from the 14 object count. |
| MBS utilisation: quarterly June 2025–26, year-to-date July–June 2025–26, annual State/Territory 2009–10 to 2024–25 workbook | Exact official categories are the [June-quarter 2025–26](https://www.health.gov.au/resources/publications/medicare-quarterly-statistics-state-and-territory-june-quarter-2025-26?language=en), [YTD July–June 2025–26](https://www.health.gov.au/resources/publications/medicare-statistics-year-to-date-summary-tables-july-to-june-2025-26), and [annual](https://www.health.gov.au/resources/publications/medicare-annual-statistics-state-and-territory-2009-10-to-2025-26?language=en) workbook. All three direct workbook GETs timed out with zero bytes in [run 36333396964](https://github.com/edithatogo/global-medicines-atlas/actions/runs/36333396964); the corrected metadata-only endpoint probe [36452243269](https://github.com/edithatogo/global-medicines-atlas/actions/runs/36452243269) timed out before receiving headers. The 2026-10-05 Department follow-up is in the existing email thread; a readback found only sent messages and no agency reply. The annual page advertises 2025–26 while its linked attachment filename ends in 2024–25. | Category and domain are covered by the MBS utilisation publication authorization; the exact workbook identity/period mismatch, applicable terms and any agency-supported mirror remain unconfirmed. | Do not retry while endpoint and transport are unchanged. Obtain an agency-supported route or a demonstrable transport change, resolve the annual workbook identity and reuse/attribution terms, then require exact bytes, period/schema-era inspection, B1 receipts and independent verification. |
| PBS schedule: legacy schema eras and missing versions | Official documentation records G2B XML 1.8 (`2006-12`–`2012-10`), PBS XML 2.8–2.12 (`2012-12`–`2017-08`), alternate 2.12 (`2017-09`–`2018-08`), and v3 from `2017-09`. The public archive presently has one exact schedule snapshot: `2026-04-01` v3 at revision `31ec854ef9fc82f30a0dbe743fdf50a2e5bd24a7`. Earlier era-specific objects are not identified in the archive inventory. Official documentation says legacy XML/text distribution is discontinued. | `source-rights-review-ledger.json` marks `au-pbs-historical-xml` as `catalogue_only`, with redistribution, transformation, and source-byte publication `unknown`; no maintainer source-rights approval exists. The historical April 2026 publication's past authorization and public visibility do not expand future rights. | Resolve source-specific rights first. Then identify exact official or approved mirror URLs and exact effective dates, acquire only through hosted controls, qualify each schema era separately, and bind every object to source-native identity, receipt, rights, validity, and anonymous digest readback. |
| PBS schedule: current public API rolling history | Official distribution documentation says the public Schedule API replaced XML/text and exposes effective schedules for the latest 12 months. No API payload was requested or acquired in this review; exact month/object identities were not enumerated. | Public access and local copy to the user's own systems are documented, but retention duration, external redistribution, and a source-specific maintainer rights decision remain unresolved in `australian-pbs-api-public-access-preflight-20260929.json`. | Resolve retention and redistribution rights and define the exact rolling-period snapshot denominator before any B2 retention or public publication. Keep API model versions separate from XML schema eras. |
| PBS utilisation/expenditure snapshots already in the public archive | The October 4 current-tree inventory reports six raw paths: expenditure reports for 2023–24 and 2024–25; DOS pharmacy-type CSVs for July 2024–June 2025 and July 2025–June 2026; a DOS summary workbook for July 2021–June 2026; and `pbs-item-drug-map.csv`. The latter has a byte count and Git blob identity but no LFS SHA-256 in the observed tree. The `date_of_processing_historical` category is authorized but no corresponding archived raw path appears in that inventory. | The PBS utilisation publication authorization covers its listed source/category/domain families and asserts redistribution permission. M-112's per-object rights and lineage reconciliation still reports rights unresolved; archive visibility is not a rights grant. | Reconcile each path to its source receipt, period, exact payload digest and rights record; recover the missing processing-history category only after its exact source and rights are established. Resolve the item-map digest gap. |
| Donor empty placeholders and failed-source records | Empty notebook/XML placeholders remain identified by the pinned donor inventory and donor Git history; they are not analytical snapshots and are not among the non-empty payloads in the MBS public archive authorization. The MBS utilisation manifest retains the three failed Health.gov resources and unavailable family sentinel as partial-run evidence. | Keep donor objects under their pinned donor provenance/licence records; failed-source metadata carries no payload rights. | Preserve exact donor paths, zero-byte state and provenance where useful; keep failure records in B1. Neither placeholders nor failures count as acquired snapshots. |

### M-107 decision

The independently obtainable evidence is now reconciled without repeating the
unchanged Health.gov requests. Two exact-main MBS harvests passed, adding the
November 2026 release and recent January/March 2026 revisions; both anonymous
receipts and the final cleanup receipt were read back. The official January,
March, and both November 2025 XML releases remain missing despite being listed
on official pages; the harvest receipt does not identify per-page retrieval
errors, so the next safe step is to improve page-level failure reporting and
target only those exact URLs. The broader MBS historical page families from
1974 onward also need an enumerated format-aware denominator. Existing PBS utilisation snapshot
metadata is individually enumerated, but per-object rights and lineage remain
open. PBS historical XML eras and current API periods lack the rights or exact
source identities needed for further acquisition. The MBS/PBS expected-period
denominator is still incomplete; M-107 remains **blocked** until exact source
inventories, retrieval receipts, source-specific rights and schema-era
acceptance evidence reconcile across every required snapshot.

The manual exact-main [HEAD-only egress run](https://github.com/edithatogo/global-medicines-atlas/actions/runs/36376037675)
at merged commit `fa924f0d7ff31b5009fedf5816b5af1f31523425` timed out on all
three direct workbook URLs at the 15-second per-request deadline. Its durable
[bounded receipt](https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-5863107539)
records no redirects, no response-body reads, and no publication. The first
probe deliberately omitted transport exception details, so it cannot yet tell
whether the timeout occurred during connection setup or response handling. A
follow-up records only finite timeout-stage labels; it will not retry a byte
download or infer a DNS/network-policy cause.

The second [classified HEAD run](https://github.com/edithatogo/global-medicines-atlas/actions/runs/36377031967)
on commit `254cf7c1c66c069daa95153957661c1e15e88452` labeled all three results
`wall_clock`. Its 15-second HTTP operation timeout equaled the hard deadline,
so the deadline could mask the underlying HTTP phase. The next bounded probe
uses shorter operation timeouts (7.5 seconds general, at most 5 seconds to
connect) beneath the same 15-second request cap; it still reads no body and
retains no exception detail.
