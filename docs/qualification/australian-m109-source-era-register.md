# M-109 Australian source-era register

Status: partial qualification; M-109 remains blocked. This register is an
evidence index and does not expand or silently reduce the approved denominator.

## Current denominator definition

The track initialization record defines MBS as the July 2025 XML, July 2024
four-sheet P7 workbook, and later approved snapshots. It defines PBS as the
existing minimal fixture plus governed PBS v3 source acquisition. That record
does not enumerate the later approved MBS snapshots or give the governed PBS
v3 corpus a complete list of required releases. Until those identities are
reconciled into a canonical source-era list, completeness cannot be counted.
Fixtures are not real-source evidence.

## Source-era evidence

| Source era | Native structure / denominator | Field meanings | Temporal semantics | Transformations | State and next evidence |
| --- | --- | --- | --- | --- | --- |
| MBS July 2025 XML v3 (`2025-07-version-3`) | Exact SHA-256 `db873768c5795222455033e2bad28586f19bbf2a10c7d58f06a0671d9111a556`; 5,989 records; 40 Silver fields; 239,560 field occurrences; six typed candidate tables. | Official XML field definitions are mapped across all 40 fields in the [field-semantics crosswalk](mbs-xml-v3-field-semantics.md). | Exact `DD.MM.YYYY` date grammar qualified over 11 native date fields; null, absent, and converted states kept distinct. Snapshot-relative flags and source dates do not prove current status. | Candidate projection and field lineage are bound to the exact source digest. Decimal/code/date candidate rules are not Silver admission. | Field meanings and date grammar qualified for this exact era; candidate-only. Complete admission, source lifecycle, and public derived-data rights remain separate. |
| MBS July 2024 Group P7 workbook | Exact SHA-256 `2f1cbc2d2dcbb93be86f42c8dbbe9f5f9e8fb550cad38b6ee54d0e9bdd2e27b8`; four sheets; 13,742 cells; 99 header/field mappings; four formula cells and two error cells in the recorded workbook profile. | Headers and typed candidate destinations are inventoried; source-specific meaning for P7 annotations and workbook-only fields is not qualified by the XML guide. | Four date columns have `DD.MM.YYYY` lexical shape. 1,276 values are calendar-valid under both DMY and MDY; no convention is selected. XML date semantics are not transferred. | Candidate status counts preserve unsupported dates, unrepresentable amounts, formulas and errors; no semantic promotion. | Structure/lineage only; archive storage is not source-origin acquisition. Await applicable source-owner date clarification; qualify workbook meanings and formulas separately. |
| PBS 2026-04-01 XML V3 archive member | Exact member digest and identity in the [PBS v3 date receipt](../../quality/qualifications/pbs-v3-2026-04-01-date-profile-qualification-20260929.json); 7,730,684 elements and 18,208,758 native fields. | Domain meanings, field-level mappings, and current-status interpretation remain unqualified. | ASCII date grammar profile qualified for the exact member only: 2,799 converted date values and one recognized slot absent. No intervals/current-state inference; 7,727,884 elements remain outside recognized date roles. | Structural/storage projections and Parquet round trips passed; domain projection remains a candidate. | Historical exact-member grammar only. Source-era field meanings and any cross-release transformation remain open. |
| PBS G2B XML 1.8 (2006-12 to 2012-10) | Era is documented in the source-transition receipt; no exact approved corpus profile is recorded here. | Unqualified. | Unqualified. | Unqualified. | Obtain/identify the approved source identities and exact-era schema evidence. |
| PBS XML 2.8–2.12 (2012-12 to 2017-08) | Era range documented; exact approved member denominator not reconciled. | Unqualified. | Unqualified. | Unqualified. | Reconcile exact approved source identities before profiling. |
| Alternate PBS XML 2.12 (2017-09 to 2018-08) | Distinct documented alternate era; no exact approved member profile recorded. | Unqualified. | Unqualified. | Unqualified. | Keep separate from mainline PBS XML 3.x and reconcile denominator. |
| PBS XML 3.x historical releases (from 2017-09) | April 2026 member is the only exact member qualified in this register; other releases are not enumerated. | Unqualified except for the exact date-role labels used by the narrow date profile. | The April 2026 date grammar result does not establish other release semantics. | No general v3 transformation accepted. | Enumerate each approved release/schema revision and qualify independently. |
| Current PBS public API / API CSV (model 3.7.8, observed 2026-08) | Current distribution metadata and model documentation reviewed; no payload requested or acquired. Public history is limited to the most recent 12 months per the recorded documentation. | Current API field meanings and crosswalk to historical XML remain unqualified. | Current-effective schedule and monthly update metadata are not a field-level temporal mapping. | No API transformation run. | Public access is documented, but project retention and external redistribution authority remain unresolved. Obtain provider clarification and a source-specific maintainer rights decision before acquisition. |
| Minimal PBS fixture | Synthetic fixture only; not a source era or real corpus. | Fixture contract only. | No real-source temporal evidence. | Test-only transformation behavior. | Must not count toward M-109 source-era completion. |

## Qualification rule

An era may be marked qualified only when exact source identity and native
denominators bind to source-backed schema, field meaning, temporal meaning,
and transformation evidence. Unsupported fields, absent values, formulas,
ambiguous dates, unresolved historical versions, rights limits and missing
releases remain explicit. A profile for one era cannot be inherited by another
because names or formats look similar. Silver acceptance stays blocked until
the approved source-era denominator is enumerated and every required era is
qualified.

The governing PBS-era and rights observations are recorded in the [PBS source
transition receipt](../../quality/qualifications/pbs-source-transition-20260929.json)
and [public API rights preflight](../../quality/qualifications/australian-pbs-api-public-access-preflight-20260929.json).
