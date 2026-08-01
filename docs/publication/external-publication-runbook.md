# External publication runbook

This runbook keeps the software, research protocol, and medicine datasets as
separate publication identities.

## Current identities

| Output | Canonical system | Publication state |
| --- | --- | --- |
| Source and software release | GitHub | `v1.0.0rc1` published as a prerelease |
| Software archival record | Zenodo | Enable GitHub integration; create a software record from the release |
| Protocol and preregistration | OSF | Submission package prepared; registration remains gated by final preview |
| Catalogue and cleared derived data | Hugging Face | Catalogue-only publication is eligible; source-derived bulk data remains rights-gated |
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
2. Enable this GitHub repository in Zenodo and create the software record from
   the published GitHub release.
3. Create the OSF project, upload the prepared submission package, connect
   GitHub and the archival records, and preview the registration.
4. Publish the Hugging Face catalogue-only repository with a dataset card that
   links each source and records the unresolved-data boundary.
5. Publish a separate Hugging Face/Zenodo dataset version only after the rights
   manifest is approved.

## Human gates

OSF registration, public Hugging Face dataset visibility, and public Zenodo
dataset publication are irreversible or difficult-to-reverse dissemination
actions. They require final maintainer confirmation after the service preview
and rights manifest have been inspected.
