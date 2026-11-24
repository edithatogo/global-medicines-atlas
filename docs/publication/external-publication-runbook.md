# External publication runbook

This runbook keeps the software, research protocol, and medicine datasets as
separate publication identities.

## Current identities

| Output | Canonical system | Publication state |
| --- | --- | --- |
| Source and software release | GitHub | `v1.0.0rc1` published as a prerelease |
| Software archival record | Zenodo | Published at [10.5281/zenodo.21734811](https://doi.org/10.5281/zenodo.21734811) from `v1.0.0rc1`; software-only |
| Protocol and preregistration | In-repo + Zenodo | Persistent identity is `research/protocol/` plus [10.5281/zenodo.21734811](https://doi.org/10.5281/zenodo.21734811). OSF is deprecated. |
| Catalogue metadata and public FDA/EMA/TGA/Medsafe artefacts | Hugging Face | Published at [`edithatogo/global-medicines-atlas-catalogue`](https://huggingface.co/datasets/edithatogo/global-medicines-atlas-catalogue); durable publisher is GitHub Actions `.github/workflows/data-layer-archive.yml`. Credential-gated payloads remain withheld. |
| Dataset archival record | Zenodo | Separate record, only for assets with explicit redistribution rights |

## Bulk archive identities

Two complete source mirrors are separate publication identities from the
bounded catalogue. They are dispatched from `main` by
[`.github/workflows/publish-bulk-archive.yml`](../../.github/workflows/publish-bulk-archive.yml)
for the original source-backed archives. Direct online openFDA transfers now
use GitHub-hosted runners and stage only a small group of ZIPs at a time.

| Batch contract | Hugging Face identity | Contents |
| --- | --- | --- |
| `quality/source-batches/openfda-all-20261030/` | `edithatogo/global-medicines-atlas-openfda-all-20261030` | Every recorded `download.open.fda.gov` partition across 31 openFDA endpoints, unmodified source JSON zips with per-partition receipts. |
| `quality/source-batches/faers-live-20260821/` | `edithatogo/global-medicines-atlas-faers-live-20260821` | 90 FAERS/AERS quarterly releases, 2004-Q1 to 2026-Q2, with receipts, lineage and source-faithful Parquet projections. |

Neither identity adds endpoints to the B0 source index, and presence in either
archive is not Atlas coverage. The FAERS container `faers-history.private.tar`
is excluded because it duplicates the published corpus byte for byte; the
`private` marker names the workspace that held the bytes, not a restricted
classification.

## Hosted openFDA snapshots

[`publish-fresh-openfda.yml`](../../.github/workflows/publish-fresh-openfda.yml)
checks FDA's download index daily at 16:17 UTC. A different index is retained
as a candidate for review. An approved batch is identified by a committed
`quality/source-batches/openfda-YYYYMMDD/manifest.json` with an explicit
maintainer approval, the exact index SHA-256, the approved endpoint counts,
the UDI exclusion and the corresponding Hugging Face dataset. Unapproved
indexes get a summary and an artifact and have no publication job.

The schedule checks the newest approved edition. Dispatch with
`publish=false` for a preview or with `batch` and `publish=true` for an approved
edition. Publication resumes from `ARCHIVE-PROGRESS.json` and verifies its
committed file inventory before retrieving any missing ZIPs. If FDA changes
the approved index during capture, the run stops and retains its checkpoint.
The final commit replaces the checkpoint with the full artifact manifest.
The verifier can rerun against that revision without reacquiring FDA data.
Only a successful anonymous readback marks the immutable revision
`archive-verified`. The November 20 edition's prior verified revision is
recorded in its contract.
[November verification](https://github.com/edithatogo/global-medicines-atlas/actions/runs/45098999576)

The distinct [October historical recovery](../../quality/source-batches/openfda-all-20261030/README.md)
uses its committed original checksums and runs on demand when an online
copy is available.

## Required evidence before publication

Every public dataset artifact must have an artifact-level manifest recording:

- source authority and URL;
- retrieval date and snapshot identity;
- fields and transformations;
- licence and redistribution decision;
- required attribution and notices;
- content digest and schema version.

Unknown or unresolved rights block publication. The Apache-2.0 software licence
does not license third-party medicine data.

## Service actions

1. Authorize the Renovate GitHub App and verify the Dependency Dashboard issue.
2. The software record is published from the GitHub release; verify its DOI,
   seven-asset manifest, and software-only boundary during subsequent audits.
3. OSF is deprecated. Do not create or submit OSF registrations. Keep the
   in-repo protocol and Zenodo software record as the persistent identity.
4. GitHub Actions workflow
   [`.github/workflows/data-layer-archive.yml`](../../.github/workflows/data-layer-archive.yml)
   packages FDA, EMA, TGA, and Medsafe public artefacts plus catalogue
   metadata and publishes them to the Hugging Face catalogue identity.
   See [`data-layer-archive-receipt.md`](./data-layer-archive-receipt.md).
5. Publish a separate Hugging Face/Zenodo dataset version only after the rights
   manifest is approved.

## Human gates

Public Hugging Face dataset visibility for the no-credential catalogue and the
software-only Zenodo record already exist. OSF is deprecated. A public stable
software release and any restricted-payload publication remain explicit
maintainer gates.
