# Federation source metadata contract

Public Australian source archives must carry source-specific metadata rather
than a generic repository description. The offline validator covers the MBS
and PBS archive identities independently and requires:

- an exact approved dataset/source pairing and source-specific card title;
- a non-empty intended-use and limitation statement that preserves the
  distinction between benefits, formulary, regulatory and clinical evidence;
- Croissant distributions that exactly equal the receipt-bound provenance
  payload denominator by path, order and SHA-256;
- a citation that names the exact dataset revision;
- complete payload coverage, explicit exclusions, approved permission evidence
  and attribution;
- a distinct correction route, withdrawal policy, and exactly one current
  version-history entry matching the source version and effective date.

`validate_source_metadata` is pure and performs no network or filesystem I/O.
Passing it is metadata readiness only. It is not source admission, rights
approval, anonymous byte verification, publication, or authorization to modify
a Hugging Face dataset or collection.

The historical Phase 1 intended-failure output predates retained evidence and
cannot be reconstructed honestly. The track records that loss explicitly. The
current slice retains its own reproducible intended-red result: test collection
failed with `ModuleNotFoundError` before the validator existed, followed by
valid and hostile fixture qualification after implementation.
