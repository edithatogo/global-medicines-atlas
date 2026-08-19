# Data-layer Hugging Face archival receipt

**Observed:** 2026-08-19. Maintainer approval covered Hugging Face archival of
obvious public data that does not require credentials. This receipt does not
approve source-derived bulk medicine rows, credential creation, or licensed
vendor payloads.

## Published object

| Field | Observed value |
| --- | --- |
| Dataset | [`edithatogo/global-medicines-atlas-catalogue`](https://huggingface.co/datasets/edithatogo/global-medicines-atlas-catalogue) |
| Revision | [`b25af36da32ffa3ddc5d525f1c568459d23f6e11`](https://huggingface.co/datasets/edithatogo/global-medicines-atlas-catalogue/tree/b25af36da32ffa3ddc5d525f1c568459d23f6e11) |
| Visibility | public |
| Plan SHA-256 | `254de2442dc6724ee2e63f27071712c92585cb306de146c913b9b7251899a8f5` |
| Machine receipt | `quality/qualifications/data-layer-archive-receipt.json` |

The dataset remains the existing Hugging Face publication identity. This
revision adds a Parquet source inventory, publication contracts, and
representative governed fixtures. It does not replace the GitHub software
identity or the Zenodo software archive.

## Inventory

- 96 catalogued sources were classified.
- 85 are public/no-credential; catalogue metadata is archived for all of them.
- 11 credential-gated sources are catalogue-metadata-only and have no payload
  in this revision.
- Governed fixtures are labelled `representative_fixture_not_live_coverage`.
- No live source dump was downloaded.

## Skipped payloads

Credential or restricted-byte sources omitted from fixture archival:

`au-amt-rf2`, `au-pbs-embargo`, `eu-ema-pms-fhir`, `eu-spor-rms-oms`,
`gb-nhs-dmd`, `gb-trud-api`, `kr-hira-reimbursement`, `kr-mfds-nedrug`,
`nz-nzhts-fhir`, `nz-nzulm-bulk`, `sa-sfda-drug-list`.

`vendor/nzmedicines` licensed NZULM/NZMT fixtures were excluded.

## Remaining gates

Source-derived bulk publication, OSF licence resolution, and stable-v1
promotion remain independent gates. Missing fixture coverage is not negative
evidence of source absence.
