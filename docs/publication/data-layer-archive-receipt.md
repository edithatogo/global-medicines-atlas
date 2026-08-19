# Data-layer Hugging Face archival receipt

**Observed:** 2026-08-19. Maintainer approval covered Hugging Face archival of
public/no-credential FDA, EMA, TGA, and Medsafe artefacts plus complete
metadata. GitHub Actions is the durable publisher. This receipt does not
approve credentialed payloads, licensed NZULM/NZMT vendor bytes, or
consequential clinical claims.

## Published object

| Field | Observed value |
| --- | --- |
| Dataset | [`edithatogo/global-medicines-atlas-catalogue`](https://huggingface.co/datasets/edithatogo/global-medicines-atlas-catalogue) |
| Prior revision | [`b25af36da32ffa3ddc5d525f1c568459d23f6e11`](https://huggingface.co/datasets/edithatogo/global-medicines-atlas-catalogue/tree/b25af36da32ffa3ddc5d525f1c568459d23f6e11) (catalogue metadata and representative fixtures) |
| Current revision | Pending GitHub Actions publish from `.github/workflows/data-layer-archive.yml` |
| Publisher | GitHub Actions workflow `data-layer-archive.yml` |
| Visibility | public |
| Machine receipt | `quality/qualifications/data-layer-archive-receipt.json` |

The dataset remains the existing Hugging Face publication identity. Live public
artefacts for FDA, EMA, TGA, and Medsafe are packaged under `payloads/` with
per-source metadata. Hugging Face is an archive boundary, not bronze
source-of-truth.

## Inventory

- 96 catalogued sources are classified.
- Scoped authorities: FDA, EMA (including Union Register), TGA, Medsafe.
- Public/no-credential scoped sources receive payload archival or a labelled
  representative fixture after three failed live attempts.
- `eu-ema-pms-fhir` and `eu-spor-rms-oms` are metadata-only (credentials).
- NZULM/NZHTS, AMT, PBS embargo, dm+d/TRUD, and `vendor/nzmedicines` remain
  excluded.

## External gate

If Actions cannot authenticate to Hugging Face, the named missing secret is
`HF_TOKEN`. Local packaging and the workflow still land. Do not paste
credentials into issues or chat.

## Remaining gates

Source-derived bulk beyond these four public authorities, OSF licence
resolution, and stable-v1 promotion remain independent gates.
