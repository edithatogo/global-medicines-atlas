# Stable v1 publication-metadata qualification

This Phase 3 preflight deterministically verifies the existing publication
contracts and package generator without making an external release. Its
machine-readable result is
`metadata_qualified_external_gates_blocked`, recorded in
`quality/qualifications/stable-v1-publication-metadata.json`.

The qualification regenerates the governed package from the two self-authored
`ZZ-FIXTURE` rows. It then validates the dataset card against the reviewed
Pydantic contract, validates the Croissant record and its canonical Parquet
distribution, and checks every `SHA256SUMS` and package-manifest binding against
the exact emitted bytes. The receipt also binds the input contracts, identity
registry, implementation modules, schemas, script, `uv.lock`, and every
generated package member.

## Publication identity boundary

The identity registry assigns non-overlapping roles to GitHub, Hugging Face,
Zenodo, and OSF. Links between those intellectual objects must be closed and
reciprocal. Configured identifiers must use the expected HTTPS host and remain
unique after normalization.

The current GitHub repository URL is configured but not independently verified
for release purposes. Hugging Face, Zenodo, and OSF identifiers remain null
placeholders. Every licence decision remains unresolved. The qualification
therefore keeps the external-identifier, licence, and publication gates
blocked; it does not infer evidence from a URL, repository configuration, or
passing CI.

## Safety boundary

No restricted data is included. Only self-authored synthetic fixture rows and
reserved `.invalid` evidence URLs are processed. This task performs no external
publication, no release, no signature, no credential lookup, and no remote
write. It does not approve a software or dataset licence and does not qualify a
production medicine-data package.

Run the deterministic check with Python 3.14:

```console
uv run --python 3.14.6 --group dev python scripts/qualify_stable_v1_publication_metadata.py --check
```

Regeneration is explicit and local:

```console
uv run --python 3.14.6 --group dev python scripts/qualify_stable_v1_publication_metadata.py
```

Both commands are offline. The first recomputes every input and rejects a stale
or altered receipt. The second writes only the local deterministic receipt; it
does not publish, sign, create a release, or require credentials.

## Remaining gates

- Production source-by-source redistribution and metadata rights review.
- Durable, non-overlapping Hugging Face, Zenodo, and OSF identifiers.
- Independent identifier evidence for every configured publication surface.
- Explicit maintainer licence selection and stable-release approval.
- A separately qualified production package, signature, release, publication,
  and externally observable verification receipt.

These blockers are expected Phase 3 authority boundaries, not successful
publication claims.
