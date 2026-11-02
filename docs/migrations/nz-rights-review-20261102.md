# NZ source rights review — 2 November 2026

This is the current source-specific review for [#51](https://github.com/edithatogo/global-medicines-atlas/issues/51),
the rights follow-up to the archived [migration #6](https://github.com/edithatogo/global-medicines-atlas/issues/6).
It supersedes the blanket pending-source statements in the August NZ disposition
and external-gate register. Those historical records and their hash-bound
software manifest remain unchanged.

The maintainer approved publication of everything permitted by source terms on
2 November 2026. Supporting private evidence stays outside Git, releases and
Hugging Face. No private permission document is required to be made public.
Approval does not change third-party terms or grant downstream rights that a
supplier withholds.

## Source decisions

| Source | Verified official terms | Decision and exact boundary |
| --- | --- | --- |
| NZULM / NZMT supplied through NZULM | [NZULM data access agreement](https://info.nzulm.org.nz/data-access) permits sharing and adaptation; requires attribution, the disclaimer and supplier terms. It identifies Pharmac's CC BY 3.0 NZ terms and Medsafe's copyright statement. | Conditional redistribution is permitted. A fresh licensor permission is **not** a blanket prerequisite. Keep package-specific terms and source provenance with an exact archive, and carry independent supplier restrictions. This does not license a separately sourced full SNOMED release. |
| Pharmac funding, subsidy, HML and Schedule | [Pharmac copyright](https://www.pharmac.govt.nz/about-this-site/copyright) licenses its content under CC BY 4.0 unless otherwise stated; marks, photographs and identified third-party works have exceptions. | Publish eligible Pharmac-owned material with attribution, source links, change notice and no endorsement claim. Retain CC BY 3.0 NZ where that is the supplied NZULM component's licence; do not silently relicense it. The three existing public Pharmac snapshots are reused at their immutable revision. |
| Medsafe regulatory tables | [Medsafe copyright](https://www.medsafe.govt.nz/other/siteinfo.asp) permits Crown material for personal, academic or clinical use with attribution. Commercial reuse requires written permission. Sponsor data sheets/CMI and SMARS have distinct conditions. | Academic preservation is permitted within those conditions; the material must not be represented as Apache-2.0, CC BY or unrestricted commercial data. A public archive must retain the use restriction. SMARS is not included. Unchanged sponsor documents have separate personal/clinical/academic permission, not a general commercial grant. |
| NZF / NZFC monographs, PILs and licensed content | The [official FAQ](https://nzformulary.org/faq.html) explicitly attributes overseas access limits to licensing: access is limited to NZ, Cook Islands, Niue and Tokelau. The [site](https://nzformulary.org/) reserves rights. | Confirmed restriction: do not mirror licensed content to an unrestricted worldwide dataset. Historical DocumentReference URLs and structural code do not mean that linked documents were acquired or licensed. The reviewed migration contains references, not an acquired NZF document corpus. |
| Full SNOMED CT / AMT and semantic mappings | [SNOMED licensing](https://www.snomed.org/get-snomed) requires registration/licensing and imposes conditions on non-member deployment; web deployments have additional permission conditions. The [GPS guide](https://docs.snomed.org/implementation-guides/gps-implementation-guide/technical-application) separately permits its flat identifier/term set under CC BY 4.0. | Confirmed restriction: a full hierarchy or licensed terminology payload cannot be released as an unrestricted worldwide archive. Do not treat opaque identifiers alone as the full ontology. GPS is an explicit open exception, not a licence for the historical NZ mappings or a reason to acquire a new corpus in this review. |
| RxNorm | [NLM terms](https://www.nlm.nih.gov/research/umls/rxnorm/docs/termsofservice.html) put NLM-created normalized names and codes in the public domain; full releases also contain separately restricted source vocabularies. | Permit NLM-created content with acknowledgement, historical-version notice and no endorsement. Reuse both existing public RXCUI files. Confirmed restriction attaches to proprietary source-vocabulary content, not all RxNorm data. No full mixed release is approved by this review. |
| Preserved Git bundle and mixed derivatives | The preserved bundle identity and 162-asset inventory remain in the archived migration. Source permissions above apply to embedded content, regardless of the repository owner's software licence. | Preserve the bundle privately. Do not upload a mixed history, opaque database or release ZIP under an unrestricted label while it may contain the specifically restricted components above. A filtered derivative needs an exact field/member manifest and the applicable notices; this review does not invent its contents. |
| First-party code, tests and synthetic fixtures | Repository Apache-2.0 and the existing exact 15-file approval. | Already public in Git. All 15 files are rechecked against their approved hashes; no duplicate upload or new release is needed. Software releases and attestations retain the same payload exclusions. |

## Publication reconciliation

The [current manifest and verification receipt](../../quality/qualifications/nz-rights-publication-review-20261102.json)
records the official term-page identities, all 162 historical inventory paths,
the existing software cohort and the five relevant public HF objects. The
objects are anonymously streamed and checked against their existing exact
manifest, with no token and no local source-payload file. Reuse is publication
reconciliation, not a new upload, new admission or new coverage claim.

The three Pharmac objects and two public-domain RXCUI objects are already in
[`edithatogo/global-medicines-atlas-international-permissive-20260821`](https://huggingface.co/datasets/edithatogo/global-medicines-atlas-international-permissive-20260821/tree/e6aa97ffe46eb32a41d7c73550fbd52811a9701b).
No duplicate dataset is created. This is the exact historical snapshot; it
does not establish current or complete NZ medicines coverage.

The historical 2023 local corpus is absent from this checkout. The inventory
was originally metadata-only for 132 OneDrive placeholders. A bounded filename
search of the retained recovery area, project checkout estate and existing
OneDrive location did not locate the two named ZIP surfaces or the preserved
bundle. This is an availability result, **not** a newly discovered legal
restriction and not proof that those privately preserved assets no longer
exist. No unrelated cloud file is hydrated and no private asset is published.
There is no locally available new payload whose publication can truthfully be
reported complete. Eligible source bytes recovered later retain the affirmative
permissions above and must use Actions-to-public-HF with exact manifest,
supplier notices and anonymous digest verification.

## Remaining #51 boundary

The generic request for public permission paperwork is removed. The written
review and available approved-publication reconciliation are complete. #51
remains open specifically for unrestricted publication of licensed NZF content,
full SNOMED/AMT semantic content and proprietary RxNorm source vocabularies.
Medsafe's commercial-use restriction must also remain attached to any future
Medsafe-derived archive. None is a restriction on the already published
first-party software, eligible Pharmac data or NLM-created identifiers.

No public release, Git history rewrite, compatibility-repository archival,
federation qualification or clinical-use claim is made by this packet.

## Ownership and verification

Chat `01a19600-56dd-73a2-9ff5-4a2484a54493` owns this scoped review in
`/Volumes/PortableSSD/GitHub/global-medicines-atlas`, branch
`codex/nz-rights-closeout-51`, based on `495f08c34092137df0e86de703c22fe379d50d4a`.
Owned paths are this report, its public metadata receipt, the source-rights
register link and the archived track's follow-up plan/evidence. Existing
ownership entries remain history. No credential, private source byte, native
binding or ongoing acquisition is transferred. Focused manifest/inventory
checks and protected CI qualify this documentation packet.
