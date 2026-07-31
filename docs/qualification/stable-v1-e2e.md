# Stable v1 end-to-end product qualification

Run the deterministic Phase 2 qualification with Python 3.14:

```console
uv run --python 3.14.6 --group dev python scripts/qualify_stable_v1_e2e.py
```

The command writes `build/stable-v1/e2e-qualification.json`. Its SHA-256
identity binds a semantic projection of one governed read-only DuckDB fixture,
four comparison-validity negative controls, and the public API, CLI, and Atlas
results. Volatile response timestamps are deliberately excluded from the
projection, so repeated runs are byte-for-byte deterministic.

The receipt qualifies these behaviours on every surface:

- bounded concept search and canonical concept detail;
- jurisdiction and source visibility;
- distinct regulatory and funding conclusions;
- explicit abstention when comparison evidence is unknown; and
- no claim of medicine equivalence, substitutability, therapeutic
  interchangeability, or equal benefit.

The Atlas evidence is its rendered canonical identity, jurisdiction-dimension
cards, source labels, unknown-state explanation, and explicit non-equivalence
language. The qualification also inspects the same comparison response consumed
by the Atlas and verifies all four machine-readable safety flags remain false.

This is fixture-qualified v0.9 candidate evidence. It performs no network,
publication, release, clinical, or regulatory action and does not establish
production data coverage or stable-v1 release approval.
