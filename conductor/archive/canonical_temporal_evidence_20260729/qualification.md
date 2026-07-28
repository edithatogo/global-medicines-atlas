# Temporal qualification procedure

Archived procedure. External live qualification remains open in issue #54.

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

## Exact fixture-to-live transition

Fixture qualification proves only that the schemas, transformations,
reconciliation rules and release machinery execute deterministically. It does
not promote, mutate or reuse a fixture receipt as live evidence.

Promotion to `live_qualified` requires a new qualification run whose complete
input set replaces fixture evidence with:

1. Newly acquired `EvidenceClass.LIVE` source receipts for the authoritative
   payloads used by the release.
2. `RightsState.PERMITTED` and a reviewed rights reference on every qualifying
   receipt.
3. Successful retrieval timestamps, payload digests, byte counts and
   transformation lineage that are verified as current by the
   `live_lineage_verification` gate. A stale retrieval must fail that gate;
   this workflow does not invent one universal source-age threshold.
4. Coverage observations reconciled to each qualifying receipt by receipt ID,
   source ID and jurisdiction, with non-null eligible denominators.
5. A clean repository, declared schema and migration versions, and every
   requirement gate passing.

The resulting release evidence may be `live_qualified`, but it cannot approve,
sign, tag or publish itself. Requesting approval without a separately verified
maintainer approval receipt remains blocked.

The golden negative-control matrix in
`tests/fixtures/release-evidence/blocked-live-v0.4.json` is executable evidence
that fixture, synthetic, unknown-rights, stale and denominator-free inputs
cannot promote v0.4.

## Durable external-gate transfer

All remaining source-specific rights review, lawful current acquisition,
immutable live receipts, defensible live denominators, dm+d access, Japanese
translation review, live API/bulk population-equivalence qualification and
final publication qualification are transferred to
[GitHub issue #54](https://github.com/edithatogo/global-medicines-atlas/issues/54).

Closing or archiving this local implementation track does not close issue #54,
does not create live-qualified evidence and does not imply publication
approval. A future live promotion must cite the issue resolution evidence and
produce a fresh release-evidence record from the qualifying live inputs.

Public release, signing, tagging and external publication remain separate
maintainer gates.
