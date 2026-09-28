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
