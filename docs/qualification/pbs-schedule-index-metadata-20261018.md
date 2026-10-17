# PBS schedule-index metadata observation, 2026-10-18

The official [PBS schedule archive](https://www.pbs.gov.au/publication/schedule/archive)
links year pages for 2003–2026. A metadata-only read of all 24 pages found 316
links labeled as PBS XML or PBS API CSV, spanning 197 distinct schedule dates.
The exact page and link identities, page digests, and retrieval boundaries are
in [`australian-pbs-schedule-index-metadata-20261018.json`](../../quality/qualifications/australian-pbs-schedule-index-metadata-20261018.json).

The page labels expose 88 XML links without a stated version from April 2007
through August 2017; 105 links labeled XML V3 and 105 labeled V2 down-converted
from September 2017 through May 2026; and 18 API CSV links from April 2025
through September 2026. The paired V2 links are explicitly down-converted
representations. Unversioned XML labels are not assigned a schema era by this
observation. A linked file's label does not prove its actual schema or contents.

The XML links stop at May 2026 in this archive-page capture while API CSV links
continue through September 2026. The Department's [API notice](https://www.pbs.gov.au/news/2024/12/new-pbs-schedule-data-api-and-api-csv-files)
describes monthly API and CSV distribution and replacement of older formats.
The official [PBS XML Schema v2.1 document](https://data.pbs.gov.au/download/88817), dated 28 April 2008, lists earlier schema milestones beginning with version 1.1.1 in December 2006, then versions 1.3, 1.4 and 1.5 during 2007. This establishes a schema-document history before the archive index's first XML link in April 2007, but it does not identify every schedule release or prove that a public release exists for each milestone.

The [PBS API information page](https://data.pbs.gov.au/api/pbs-api.html), updated 11 December 2025, says the API contains every effective schedule for the most recent 12 months. That is useful for bounding the API's documented current window; it does not establish a complete historical series or GMA retention and redistribution rights. The schedule archive, schema history and API window therefore provide distinct partial evidence, not a complete approved PBS denominator. Missing archive links remain non-evidence of source absence elsewhere.

No schedule XML, API CSV, ZIP, or schedule PDF payload was fetched or read. Historical XML reuse remains unknown, and current API retention and redistribution remain unauthorized pending source-specific provider clarification and the required maintainer rights decision. No source semantics, Silver admission, M-109 or M-107 acceptance, or publication status changed.
