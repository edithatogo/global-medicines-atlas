# MBS XML v3 field semantics: July 2025 era

Status: official field meanings are mapped for the 40-field Silver contract;
the mapping is limited to the exact July 2025 XML v3 era and remains a
candidate transformation, not Silver admission.

## Evidence and binding

The source is the July 2025 MBS XML v3 release with SHA-256
`db873768c5795222455033e2bad28586f19bbf2a10c7d58f06a0671d9111a556`,
8,194,522 bytes, 5,989 source records, and schema era `2025-07-version-3`.
The exact public candidate receipt is
[`qualification.json`](../../quality/qualifications/australian-mbs-v4-candidate-2025-07/qualification.json).
It accounts for all 40 contracted fields and 239,560 field occurrences. The
official [MBS XML field descriptions](https://www.mbsonline.gov.au/internet/mbsonline/publishing.nsf/Content/FAQ-XML_Help)
define the meanings below, including XML optionality, null defaults, code
rules, numeric precision and the `DD.MM.YYYY` date convention. The source is
historical and these definitions are not carried to the P7 workbook or another
XML release without exact-era evidence.

## Field meaning and transformation boundary

| Native field(s) | Official meaning and qualified handling |
| --- | --- |
| `ItemNum`, `SubItemNum` | MBS item and precedent-item sub-item identifiers. Preserve lexical identity; the source says `SubItemNum` is not populated in this XML. |
| `Category`, `Group`, `SubGroup`, `SubHeading` | Hierarchy codes to which an item relates. Preserve each code at its native level; optional empty/null hierarchy is not a negative classification. |
| `ItemStartDate`, `ItemEndDate` | Date item commenced / ceased. Parse the exact XML grammar as a source date; a null end date means no end date is stated in this snapshot, not timeless current validity. |
| `ItemType`, `FeeType`, `ProviderType` | Source item type (`S`, `P`, `D`), fee type (`N`, `D`), and applicable provider-category code. Preserve source codes; do not translate into regulatory approval or provider eligibility claims. |
| `NewItem`, `ItemChange`, `AnaesChange`, `DescriptorChange`, `FeeChange`, `EMSNChange` | Source change/new-item flags. Preserve literal flags and blanks; `NewItem=Y` is relative to the source's base report date, and a blank `FeeChange` can occur for a new item. |
| `Anaes`, `BasicUnits`, `AnaesChange` | Anaesthetic indicator, anaesthetic basic units, and anaesthetic-change flag. `BasicUnits` is only present in the documented item range; absence remains distinct from zero. |
| `Description`, `DescriptionStartDate`, `DescriptorChange` | Item description, date the current description commenced, and descriptor-change flag. Preserve description text; date is the source's description-start date, not a date inferred from wording. |
| `FeeStartDate`, `ScheduleFee`, `FeeChange`, `FeeType` | Current schedule-fee commencement, schedule fee, fee-change flag, and normal/derived fee type. Fee amounts use exact decimal parsing in AUD; `ScheduleFee` applies only to normal-fee items. |
| `DerivedFee`, `DerivedFeeStartDate` | Derived-fee description/expression and date it commenced. Preserve the expression as source text; do not evaluate it as a schedule amount. |
| `BenefitType`, `Benefit75`, `Benefit85`, `Benefit100`, `BenefitStartDate` | Benefit-level selector, its conditionally present 75/85/100 percent benefit amounts, and date the current benefit level(s) commenced. Parse amounts as exact AUD decimals; retain absent values according to `BenefitType`, not as zero. |
| `EMSNCap`, `EMSNStartDate`, `EMSNEndDate`, `EMSNChangeDate`, `EMSNFixedCapAmount`, `EMSNPercentageCap`, `EMSNMaximumCap`, `EMSNDescription` | Extended Medicare Safety Net cap status/type, start/end/change dates, fixed/percentage/maximum values, and derived-fee cap description. Preserve cap kind and exact numeric values. The official page says ended caps before the report date are not reported; null therefore cannot establish no historical cap. |
| `QFEStartDate`, `QFEEndDate` | Commencement/end of time-limited listing evaluation. These describe the evaluation period, not item commencement/cessation or a coverage/funding conclusion. |

The typed candidate maps these native fields to `services`, `hierarchy`,
`descriptions`, `fees`, `benefits` and `caps` under
[`mbs_field_contracts`](../../src/global_medicines_atlas/australian_source_contracts.py).
Date parsing is independently qualified only for this exact source identity
in the [MBS v3 date receipt](../../quality/qualifications/mbs-xml-v3-date-profile-qualification-20260929.json).
The receipt distinguishes converted, null and absent fields and found no
invalid or unsupported date values. Amount, identifier and code projection
denominators are candidate evidence; this semantic table does not establish a
source-origin acquisition lifecycle, Silver admission, public derived-data
rights, or M-109 acceptance.

## Remaining MBS and cross-source gaps

- July 2024 P7 is a separate four-sheet workbook era. Its field-lineage
  inventory exists, but its date convention is unselected (1,276 values are
  ambiguous between day/month and month/day) and workbook field meanings and
  transformations are not qualified by this XML table.
- Other approved MBS snapshots and schema eras need exact identity-bound
  native schema, meaning, temporal and transformation evidence; do not inherit
  this XML mapping by resemblance.
- PBS April 2026 XML v3 has an exact date grammar profile only. Its domain
  field meanings remain unqualified. Earlier documented G2B/PBS XML eras and
  the current API/API CSV model require separate era profiles.
- The current PBS API's source-specific access, retention and redistribution
  decisions remain unresolved. No current API payload has been requested or
  acquired; this document does not authorize it.

Accordingly, M-109 remains partial and blocked.
