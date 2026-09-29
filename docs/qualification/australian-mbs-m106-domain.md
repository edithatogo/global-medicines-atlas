# M-106 independent MBS domain qualification, 2026-09-27

M-106 remains **blocked**. The admitted MBS XML establishes an independent
service-benefit source domain for the retained July 2025 and approved August
2026 XML snapshots. Their native fields do not contain
participant counts, and the historical HTML participant probe is synthetic or
failed-source evidence rather than a live participant denominator.

| Dimension | Current evidence | Qualified boundary |
| --- | --- | --- |
| Service/item and group | `MbsSourceRecord` retains `ItemNum`, `Category`, `Group`, `SubGroup`, `SubHeading`, and source ordinal. The approved August 2026 XML receipt records 6,046 admitted `Data` records. | Source-native service rows for that exact release; no medicine or PBS assertion. |
| Fee and benefit | The same source-native records retain `ScheduleFee`, `DerivedFee`, `Benefit75`, `Benefit85`, `Benefit100`, `BenefitType`, and related fields without renaming or imputing missing values. | Field preservation, not a claim that every field is populated in every row or a participant payment total. |
| Temporal state | `ItemStartDate`, `ItemEndDate`, `FeeStartDate`, `BenefitStartDate`, and other native date/change fields are retained. The receipt pins the August release identity. | Source values and release identity; no inferred effective interval where the source omits one. |
| Participant count | The XML schema's 40 named fields contain no participant-count measure. The donor's item/participant HTML endpoints have only compatibility fixtures and failed historical requests. | **Unqualified.** No zero count, missing patient inference, or item-level participation claim. |

The [hosted release and anonymous-verification receipt](https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-5467154799) binds the exact August payload, 6,046 rows, manifest, and public revision. The [source rights ledger](../../quality/qualifications/source-rights-review-ledger.json) authorizes only the exact content-addressed payloads named by its approval. It does not extend to another statistics workbook or HTML endpoint.

The Australian Government [Medicare annual state and territory dataset](https://www.health.gov.au/resources/publications/medicare-annual-statistics-state-and-territory-2009-10-to-2025-26?language=en) is a candidate *separate* patient denominator: its publication page describes annual patients, all services, out-of-hospital services, and broad service types by state and territory for 2009–10 through 2025–26. Its [explanatory notes](https://www.health.gov.au/resources/publications/explanatory-notes-for-medicare-statistics?language=en) govern calculation and interpretation. The maintainer's [MBS utilisation publication authorization](../../quality/qualifications/australian-mbs-utilisation-publication-authorization.json) already covers this source family and annual-statistics category. The [hosted utilisation harvest audit](stable-v1-blocker-audit-20260913.md) records that this workbook timed out and the published archive is partial. Neither authorization nor the page supplies an admitted patient denominator or item-level participant count.

Metadata discovery found the official Services Australia [MBS item reports](https://medicarestatistics.humanservices.gov.au/VEA0032/SAS.Web/statistics/mbs_item.html) and the catalogued [Items by Patient Demographics resource](https://data.gov.au/data/dataset/medicare-benefits-schedule-mbs-group-by-patient-demographics-report/resource/492b39de-8c97-4bbf-880e-e97d933daa9c). The catalogued field list contains item, state, age range, gender, services, and benefit; the resource data was last updated in 2016. The report description says item-level and demographic statistics are available and that small demographic groups are suppressed. This is a candidate for bounded item-service counts, not proof of distinct patient counts, current coverage, or project reuse rights. A [value-free source review](../../quality/qualifications/australian-mbs-item-demographic-source-review-20260929.json) records those limits and the sent inquiry to the published Services Australia statistics contact.

Next acceptance work is source-specific: recover the authorized annual workbook through the governed hosted path, verify its exact identity and native patient, service, geography, and period denominators, and preserve the source-specific rights basis. If item-level participant counts remain required, obtain source-owner clarification on a distinct-patient measure and qualify it separately from item services. Keep M-106 blocked until participant evidence and the remaining real-corpus field denominators have been checked.

## Official workbook link recheck, 2026-09-29

The exact observations and direct workbook targets are preserved in the
[metadata-only receipt](../../quality/qualifications/australian-mbs-workbook-link-drift-20260929.json)
(SHA-256 `d6a56898f06de71776848409943a06b3d3e09c84b06df2ab0c90a69a5983fd0e`).
The current official [annual state and territory page](https://www.health.gov.au/resources/publications/medicare-annual-statistics-state-and-territory-2009-10-to-2025-26?language=en)
still describes data through 2025-26 but its Excel link targets
`medicare-annual-statistics-state-and-territory-2009-10-to-2024-25.xlsx`.
The official [rolling 12-month page](https://www.health.gov.au/resources/publications/medicare-annual-statistics-rolling-12-months-july-2009-to-june-2026?language=en)
describes coverage through June 2026, while its Excel link targets
`medicare-annual-statistics-rolling-12-months-july-2009-to-march-2026.xlsx`.
The web reader exposed these link targets but could not parse either Excel
response's media type; no workbook bytes were retained or inspected. This is
metadata-only evidence and does not replace the earlier hosted timeout receipt.

The rolling-series category is not listed in the exact categories of the
existing `australian-mbs-utilisation-publication-authorization.json`. Do not
acquire or publish it under that record without a maintainer-approved scope
extension. Both period/link mismatches remain source questions; neither page
currently supplies a verified patient denominator or item-level participant
count. Keep M-106 blocked and do not repeat the previous endpoint probes until
the source endpoint or approved transport changes.
