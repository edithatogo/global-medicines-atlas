# FAERS quarterly corpus 2026-08-21

Committed contract for publishing the acquired FAERS/AERS quarterly corpus as
`edithatogo/global-medicines-atlas-faers-live-20260821`.

## What is published

The `runs/` tree of the private acquisition workspace: 90 quarterly releases
covering 2004-Q1 to 2026-Q2, with download, bronze and content-addressed
clean-room payload copies, per-item receipts, lineage and transformation
records, and source-faithful Parquet projections.

The corpus was exercised on 20 August 2026 with 92 succeeded items, 90 accepted
quarterly releases, 2 quarantined documentation items and no failures.

## What is excluded

`faers-history.private.tar` is deliberately excluded. It is a 28 GB container
whose 2,464 members are byte-identical to `runs/corpus`, so publishing it would
duplicate the archive without adding evidence. Exclusion is set by publishing
`runs/` as the archive root, not by a filter that could silently widen.

## Rights

FAERS/AERS quarterly files are U.S. federal government works and are public
domain in the United States under 17 U.S.C. 105. The `private` marker in the
source workspace names the repository that held the bytes, not a restricted
classification: the payload set is the public FDA quarterly file series.

## Publication route

`scripts/publish_bulk_archive.py`, dispatched by
`.github/workflows/publish-bulk-archive.yml` on the dedicated
`gma-archive` self-hosted runner. Local upload is refused by
`require_hosted_main`; the workflow also requires the production environment and
the explicit maintainer approval value before any external write.
