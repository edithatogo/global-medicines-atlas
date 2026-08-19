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

The live identity registry assigns non-overlapping roles to GitHub, Hugging
Face, and Zenodo. OSF is deprecated as a live publication identity; historical
OSF landing-page verification remains labelled superseded. Links between the
live intellectual objects must be closed and reciprocal. Configured identifiers
must use the expected HTTPS host and remain unique after normalization.

The current registry verifies the GitHub software source, the public
no-credential Hugging Face catalogue archive, and the Zenodo software DOI.
The Hugging Face identifier applies to catalogue metadata, publication
contracts, and representative governed fixtures. It does not license or publish
credentialed or restricted source payloads. The Zenodo identifier applies to
software and is the durable public archival path for the in-repo protocol
artefacts. The qualification therefore keeps the production-package, signature,
and final-publication gates blocked; it does not infer those outcomes from a
URL, repository configuration, or passing CI.

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

- A separately qualified production package, signature, stable-v1 promotion,
  and externally observable verification receipt.
- Production disaster-recovery authority for live production systems.
- Credentialed and restricted source payloads (NZULM, AMT, PBS embargo,
  dm+d/TRUD, EMA PMS, SPOR, and the other skipped sources) remain out of
  scope.

Public/no-credential catalogue archival is complete. OSF registration-record
licence work is cancelled because OSF is deprecated. These remaining items are
isolated authority boundaries, not unfinished OSF or derived-data identity
work.
