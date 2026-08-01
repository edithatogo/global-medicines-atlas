# External publication reconciliation receipt

**Observed:** 2026-08-01 from publicly readable service endpoints. This
receipt records external state; it does not perform an external write, approve
an OSF registration, or authorise publication of source-derived medicine data.

## Verified public objects

| Object | Verified identifier | Evidence observed |
| --- | --- | --- |
| GitHub software release | [`v1.0.0rc1`](https://github.com/edithatogo/global-medicines-atlas/releases/tag/v1.0.0rc1) | Published 2026-08-01 04:33:03 UTC from commit `5a6b9ef78e6de44e10ee314691a226d75017f780`, with seven assets and GitHub SHA-256 asset digests. |
| Hugging Face catalogue | [`edithatogo/global-medicines-atlas-catalogue`](https://huggingface.co/datasets/edithatogo/global-medicines-atlas-catalogue) | Public revision `27fb6f49412189c86475cf523afc306f331bb479`; tree contains only the dataset card, `.gitattributes`, `medicine_source_catalog.json`, and `international-resource-v5.json`. The three published content files exactly matched this checkout's SHA-256 bytes. The card declares Apache-2.0 and states that it is not a redistribution of third-party medicine data. |
| Zenodo software archive | [10.5281/zenodo.21734811](https://doi.org/10.5281/zenodo.21734811) | Public software record, version `1.0.0rc1`, Apache-2.0, seven assets. Its `qualified-assets.json` names the same release commit and four payload SHA-256 values as the GitHub release; its `SHA256SUMS` covers the deposited assets. The record description excludes source-derived medicine data. |

## Relationship and scope check

The Zenodo record links the GitHub repository and the catalogue-only Hugging
Face distribution as supplements. These are distinct objects: GitHub and
Zenodo identify software, while Hugging Face distributes only the public source
catalogue metadata and schema. The identifiers do not grant rights in any
source payload, terminology, product information, or derived medicine data.

## Remaining gates

- The OSF project `https://osf.io/pcdnm/` now has a private draft registration
  `6a6dca79265e7ef20ac266e1`, reviewable at
  `https://osf.io/registries/drafts/6a6dca79265e7ef20ac266e1/review`. The draft
  has not been submitted or made public; it is not a registration receipt.
- Final OSF preview, maintainer confirmation, ethics-applicability wording,
  submission, and post-submission public identifier remain open.
- Every source-derived dataset remains subject to the source-by-source rights
  policy in [`SOURCE_RIGHTS.md`](../data-sources/SOURCE_RIGHTS.md). No
  source-derived payload is covered by this receipt.
- OSF registration and any new source-derived-data publication remain explicit
  maintainer decisions after the relevant preview and rights review.
