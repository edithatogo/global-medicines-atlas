# RxNorm resolution and lineage

RxNorm is used to generate terminology candidates. A result is not a reviewed
cross-jurisdiction medicine mapping and does not establish clinical,
therapeutic, or substitution equivalence.

## Resolution order

Resolution is deterministic and stops at the first tier that returns candidates:

1. The governed local fixture or extract.
2. An optional locally configured RxNav-compatible service.
3. An optional public NLM RxNav endpoint.
4. An empty tuple when every configured tier is unavailable or has no result.

Remote failures do not alter results available from the local fixture. A failed
local service does not prevent a separately configured public fallback.

## Lineage contract

Every candidate carries:

- RxNorm release identity, including an explicit `unverified-current` value
  when an endpoint does not expose a pinned release;
- a deterministic receipt identifier and SHA-256 of the exact fixture or API
  response bytes;
- the query method and endpoint class;
- source URI and timezone-aware retrieval time;
- rights state and, when rights are marked permitted, a rights reference; and
- `candidate_only=true`.

The local fixture uses a fixed retrieval clock to keep regeneration
deterministic. API retrievals use the observed UTC time and hash the exact
response body. Rights default to `unknown`; network success does not qualify
licensing or redistribution.

## Production qualification

A production local extract needs a lawful current release, immutable source
receipt, checksum, release identity, and reviewed rights disposition. Public or
local RxNav availability alone is not evidence that an API and bulk release
describe the same population.

Terminology candidates must pass the matching feature, confidence, abstention,
and adjudication workflow before they can become reviewed mapping assertions.
