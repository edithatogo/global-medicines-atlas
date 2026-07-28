# ADR 0002: Canonical Repository Identity

- **Status:** Accepted
- **Date:** 2026-07-29
- **Decision:** Use `edithatogo/global-medicines-atlas` as the canonical hosted repository.

## Context

The brownfield workspace began under the local NZULM project name, but the
product compares medicine registration, regulatory approval, funding,
reimbursement, and formulary systems globally. NZULM/NZMT is a first-class
source family rather than the product boundary.

The existing `edithatogo/nzmedicines` repository is valuable prior work and
must retain its history, but its name and narrow FHIR fixture scope do not
describe the global system.

## Decision

The product name is **Global Medicines Atlas**, with repository slug
`global-medicines-atlas`.

The canonical hosted repository is:

`https://github.com/edithatogo/global-medicines-atlas`

It is initially private, with issues enabled and wiki disabled. The local
remote name is `origin`. The repository is created empty so that connection
does not accidentally publish restricted source payloads or an unreviewed
brownfield history.

## Consequences

- Conductor tracks and GitHub issues use `global-medicines-atlas` as their
  canonical repository identity.
- `nzmedicines` is migrated into the monorepository and later retained only as
  an archived or narrowly scoped compatibility mirror after explicit review.
- The first push is a separate publication action gated by tracked-file,
  history, secret, licence, provenance, and large-file audits.
- Public visibility requires a later explicit release decision.

