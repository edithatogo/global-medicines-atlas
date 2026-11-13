# AIHW PBS ATC2 monthly data

The publisher's previously unavailable monthly ATC2 ZIP was recovered on
13 November 2026. The original public ZIP is 88,904,070 bytes and has SHA-256
`30552d9f7e49e35787b2ac2719cf2177352fb1c38fe9e100127ce790b7ab1a0a`.
Its ZIP CRC check passed. It contains one 159,895,216-byte workbook with six
data tables. The reviewed PBS archive manifest has 1,076 entries and no payload
with this digest.

[Exact publication contract](../../quality/qualifications/aihw-pbs-atc2-monthly-public-20261113.json) ·
[Publisher data page](https://www.aihw.gov.au/reports/medicines/pbs-monthly-data/data)

The workbook's monthly columns run from **January 2015 to September 2026**.
Tables report prescriptions and government benefits per estimated resident
population for Australia, states and territories, and local government areas.
The LGA tables cover ages 0–18, 19–64, 65 and over, and all ages. Worksheet
dimensions recorded in the contract are declared workbook bounds.

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
GitHub Actions at the pinned PBS archive parent. It verifies the new objects
and preserves the previous manifest before removing temporary source copies.
The local recovery copy remains until the hosted anonymous digest verification
passes. The source is an AIHW public aggregate, and the contract excludes
participant and cohort-derived files.
