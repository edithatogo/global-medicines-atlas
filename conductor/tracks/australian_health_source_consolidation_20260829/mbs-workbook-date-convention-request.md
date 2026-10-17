# Legacy Group P7 workbook date convention inquiry

**Status:** MBS Online replied on 2026-10-13 asking for the webpage identifying
the workbook. The first reply supplied the official July 2024 downloads page,
but that page does not list the P7 workbook; it was contextual, not an exact
workbook locator. A second value-free follow-up supplied the exact pinned donor
archive path, commit, and digest while explicitly distinguishing that archived
copy from Department publication. Official provenance and workbook-specific
date convention remain unconfirmed. The original sent-message receipt is in
`quality/qualifications/provider-outreach-receipts-20260929.json`; the reply and
follow-up metadata are recorded in
`quality/qualifications/mbs-workbook-date-source-owner-clarification-20261017.json`.
The original inquiry text below incorrectly described the workbook as
identified in the public July 2024 MBS downloads. The official page does not
list the P7 workbook; the first reply supplied it only as contextual
information, and the second reply supplied the exact donor-archive locator.
This correction preserves the historical message while making its locator
error explicit.

The official XML specification documents
`DD.MM.YYYY` for XML fields but does not establish the convention for the
separate legacy Group P7 workbook. Keep the workbook date profile unset until
source-specific evidence is obtained.

**Proposed recipient:** `enquiries@health.gov.au`  
**Subject:** Date convention for July 2024 MBS Group P7 workbook

Hello,

Could you please confirm the date convention used in the legacy July 2024
Medicare Benefits Schedule Group P7 (Genetics) workbook, specifically whether
its textual dates are day-month-year or month-day-year? The workbook is
identified in the public July 2024 MBS downloads as `MBS - 2024.07 - Group P7
(Genetics).xlsx`.

The MBS XML documentation specifies `DD.MM.YYYY` for XML date fields, but we
have not assumed that convention applies to this separate workbook. A
value-free structural check found 1,276 date cells calendar-valid under both
orders and four valid only under day-month-year. No cell values are included
here. Please point us to documentation or confirm the convention for this
workbook edition.

We will retain the source-native text and leave semantic date conversion
disabled until the workbook-specific convention is documented. We have not
attached or transmitted workbook contents.

Thank you,
Global Medicines Atlas

## First follow-up sent 2026-10-17

MBS Online requested the webpage where the named workbook is available. The
official [July 2024 MBS downloads page](https://www.mbsonline.gov.au/internet/mbsonline/publishing.nsf/Content/Downloads-240701)
was provided, and the source owner was asked to confirm whether this workbook
edition uses day-month-year, month-day-year, or has no documented convention.
No workbook bytes or cell values were sent. No date profile was selected.

## Second follow-up sent 2026-10-17

The official downloads page did not list P7, so a second value-free message
identified the exact donor-archived copy:

- Repository: `edithatogo/aus-health-data-scraper`
- Commit: `931da0b9b6ae3e3cec0743568abb71a50d62b7cf`
- Path: `data/source/MBS - 2024.07 - Group P7 (Genetics).xlsx`
- Pinned [GitHub object](https://github.com/edithatogo/aus-health-data-scraper/blob/931da0b9b6ae3e3cec0743568abb71a50d62b7cf/data/source/MBS%20-%202024.07%20-%20Group%20P7%20(Genetics).xlsx)
- SHA-256: `2f1cbc2d2dcbb93be86f42c8dbbe9f5f9e8fb550cad38b6ee54d0e9bdd2e27b8`
- Size: 87,727 bytes

The question asks MBS Online to confirm or deny Department provenance for this
exact copy and, if confirmed, its date convention; otherwise, to state that it
cannot confirm. The GitHub locator proves only the identity of a donor-archived
copy, not Department authorship or publication. No workbook bytes or cell
values were sent, and no date profile was selected.

## Boundary

The inquiries included no source cell values or workbook bytes. Sending them
does not change the approved source scope, authorize acquisition or
publication, select a date profile, or establish semantic promotion.
