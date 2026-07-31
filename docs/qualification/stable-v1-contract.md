# Stable v1 qualification contract

The stable-v1 projection is a qualification view over existing authorities. It
does not replace `conductor/requirements.md`, `conductor/maturity-model.json`,
the medicine source catalog, or the governed publication contracts.

Stable promotion fails closed. Every Must requirement must appear in the
projection with evidence or an explicit blocker; every blocking maturity
dimension must reach M5; and every release gate must pass. An unresolved
licence, publication identity, source-maturity assignment, support boundary,
clean-room rehearsal, or maintainer approval keeps `qualification_state`
`blocked`.

## Contract boundaries

- `schemas/canonical-medicine-v2.json` is the structural medicine model for
  substances, products, packages, indications, prices, and restrictions.
- It is not the temporal assertion migration called `v1_to_v2`; migration
  implementations and rollback rehearsals must name both contract families.
- `schemas/comparison-validity-v1.json` makes granularity, indication,
  population, mapping, normalization, and material mismatches explicit.
  `inappropriate_comparison` is an outcome, not an inferred absence.
- Source maturity is projected from the existing source catalog. This contract
  does not create a second jurisdiction registry. The derived matrix in
  `quality/qualifications/stable-v1-source-maturity.json` keys every row to the
  catalog's `source_id`, records documentation readiness, and conservatively
  caps catalog-only evidence at M2.
- GitHub, Hugging Face, Zenodo, and OSF identities have distinct object roles.
  Stable qualification consumes the academic track's identity decisions and
  does not pre-empt them.
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

The initial projection intentionally records unresolved gates. It is a contract
for subsequent implementation and evidence collection, not a stable-release
claim.

## Rehearsal and support gates

`quality/qualifications/stable-v1-rehearsal-plan.json` defines clean-room
reproduction, structural canonical migration, rollback, and governed recovery
as separate receipt-producing rehearsals. It deliberately does not implement
the structural schema migration.

`quality/qualifications/stable-v1-support-readiness.json` is the authoritative
Phase 1 register for candidate platforms, documentation readiness, limitations,
and residual risks. It remains blocked while any blocking risk is unresolved
or a support boundary is unverified.

`quality/qualifications/publication-identities.json` is the authoritative
publication-surface registry. GitHub identifies software source/releases,
Hugging Face a derived dataset distribution, Zenodo a versioned archival DOI
record, and OSF the protocol/preregistration. Related records may link without
reusing object roles or identifiers. A configured URL is not verified evidence,
and no licence is approved without both an expression and durable maintainer
decision evidence. The executable release gate therefore remains blocked until
those external decisions and receipts exist.
