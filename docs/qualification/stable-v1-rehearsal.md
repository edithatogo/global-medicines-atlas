# Stable v1 aggregate rehearsal

Run the deterministic representative rehearsal with:

```console
uv run --python 3.14 python scripts/rehearse_stable_v1.py
```

The command writes a content-bound receipt to
`build/stable-v1/rehearsals/aggregate.json`. A constrained child process
independently computes the representative schema-v1 and schema-v2 identities.
The controlling process repeats the migration, verifies determinism, performs
the exact schema-v2 to schema-v1 rollback, and executes the governed local
recovery rehearsal. Any identity, assertion-kind, restore, rollback, current
input, schema, fixture-tree, or receipt-integrity mismatch fails closed and
leaves no aggregate receipt.

The receipt binds the aggregate implementation, runner, dependency lock,
canonical and rehearsal schemas, recovery implementation, representative
fixture identities, and a deterministic qualification-input tree identity.
Verification re-hashes those inputs from the current checkout; a valid
self-hash alone is insufficient.

This is deterministic representative-fixture evidence. The child process
strengthens independence from parent-process state, but it is not the
artifact-only stable-release clean room: it uses the current checkout and
interpreter. The recovery exercise uses synthetic local artifacts and does not
qualify production disaster recovery, independent backup storage, RPO, RTO,
or crash consistency. It performs and claims no GitHub, Hugging Face, Zenodo,
or other external publication. OSF is deprecated and is not a rehearsal target.
