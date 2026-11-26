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
GitHub-hosted runner validates the committed frozen plan, pins the
public Hugging Face revision, and compares missing ZIPs with the FDA copies
and pinned Internet Archive captures where available.
Add a reviewed direct public HTTPS URL to [online-sources.json](online-sources.json)
under its exact archived path to check another copy of a ZIP or original receipt.
The runner bounds the download to the original size and requires the frozen
SHA-256. Temporary links, redirects and credentials are excluded.
The run retains the checksum results and missing metadata inventory. Dispatch
with explicit `publish=true` to append files that match. The workflow verifies each
published batch anonymously and retains its immutable revision and digests
in Actions. The October acquisition receipts remain part of the frozen
inventory and require their original bytes.
The runner can reproduce the original dataset README and artifact manifest
from the saved contract and plan. It checks both original hashes and holds
these two files until the rest of the inventory has been restored.

The committed [publication plan](publication-plan.json) is the unchanged
`plan.json` from [Actions artifact 14882420929](https://github.com/edithatogo/global-medicines-atlas/actions/runs/45306884017/artifacts/14882420929).
Its canonical plan SHA-256 is
`1c63f597717bcbcb4753a644f7e7d07387e6f9cac9740833fb7c915ad1456ed0`.
The committed [recovery receipt](online-recovery.json) is the unchanged
`online.json` from [Actions artifact 14898987896](https://github.com/edithatogo/global-medicines-atlas/actions/runs/45348112303/artifacts/14898987896).
It records the 65 new anonymous readbacks and the still-incomplete dataset
at `f0d60240cb55fa591ad6cf15540a0c2ce0a2eab8`.

The maintainer stopped the earlier source route on 24 November and authorised
temporary read-only access to the remaining original files on 26 November.
Use `publish=true` and `private_source=true` together for that approved
connection. The GitHub-hosted runner checks the current Hugging Face revision
and reads only missing originals from the source. It fetches bounded ranges in
parallel and checks each complete file against the frozen SHA-256 before a
four-file commit. It rebuilds the final README and artifact manifest from the
committed plan. The default route checks public
sources. Publication requires the production environment and explicit
maintainer approval. Completion requires a separate job to verify the checksums of all
4,803 files anonymously at one public revision.

For this approved temporary recovery, the hosted publisher stops between
committed batches after approximately four hours and 40 minutes. It retains a
checkpoint and queues the next GitHub-hosted run while the temporary window is
open. An error or a run without checkpoint progress stops the chain for
investigation. The chain stops when the full inventory reaches the independent
verification job; it cannot queue another run after 29 November 2026 at 05:00
UTC. The read-only source remains necessary until all originals are committed.
