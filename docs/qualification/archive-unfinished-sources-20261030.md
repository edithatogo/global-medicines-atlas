# Unfinished source acquisition — 30 October 2026

The maintainer explicitly extended the finite acquisition scope to the 100 source
IDs previously classified `needs_source_recipe` or `needs_source_review`. This
supersedes the earlier small-batch stop for this lane only. Federation remains
deferred; original federation and Stable v1 gates are unchanged.

## First qualified batch

Thirteen sources, 39 immutable native files, acquired using the shared batch runner:

| Batch | Sources | Exact scope |
|---|---|---|
| cms-medicaid-20261030 | MDRP, NADAC | Q2 2026 product table; 28 October 2026 NADAC export |
| singapore-register-20261030 | HSA register | Complete response, 5,511 records; no product documents |
| colombia-register-20261030 | INVIMA | Current valid CUM registration export |
| brazil-register-20261030 | ANVISA | Published DATAVISA medicines CSV |
| brazil-conitec-20261030 | CONITEC | Published 2012–first-half-2025 demand-status ZIP |
| japan-mhlw-20261030 | NHI price, NDB utilisation | Five current price files; 21 medicine quantity tables from tenth NDB release |
| sweden-tlv-20261030 | TLV | Complete current price/subsidy export; no individual decision PDFs |
| who-eml-20261030 | WHO EML | 2025 adult and children model lists |
| east-africa-eml-20261030 | Kenya, Uganda | National lists published in 2023 |
| who-mi4a-20261030 | WHO MI4A | 2026 public purchase dataset and vaccine product list |

Exact URLs, source terms, reuse observations and attribution are retained in each
`quality/source-batches/<batch>/` directory. Local preparation does not count as
public archival. Only successful hosted publication with anonymous per-file
verification establishes that result.

The runner now accepts finite, same-host HTTPS multi-file selections. Every file
has its own receipt, digest and resume validation; the publisher packages every
selected object. No crawler, background schedule or new framework is introduced.

Initial failures are retained: MDRP and Colombia exceeded the original 64 MiB
bound; their explicit bound is now 512 MiB. CONITEC returned
`binary/octet-stream`, now accepted by this runner. Core receipt contracts and
historical acceptance bindings are unchanged.

Local validation: 134 focused acquisition/publication tests passed; all 39
payload digests verified, ZIP/XLSX member CRC checks passed, Singapore response
record count equals its declared total. Metadata-only validation evidence is
`quality/qualifications/archive-unfinished-first-batch-20261030.json`.

The next three clear-rights sources are the WHO 2025 adult/children EML PDFs,
Kenya EML 2023 and Uganda EMHSLU 2023. Their embedded licences explicitly permit
noncommercial reproduction with attribution; separate archive notices preserve
that restriction. WHO exposed a catalogue/receipt mismatch: `GLOBAL` now maps to
the repository's existing `GLB` receipt code without changing the receipt schema.

Hosted CI found three stale derived-ledger assertions after catalogue recipe
updates. Regenerate the prompt audit and bounded future ledger, and update their
exact expected queue counts. Catalogue-wide rights remain unresolved; exact batch
rights do not authorize every object or historical release in a source.

## Continuing inventory

The remaining 87 entries have individual assessments being finalised, including four with
previously retained private evidence. An absent recipe is unfinished engineering,
not an external blocker. Public access alone is not a redistribution licence.
No source is counted complete merely because a landing page was fetched.

WHO MI4A uses the WHO dataset terms for public-health-purpose reproduction and distribution. It is not relabelled under the separate data.who.int licence. Original anonymisation, attribution and restrictions remain attached. Both XLSX files passed digest and ZIP member integrity verification.
