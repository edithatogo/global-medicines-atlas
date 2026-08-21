# NZ medicines rights and compatibility disposition

**Status:** narrow public manifest approved; restricted source rights remain fail-closed
**Issues:** [#50](https://github.com/edithatogo/global-medicines-atlas/issues/50), [#51](https://github.com/edithatogo/global-medicines-atlas/issues/51), [closed migration #6](https://github.com/edithatogo/global-medicines-atlas/issues/6)  
**Source snapshot:** [`nzmedicines` at `6a8ecfae67f15d635750d11d5f446b93d76c1865`](./nzmedicines.md)

This record implements the local, evidence-based portion of the NZ medicines
rights and compatibility work. It is a disposition matrix, not a licence
grant, legal opinion, or approval to publish. Where the upstream authority,
licence, permission, or redistribution terms are not evidenced, the decision
is **retain locally / do not redistribute**.

## Decision matrix

| Asset or source family | Local role and evidence | Rights/authority status | Current disposition | Publication boundary | Required gate |
|---|---|---|---|---|---|
| `nzmedicines` Git history and `nzmedicines-all.bundle` | Preserved snapshot, commit `6a8ecfae67f15d635750d11d5f446b93d76c1865`; bundle SHA-256 `f4414798f1b35558c69472d86d29b0b83facb2e799c9a20692b62fc889847223`; see [`nzmedicines.md`](./nzmedicines.md) | Provenance is verified; redistribution permission is not established by preservation | Preserve locally as immutable evidence | Do not redistribute the bundle or history in public artefacts | Written rights decision and approved manifest in #51 |
| NZULM/NZMT hierarchy, relationship, pack, container, and substance inputs | Local inventory records the source family and local-only boundary; used by the NZ adapter | Source terms and redistribution rights require source-specific evidence | Retain locally; use only behind governed adapter contracts | No source payload release, public mirror, or derived release containing restricted fields | Written NZULM/NZMT decision in #51 |
| Medsafe regulatory product, application, ingredient, package, route, and status data | Inventoried as regulatory inputs, separate from funding assertions | Authority and reuse terms are not inferred from public accessibility | Retain locally; preserve provenance and currentness metadata | No raw or derived public release until source terms and fields are approved | Source-specific review in #51 |
| Historical NZF monograph/PIL `DocumentReference` fixtures | Recorded in the archived inventory; removed from the current tree | Historical provenance is known; linked NZF content rights/currentness are unresolved | Preserve only local history metadata | Do not redistribute linked documents or treat URLs as captured evidence | NZF rights/currentness decision in #51 |
| SNOMED CT / AMT mappings and identifiers | Inventoried local mapping inputs; identifiers remain source-native | Terminology licence and access conditions apply independently | Retain locally; transform only under source terms | No terminology payload, unrestricted mapping dump, or public derived claim | Terminology-specific decision in #51 |
| RxNorm-derived identifiers or mappings | Any local or future RxNorm-derived content is a separate terminology source | U.S. terminology terms and conditions must be verified separately | Retain only the minimum metadata needed for adapter interoperability | No RxNorm payload redistribution without verified terms | RxNorm-specific decision in #51 |
| PHARMAC/funding, subsidy, prescribing, HML, and PS inputs | Inventoried as funding/formulary inputs and modelled separately from regulatory approval | Funding-source reuse terms and field-level restrictions are not yet evidenced | Retain locally; never infer regulatory approval from funding status | No raw funding payload or unsupported public funding assertion | Funder-specific decision in #51 |
| First-party adapter code, schemas, tests, documentation, and deterministic tooling | Maintainer-created implementation in this repository | Apache-2.0 repository software boundary applies | Publish as software under the repository licence, excluding restricted payloads | Software-only releases may include code and synthetic/minimal fixtures that pass the manifest gate | Existing repository release controls |
| Catalogue-only metadata already published to Hugging Face | [`global-medicines-atlas-catalogue`](https://huggingface.co/datasets/edithatogo/global-medicines-atlas-catalogue); source payloads intentionally omitted | Publication boundary was designed as catalogue metadata, not source redistribution | Keep as catalogue metadata; re-check before adding fields | Do not expand with source-derived fields until #51 approves the manifest | #51 manifest review |
| Software-only Zenodo release | DOI [`10.5281/zenodo.21734811`](https://doi.org/10.5281/zenodo.21734811); seven software assets | Software release boundary; not evidence of source-data permission | Keep software-only | Do not upload source payloads, preserved bundle, or restricted fixtures | #51 approved public artifact manifest |
| Upstream compatibility notice and README/description change | Published through [`nzmedicines` PR #1](https://github.com/edithatogo/nzmedicines/pull/1) as `74f48d27caa22755a6c296e1d5b54b52af93397f` | Maintainer approved and hosted state verified | Keep the notice and canonical links current | Notice grants no payload access or redistribution rights | Executed #50 decision |
| Narrow compatibility mirror or upstream archival | Canonical development remains in this repository | Maintainer selected an unarchived compatibility and provenance mirror | Retain without a synchronization or new-development promise during the quiet period | Any later archival is a separate reversible decision | Executed #50 decision |

## Implemented local decisions

1. `global-medicines-atlas` is the canonical implementation and governance
   repository.
2. The `nzmedicines` snapshot was removed from the current tree after the
   maintainer approved rights remediation. Its source commit, per-file digests,
   and local-only bundle identity remain recorded as historical metadata.
3. The preserved Git bundle is local evidence only and is not part of a public
   release manifest.
4. Regulatory approval, funding/formulary status, and terminology identity are
   separate assertion dimensions; none is inferred from another.
5. Structure-only FHIR `DocumentReference` fixtures do not grant permission to
   redistribute the referenced NZF material.
6. Unknown, mixed, or source-restricted rights fail closed. The public release
   boundary is limited to first-party software and explicitly approved
   metadata/fixtures.
7. On 2026-08-21 the maintainer approved that narrow public boundary as policy;
   the exact hash-bound cohort is recorded in
   `quality/qualifications/nz-public-artifact-manifest-20260821.json`. No
   restricted source bytes or derived restricted fields were approved.
8. The adapter now uses a minimal first-party synthetic FHIR bundle with
   invented identifiers and labels. It is structural test evidence only and
   does not qualify NZULM/NZMT coverage.
9. Removing the current-tree snapshot does not rewrite its historical public
   Git presence. History rewriting remains outside this bounded remediation.

## Compatibility decision status

The local compatibility work supports the NZ adapter and fixtures. The
upstream notice, description, canonical homepage, and unarchived mirror state
are now verified. Redistribution of preserved history, NZULM/NZMT/NZF,
terminology, regulatory, or funding payloads remains pending, as does adding
any such payload to Hugging Face, Zenodo, or another public artefact.

Those redistribution actions require explicit approval and action-time receipts. See the
[external gate register](./nzmedicines-external-gates.md) for the authoritative
hosted-action boundary and the archived [asset inventory](../../conductor/archive/nzmedicines_migration_20260727/migration-inventory.md)
for file-level evidence.

## Review evidence

- The archived inventory contains 162 unique assets and records per-file
  digests, provenance, disposition, and local rights boundaries.
- The preservation record binds the upstream commit, tree digest, and bundle
  digest.
- The repository rights policy requires source-specific evidence and prohibits
  treating local preservation or transformation as redistribution permission:
  [`SOURCE_RIGHTS.md`](../data-sources/SOURCE_RIGHTS.md).

This document should be revised only when a source-specific rights decision,
approved public manifest, or hosted compatibility action is evidenced.
