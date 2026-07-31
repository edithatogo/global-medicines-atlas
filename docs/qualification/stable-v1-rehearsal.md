# Stable v1 aggregate rehearsal

Run the deterministic representative rehearsal with:

```console
uv run --python 3.14 python scripts/rehearse_stable_v1.py
```

The command writes a content-bound receipt to
`build/stable-v1/rehearsals/aggregate.json`. It runs the canonical schema-v1 to
schema-v2 migration and exact rollback in both a constrained child process and
the controlling process, then executes the governed local recovery rehearsal.
Any identity, assertion-kind, restore, rollback, or receipt-integrity mismatch
fails closed and leaves no aggregate receipt.

This is deterministic representative-fixture evidence. The child process
strengthens independence from parent-process state, but it is not the
artifact-only stable-release clean room: it uses the current checkout and
interpreter. The recovery exercise uses synthetic local artifacts and does not
qualify production disaster recovery, independent backup storage, RPO, RTO,
or crash consistency. It performs and claims no GitHub, Hugging Face, Zenodo,
OSF, or other external publication.
