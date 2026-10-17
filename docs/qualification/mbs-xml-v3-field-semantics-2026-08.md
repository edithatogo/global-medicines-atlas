# MBS XML v3 field semantics: August 2026 era

Status: source-native field meanings and the declared date grammar are bound to
the exact 1 August 2026 release. The six-table transformation remains a
candidate. This record does not qualify historical parity, completeness,
public v4 admission, or M-109 as a whole.

## Exact source and documentation

The source is MBS XML release `MBS-XML-20260801`, released 29 July 2026 and
effective 1 August 2026. Its bytes match both the B1 receipt and the official
[August release page](https://www.mbsonline.gov.au/internet/mbsonline/publishing.nsf/Content/Downloads-20260801):
SHA-256 `c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565`,
8,293,331 bytes. The exact-main hosted no-date presence baseline is
[`mbs-source-era-candidate-2026-08-01-presence-baseline.json`](../../quality/qualifications/mbs-source-era-candidate-2026-08-01-presence-baseline.json).
It counts 6,046 source records, all 40 native fields, and 241,840 field
occurrences. Every per-field source-presence state matches its projected
native state; this baseline has no selected date grammar and contains
aggregate counts only, no source values. The updated DMY candidate report is
pending its own exact-main hosted run.

The Department's [XML field descriptions](https://www.mbsonline.gov.au/internet/mbsonline/publishing.nsf/Content/FAQ-XML_Help)
define field meanings, optionality, conditions, value types, numeric widths,
null defaults, and the `DD.MM.YYYY` date format. The August release page links
to those descriptions and says that, apart from the named new item, no further
changes are reflected compared with the 28 May 2026 XML. The field-description
page itself was last updated 4 March 2022; it is used here as the Department's
published XML field guide, while the exact August identity and its field
denominator are independently bound to the 2026 release. This is not evidence
that the 2022 page is a complete version history.

## Native meaning and transformation boundaries

| Native field(s) | Meaning and handling for this source era |
| --- | --- |
| `ItemNum`, `SubItemNum` | Item and precedent-item sub-item identifiers. Preserve lexical identity. The guide says `SubItemNum` is not populated in this XML. |
| `Category`, `Group`, `SubGroup`, `SubHeading` | Source hierarchy codes. Preserve each native level; optional or null values are not negative classifications. |
| `ItemStartDate`, `ItemEndDate` | Item commencement and cessation dates. Parse only with the documented `DD.MM.YYYY` grammar. A null end date says no end date is stated in this snapshot, not that validity is timeless. |
| `ItemType`, `FeeType`, `ProviderType` | Source item kind, fee kind, and applicable provider-category code. Preserve the codes; do not infer approval or eligibility. |
| `NewItem`, `ItemChange`, `AnaesChange`, `DescriptorChange`, `FeeChange`, `EMSNChange` | Literal source change indicators. `NewItem` is relative to the source base report date; a blank `FeeChange` may occur for a new item. |
| `Anaes`, `BasicUnits` | Anaesthetic indicator and basic units. The guide limits basic units to the documented item range; absence is not zero. |
| `Description`, `DescriptionStartDate`, `DescriptorChange` | Item description, its commencement date, and descriptor-change indicator. Preserve text and parse the date only with the documented grammar. |
| `FeeStartDate`, `ScheduleFee`, `DerivedFeeStartDate`, `DerivedFee`, `FeeChange`, `FeeType` | Current normal-fee commencement and amount, derived-fee commencement and description, change flag, and fee kind. Preserve derived-fee text without evaluating it. Parse monetary amounts as exact decimals; schedule fee applies only to normal-fee items. |
| `BenefitType`, `Benefit75`, `Benefit85`, `Benefit100`, `BenefitStartDate` | Benefit selector, conditionally present benefit amounts, and current benefit commencement date. Preserve conditional absence according to the source fields; never coerce it to zero. |
| `EMSNCap`, `EMSNStartDate`, `EMSNEndDate`, `EMSNChangeDate`, `EMSNFixedCapAmount`, `EMSNPercentageCap`, `EMSNMaximumCap`, `EMSNDescription` | Extended Medicare Safety Net cap type, dates, values, and derived-fee cap description. Preserve type and exact numeric values. The guide says caps that ended before the report date are omitted, so null cannot establish no historical cap. |
| `QFEStartDate`, `QFEEndDate` | Start and end of time-limited listing evaluation. These do not represent item commencement, cessation, or funding conclusions. |

The typed candidate retains source-native fields and distinguishes missing XML
elements from present null values. The updated qualifier selects the date
grammar only for this exact August release and records converted, invalid, and
unsupported values separately. Exact-main validation of that selection
remains pending; it does not use values from this release to retrofit an
older source era.

## Limits

- These meanings and transformations apply to the exact August 2026 source
  identity only. They do not transfer to the 2025 XML, the July 2024 P7
  workbook, other MBS releases, PBS eras, or the current PBS API.
- The candidate report's quality findings and unverified public v4 identity
  remain blockers. Matching source presence to native projection establishes
  neither content correctness nor complete coverage.
- No source values or bytes are retained in the report; no derived dataset
  publication, admission, Gold relationship, or patient denominator is claimed.

M-109 remains partial and blocked.
