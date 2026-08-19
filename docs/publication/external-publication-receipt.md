# External publication reconciliation receipt

**Observed:** 2026-08-03 from authenticated OSF and publicly readable service
endpoints. This receipt records external state and does not authorise
publication of source-derived medicine data.

## Verified public objects

| Object | Verified identifier | Evidence observed |
| --- | --- | --- |
| GitHub software release | [`v1.0.0rc1`](https://github.com/edithatogo/global-medicines-atlas/releases/tag/v1.0.0rc1) | Published 2026-08-01 04:33:03 UTC from commit `5a6b9ef78e6de44e10ee314691a226d75017f780`, with seven assets and GitHub SHA-256 asset digests. |
| Hugging Face catalogue | [`edithatogo/global-medicines-atlas-catalogue`](https://huggingface.co/datasets/edithatogo/global-medicines-atlas-catalogue) | Public revision `27fb6f49412189c86475cf523afc306f331bb479`; tree contains only the dataset card, `.gitattributes`, `medicine_source_catalog.json`, and `international-resource-v5.json`. The three published content files exactly matched this checkout's SHA-256 bytes. The card declares Apache-2.0 and states that it is not a redistribution of third-party medicine data. |
| Zenodo software archive | [10.5281/zenodo.21734811](https://doi.org/10.5281/zenodo.21734811) | Public software record, version `1.0.0rc1`, Apache-2.0, seven assets. Its `qualified-assets.json` names the same release commit and four payload SHA-256 values as the GitHub release; its `SHA256SUMS` covers the deposited assets. The record description excludes source-derived medicine data. |

## Relationship and scope check

The Zenodo record links the GitHub repository and the catalogue-only Hugging
Face distribution as supplements. These are distinct objects: GitHub and
Zenodo identify software, while Hugging Face distributes public catalogue
metadata. The identifiers do not grant rights in restricted source payloads.
A later public/no-credential archive revision
`b25af36da32ffa3ddc5d525f1c568459d23f6e11` is recorded in
[`data-layer-archive-receipt.md`](./data-layer-archive-receipt.md).

## OSF registration receipt (historical, deprecated)

The OSF project [`https://osf.io/pcdnm/`](https://osf.io/pcdnm/) produced
registration [`ej5nf`](https://osf.io/ej5nf/) on 2026-08-03. OSF assigned DOI
[`10.17605/OSF.IO/EJ5NF`](https://doi.org/10.17605/OSF.IO/EJ5NF). The
authenticated API receipt is
[`https://api.osf.io/v2/registrations/ej5nf/`](https://api.osf.io/v2/registrations/ej5nf/).
The registration was public, with `pending_registration_approval=false` and
`reviews_state=initial`. On 2026-08-19 the maintainer deprecated OSF as a live
identity. Do not complete OSF licence resolution or further OSF submission.
The persistent protocol identity is the in-repo artefacts plus Zenodo DOI
`10.5281/zenodo.21734811`.

## Remaining gates

- Historical OSF registration `ej5nf` is deprecated/superseded. Do not complete
  OSF licence resolution or further OSF submission.
- Public/no-credential Hugging Face catalogue archival is complete (revision
  `b25af36da32ffa3ddc5d525f1c568459d23f6e11`; 85/96 sources). Credentialed and
  restricted sources remain out of scope.
- Isolated remaining gates are stable-v1 promotion approval and production
  disaster-recovery authority.
