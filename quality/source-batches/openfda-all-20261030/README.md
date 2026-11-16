# openFDA bulk archive 2026-10-30

Committed contract for publishing the completed openFDA bulk snapshot as
`edithatogo/global-medicines-atlas-openfda-all-20261030`.

## What is published

Every recorded `download.open.fda.gov` partition for the 31 openFDA endpoints,
stored as the unmodified source JSON zip files, together with the
per-partition acquisition receipts and the acquisition manifest.

## Why a separate dataset

The Atlas catalogue identity publishes a bounded 13-surface FDA cohort. This
archive is a complete bulk mirror of the openFDA download service, so it is a
different publication identity with its own rights record and its own revision
history. Presence in this archive is not Atlas coverage and does not add those
endpoints to the B0 source index.

## Completion of the acquisition

The original run on 30 October 2026 finished with 2,392 of 2,396 partitions.
Four `drug/event` partitions failed and left truncated `.part` files. On
15 November 2026 each was re-fetched from its recorded URL, verified against the
recorded `Content-Length`, and the `.part` files were removed before the
inventory was frozen. The snapshot is now complete at 2,396 payloads.

## Publication route

`scripts/publish_bulk_archive.py`, dispatched by
`.github/workflows/publish-bulk-archive.yml` on the dedicated
`gma-archive` self-hosted runner. Local upload is refused by
`require_hosted_main`; the workflow also requires the production environment and
the explicit maintainer approval value before any external write.
