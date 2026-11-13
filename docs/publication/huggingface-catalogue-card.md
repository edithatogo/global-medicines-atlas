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
configs:
- config_name: source_inventory
  data_files:
  - split: train
    path: inventory/source-inventory.parquet
---

# Global Medicines Atlas source catalogue

[![GitHub CI](https://github.com/edithatogo/global-medicines-atlas/actions/workflows/test-goblin.yml/badge.svg?branch=main)](https://github.com/edithatogo/global-medicines-atlas/actions/workflows/test-goblin.yml)
[![Software DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21734811.svg)](https://doi.org/10.5281/zenodo.21734811)

[GitHub homepage](https://github.com/edithatogo/global-medicines-atlas) ·
[User guide](https://github.com/edithatogo/global-medicines-atlas/blob/main/docs/user-guide.md) ·
[Roadmap](https://github.com/edithatogo/global-medicines-atlas/blob/main/conductor/roadmap.md) ·
[Code/data rights](https://github.com/edithatogo/global-medicines-atlas/blob/main/DATA_LICENSE.md)

## The medallion model — applied to this archive

![Four GMA layers: Bronze contains B0 index, B1 acquisition metadata and B2 immutable native evidence; Silver typed data, Gold reviewed links and Platinum products follow with separate acceptance gates.](https://huggingface.co/datasets/edithatogo/global-medicines-atlas-catalogue/resolve/main/assets/medallion.svg)

**Bronze B0** indexes authorities, datasets and URLs; **B1** binds rights,
retrieval dates, native identity and checksums; **B2** preserves native bytes
or a lawful immutable reference. Those are strata inside Bronze. Parquet and
catalogues are rebuildable projections. Silver preserves typed source fields
and explicit unknowns, Gold qualifies relationships, and Platinum supplies the
CLI, API, Atlas and reproducible exports. Regulatory approval, public funding,
formulary and terminology assertions remain separate.

This catalogue is a discovery/archive surface, not proof of full acquisition,
current global coverage or production acceptance. Related approved archives:
[Australian MBS](https://huggingface.co/datasets/edithatogo/australian-mbs-source-archive),
[Australian PBS](https://huggingface.co/datasets/edithatogo/australian-pbs-source-archive),
and [historical NZULM 2023](https://huggingface.co/datasets/edithatogo/nzulm-2023-source-archive).
Their own editions, receipts, source terms and licence exclusions govern use.

## Australian MBS and PBS archives

The public Australian inventory was reconciled on 13 November 2026.
All 1,759 frozen objects matched their approved archive identities.
The September 2025 PBS schedule API ZIP contains 33 CSVs. Historical MBS
demographics source ZIPs start in 1993. PBS utilisation includes the 1991–2008
ATC2 teaching CSV and the May 2002–January 2015 AIHW historical workbook.

[Pinned revisions, the September ZIP and its 33 member names, and qualification status](https://github.com/edithatogo/global-medicines-atlas/blob/main/docs/qualification/australian-public-archive-reconciliation-20261113.md) ·
[MBS utilisation archive](https://huggingface.co/datasets/edithatogo/australian-mbs-utilisation-archive) ·
[PBS utilisation archive](https://huggingface.co/datasets/edithatogo/australian-pbs-utilisation-archive)

<!-- gma-progress:start -->
## Roadmap snapshot — 3 November 2026

![Roadmap ledger completion](https://huggingface.co/datasets/edithatogo/global-medicines-atlas-catalogue/resolve/main/assets/roadmap.svg)

**14/20 delivery tracks closed (70%); 84/92 tracked Stable v1 requirements verified (91.3%).** Measured on 3 November 2026. 6 tracks and 8 requirements remain open.

These are separate, unweighted ledger counts, not worldwide source coverage, effort or release readiness. A single mandatory gate can block release.

[Measurement and bound snapshot](https://github.com/edithatogo/global-medicines-atlas/blob/main/docs/project-overview.md). Federation, independent recovery and production service qualification retain their gates.
<!-- gma-progress:end -->

## Citation and reuse

For software, use [CITATION.cff](https://github.com/edithatogo/global-medicines-atlas/blob/main/CITATION.cff)
and record the exact commit. DOI
[10.5281/zenodo.21734811](https://doi.org/10.5281/zenodo.21734811) identifies the
archived software prerelease; it does not identify all later data snapshots.
For data, cite the upstream authority and edition, this dataset identifier, the
full immutable revision, object path and SHA-256. Apache-2.0 applies to
project-owned code/metadata; it does not relicense third-party source material.


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

## Historical access/versioning inspection — 27 October 2026

Public repository with anonymous access. Public availability does not itself establish source reuse permission or completeness.

Explicit compatible table subsets are configured; manifests and unrelated raw/source artifacts are excluded from automatic row loading.

The asset inventory was checked at revision `a30a649a25c93740109d306f7b7edfd6cd268ac3`. Counts/status in source receipts apply to those editions and runs, not all upstream sources. Snapshots, candidates, fixtures and metadata-only products must not be represented as complete released datasets or clinically/operationally validated products.

Start with [SHA256SUMS](https://huggingface.co/datasets/edithatogo/global-medicines-atlas-catalogue/blob/a30a649a25c93740109d306f7b7edfd6cd268ac3/SHA256SUMS).

For reproducible use, record this repository identifier, pinned revision and relevant manifest/object hashes, plus the upstream source and required attribution. Use `hf_hub_download` with an explicit `revision` and `repo_type="dataset"` for individual assets; verify published checksums before transformation. Code licences do not override source-document, base-model or third-party rights. Where a dataset-wide licence is not established, `license: other` means inspect the recorded source terms and do not assume a new grant.

Report metadata or integrity concerns through this repository's Community tab or its identified source-project tracker, with revision/path/hash. Do not disclose sensitive payloads or private access details publicly. This metadata maintenance does not authorise model deployment, new data release, medical decisions or source-rights changes.
