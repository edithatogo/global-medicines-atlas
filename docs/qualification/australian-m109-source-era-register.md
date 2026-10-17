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

The metadata-only identity inventory dated 2026-10-17 now reconciles to the
latest M-108 MBS archive append receipt: revision
`da83cad9116e2f9a5b927be7b080e9a5e5ea6998`, with a 212-object root manifest
whose SHA-256 is
`68e6bb97ee43117b860ff1c57e625a00075c734e933d08b3cd67de673432d055`. The
manifest exposes 86 distinct MBS schedule/P7 payload digests across 90 exact
paths. This is a **known-object inventory**, not the complete expected-release
denominator or an official-release match for every path. Four paths previously
listed as absent are now present in archive metadata (January and March 2025,
and both November 2025 XML revisions); their presence does not by itself prove
official provenance, full historical coverage, semantics, or admission. PBS
historical releases are still not enumerated, and the current PBS API rolling
window has no source-specific retention or redistribution decision. The
inventory records these distinctions and does not convert public archive
visibility into rights or admission. See
[`australian-m109-source-era-identities-20261017.json`](../../quality/qualifications/australian-m109-source-era-identities-20261017.json).

### Known exact identities at the pinned public revisions

| Source family | Exact objects observed | Rights and qualification boundary |
| --- | --- | --- |
| MBS schedule and P7 | 86 distinct payload digests across 90 paths in the current MBS archive root manifest. This includes the July 2024 P7 workbook; July 2025 XML v3; 2025 January, March, and November XML objects; and all other schedule XML objects observed in that manifest. The August 2026 payload has both a content-addressed path and a legacy alias with the same digest and byte count. The exact per-object paths, digests, and byte counts are in the metadata-only identity inventory. | The two donor payloads are exact-item covered by the legacy authorization; schedule XML objects retain the recorded `monthly_schedule_xml` authorization basis. Only July 2025 v3 has the recorded full source-field semantic crosswalk and six-table value parity; identity and category authorization do not transfer those semantics to another release. |
| PBS historical schedule | One April 2026 XML v3 member in the current archive revision `48fd7345fb09277bb5b85644dba72804633a2abb`; the manifest SHA-256 is unchanged at `e6c9abbc62bd44fc47049306a92cc8efc9700031908586262c2b82a907546460`. | The exact member has a date-role profile only. The source-rights ledger still records historical XML reuse as unknown, so it is listed as observed evidence, not as an approved M-109 processing denominator. |
| PBS historical eras and current API | Exact required release identities are not yet enumerated. | G2B 1.8, XML 2.8–2.12, alternate 2.12, later XML 3.x, and the current rolling API remain distinct. No API payload was requested or acquired; retention and redistribution decisions remain open. |

The MBS archive's observed file list is not a complete official schedule
history. Although archive metadata now lists the four 2025 paths previously
missing from the inventory, the full official history and expected-period
denominator remain unreconciled. The PBS archive contains one known schedule
snapshot and cannot establish its historical denominator. Therefore exact
identities for currently held objects are now recorded, while expected-period
completeness, source-era semantics, and M-109 acceptance remain open.

## Source-era evidence

| Source era | Native structure / denominator | Field meanings | Temporal semantics | Transformations | State and next evidence |
| --- | --- | --- | --- | --- | --- |
| MBS July 2025 XML v3 (`2025-07-version-3`) | Exact SHA-256 `db873768c5795222455033e2bad28586f19bbf2a10c7d58f06a0671d9111a556`; 5,989 records; 40 Silver fields; 239,560 field occurrences; six typed candidate tables. | Official XML field definitions are mapped across all 40 fields in the [field-semantics crosswalk](mbs-xml-v3-field-semantics.md). | Exact `DD.MM.YYYY` date grammar qualified over 11 native date fields; null, absent, and converted states kept distinct. Snapshot-relative flags and source dates do not prove current status. | Exact-main Test-Goblin run [38908829291](https://github.com/edithatogo/global-medicines-atlas/actions/runs/38908829291) on merge `2666e6e026867be99d85f1e32bc9b381afe50efc` emitted value-free artifact `public-mbs-source-silver-tables-parity-receipt` (artifact 12048749308; SHA-256 `0743f6039e3da1d5bac05d013f3fd629d22da94df014033cdac66b0bb19ef5b6`). The exact receipt is preserved durably in [the repository qualification](../../quality/qualifications/mbs-source-silver-tables-parity-2025-07-v3.json) with that same SHA-256 and is validated against Pydantic and JSON Schema. It binds the pinned source revision and Silver manifest, compares the canonical six tables (`services`, `hierarchy`, `descriptions`, `fees`, `benefits`, `caps`), and reports 5,989 rows per table with source-to-candidate value parity. | Field meanings and date grammar qualified for this exact era; six-table source-to-candidate parity is verified, but remains candidate-only. The receipt does not establish rights, production admission, publication, promotion, completeness across other eras, or full M-109 acceptance. |
| MBS August 2026 XML (`2026-08-01`) | Exact SHA-256 `c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565`; 8,293,331 bytes; exact B1 receipt and hosted B2 archive identity. A new exact-main candidate workflow compares the pinned archive bytes with the official release and emits aggregate six-table counts and lineage digests only. | Not yet accepted. Existing XML documentation is a reference for review, not proof that each August field retained the July 2025 meaning. | The candidate does not select or transfer a date grammar; exact-era date and temporal semantics remain unqualified. | Candidate qualifier and focused tests are implemented in `scripts/qualify_mbs_source_era_candidate.py`; the exact-main hosted run remains pending merge and readback. It is read-only and retains no source bytes. | Source identity is authorized and receipt-backed; semantic crosswalk, temporal qualification, transformation parity, and M-109 acceptance remain open. The approved source-era denominator and historical snapshot set are incomplete. |
| MBS July 2024 Group P7 workbook | Exact SHA-256 `2f1cbc2d2dcbb93be86f42c8dbbe9f5f9e8fb550cad38b6ee54d0e9bdd2e27b8`; four sheets; 13,742 cells; 99 header/field mappings; four formula cells and two error cells in the recorded workbook profile. | Headers and typed candidate destinations are inventoried; source-specific meaning for P7 annotations and workbook-only fields is not qualified by the XML guide. | Four date columns have `DD.MM.YYYY` lexical shape. 1,276 values are calendar-valid under both DMY and MDY; no convention is selected. XML date semantics are not transferred. The official July 2024 downloads page does not list P7. A second value-free contact supplied the exact pinned donor-archive copy (commit `931da0b9b6ae3e3cec0743568abb71a50d62b7cf`, 87,727 bytes, same SHA-256) and asked MBS Online to confirm or deny Department provenance and, if confirmed, the date convention. Neither message confirms provenance or convention. | Candidate status counts preserve unsupported dates, unrepresentable amounts, formulas and errors; no semantic promotion. | Structure/lineage only; archive storage is not source-origin acquisition. Await source-owner clarification for this exact archived copy; qualify workbook meanings and formulas separately. See [the source-owner clarification receipt](../../quality/qualifications/mbs-workbook-date-source-owner-clarification-20261017.json). |
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
