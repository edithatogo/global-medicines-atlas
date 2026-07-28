# Regenerable Matching Indexes

Semantic retrieval is optional candidate generation. It does not establish
medicine, clinical, or therapeutic equivalence, and its absence does not
disable deterministic identifier or lexical matching.

The canonical input is a governed set of medicine records plus embeddings
supplied by an external, separately reviewed process. This repository does not
silently download a model or generate embeddings while building an index.

Each index row records the canonical concept identifier, mapping level, source
snapshot, schema version, text-field selection version, and vector. The
manifest additionally binds the embedding provider, model and version, index
version, generation command, source snapshot digest, and rights and
redistribution disposition. Rows are sorted before hashing so regeneration is
independent of input order.

LanceDB is a disposable derived store. Delete and regenerate it from governed
inputs whenever its schema or lineage changes. `manifest.json` is metadata
only; it does not grant permission to redistribute source text, embeddings, or
the index.

Generate an index from JSONL rows and a JSON lineage document:

```console
uv run --python 3.14.6 python scripts/generate_matching_indexes.py \
  rows.jsonl lineage.json build/matching-index
```

Applications should construct `optional_semantic_retriever(...)`. A missing,
unreadable, or unavailable index returns a deterministic empty candidate set,
leaving the authoritative deterministic matching path operational.
