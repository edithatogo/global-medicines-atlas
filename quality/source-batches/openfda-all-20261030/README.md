# openFDA bulk archive 2026-10-30

Committed contract for publishing the completed openFDA bulk snapshot as
`edithatogo/global-medicines-atlas-openfda-all-20261030`.

## Frozen inventory

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

Dispatch `.github/workflows/publish-october-openfda-hosted.yml` on `main`
with the default `publish=false` to check online availability. The
GitHub-hosted runner reads the frozen plan retained by Actions, pins the
public Hugging Face revision, and compares missing ZIPs with the FDA copies
and pinned Internet Archive captures where available.
The run retains the checksum results and missing metadata inventory. Dispatch
with explicit `publish=true` to append exact ZIPs. The workflow verifies each
published batch anonymously and retains its immutable revision and digests
in Actions. The October acquisition receipts remain part of the frozen
inventory and require their original bytes.

The maintainer stopped the earlier source route on 24 November. The current
October workflow reads from online services on GitHub-hosted runners.
Publication requires the production environment and explicit maintainer
approval. Completion requires a separate job to verify the checksums of all
4,803 files anonymously at one public revision.
