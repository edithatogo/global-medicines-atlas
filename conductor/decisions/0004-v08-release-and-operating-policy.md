# ADR 0004: v0.8 release and operating policy

## Status

Accepted on 2026-07-31 by the accountable maintainer.

## Decision

Global Medicines Atlas will qualify v0.8 as a software-only release candidate.
Python 3.14 remains authoritative. Mojo remains an experimental, measured
kernel path with a complete Python fallback and may be promoted only through
ADR 0003.

The repository will use strict solo-maintainer governance: pull requests,
linear history, resolved conversations, required automated checks, and
administrator enforcement, with no invented reviewer requirement. Emergency
bypass must be exceptional and auditable.

Codecov is the authoritative hosted coverage service. Its project target is
91%, its patch target is strictly above 90%, and Test-Goblin lanes upload
separate flags through GitHub OIDC. GitHub-hosted Linux is the blocking
performance-baseline environment.

Renovate will use the GitHub App once the maintainer authorizes installation.
Until then, its validated repository configuration is preparation rather than
evidence of an active dependency-update service.

The original `nzmedicines` repository will be retained narrowly as a
compatibility mirror. The canonical implementation and future development
remain in Global Medicines Atlas.

## Research and publication gates

The OSF protocol, preregistration, Hugging Face dataset records, Zenodo
metadata, and linkage manifests may be prepared offline. OSF is now deprecated
as a live identity. Hugging Face public/no-credential catalogue archival and
the software-only Zenodo record exist. They must not be used to imply
redistribution of restricted medicine payloads. Preregistration must precede
substantive live comparative analysis.

International source evidence will be assembled as a provenance and rights
pack. Redistribution, licence interpretation, and consequential status claims
require human source-specific determination.

## Delivery order

1. Complete operational-hardening Phase 3 and qualify the software-only v0.8
   candidate.
2. Prepare the academic protocol and preregistration offline.
3. Complete stable-v1 engineering.
4. Resolve rights and live-source qualification gates.
5. Obtain explicit approval for each external publication.
6. Publish only the approved records and artifacts.

## Consequences

- A green software release does not imply that live medicine datasets are
  publishable, globally complete, or clinically equivalent.
- Mojo, external publication, source redistribution, and disaster-recovery
  claims remain evidence-gated.
- Hosted state must be recorded separately from local configuration.
