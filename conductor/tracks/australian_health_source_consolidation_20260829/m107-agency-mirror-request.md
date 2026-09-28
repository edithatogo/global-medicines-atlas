# M-107 agency-hosted endpoint inquiry

**Status:** sent 2026-09-28 to `enquiries@health.gov.au` from
`d.a.mordaunt@gmail.com`; the Department acknowledged receipt automatically,
but no substantive response or endpoint has been supplied. Sent and
acknowledgement receipts are recorded in
`quality/qualifications/provider-outreach-receipts-20260929.json`.

The maintainer selected an agency-hosted mirror as the M-107 delivery route.
This inquiry does not approve a new endpoint, expand source authorization, or
qualify a workbook.

**Subject:** Request for an agency-hosted automated retrieval route for Medicare
statistics workbooks

Hello,

We maintain Global Medicines Atlas, a research project that catalogs publicly
released Medicare statistics as source evidence. Our approved automated
acquisition workflow cannot currently retrieve the workbook attachments from
its hosted runner. A recent metadata-only HEAD check on the exact authorized
quarterly, annual and year-to-date workbook URLs timed out while waiting for
response headers on all three. It read no workbook bytes and followed no
redirects. We are seeking an agency-hosted mirror or another Department-approved
endpoint that the workflow can retrieve without using a workstation as a
source-byte cache.

Could you please identify an agency-controlled endpoint for the public State
and Territory quarterly, annual, and year-to-date summary workbooks, including
the historical releases needed to retain their published time series? We also
noticed that the annual publication page describes coverage through 2025-26,
while its linked attachment filename ends in 2024-25. We have not inspected the
workbook itself. Please confirm the intended period and whether the attachment
is current.

For the endpoint and files, please clarify:

- the exact reporting period and historical coverage for each workbook;
- how corrected or superseded releases are identified and retained;
- applicable public reuse terms and required attribution;
- whether stable URLs, file identifiers, checksums, or a machine-readable
  catalogue are available; and
- whether the endpoint is intended to support automated retrieval.

The project will preserve published workbook bytes and their source identities,
and will not infer missing coverage or treat these aggregate statistics as
patient-level data. Our currently approved domains are `health.gov.au` and
`data.gov.au`. If you recommend a different host, we will confirm that route is
explicitly authorized before acquisition.

For context, the Department's pages are [Medicare statistics collection](https://www.health.gov.au/resources/collections/medicare-statistics-collection),
[annual statistics](https://www.health.gov.au/resources/publications/medicare-annual-statistics-state-and-territory-2009-10-to-2025-26?language=en),
[quarterly statistics](https://www.health.gov.au/resources/publications/medicare-quarterly-statistics-state-and-territory-june-quarter-2025-26?language=en),
and [year-to-date tables](https://www.health.gov.au/resources/publications/medicare-statistics-year-to-date-summary-tables-july-to-june-2025-26?language=en).

Thank you,
Dylan Mordaunt
Global Medicines Atlas
