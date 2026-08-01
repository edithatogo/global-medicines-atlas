# OSF maintainer review and registration gate

**Review scope:** issues [#66](https://github.com/edithatogo/global-medicines-atlas/issues/66) and [#70](https://github.com/edithatogo/global-medicines-atlas/issues/70)  
**Package:** [`research/preregistration/`](../../research/preregistration/)  
**Manifest:** [`osf-submission-manifest.json`](../../research/preregistration/submission/osf-submission-manifest.json)  
**Status:** package review complete; OSF draft created, not submitted

## Review decision

The repository-owned preregistration package is internally review-ready:

- it is explicitly prospective and descriptive;
- regulatory and public-funding outcomes remain separate;
- the source census is a governed denominator, not a live-coverage claim;
- source-derived payloads are excluded unless rights are separately approved;
- the package has deterministic file sizes and SHA-256 identities;
- the package records amendments, deviations, data management, and ethics
  applicability; and
- the package's external-action flag remains `false` until registration is
  explicitly authorised.

This review does not constitute an institutional ethics determination, legal
rights determination, OSF registration, or approval to publish source-derived
medicine data.

## Identity reconciliation

| Object | Role | Verified state |
|---|---|---|
| GitHub | software source and release | `https://github.com/edithatogo/global-medicines-atlas` |
| Hugging Face | catalogue-only derived distribution | `https://huggingface.co/datasets/edithatogo/global-medicines-atlas-catalogue` |
| Zenodo | software-only archival DOI | [`10.5281/zenodo.21734811`](https://doi.org/10.5281/zenodo.21734811) |
| OSF | protocol and preregistration | project link [`https://osf.io/pcdnm/`](https://osf.io/pcdnm/); registration state unresolved |

The OSF project is now authenticated and a private draft registration was
created from it. Draft ID: `6a6dca79265e7ef20ac266e1`; review URL:
`https://osf.io/registries/drafts/6a6dca79265e7ef20ac266e1/review`. This is not
a submitted or public registration.

The project storage contains all ten expected package files, including the
manifest, covering narrative, structured responses, protocol, analysis plan,
amendment history, deviation register, data-management and ethics statement,
citations, and README. The draft's structured registration responses remain
empty; the uploaded package is therefore retained as review material and the
draft is not submitted.

## Registration gate

Before an OSF registration write, the maintainer must confirm:

1. the final public wording and ethics-applicability statement;
2. the exact manifest digest and package contents to register;
3. the OSF project, contributor, embargo, and registration-template settings;
4. the licence and source-rights boundary for every attached artefact; and
5. that the authenticated OSF account has authority to create the registration.

After an authorised registration, append the registration URL, registration
identifier, timestamp, package digest, public/embargo state, and API or landing
page receipt to [`external-publication-receipt.md`](./external-publication-receipt.md)
and `quality/qualifications/publication-identities.json`.

Until the submission receipt exists, the package remains `draft_not_submitted`
and the OSF identity remains `draft_created_not_submitted`. No source-derived
dataset is to be added to the OSF package as part of this gate.
