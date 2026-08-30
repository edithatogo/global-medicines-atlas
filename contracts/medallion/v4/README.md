# Public dataset federation v4

This additive contract describes one immutable public object and the receipts
supporting its distribution. It does not replace medallion v1 promotion,
v2 field lineage, or v3 replay contracts. Their referenced documents still
require their own schema and semantic validation. Distribution does not promote
a medallion layer or turn MBS service-benefit evidence into medicine evidence.

## Portable conformance

Consumers vendor `federation.schema.json` unchanged and pin its SHA-256:
`ac28485a70e0853266e4c140f9a07cd557eb27816b0b408b9bf2927a4cffacec`.
Validate using JSON Schema Draft 2020-12 **with format validation enabled**,
then call `global_medicines_atlas.federation.validate_federation_semantics`.
The semantic function expects schema-validated input; it is not a parser or
untrusted-input boundary. Python is the complete fallback. Future incompatible
schema changes require a new version rather than editing these frozen bytes.

The `fixtures/` documents and the tests in `tests/test_federation_contract.py`
are portable positive/negative canaries. All fixture identities and receipts
are synthetic and grant no publication or clinical authority. They are not
examples of a real hosted run, replica, or collection. Local GMA conformance
does not establish adoption by any other repository. Downstream entries remain
empty until exact consumer commits and canary receipts exist.

This extends the existing byte-pinned v1-v3 pattern also found in the
maintainer-owned reimbursement-atlas `contracts/medallion` directory; no second
authority, transport client, dependency, or source acquisition path is added.

## Identity and evidence

Every object binds producing and contract repositories, Git commits, source and
acquisition identities, layer/stratum, representation, schema era, comparison
cohort, effective and retrieval dates, Hub dataset/revision/path, bytes and
SHA-256. Optional observed Xet/LFS identities are null when unknown, not
invented. Paths use a deliberately conservative portable character set; mutable
branches, absolute paths, traversal, URL escapes and empty components fail.

Publication must identify GitHub Actions and its workflow/run/commit. The
anonymous clean-room verification must bind the same dataset, revision, path,
byte count and digest. Authorization binds the exact digest and destination;
sensitivity and publication are independent, required states. Receipt references
carry their own digest so a mutable issue URL is not sufficient identity.

Schema validation and semantic consistency **do not prove any claim true**.
Before admitting live data, consumers must authenticate the authority and
authorization records, verify the contract schema digest against their trusted
pin, resolve referenced receipt digests, validate v1-v3 lineage/promotion
evidence, check the exact public/non-gated revision and anonymously verify
bytes. A document containing `passed` is not itself a verification result.
Never fetch an arbitrary receipt URL without the existing HTTP destination,
size and timeout policy. This module performs no I/O or automatic promotion.

## Recovery and cache boundaries

A primary can honestly retain null RPO/RTO and pending independent restoration.
A compatibility duplicate cannot claim independence. An independent replica
declaration needs distinct administrative domains and observed geographic
regions, non-null RPO/RTO targets, authorization, and a restore receipt; these assertions still require
external verification. Same-account HF copies are compatibility, not independent
durability. Non-HF publication and independent-target provisioning are separate
gates and are not implemented by this schema.

Mandatory text cannot be blank or padded. Replica domain and region identities
are compared case-insensitively after trimming; formatting does not establish
independence. B0 is exclusively an index, never a rebuildable projection.

Caches have a finite byte budget, creation/expiry, origin, offline policy, and
cleanup state. Removed caches require a cleanup receipt; transient caches cannot
claim removal. These fields are a policy contract, not a cache implementation.
Offline readers must fail closed or use only exact verified content. Raw B2
objects remain distinct from rebuildable projections; every projection needs
input lineage and later layers additionally require promotion evidence.

## Remaining integration

This is the schema/semantic foundation. Hosted manifest emission, complete
estate enumeration, live v4 receipts, remote readers, cache enforcement,
cross-repository adoption and independent recovery still need implementation
and qualification. Existing MBS/PBS receipts are not retroactively called v4.
