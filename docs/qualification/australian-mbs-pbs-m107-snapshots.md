# M-107 Australian MBS/PBS snapshot inventory, 2026-09-27

M-107 remains **blocked**. An anonymously readable public revision proves an
object exists at that revision; it does not prove that every historical period
or source category was acquired. Read-only metadata checks on 2026-09-27
returned HTTP 200, `private=false`, `gated=false` for the three revisions below.
No source payload was downloaded during this audit.

| Source family | Pinned public evidence | Snapshot and completeness boundary |
| --- | --- | --- |
| MBS schedule/legacy | [`australian-mbs-source-archive` revision `c39dd99`](https://huggingface.co/datasets/edithatogo/australian-mbs-source-archive/tree/c39dd99ab8a6fcf557aeec391e1891b5fa18754f), [donor inventory](../../quality/qualifications/australian-health-donor-inventory.json), and [August release receipt](https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-5467154799) | Exact July 2025 XML and July 2024 four-sheet P7 workbook are retained as legacy; exact August 2026 XML has 6,046 admitted rows. Donor empty notebook/XML placeholders remain historical artifacts, not data coverage. The scheduled run revalidates only the authorized August release. This is not a complete monthly series. |
| MBS utilisation | [`australian-mbs-utilisation-archive` revision `7f8f6b7`](https://huggingface.co/datasets/edithatogo/australian-mbs-utilisation-archive/tree/7f8f6b7e973a0b5f68d6ddff9dfea6a0db61b697), [hosted run and receipt](https://github.com/edithatogo/global-medicines-atlas/actions/runs/34358783818), [authorization](../../quality/qualifications/australian-mbs-utilisation-publication-authorization.json) | Public manifest lists 14 historical group/demographics raw objects with paired B1 receipts. Three current health.gov.au quarterly, annual, and year-to-date workbooks timed out; the durable run receipt says `coverage_status=partial`. Historical group/demographics objects are not equivalent to the absent current patient workbook. The manifest currently omits the run failure status; the proposed publisher change records a bounded `latest_run_coverage` on future revisions, without rewriting this one. |
| PBS source | [`australian-pbs-source-archive` revision `31ec854`](https://huggingface.co/datasets/edithatogo/australian-pbs-source-archive/tree/31ec854ef9fc82f30a0dbe743fdf50a2e5bd24a7), [historical qualification audit](pbs-public-qualification.md) | Exact 1 April 2026 v3 ZIP, XML member, B1 receipt, and source-faithful Parquet are public. Historical qualification has failed at transport or timed out; published object identity is not a qualified historical series or complete schema-era comparison. |

The [official quarterly](https://www.health.gov.au/resources/publications/medicare-quarterly-statistics-state-and-territory-june-quarter-2025-26?language=en), [annual](https://www.health.gov.au/resources/publications/medicare-annual-statistics-state-and-territory-2009-10-to-2025-26?language=en), and [year-to-date](https://www.health.gov.au/resources/publications/medicare-statistics-year-to-date-summary-tables-july-to-june-2025-26) pages still advertise the three workbook categories. Page presence is discovery evidence, not byte acquisition or a successful snapshot. The annual page describes patients only at its own aggregate geography/time denominator; no item-level count follows from it.

Next acceptance work is to recover those three authorized workbooks through a supported hosted delivery path, retain failures and attempts as B1 evidence, and independently verify their bytes, schema-era labels, periods, and completeness. PBS historical qualification needs its separate transport recovery and schema-era checks. A complete M-107 claim requires an enumerated expected-period/source inventory, checked against actual receipts; the present public archives establish only the exact objects above.

The hosted utilisation publisher now requires discovery of all five authorized
source/category families before staging. A failed `data.gov.au` package query,
missing workbook category, or inaccessible publication page cannot yield a
`complete` run by silently reducing the selected-resource denominator.

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
M-107 remains blocked pending an independently verified, authorized hosted
delivery path and byte-level receipt for each missing workbook. Do not retry
the unchanged harvest merely to reproduce the page timeout.
