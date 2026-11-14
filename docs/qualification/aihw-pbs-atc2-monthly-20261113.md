# AIHW PBS ATC2 monthly data

The publisher's previously unavailable monthly ATC2 ZIP was recovered on
13 November 2026. The original public ZIP is 88,904,070 bytes and has SHA-256
`30552d9f7e49e35787b2ac2719cf2177352fb1c38fe9e100127ce790b7ab1a0a`.
Its ZIP CRC check passed. It contains one 159,895,216-byte workbook with six
data tables. The reviewed PBS archive manifest has 1,076 entries and no payload
with this digest.

[Exact publication contract](../../quality/qualifications/aihw-pbs-atc2-monthly-public-20261113.json) ·
[Publisher data page](https://www.aihw.gov.au/reports/medicines/pbs-monthly-data/data)

Each of the six tables has 141 monthly columns from **January 2015 to September
2026**. Counting worksheet rows after the title and field headings gives 688
national rows, 5,504 state and territory rows, and 93,912 rows in each of the
four LGA tables, for **381,840 data rows**.
Tables report prescriptions and government benefits per estimated resident
population for Australia, states and territories, and local government areas.
The national and state tables identify the prescription group, age band and
measure. The LGA tables identify state, LGA code and name, prescription group
and measure, with one table each for ages 0–18, 19–64, 65 and over, and all ages.

The archived AIHW environmental PBS extract uses **weekly** periods and SA4
geography, with count and crude-rate fields. It is a different public
representation from the monthly LGA and age tables inspected here. This
comparison does not establish value-by-value equivalence across the archive.
AIHW notes that later releases can revise monthly values for claim and population
updates. [Publisher data page](https://www.aihw.gov.au/reports/medicines/pbs-monthly-data/data)

Source: Australian Institute of Health and Welfare. AIHW makes downloadable
website material available under CC BY 4.0, subject to the exclusions and any
separate terms described on its copyright page. The archive receipt retains
the source, attribution and licence references with the original ZIP.
[AIHW copyright](https://www.aihw.gov.au/copyright) ·
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

The authorised operation appends the ZIP and its source receipt through
GitHub Actions at the pinned PBS archive parent. The first hosted acquisition
failed at the AIHW download server. The reviewed recovery route uses an
unpublished GitHub draft containing the same public ZIP, with its exact asset
identity, length and digest checked before staging. The workflow verifies the
new objects and preserves the previous manifest before temporary source copies
are removed.
The local recovery copy remains until the hosted anonymous digest verification
passes. The source is an AIHW public aggregate, and the contract excludes
participant and cohort-derived files.
