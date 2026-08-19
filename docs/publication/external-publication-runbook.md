# External publication runbook

This runbook keeps the software, research protocol, and medicine datasets as
separate publication identities.

## Current identities

| Output | Canonical system | Publication state |
| --- | --- | --- |
| Source and software release | GitHub | `v1.0.0rc1` published as a prerelease |
| Software archival record | Zenodo | Published at [10.5281/zenodo.21734811](https://doi.org/10.5281/zenodo.21734811) from `v1.0.0rc1`; software-only |
| Protocol and preregistration | OSF | Submission package prepared; registration remains gated by final preview |
| Catalogue metadata and public FDA/EMA/TGA/Medsafe artefacts | Hugging Face | Published at [`edithatogo/global-medicines-atlas-catalogue`](https://huggingface.co/datasets/edithatogo/global-medicines-atlas-catalogue); durable publisher is GitHub Actions `.github/workflows/data-layer-archive.yml`. Credential-gated payloads remain withheld. |
| Dataset archival record | Zenodo | Separate record, only for assets with explicit redistribution rights |

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
3. Create the OSF project, upload the prepared submission package, connect
   GitHub and the archival records, and preview the registration.
4. GitHub Actions workflow
   [`.github/workflows/data-layer-archive.yml`](../../.github/workflows/data-layer-archive.yml)
   packages FDA, EMA, TGA, and Medsafe public artefacts plus catalogue
   metadata and publishes them to the Hugging Face catalogue identity.
   See [`data-layer-archive-receipt.md`](./data-layer-archive-receipt.md).
5. Publish a separate Hugging Face/Zenodo dataset version only after the rights
   manifest is approved.

## Human gates

OSF registration, public Hugging Face dataset visibility, and public Zenodo
dataset publication are irreversible or difficult-to-reverse dissemination
actions. They require final maintainer confirmation after the service preview
and rights manifest have been inspected.
