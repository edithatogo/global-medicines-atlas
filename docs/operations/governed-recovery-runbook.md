# Governed recovery runbook

This procedure rehearses deterministic backup, restore, and rollback for
local governed artifacts. It does not qualify production disaster recovery.

## Rehearse

From a clean checkout with the locked Python 3.14 environment:

```powershell
uv sync --python 3.14.6 --locked
uv run --python 3.14.6 python scripts/rehearse_governed_recovery.py
```

The command writes `build/recovery/rehearsal-receipt.json` and exits non-zero
unless backup verification, restoration, rollback, and failed-restore
quarantine all pass.

## Operator checks

Before restoring real governed artifacts:

1. confirm the source and destination are explicit regular directories;
2. preserve the content-addressed backup receipt with the bundle;
3. verify enough same-filesystem capacity for staging and predecessor
   safeguard copies;
4. stop writers and record the exact canonical state being replaced;
5. retain rollback and failed-restore quarantine directories until the
   incident or maintenance review closes.

Escalate any digest mismatch, symlink, non-regular file, failed safeguard, or
failed predecessor recovery as an integrity incident. Do not retry by copying
individual files around the recovery boundary.

## Limitations and authority gates

The repository qualifies local fixture-artifact behavior only. Selecting
independent immutable storage, credentials, retention, deletion, recovery
point objectives, recovery time objectives, and crash-consistent filesystems
requires maintainer authorization and separate measured evidence.
