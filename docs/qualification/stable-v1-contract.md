# Stable v1 qualification contract

The stable-v1 projection is a qualification view over existing authorities. It
does not replace `conductor/requirements.md`, `conductor/maturity-model.json`,
the medicine source catalog, or the governed publication contracts.

Stable promotion fails closed. Every Must requirement appears in the
projection with evidence or an explicit blocker; every blocking maturity
dimension must reach M5; and every release gate must pass. The reconciled
contract remains blocked by current-scope Bronze landing, observable Renovate
output, the resulting M5 transition, and explicit final stable-release
approval. The existing `v1.0.0rc1` authority is not final-v1 approval.

## Contract boundaries

- `schemas/canonical-medicine-v2.json` is the structural medicine model for
  substances, products, packages, indications, prices, and restrictions.
- It is not the temporal assertion migration called `v1_to_v2`; migration
  implementations and rollback rehearsals must name both contract families.
- `schemas/comparison-validity-v1.json` and its executable runtime make
  granularity, indication, population, mapping, normalization, and material
  mismatches explicit. Material mismatches are inappropriate comparisons and
  unknown dimensions abstain. Literal false claim fields prevent any verdict
  from establishing medicine equivalence, substitutability, therapeutic
  interchangeability, or equal benefit.
- Source maturity is projected from the existing source catalog. This contract
  does not create a second jurisdiction registry. The derived matrix in
  `quality/qualifications/stable-v1-source-maturity.json` keys every row to the
  catalog's `source_id`, records documentation readiness, and conservatively
  caps catalog-only evidence at M2.
- GitHub, Hugging Face, and Zenodo identities have distinct object roles. OSF
  is deprecated as a live identity.
- Existing publication rights, checksum, privacy, and verification contracts
  remain authoritative.

## Initial support boundary

Python 3.14 is the authoritative engine. Mojo remains experimental. Windows,
Linux, and macOS are candidate support targets until clean-wheel and sdist
consumer rehearsals verify them. LanceDB is derived acceleration; stable core
installation must remain usable through deterministic fallback without it.

`quality/qualifications/stable-v1-consumer-compatibility.json` defines the
wheel, source-distribution, package-metadata, CLI, API, dynamic-version,
reinstall, core-fallback, and OpenAPI probes. `contracts/openapi-v1.json` is a
minimal public compatibility baseline: path, method, and operation identity
removals fail, and mutation operations remain forbidden. Pull requests execute
the rehearsal independently on Windows, Linux, and macOS and retain one
receipt per platform; the support gate remains unverified until all hosted
receipts pass for the same commit.

The software contracts, clean consumers, structural migration, comparison
validity, discovery, independent fixture reproduction, support documentation,
hosted governance, and bounded publication controls are now verified. This is
still not a stable-release claim: Bronze current-scope completion and Renovate
output remain observable technical gates, and final promotion remains a human
gate.

## Rehearsal and support gates

`quality/qualifications/stable-v1-rehearsal-plan.json` defines clean-room
reproduction, structural canonical migration, rollback, and governed recovery
as separate receipt-producing rehearsals. It deliberately does not implement
the structural schema migration.

`quality/qualifications/stable-v1-support-readiness.json` is the authoritative
register for platforms, documentation readiness, limitations, and residual
risks. Its support boundaries pass. The register remains blocked only because
maintainer-confirmed Renovate activation has not yet produced an observable
Dashboard or update pull request. Production DR remains unqualified but is a
separate, accepted limitation of a software-only stable release.

`quality/qualifications/publication-identities.json` is the authoritative
publication-surface registry. GitHub identifies software source/releases,
Hugging Face a derived dataset distribution, and Zenodo a versioned archival DOI
record. OSF is deprecated. Related records may link without reusing object
roles or identifiers. Apache-2.0 software and the public/no-credential Hugging
Face catalogue archive now have that evidence. Stable-v1 promotion and
production disaster-recovery authority remain isolated remaining gates.
