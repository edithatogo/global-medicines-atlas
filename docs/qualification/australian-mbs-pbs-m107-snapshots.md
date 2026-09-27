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
