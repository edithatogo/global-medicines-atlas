# Draft request: Medstat export response format

**Status:** prepared, not sent. Denmark's bounded internal acquisition and
retention authority remains limited to source-generated aggregate result
exports with exact query parameters. No result bytes are attached or included.

**Suggested recipient:** `kontakt@sundhedsdata.dk`, published on the official
[Medstat site](https://medstat.dk/).

**Subject:** Clarification of Medstat interactive Excel export response format

Hello,

We are validating the documented Medstat interactive export for a bounded
aggregate query. For the 2025 national turnover result, requesting the primary
and hospital sector strata in one source-generated export returned HTTP 200,
with a suggested `.xls` filename and `text/html;charset=UTF-8` response type.
A bounded structural diagnostic transiently read the 4,446-byte response to
count HTML elements. It did not emit the response text or retain the bytes. It
found one source-titled HTML document containing a single table, but no forms
or interactive controls.

Could you confirm whether this response is an intended HTML-formatted
spreadsheet that Excel is expected to open, or an error/fallback page? Please
also identify the documented response format or media type for the supported
interactive export route and whether the selected 2025 query across the primary
and hospital sectors is supported as one export.

We will keep the response rejected until its format is confirmed. We will not
publish the data or expand the approved query scope.

For reference, we reviewed the public Medstat landing page, its “Datagrundlag
og beskrivelse” page, and the “Download” page. The last page lists supporting
metadata CSV files; it does not document the interactive result export's
response format.

Thank you,
Dylan Mordaunt
Global Medicines Atlas
