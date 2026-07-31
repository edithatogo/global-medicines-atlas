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
  does not create a second jurisdiction registry.
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

The initial projection intentionally records unresolved gates. It is a contract
for subsequent implementation and evidence collection, not a stable-release
claim.
