# Legacy Group P7 workbook date convention inquiry

**Status:** MBS Online replied on 2026-10-13 asking for the official webpage
identifying the workbook. A value-free follow-up with the July 2024 downloads
page was sent on 2026-10-17; the workbook-specific date convention remains
unconfirmed. The original sent-message receipt is in
`quality/qualifications/provider-outreach-receipts-20260929.json`; the reply and
follow-up metadata are recorded in
`quality/qualifications/mbs-workbook-date-source-owner-clarification-20261017.json`.
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

## Follow-up sent 2026-10-17

MBS Online requested the webpage where the named workbook is available. The
official [July 2024 MBS downloads page](https://www.mbsonline.gov.au/internet/mbsonline/publishing.nsf/Content/Downloads-240701)
was provided, and the source owner was asked to confirm whether this workbook
edition uses day-month-year, month-day-year, or has no documented convention.
No workbook bytes or cell values were sent. No date profile was selected.

## Boundary

The inquiry included no source cell values or workbook bytes. Sending it does
not change the approved source scope, authorize acquisition or publication,
select a date profile, or establish semantic promotion.
