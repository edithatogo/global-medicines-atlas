---
pretty_name: Global Medicines Atlas source catalogue
license: apache-2.0
language:
  - en
  - mul
tags:
  - medicines
  - regulatory-data
  - pharmacovigilance
  - data-catalogue
  - provenance
  - parquet
---

# Global Medicines Atlas source catalogue

This Hugging Face dataset archives catalogue metadata, publication contracts,
and public/no-credential artefacts for FDA, EMA, TGA, and Medsafe sources.
GitHub Actions (`.github/workflows/data-layer-archive.yml`) is the durable
publisher. Hugging Face is an archive boundary, not an ingest origin.

## Contents

- `medicine_source_catalog.json`: source authorities, jurisdiction, dimensions,
  available fields, acquisition mode, and rights boundaries.
- `international-resource-v5.json`: canonical resource schema.
- `inventory/source-inventory.parquet`: Arrow/Parquet inventory of every
  catalogued source, with access class, authority group, and archival
  disposition.
- `inventory/archival-manifest.json`: skipped sources, live payload IDs, and
  the GitHub Actions publisher identity.
- `payloads/`: live public artefacts for in-scope FDA, EMA, TGA, and Medsafe
  sources with `authentication: none`. Credential-gated sources are omitted.
- `fixtures/`: representative governed fixtures. These are used when a live
  file is too large or rate-limited after three attempts, and they are not
  live coverage.
- `metadata/sources/`: per-source rights, licence, retrieval URI, digest,
  timestamps, native identifiers, and schema notes.
- `metadata/`: publication identities and the fail-closed source-rights matrix.

## Rights boundary

This archive does not grant rights to source data, terminology, product
information, or regulator/funder content. Each source remains subject to its
own licence, terms, access controls, attribution requirements, and publication
decision. Credential-gated and licensed payloads, including NZULM/NZMT vendor
fixtures, EMA PMS FHIR, and SPOR, are metadata-only. Unknown or unresolved
rights stay withheld from public derived-row publication.

## Reproducibility

Canonical source and software repository:
<https://github.com/edithatogo/global-medicines-atlas>

See `SOURCE_RIGHTS.md`, `DATA_LICENSE.md`, and the publication runbook before
using any source listed here.
