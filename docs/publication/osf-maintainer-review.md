# OSF maintainer review and registration gate

**Review scope:** issues [#66](https://github.com/edithatogo/global-medicines-atlas/issues/66) and [#70](https://github.com/edithatogo/global-medicines-atlas/issues/70)  
**Package:** [`research/preregistration/`](../../research/preregistration/)  
**Manifest:** [`osf-submission-manifest.json`](../../research/preregistration/submission/osf-submission-manifest.json)  
**Status:** package review complete; OSF registration not verified or submitted

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

The OSF link is not treated as a registration receipt. The anonymous OSF API
request to `https://api.osf.io/v2/nodes/pcdnm/` returned `401 Unauthorized` on
2026-08-01. The public landing page returned HTTP 200 but did not expose a
machine-verifiable registration state.

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

Until those receipts exist, the package remains `draft_not_submitted` and the
OSF identity remains `unresolved`. No source-derived dataset is to be added to
the OSF package as part of this gate.
