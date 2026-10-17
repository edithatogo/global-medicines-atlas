# M-111 public consumer preflight — 2026-10-17

## Result

M-111 remains **blocked**. The current MBS Silver product has a verified
public identity and six exact Parquet object identities, but its manifest is
candidate-only and it has no independent product admission. The API, CLI,
Atlas, and export surfaces therefore must not claim a successful public
consumer query for it. The 57 focused fail-closed and consumer-control tests
pass; they verify unavailable/unknown behavior and the guards against
self-admission. They do not turn a candidate into an admitted product or
qualify a successful query.

## Exact pinned public product

The current candidate is `silver/mbs/v4/2025-07-v3` in
`edithatogo/australian-mbs-source-archive`. The public archive head is
`da83cad9116e2f9a5b927be7b080e9a5e5ea6998`; its root archive manifest SHA-256
is `68e6bb97ee43117b860ff1c57e625a00075c734e933d08b3cd67de673432d055` and
contains 212 source-archive objects. The current nested Silver product manifest
at `silver/mbs/v4/2025-07-v3/manifest.json` has the same SHA-256,
`bbdb1bdac49fc1a7f8399ca02cf52a9b0e3a1fbc31e472e3957f1d278ab39a59`, as the
previously qualified candidate. All six Parquet table objects match the
manifest SHA-256 and byte count returned in anonymous resolve response headers;
the two small, value-free JSON sidecars were fetched and hashed against the
manifest. All eight identities match at the current revision. No Parquet or
source payload bytes were read. The root archive manifest does not list this
separate nested Silver prefix, so its identity is bound by the nested manifest
and exact object digests rather than root-manifest membership. The original
product publication revision is
`ba82cd1d0f9b0f28514df431b8da3a6c207d76fa`. The current product qualification
explicitly remains `candidate_only`; successful consumer queries were not
attempted.

The current qualification reports six tables and nine files including the
nested manifest, while the existing value-free parity receipt binds the exact
table paths, row/field counts, byte counts, and SHA-256 values. These
identities are preserved in the machine-readable report.

The parity and identity receipts are technical evidence only. They do not
provide a new rights conclusion, product admission, representative cohort,
current-coverage claim, or permission to publish another product.

## Consumer controls

The focused suite covers the API's bounded unavailable response, CLI runtime
failure handling, Atlas preservation of unknown states, and export/package
guards. It also verifies that verified transport, mutable candidate metadata,
or empty trust cannot self-admit an Australian product. The current run
passed 57 tests with one existing Starlette/httpx deprecation warning.

All four consumer surfaces remain blocked for successful public-product
queries until an exact product is independently admitted with its source
rights, lineage, and semantic evidence. After admission, M-111 still requires
freshness, denominator and cohort coverage, confidence/review canaries,
per-surface query results, and public export restore evidence.

No source or Parquet payload bytes were downloaded for this preflight. No
consumer query, admission, rights decision, publication, or release was
performed.
