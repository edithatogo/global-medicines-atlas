# Federated immutable-object reader

Install the opt-in `global-medicines-atlas[federation]` extra. This reuses the
already-locked JSON Schema library without adding it to the default runtime.
The core Python/Mojo fallback and v1-v4 schema bytes are unchanged.

`FederatedReader` implements the transport/cache part of the v4 consumer
contract. It does **not** decide source rights, authenticate producers, or
approve publication or layer promotion. Before adding an exact document digest
to `admitted_contracts`, the consuming application must independently verify
its producer authority, hash-bound authorization/publication/verification
receipts and v1-v3 lineage/promotion evidence. Never compute an allowlist entry
from arbitrary downloaded JSON merely to bypass this boundary. An empty
allowlist admits nothing; changing receipt or policy bytes changes admission.

Supply the unmodified v4 schema bytes. The reader pins their SHA-256, validates
the document with format checks and existing semantic guards, and checks its
schema identity. The schema is not downloaded at runtime. Synthetic fixtures
are not real publication evidence.

## Retrieval and local-data boundary

An online open performs anonymous metadata and payload requests at the exact
Hub dataset/revision/path. It rejects private/gated/misbound metadata, HTTP
failures, non-identity encoding, excessive redirects, partial/oversized objects
and digest mismatches before exposing a seekable stream. It never falls back
silently to an older cache. `VerifiedRead.origin` distinguishes remote retrieval
from explicit offline reuse; the contract digest and object identity travel
with the stream.

Live raw B2 source reads require the GitHub Actions run environment. Local
qualification uses only synthetic byte fixtures, with no live source download.
Approved derived-product reads may use transient local materializations. There
is no upload, visibility mutation, automatic source discovery or publication
path. Run-environment checks are a fail-closed operational guard, not a claim
that environment variables alone authenticate a hostile process.

The production transport reuses GMA's validated-IP binding and private-network
rejection. HTTPS redirects are restricted to the Hub and enumerated HF CDN/Xet
hosts; credentials in URLs, alternate ports and fragments are rejected. Unknown
CDNs require review rather than an unrestricted redirect fallback. No HF token,
netrc credentials or environment proxy is loaded. Cookies are cleared between
redirects. Signed redirect URLs and raw transport errors are not logged.
The transport factory is a trusted test-injection boundary, not untrusted
configuration; production callers use the default binding transport.

## Bounded transient storage

Use `with FederatedReader(...) as reader` and `with reader.open(document) as
result`. The returned stream is read-only and seekable only inside its context.
Payloads stream through 64 KiB chunks into private temporary files rather than
being loaded wholesale into memory. No durable path or source corpus is
created. Cache files are separate from caller-owned result streams, so eviction
or reader close cannot invalidate an active result.

Limits include per-object bytes (also bounded by the admitted contract), total
cache bytes, cache entry count, concurrent open-result count, metadata/document
bytes, redirect count and network timeouts/deadline checks. Temporary payload
storage is bounded by `cache_bytes + max_open_reads * max_object_bytes`, plus
one bounded metadata spool. Each individual blocking network operation has
the configured HTTP timeout; deadline checks also stop further redirects and
body consumption. This is not a hard real-time process termination guarantee.

The cache uses exact document identities, LRU eviction, and the admitted cache
expiry. Expired entries cannot be reused. `offline=True` performs no network
I/O, requires `verified_exact_digest_only`, and rechecks byte count and digest
before returning anything. `fail_closed`, cache miss, expiry and corruption
fail explicitly. Offline success does not claim current remote visibility;
withdrawals/revocations require the caller to refresh its admission set or close
the reader. Online opens always recheck public metadata and bytes.

Only successfully verified public copies enter the cache. Closing or evicting
them removes owned transient copies, never a source archive or remote object.
Failed transfers expose no data and are discarded as incomplete scratch files,
not recorded as successful acquisition or cleanup of an authoritative source.

## Qualification and remaining work

Synthetic HTTP transports exercise the real reader without fake servers,
credentials or live payloads. Tests cover validation/admission, anonymous
redirects, errors and timeouts, identity/visibility, resource ceilings, cache
expiry/corruption, eviction, and active stream lifetimes.

Reuse inspected: reimbursement-atlas commit
`7077fab6de4f566607bb73e5b44cbbe14d8245c0` contains v1-v3 contract staging, not a
v4 bounded consumer. GMA's existing `BoundIPAddressTransport` and v4 semantic
validator are reused rather than creating another acquisition/publication
authority. Dependency versions are unchanged.

This implementation does not establish live v4 emission, automatic admission,
downstream deployment, derived-dataset publication or independent recovery.
Those track requirements remain open. Existing MBS/PBS receipts are not
retroactively labelled v4.
