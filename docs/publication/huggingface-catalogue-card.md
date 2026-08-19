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

This Hugging Face dataset archives the Global Medicines Atlas data layer that
can be published without credentials: catalogue metadata, publication
contracts, and already-governed representative fixtures. It is not a
redistribution of live third-party medicine source dumps.

## Contents

- `medicine_source_catalog.json`: source authorities, jurisdiction, dimensions,
  available fields, acquisition mode, and rights boundaries.
- `international-resource-v5.json`: canonical resource schema.
- `inventory/source-inventory.parquet`: Arrow/Parquet inventory of every
  catalogued source, with access class and archival disposition.
- `inventory/archival-manifest.json`: skipped sources, fixture provenance, and
  the explicit statement that no live dump was downloaded.
- `fixtures/`: representative governed fixtures for public, no-credential
  sources. These are not live coverage and do not establish current
  authorization, funding, or formulary status.
- `metadata/`: publication identities and the fail-closed source-rights matrix.

## Rights boundary

This archive does not grant rights to source data, terminology, product
information, or regulator/funder content. Each source remains subject to its
own licence, terms, access controls, attribution requirements, and publication
decision. Credential-gated and licensed payloads, including NZULM/NZMT vendor
fixtures, are omitted. Unknown or unresolved rights stay withheld from public
derived-row publication.

## Reproducibility

Canonical source and software repository:
<https://github.com/edithatogo/global-medicines-atlas>

See `SOURCE_RIGHTS.md`, `DATA_LICENSE.md`, and the publication runbook before
using any source listed here.
