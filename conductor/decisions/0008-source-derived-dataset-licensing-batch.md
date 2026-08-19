# Decision 0008: source-by-source licensing approval for derived datasets

**Status:** decision required from maintainer; no source-derived publication is
approved by this record alone.

**Scope:** the 96 sources in
`src/global_medicines_atlas/data/medicine_source_catalog.json`, including
regulatory, funding, formulary, pricing, terminology, product-information and
document sources. This decision covers retention, transformation, inclusion in
derived datasets, Hugging Face/Zenodo distribution, and public API exposure.

**Related controls:** GitHub issues [#50](https://github.com/edithatogo/global-medicines-atlas/issues/50),
[#51](https://github.com/edithatogo/global-medicines-atlas/issues/51),
[#54](https://github.com/edithatogo/global-medicines-atlas/issues/54),
[#66](https://github.com/edithatogo/global-medicines-atlas/issues/66), and
[#70](https://github.com/edithatogo/global-medicines-atlas/issues/70).

## Decision options

| Option | Meaning | Recommendation | Contingency and trade-off |
|---|---|---|---|
| **A — Metadata/catalogue only** | Publish source identity, authority, URL, field schema, access mode, rights state, and a pointer; no source bytes, records, copied text, or source-derived row values. | **Recommended default for every unresolved source.** Safest useful global catalogue and supports adapter planning. | If metadata itself has terms or access restrictions, retain only a minimal internal source identifier and public landing-page URL. Coverage claims remain discovery-only. |
| **B — Restricted internal acquisition** | Acquire and retain source payloads in a controlled, non-published workspace; publish only digests, receipts, and derived quality metrics that do not reconstruct source content. | Recommended where operational validation needs current payloads but redistribution rights are unclear. | Requires access controls, retention/deletion schedule, provenance, lawful access record, and a source-specific review. No HF/Zenodo attachment or public API exposure. |
| **C — Derived-public release** | Publish a transformed dataset under an approved source-compatible licence, with attribution, notices, field-level provenance, and regeneration instructions. | Recommended only after every row in the source decision is `approved_public_derived`. | If any field or source changes terms, immediately downgrade the affected release to A or B, withdraw the affected artifact if required, and issue a correction receipt. |
| **D — Exclude/quarantine** | Do not acquire or retain payload; keep only a blocker record. | Required for prohibited, inaccessible, personal, confidential, contractually restricted, or legally ambiguous material. | Reconsider only on written source-owner permission or a new authoritative licence interpretation. |

## Batch approval matrix

The batch is an approval queue, not an assumption of permission. The
recommended disposition is the current safe disposition pending a completed
source receipt.

The first source-specific rights receipt is now recorded for `us-openfda-ndc`:
[`quality/qualifications/source-rights-receipts/us-openfda-ndc-20260803.json`](../../quality/qualifications/source-rights-receipts/us-openfda-ndc-20260803.json).
It supports only a scoped CC0 metadata candidate and does not itself approve
public distribution; the source remains `catalogue_only` until field-level
payload and transformation qualification is complete. All other sources
remain blocked pending their own receipt.

| Batch | Sources / jurisdictions | Primary content | Current catalogue state | Recommended disposition | Approval needed for Option C | Main contingency |
|---|---|---|---|---|---|---|
| NZ | `nz-*` (NZL) | Medsafe registration, NZULM/NZMT, PHARMAC funding, NZ health terminology | Fixture/catalogue or review required | **A**, with **B** only for lawfully acquired NZULM/NZMT/Medsafe/PHARMAC payloads | Written terms/licence for NZULM/NZMT, Medsafe, PHARMAC and any SNOMED/AMT dependency; field-level redistribution and attribution decision | Keep source-native identifiers and schema metadata only; do not publish copied product rows |
| Australia | `au-*` (AUS) | ARTG, PBS API/bulk/history, AMT, product information | Catalogue-only/review required | **A** pending PBS and TGA terms review | PBS and TGA source terms, API/bulk permissions, historical retention and derived-field rights | Publish adapters and source links without payload; separate regulatory ARTG from PBS funding |
| United States | `us-*` (USA) | Drugs@FDA, Orange Book, DailyMed, CMS funding/formularies, RxNorm/UNII/NDC | Mixed: government/open terms plus review-required dependencies | **A** by default; **C candidate** for explicitly permissive components after verification | Confirm each endpoint's terms; separate US government data, openFDA, DailyMed, CMS agreement, RxNorm/UMLS and UNII terms; prohibit approval inference from NDC | Split into source-specific artifacts; exclude restricted terminology or CMS fields from public dataset |
| European Union | `eu-*` (EU) | EMA product, Article 57, PMS, SPOR/RMS/OMS, Union Register | Fixture/catalogue or review required | **A**; **B** for controlled validation | EMA/API terms, reuse licence, attribution, update and redistribution scope for each endpoint | Publish only identifiers, links and schema descriptors until EMA confirms derived-data reuse |
| United Kingdom | `gb-*` (GBR) | MHRA products, NHS dm+d/TRUD, Drug Tariff, NICE and market data | Catalogue-only/review required | **A**; **B** for licensed dm+d access | NHS/TRUD licence and syndication terms, MHRA/NICE reuse terms, payer-data restrictions | Do not combine dm+d-derived values with public records unless licence permits; retain only mapping receipts |
| Canada | `ca-*` (CAN) | Health Canada DPD/NOC, provincial formularies, CDA recommendations | Catalogue-only/review required | **A**; **B** for controlled source review | Federal and provincial terms, database rights, provincial payer permissions, attribution and territorial scope | Keep federal/provincial datasets separate; no national funding conclusion from one province |
| Japan and Korea | `jp-*`, `kr-*` (JPN/KOR) | PMDA approvals/inserts, MHLW prices, MFDS/NEDrug, HIRA reimbursement/codes | Catalogue-only/review required | **A**; **B** after language and field review | Japanese/Korean source terms, translation rights, terminology mappings, commercial-use and attribution limits | Publish source links and native IDs only; translated fields remain internal until reviewed |
| Other national and regional sources | `ae-*`, `ar-*`, `bh-*`, `br-*`, `ch-*`, `cl-*`, `co-*`, `de-*`, `dk-*`, `fr-*`, `gcc-*`, `id-*`, `in-*`, `kw-*`, `mx-*`, `my-*`, `ng-*`, `nl-*`, `no-*`, `om-*`, `ph-*`, `qa-*`, `sa-*`, `se-*`, `sg-*`, `th-*`, `za-*`, plus `global-*` | Registers, formularies, prices, WHO and terminology resources | Predominantly review required | **A**; **D** where access or rights are unclear | Source-owner terms, language/translation, completeness, national database rights, WHO terms, and any authentication contract | Retain catalogue entries only and prioritize sources with explicit open-data licences |

## Source-level approval fields

No source may move to `approved_public_derived` until all fields below are
completed for the exact `source_id`. A batch approval may share rationale and
controls, but it must enumerate every source ID and may not use a jurisdiction
label as a substitute for source-level evidence.

| Field | Required evidence | Fail-closed rule |
|---|---|---|
| Identity and authority | Official landing page, endpoint, source owner, native identifier and jurisdiction | Missing or ambiguous identity means A or D |
| Licence and terms | Current licence/terms URL, version/date, database-rights position, commercial/reuse status | `review_required`, silent terms, or incompatible terms means no public derived release |
| Access authority | Public access, API key, subscription, data-sharing agreement, or written permission | Credentials alone do not establish redistribution rights |
| Field disposition | Field-by-field classification: public, derived-allowed, attribution-required, restricted, personal/confidential, prohibited | One restricted field blocks that field and any output that reconstructs it |
| Transformation | Deterministic transformation code, schema mapping, aggregation/generalisation and lossiness statement | Undocumented transformations cannot be published |
| Attribution and notices | Exact notice text, citation, source version, required logos/disclaimers and link | Missing notice blocks publication |
| Temporal scope | Retrieval timestamp, effective date, update cadence, historical retention permission | Current snapshot cannot be represented as historical completeness |
| Reproducibility | Source digest/receipt, adapter version, schema fingerprint and regeneration instructions | No durable receipt means catalogue-only |
| Publication surface | Approved surfaces: internal, GitHub, HF, Zenodo, API; licence per surface. OSF is deprecated. | Approval for one surface does not transfer to another |
| Withdrawal and correction | Contact, takedown route, retention/deletion policy, correction and downstream notification procedure | No withdrawal path means B or D |

## Batch decision requested from maintainer

Recommended decision:

1. Approve **Option A** for all 96 sources immediately.
2. Approve **Option B** only for source-specific lawful acquisition needed for
   adapter qualification, with no public payload redistribution.
3. Do **not** approve Option C in bulk. Permit a source to enter Option C only
   through an individual completed receipt satisfying the fields above.
4. Require **Option D** for any source whose terms prohibit acquisition,
   retention, transformation, or redistribution, or whose status cannot be
   resolved without legal/source-owner confirmation.
5. Keep regulatory, funding, formulary, pricing and terminology outputs as
   separately licensed and separately attributable dimensions.

This recommendation maximises useful progress while avoiding the most serious
trade-off: a broad public release could accidentally grant rights the source
owner did not grant, or collapse a source's regulatory and funding semantics.

## Acceptance and follow-up

On approval, create one machine-readable source-rights receipt per `source_id`,
link it to issues #50/#51/#54, and regenerate the publication eligibility
matrix. A source receipt must never be inferred from another source in the
same jurisdiction or from a general government/open-data assumption.
