# Offline federation receipt-byte closure

`verify_receipt_closure` checks supplied opaque receipt bytes against every
receipt reference in an exact, byte-pinned v4 contract. It performs no network
or filesystem operations and never returns receipt bodies.

The immutable result records the contract digest, every nested JSON-pointer
role, and one URL/digest/byte-count entry per supplied URL. A shared URL/digest
may serve several roles without losing their identities. Distinct URLs sharing
a digest still require distinct supplied entries. Conflicting digests at one
URL, missing/extra/duplicate supplied entries, duplicate JSON keys, invalid
schema/semantic claims and digest mismatches are rejected.

Limits are 1 MiB each for contract/schema/receipt bytes, 8 MiB aggregate receipt
bytes, 256 receipt references and supplied objects, and 2,048 characters per
receipt URL. Payload type/count/byte limits precede contract parsing and any
receipt hashing. Only tuple/list inputs are accepted; copied models are
revalidated, immutable bytes are required, and returned nested tuples are
isolated from caller-owned lists. These are input-size bounds, not a process
memory guarantee. Receipt bodies are not parsed or recursively resolved.

The result is explicitly `receipt_bytes_only`: it authenticates neither URLs
nor producers and does not validate the assertions inside any receipt. Even a
fully fabricated but internally matching packet can satisfy byte closure. It
must never directly populate `FederatedReader.admitted_contracts` or establish
rights, publication, cleanup, qualification or promotion authority. Consumers
still need trusted authority/authorization, typed v1–v3 lineage and promotion
checks, and independent public/non-gated anonymous verification. Existing
MBS/PBS receipts are not retroactively promoted to v4.

Tests use synthetic opaque bytes only. No actual receipt acquisition, public
publication, external authentication or complete federation admission is
claimed by this implementation.
