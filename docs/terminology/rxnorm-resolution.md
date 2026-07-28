# RxNorm and RxNav-compatible resolution

The atlas uses a tiered resolver instead of requiring the complete
RxNav-in-a-Box distribution.

1. A versioned, offline bootstrap fixture resolves known aliases
   deterministically.
2. An optional RxNav-compatible HTTP endpoint handles misses. The endpoint may
   be the public NLM service, a local RxNav-in-a-Box deployment, or another
   contract-compatible service.
3. Network errors and timeouts fail closed to no match. They never change a
   medicine's regulatory or funding status.

The local fixture is intentionally small. Production extracts must record their
RxNorm release, source receipt, checksum, generation command, and licensing
disposition before promotion.

RxNorm identifiers are terminology links only. A terminology match is not
evidence that a product is approved, marketed, funded, or listed on a
formulary.
