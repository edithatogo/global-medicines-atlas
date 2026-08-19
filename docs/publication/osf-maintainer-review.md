# OSF maintainer review and registration gate

**Status:** OSF deprecated (2026-08-19). Do not complete OSF licence resolution
or further OSF submission. Historical landing-page verification of `ej5nf`
remains below as a superseded receipt. Persistent identity: in-repo protocol
plus Zenodo DOI `10.5281/zenodo.21734811`.

**Review scope:** issues [#66](https://github.com/edithatogo/global-medicines-atlas/issues/66) and [#70](https://github.com/edithatogo/global-medicines-atlas/issues/70)  
**Package:** [`research/preregistration/`](../../research/preregistration/)  
**Manifest:** [`osf-submission-manifest.json`](../../research/preregistration/submission/osf-submission-manifest.json)  
**Historical status:** package review complete; public OSF registration and DOI were verified, then superseded by deprecation

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
| OSF | protocol and preregistration | registration [`https://osf.io/ej5nf/`](https://osf.io/ej5nf/); DOI `10.17605/OSF.IO/EJ5NF` |

The OSF project is now authenticated and a private draft registration was
created from it. Draft ID: `6a6dca79265e7ef20ac266e1`; review URL:
`https://osf.io/registries/drafts/6a6dca79265e7ef20ac266e1/review`. This is not
a submitted or public registration.

The project storage contains all ten expected package files, including the
manifest, covering narrative, structured responses, protocol, analysis plan,
amendment history, deviation register, data-management and ethics statement,
citations, and README. Authenticated schema validation confirms all 16 required
response keys and 17 total responses are present in the private draft. The
registration `ej5nf` was created on 2026-08-03 from the draft and is now public
with `pending_registration_approval=false`. OSF assigned DOI
`10.17605/OSF.IO/EJ5NF`. The registration landing page is
[`https://osf.io/ej5nf/`](https://osf.io/ej5nf/); the durable API receipt is
[`https://api.osf.io/v2/registrations/ej5nf/`](https://api.osf.io/v2/registrations/ej5nf/).

## Registration gate

OSF is deprecated. The historical licence-missing caveat for registration
`ej5nf` is superseded and must not be treated as an open task. Do not complete
OSF licence resolution or further OSF submission.

The registration receipt records the registration URL, registration
identifier, timestamp, package digest, public/embargo state, and API or landing
page receipt to [`external-publication-receipt.md`](./external-publication-receipt.md)
and `quality/qualifications/publication-identities.json`.

No source-derived dataset is covered by this registration or added to the OSF
package as part of this gate.
