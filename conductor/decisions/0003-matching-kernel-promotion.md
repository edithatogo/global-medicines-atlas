# ADR 0003: Matching kernel promotion

## Decision

Python 3.14 is the authoritative v0.5 matching implementation. Mojo, Rust and
Tantivy are not promoted.

## Rationale

The current fixtures establish correctness and deterministic regeneration, but
they are not a representative production-scale corpus. No Scalene profile or
repeatable benchmark demonstrates a material bottleneck that outweighs the
additional parity, packaging, supply-chain and maintenance burden.

## Promotion gate

An alternative kernel may be promoted only when it:

1. preserves candidate ordering, feature values, abstention decisions and
   reason codes on shared fixtures;
2. provides a material, repeatable benefit at representative scale;
3. passes calibration, deterministic-regeneration and supply-chain checks; and
4. retains the complete Python 3.14 fallback.

Tantivy is limited to lexical retrieval evaluation. Mojo is limited to
profiled normalization or scoring kernels. Neither may redefine the mapping
policy or convert candidates into clinical-equivalence claims.
