# Temporal qualification procedure

The Phase 3 tooling separates executable fixture qualification from live
evidence. Fixture, synthetic, dry-run and failed receipts cannot satisfy the
live gate.

## Local verification

```text
uv run --python 3.14 --group test-goblin python scripts/test_goblin.py coverage
uv run --python 3.14 --group test-goblin python scripts/test_goblin.py regeneration
uv run --python 3.14 --group typing basedpyright
```

`scripts/build_temporal_qualification.py` creates deterministic fixture-only
lineage without copying source payloads. `scripts/qualify_temporal_release.py`
evaluates supplied receipts, coverage, snapshots and gate outcomes and writes
only ignored build output.

## Live qualification gate

A live-qualified receipt requires all of the following:

1. An authoritative catalogued endpoint and successful bounded retrieval.
2. A UTC retrieval clock, payload digest, byte count and transformation digest.
3. Reviewed permission for retrieval, local processing and retention.
4. A defensible eligible population and temporal coverage denominator.
5. No fixture, synthetic, dry-run, failed or unavailable evidence in the
   qualifying set.

Public release, signing, tagging and external publication remain separate
maintainer gates.
