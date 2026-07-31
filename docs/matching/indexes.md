# Regenerable Matching Indexes

Semantic retrieval is optional candidate generation. It does not establish
medicine, clinical, or therapeutic equivalence, and its absence does not
disable deterministic identifier or lexical matching.

The canonical input is a governed set of medicine records plus embeddings
supplied by an external, separately reviewed process. This repository does not
silently download a model or generate embeddings while building an index.

Each index row records the canonical concept identifier, mapping level, source
snapshot, schema version, text-field selection version, and vector. The
governed `SemanticIndexIdentity` additionally binds the index schema version,
index version and digest, embedding model identifier and immutable revision,
source snapshot digest, vector dimension, and timezone-aware generation
timestamp. An observed
identity must exactly equal the expected identity before LanceDB is imported or
opened. Query vectors with a different dimension fail closed. Rows are sorted
before hashing so regeneration is independent of input order.

LanceDB is a disposable derived store. Delete and regenerate it from governed
inputs whenever its schema or lineage changes. `manifest.json` is metadata
only; it does not grant permission to redistribute source text, embeddings, or
the index.

Generate an index from JSONL rows and a JSON lineage document:

```console
uv run --python 3.14.6 python scripts/generate_matching_indexes.py \
  rows.jsonl lineage.json build/matching-index
```

LanceDB is installed only by the `semantic` extra; it is retained in development
test groups for adapter verification. Applications should construct
`optional_semantic_retriever(...)`. A missing dependency, identity, unreadable
index, or identity mismatch returns a deterministic empty candidate set,
leaving the authoritative exact-identifier and lexical paths operational.
Semantic hits can only be appended after those authoritative candidates and
never establish equivalence.
