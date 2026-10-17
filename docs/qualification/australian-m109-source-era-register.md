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

For the August 2026 release, the source identity is pinned at MBS archive
revision `da83cad9116e2f9a5b927be7b080e9a5e5ea6998`, raw-object SHA-256
`c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565`, and
8,293,331 bytes. The read-only `39029209737` DMY candidate and the updated
exact-main `39032003723` field-presence report are complete; the latter records
all 40 fields across 6,046 rows with zero presence/state mismatches while
keeping release-linked field semantics unaccepted. Neither run emitted six
Parquet outputs. The M-108 assessment
([source and table lineage, proposed destination, rights boundary, and
preservation steps](australian-m108-derived-products-20261017.md#august-2026-mbs-six-table-operation-assessment))
is the consolidated handoff; no further diagnostic run is needed. The next
evidence is an exact-release versioned schema/change record or source-owner
clarification. Raw-archive approval comment 5467052330 does not authorize
derived output distribution.

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
| MBS August 2026 XML (`2026-08-01`) | Exact SHA-256 `c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565`; 8,293,331 bytes; the exact B1 receipt and hosted B2 archive identity matched the official release on exact-main run [39025588261](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39025588261). The updated value-free report is preserved in [the exact-main diagnostic profile](../../quality/qualifications/mbs-source-era-candidate-2026-08-01-run-39032003723.json), SHA-256 `35265bb883a6dde7f99e349a272c29a6592a65a160d096f05600091c455e90a2`; run [39032003723](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39032003723) binds it to exact main `b5b4d3ce6e3400e0fdb84ab2b56854776c4878e6`. It reports 6,046 source records, 40 mapped fields, 241,840 field occurrences, and six per-table lineage digests. | Not yet accepted. The [August release page](https://www.mbsonline.gov.au/internet/mbsonline/publishing.nsf/Content/Downloads-20260801) identifies the exact release and says it has no further XML changes from the version published on 28 May 2026. The [XML field guide](https://www.mbsonline.gov.au/internet/mbsonline/publishing.nsf/Content/FAQ-XML_Help) provides field descriptions, types, and rules but was last updated in 2022. The hosted profile now accounts for every field in that guide, but those records do not establish release-linked semantic version history from the May snapshot. | The exact-main profile applies the official `DD.MM.YYYY` grammar as a candidate only: 42,088 values converted, 24,837 fields absent, 80,648 explicit nulls, and 94,267 values preserved; no `unsupported_format` or invalid date values remain under this profile. These aggregate counts do not establish requiredness or temporal interpretation. The 40 per-field source-presence/projected-state checks cover 6,046 rows each and report zero mismatches; they prove parser alignment for these states, not the source meaning of a field. | A bounded read-only workflow compared the approved August bytes with the official file in Actions memory and retained aggregate diagnostics only. No source values or source bytes were retained. | Source identity, six-table candidate structure, and field-presence alignment are evidenced. Release-linked field semantics, date/temporal acceptance, historical parity, public v4 admission, the full approved source-era denominator, and M-109 acceptance remain open. A current, versioned source-owner clarification or exact-era schema/change record is needed to close the semantic-history gap. |
| MBS July 2024 Group P7 workbook | Exact SHA-256 `2f1cbc2d2dcbb93be86f42c8dbbe9f5f9e8fb550cad38b6ee54d0e9bdd2e27b8`; four sheets; 13,742 cells; 99 header/field mappings; four formula cells and two error cells in the recorded workbook profile. | Headers and typed candidate destinations are inventoried; source-specific meaning for P7 annotations and workbook-only fields is not qualified by the XML guide. | Four date columns have `DD.MM.YYYY` lexical shape. 1,276 values are calendar-valid under both DMY and MDY; no convention is selected. XML date semantics are not transferred. The official July 2024 downloads page does not list P7. A second value-free contact supplied the exact pinned donor-archive copy (commit `931da0b9b6ae3e3cec0743568abb71a50d62b7cf`, 87,727 bytes, same SHA-256) and asked MBS Online to confirm or deny Department provenance and, if confirmed, the date convention. Neither message confirms provenance or convention. | Candidate status counts preserve unsupported dates, unrepresentable amounts, formulas and errors; no semantic promotion. | Structure/lineage only; archive storage is not source-origin acquisition. Await source-owner clarification for this exact archived copy; qualify workbook meanings and formulas separately. See [the source-owner clarification receipt](../../quality/qualifications/mbs-workbook-date-source-owner-clarification-20261017.json). |
| PBS 2026-04-01 XML V3 archive member | Exact member digest and identity in the [PBS v3 date receipt](../../quality/qualifications/pbs-v3-2026-04-01-date-profile-qualification-20260929.json); 7,730,684 elements and 18,208,758 native fields. | Domain meanings, field-level mappings, and current-status interpretation remain unqualified. | ASCII date grammar profile qualified for the exact member only: 2,799 converted date values and one recognized slot absent. No intervals/current-state inference; 7,727,884 elements remain outside recognized date roles. | Structural/storage projections and Parquet round trips passed; domain projection remains a candidate. | Historical exact-member grammar only. Source-era field meanings and any cross-release transformation remain open. |
| PBS G2B XML 1.8 (2006-12 to 2012-10) | Era is documented in the source-transition receipt; no exact approved corpus profile is recorded here. | Unqualified. | Unqualified. | Unqualified. | Obtain/identify the approved source identities and exact-era schema evidence. |
| PBS XML 2.8–2.12 (2012-12 to 2017-08) | Era range documented; exact approved member denominator not reconciled. | Unqualified. | Unqualified. | Unqualified. | Reconcile exact approved source identities before profiling. |
| Alternate PBS XML 2.12 (2017-09 to 2018-08) | Distinct documented alternate era; no exact approved member profile recorded. | Unqualified. | Unqualified. | Unqualified. | Keep separate from mainline PBS XML 3.x and reconcile denominator. |
| PBS XML 3.x historical releases (from 2017-09) | April 2026 member is the only exact member qualified in this register; other releases are not enumerated. | Unqualified except for the exact date-role labels used by the narrow date profile. | The April 2026 date grammar result does not establish other release semantics. | No general v3 transformation accepted. | Enumerate each approved release/schema revision and qualify independently. |
| Current PBS public API / API CSV (model 3.7.8, observed 2026-08) | Current distribution metadata and model documentation reviewed; no payload requested or acquired. Public history is limited to the most recent 12 months per the recorded documentation. | Current API field meanings and crosswalk to historical XML remain unqualified. | Current-effective schedule and monthly update metadata are not a field-level temporal mapping. | No API transformation run. | Public access is documented, but project retention and external redistribution authority remain unresolved. Obtain provider clarification and a source-specific maintainer rights decision before acquisition. |
| Minimal PBS fixture | Synthetic fixture only; not a source era or real corpus. | Fixture contract only. | No real-source temporal evidence. | Test-only transformation behavior. | Must not count toward M-109 source-era completion. |

## Official release-change metadata, 2026-10-18

The [value-free release-change record](../../quality/qualifications/australian-mbs-official-release-change-notes-20261018.json)
captures three official release-page observations and metadata-only HTTP
retrieval receipts. Each binds the exact response URL, status, client-observed
request/response times separately from the server `Date`, last-modified time,
byte length, and SHA-256; the observations' item/column
tokens and release statement were checked against that response. The page
bodies were discarded after hashing. The March 2026 version 2 page describes
removal of incorrectly included EMSN caps for 12 items and changes to columns
Y, AB, and AC. The July 2026 page documents corrections to Schedule Fee and
100% benefit for five items whose prior indexing was wrong. The August 2026
page identifies new item 73331 and states that no further XML changes occurred
relative to the file published on 28 May. No schedule XML source payload was
requested or read for this metadata review.

These notes narrow the release chronology but do not identify XML element
names for the column labels, resolve the conflicting `EMSNCap` descriptions,
or qualify semantics across the approved source-era denominator. The report
therefore preserves M-109's blocked semantic status and the need for source-
owner clarification or an exact-era schema/change record.

## August 2026 MBS predecessor comparison plan

The official [August 2026 downloads page](https://www.mbsonline.gov.au/internet/mbsonline/publishing.nsf/Content/Downloads-20260801)
identifies the XML as released 29 July and effective 1 August 2026. It says
the file includes item 73331 and that no further changes are reflected compared
with the version last published on 28 May 2026. The official [July 2026 downloads
page](https://www.mbsonline.gov.au/internet/mbsonline/publishing.nsf/Content/Downloads-20260701)
identifies `MBS-XML-20260701.XML` as released on 28 May, effective 1 July,
and records fee corrections for items 5200, 5203, 5207, 5208 and 5209. This
identifies the exact predecessor edition referenced by the August page: the
July 2026 XML published on 28 May, not a separate unnamed May release. The
archive sidecar at current revision `da83cad9116e2f9a5b927be7b080e9a5e5ea6998`
binds that July object to `raw/mbs/releases/Downloads-20260701/MBS-XML-20260701.XML`,
SHA-256 `5834d849743a3eab2b8c03e826a5ed6a488a6f65cf4c4148da3ec227e5007805`,
8,291,891 bytes, sidecar SHA-256
`01988fb6cf56c4a23bba680e8c9ee6d9b3b39d504d044676e49b4b78d1f5ba56`. The
August object at the same revision is 8,293,331 bytes with SHA-256
`c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565`; its
sidecar SHA-256 is
`9bca6260ea9d25d7ee9c184b59eed03b059d8da486dea31ec1d058965aae55ed`.
The current archive metadata joins both identities to the existing
`monthly_schedule_xml` authorization. The July/August comparison is now
implemented in `scripts/compare_mbs_source_eras.py` and attached to the bounded
exact-main Actions workflow. It binds each edition to its own pinned harvest
sidecar and rights reference; the July category authorization is not replaced
by the August exact-release approval. Exact-main run
[39037457764](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39037457764)
passed the August candidate-profile step but failed the predecessor comparison
closed, preserving incomplete aggregate artifact `12102413530`. The August
sidecar names the original acquisition path, while the B2 archive also exposes
a content-addressed path. Metadata-only inspection confirms both August paths
identify the same pinned LFS object and byte count; this alone is not a new
comparison or official-byte match. The local repair preserves both locators
and checks each against the pinned digest and byte count, alongside the exact
official payload. A new exact-main comparison remains pending merge and
readback. There is no July official-byte match or comparative result yet.

The bounded comparator runs on exact `main`: fetch both harvest sidecars, each
B2 archive object and any distinct original receipt locator, and both official
endpoints in Actions memory; verify each sidecar, archive payload, and official
payload against its pinned identity; then emit only aggregate record counts,
native-field sets, per-field
presence/null counts, and counts of changed/added/removed records and fields.
Match records by source identity only in memory; never emit item identifiers or
source values. Retain an aggregate incomplete artifact on source timeout or
identity/structure mismatch, and fail the workflow after uploading that
diagnostic. Do not generate Silver Parquet, publish a derived product, change
archive manifests, or promote field/date semantics.
If either official endpoint times out or its bytes disagree, mark the
comparison incomplete and preserve both existing archive objects and receipts;
do not treat missing data as equality or repeat an unchanged failing request.

Exact-main run
[39047005443](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39047005443)
completed successfully at commit `f6cccb0beb66d5a1322149f33dc61820eea05166`.
It matched both archived release payloads to their official endpoints and
retained the aggregate-only artifact `12105683236`. The report is preserved at
[`australian-m109-july-august-predecessor-comparison-20261018.json`](../../quality/qualifications/australian-m109-july-august-predecessor-comparison-20261018.json);
its SHA-256 is
`73ef383cd36ca2703ddd70344b572f8904b67b8d85a1f6420036fa76e4d4954b`. It
records 6,045 matched records, one added record, no removed records, and
aggregate counts for changed native fields. No record identifiers or source
values were emitted or retained, no Silver was generated, and M-109 remains
false. The previous exact-main attempt `39037457764` remains a historical
incomplete result; this successful rerun supersedes it for the comparison task.

This comparison verifies the release chronology and describes structural or
content differences. Those results cannot establish that field meanings
stayed unchanged. The Department's field-guide page was last updated on
2022-03-04, and current release pages and news entries do not supply a
versioned field-meaning history from 2022-03-04 through 2026-05-28. The
source-owner/schema-history gate remains open. Source-level archive
authorization does not authorize the six derived outputs proposed in the M-108
assessment.

### Official field-guide wording history

A value-free comparison of the official November 2013 and February 2022 XML
field guides found a documented wording delta for `ItemChange`. The 2013 guide
defines `Y`/`N` in terms of whether the **item number** changed; the 2022 guide
defines them in terms of a change to the **item**. Both describe a mandatory,
single-character alphanumeric field. The current official help page links the
February 2022 guide and says it was last updated 2022-03-04. Source PDF digests,
URLs, and exact comparison boundaries are recorded in
[`australian-mbs-field-guide-semantic-history-20261018.json`](../../quality/qualifications/australian-mbs-field-guide-semantic-history-20261018.json).

The same comparison found a conflicting `EMSNCap` legend: the November 2013
PDF and the current official help-page table say `N` means no current cap,
whereas the linked February 2022 PDF says `Y` means a current cap. That PDF
also states that `N` makes the other EMSN tags null. The pages and PDF agree on
`P` and `F` meanings. This records a source-document conflict; it does not
establish which statement applies to any release, and no code interpretation
or field mapping is selected.

This establishes a documentary wording difference, not the exact date when the
operational meaning changed, the meaning applicable to a particular release,
or the semantic history of other fields. Do not transfer either wording to a
release or promote these fields into harmonised Silver meanings. M-109 still
needs versioned, release-linked source history for each required era; no source
values were retained or emitted.

### Official March 2026 release correction

The official [March 2026 Downloads page](https://www.mbsonline.gov.au/internet/mbsonline/publishing.nsf/Content/Downloads-20260301)
identifies `MBS-XML-20260301-version 2.XML`, released 10 February and effective
1 March 2026, as removing EMSN caps incorrectly included in the 5 February
revision for 12 items. It also says corresponding columns Y, AB, and AC were
amended in line with no EMSN caps to align with prescribed legislation. The
page provides a release-specific correction, but it does not map those column
labels to XML tags or resolve the conflicting `EMSNCap` field-guide legend.
This observation is recorded in
[`australian-mbs-release-corrections-20261018.json`](../../quality/qualifications/australian-mbs-release-corrections-20261018.json).
It does not establish semantics for other fields or eras, source rights, or
M-109 acceptance.

The July/August comparator was also rerun on exact current main commit
`4b8ea386b20b1f9b034e5d8cf80ca3e05430bb4c` in hosted run
[`39048554153`](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39048554153).
The successful aggregate-only report SHA-256 is
`09b1263b8724b4cce187bbaef9a2fec033c579c2aeaa94b503faecc7b672c210`; it records
6,045 matched records, one added record, 5,445 changed records, and no removed
records. It retained no source identifiers or values and generated no Silver.
The comparison confirms release-level differences only; it does not close the
semantic-history gap or M-109.

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
