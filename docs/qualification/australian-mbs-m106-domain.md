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

A separate Services Australia [Medicare Statistics catalog](https://data.gov.au/data/dataset/medicare-statistics) was created on 2026-09-23 and updated on 2026-09-24. Its [August 2026 - MBS Item Data resource](https://data.gov.au/data/dataset/medicare-statistics/resource/dbdde899-76ab-4d8d-a05a-46b51088b49e) carries a catalog license notice of CC BY 3.0 Australia. A metadata-only CKAN query with `limit=0` reported 26,391 records and fields for year, processing month, group, subgroup, item number, state, services, and benefit; it returned no records. The data dictionary is empty and no distinct-patient field appears in the schema. This is a current item-level statistics candidate, but its field meanings and patient denominator remain unqualified. The catalog license notice is not a project-specific rights decision. The [metadata receipt](../../quality/qualifications/australian-mbs-current-item-data-metadata-20260930.json) records that no CSV rows or source bytes were accessed, and no acquisition or derived publication was authorized.

The existing source-owner clarification request was rechecked by exact subject on 2026-09-29. Only the original sent inquiry matched; no inbound reply or attachment was observed, and no follow-up was sent. The [readback receipt](../../quality/qualifications/provider-response-m106-refresh-20260930.json) leaves source-owner clarification and M-106 acceptance pending.

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
existing `australian-mbs-utilisation-publication-authorization.json`. The
maintainer selected D-006-08 to keep the authorization scope unchanged: do not
acquire, retain, or publish the rolling-series workbook while awaiting a
corrected authorized link or substantive source-owner clarification. No scope
extension or licensing conclusion is made. The independently authorized
annual-series route remains subject to its current authorization and governed
transport constraints. Both period/link mismatches remain source questions;
neither page currently supplies a verified patient denominator or item-level
participant count. Keep M-106 blocked and do not repeat the previous endpoint
probes until the source endpoint or approved transport changes.

## Source-neutral aggregate measure contract, 2026-10-11

`src/global_medicines_atlas/mbs_measures.py` defines a candidate-only contract
for aggregate service and distinct-patient counts. It binds each observation
to a source revision, path, payload digest, receipt digest, and record
identity; keeps native integer text beside its typed value; requires explicit
time-basis evidence when the basis is source-defined; and represents
suppressed, unreported, or unavailable counts without turning them into zero.
The Arrow projection carries explicit `candidate_only` status and false
admission/publication flags. Extra fields such as person identifiers are
rejected.

The contract's tests use synthetic fixture identities and values only. They
verify count semantics, period bounds, deterministic Arrow projection, and
Parquet round-trip. No source payload or source row was read for this change.
This contract defines a safe shape for future qualification; it does not
establish any real distinct-patient denominator, item-level patient count,
source-specific meaning, rights, coverage, Silver admission, or publication.
M-106 remains blocked as recorded above.

## Public patient-statistics metadata recheck, 2026-10-16

The Department of Health, Disability and Ageing's [Medicare statistics
collection](https://www.health.gov.au/resources/collections/medicare-statistics-collection)
was last updated on 10 August 2026. Its public listing includes a 2025-26
per-patient bulk-billing dashboard and an annual dataset titled *Medicare GP
Non-Referred Attendances patient bulk billing ranges – Primary Health Networks
(2009-10 to 2025-26)*. The dashboard page describes a proportion of GP
non-referred-attendance patients fully bulk billed; the annual dataset page
describes patient bulk-billing ranges by PHN. These are bounded GP/NRA and
bulk-billing products. Their page metadata alone does not establish a distinct
patient denominator for the full MBS service domain, item-level patient counts,
or the exact count values and deduplication rules. No workbook or dashboard
payload was downloaded or inspected.

The Department's [2024-25 annual report](https://www.health.gov.au/sites/default/files/2025-11/department-of-health-disability-and-ageing-2024-25-annual-report.pdf)
states that each Medicare patient has a unique identification number and that
patient counts for its MBS population-access measure are extracted from
Medicare claims held in the Department's Enterprise Data Warehouse (EDW). The
published measure reports a percentage against ABS Estimated Resident
Population; it does not publish the underlying exact numerator in the cited
methodology. The PDF text was reviewed through the web reader at pages 91–92;
no local PDF copy was saved and no patient-level rows or source dataset values
were read. This identifies the Department's EDW as an authoritative source
owner lead, not as a public or project-authorized dataset.

On 2026-10-16, a value-free inquiry was sent to the Department's published
enquiry address asking whether an existing public or releasable aggregate
dataset provides exact, deduplicated distinct-patient counts for the required
MBS cohort and periods; how patients are deduplicated across items and
services; what suppression and coverage rules apply; and what reuse and
redistribution terms govern the exact dataset. The exact sent text and
message identity are preserved in
[`m106-department-patient-denominator-inquiry.md`](../../conductor/tracks/australian_health_source_consolidation_20260829/m106-department-patient-denominator-inquiry.md).
The Department's automatic receipt and the separate earlier routing update
were read on 2026-10-16; neither answers the denominator or reuse questions.
The corrected 2026-10-16 exact-subject readback searches from each inquiry's
send date, without sender restriction, and reads the complete Services
Australia thread. It found the original 2026-09-28 inquiry and an outbound
2026-10-05 follow-up, with no inbound Services Australia reply. The Department
auto-acknowledgement was in a separate reply thread and remains receipt-only.
No further messages were sent during the refresh. See the [current response
receipt](../../quality/qualifications/provider-response-m106-refresh-20261016.json).
Keep the two public
GP/NRA products as metadata-only candidates until their contents, source
denominators, and rights are confirmed. They are outside the existing annual
statistics authorization. Do not derive a patient count from a rounded
population percentage or treat item/service counts as people. For the separate
annual state-and-territory series, wait for source-owner clarification before
acquisition, then use its existing scoped authorization; do not require a
second rights decision unless the exact object or use falls outside that scope.

## Public candidate and provider status refresh, 2026-10-17

The live Department collection now lists [Medicare annual statistics – State
and territory (2009-10 to 2025-26)](https://www.health.gov.au/resources/publications/medicare-annual-statistics-state-and-territory-2009-10-to-2025-26?language=en),
published 10 August 2026 as a 2 MB Excel dataset. Its page says it presents
annual state/territory statistics for all services, out-of-hospital services,
patients, and broad service types. This is a stronger metadata lead for an
aggregate annual patient measure than the GP/NRA bulk-billing products, but
does not establish exact count meaning, deduplication across items/services,
coverage, suppression, or the exact workbook identity. The workbook was not
downloaded or inspected, and item-level patient counts are not claimed. The
existing [MBS utilisation publication authorization](../../quality/qualifications/australian-mbs-utilisation-publication-authorization.json)
covers this source family and the `medicare_annual_statistics_state_territory`
category; no new rights decision is required to acquire and publish within
that scope. This does not authorize the rolling series, Services Australia
item report, or other categories.

The collection page also links Services Australia's [Medicare item statistics
report](https://medicarestatistics.humanservices.gov.au/statistics/mbs_item.jsp),
which returned HTTP 503 when opened during this metadata-only check. No report
or data were retrieved; the failure says nothing about whether a patient
measure exists. The published [per-patient bulk-billing dashboard](https://www.health.gov.au/resources/publications/medicare-statistics-per-patient-bulk-billing-dashboard-2025-26?language=en)
is limited to the proportion of patients fully bulk billed for GP
non-referred attendances and does not supply the full-domain denominator.

Exact-subject mailbox searches on 2026-10-17 found only the Department's
automatic receipt for the denominator inquiry and the two sent messages in the
Services Australia item-count thread; no substantive provider clarification
has arrived. The detailed page, availability, authorization scope, and message
observations are in the [metadata refresh receipt](../../quality/qualifications/australian-mbs-m106-source-metadata-recheck-20261017.json).
Keep acquisition pending until substantive source-owner clarification
establishes the annual measure definition and exact workbook identity. Then
use the existing governed annual-series authorization; do not require a
redundant rights decision or extend that scope to other candidate sources.
M-106 remains blocked until the patient denominator and its semantics are
qualified.
