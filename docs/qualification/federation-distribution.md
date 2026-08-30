# Derived-object distribution inventory

`reconcile_distribution` in the optional federation surface checks a complete
producer-supplied output inventory against exact v4 contract bytes. It reuses
the frozen v4 schema, its format validators and semantic checks, alongside the
reader's schema pin and metadata byte ceiling. No dependency versions change.

Supply `ProducedObject` entries from the producing job, not by reading the
contracts being checked. Each entry binds producer, source, acquisition, layer,
Bronze stratum, portable target path, digest, byte count and synthetic/live
evidence kind. B1 and B2 projection provenance cannot be substituted; later
layers require a null stratum through the existing v4 semantic checks.
Supply the separately governed layer-to-dataset topology as `destinations`.
The function performs no source reads, network requests or publication.

Every output must match exactly one primary projection at a public, non-gated,
immutable revision. Missing and extra contracts, duplicate producer identities,
duplicate remote locations, substituted bytes, raw objects and replica entries
fail closed. Bindings retain producer order and the SHA-256 of the exact JSON
bytes. Raw B2 objects belong to source archives, not this derived denominator.
An empty denominator is rejected rather than called complete.

This is an **internal-consistency check**, not an admission engine. The caller
is responsible for independently establishing the denominator's completeness,
destination authority and authenticity of rights, publication, verification and
lineage receipts. A successful binding must not be converted directly into a
reader admission allowlist. Self-reported JSON is not independent evidence.

Existing GMA source-specific archive manifests preserve B1/B2 authority and are
not replaced. The previously inspected reimbursement-atlas v1-v3 contracts
remain unchanged. This additive v4 utility introduces no new archive format,
destination name, dependency, data licence or downstream deployment claim.

Synthetic tests cover all four medallion layers, exact-denominator failures,
identity substitutions, revision/visibility/path guards, schema and format
checks, metadata limits, replica/raw exclusion and deterministic output order.
Live producer integration, independent receipt admission, public derivatives
and independent recovery remain separate open track requirements.
