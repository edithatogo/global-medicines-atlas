# Shared source URL inventory and bounded downloads

The [canonical catalogue](../../src/global_medicines_atlas/data/medicine_source_catalog.json)
is the single maintained source configuration. The [URL table](source-urls.csv)
contains all 176 existing source IDs, their download/API/discovery URLs,
interface type, authentication, formats, rights status and integration layer.
It is generated, not a second registry. Edit the canonical catalogue when a
verified endpoint changes, then regenerate its projections.

The table preserves missing URLs. A discovery page is not a file endpoint,
public access is not a retention grant, and older exact-inventory publication
approvals do not approve a fresh version. URLs other than the bounded Swiss/EMA
observations have not been rechecked by this change.

| Surface | Shared command behavior | Remaining configuration |
| --- | --- | --- |
| Direct file | One bounded retrieval, unchanged bytes and receipt | Exact endpoint and existing retention/reuse evidence |
| API, single response | Same retrieval through the API surface | Explicit `single_api_response` selection; receipt describes only that response |
| Paginated API | A single response does not complete the dataset | Use the existing source adapter with pagination, rate limits and a stopping rule |
| Search page or document collection | No crawling or document following | Source-specific export/discovery recipe |
| Authenticated/restricted interface | Excluded from this command | Existing approved access route |

## Commands

Use the repository-local Python 3.15.1 environment. Export is offline:

```sh
uv run --no-sync python scripts/source_download_batch.py --urls-output docs/data-sources/source-urls.csv
```

A batch file is a JSON array of explicitly selected catalogue IDs. For example,
this incomplete EMA selection previews as blocked until its existing authority
and fresh reuse decision are supplied:

```json
[
  {
    "source_id": "eu-ema-json",
    "surface": "download",
    "expected_url": "https://www.ema.europa.eu/en/documents/report/medicines-output-medicines_json-report_en.json",
    "retention_authority_reference": "",
    "reuse_decision": null
  }
]
```

`retention_authority_reference` cites an actual applicable source/endpoint
retention decision, including its terms and scope; entering text does not grant
permission. Reuse the existing decision when applicable, without another approval
round. `reuse_decision` is the existing serialized `ReuseGateDecision`, including
its current pinned discovery snapshot. The command does not manufacture search
results or treat a known archived copy as permission to download anew. A reuse
outcome stays with its existing route. Endpoint changes require updating the
catalogue and explicit selection together.

```sh
# Preview: no network or output-directory creation.
uv run --no-sync python scripts/source_download_batch.py --batch build/selected-sources.json
# Execute only that finite batch into a fresh local directory.
uv run --no-sync python scripts/source_download_batch.py --batch build/selected-sources.json --output build/source-batch-001 --execute
```

Each attempt uses existing `acquire_source`: HTTPS destination validation,
64 MiB default per payload (explicit `max_bytes` may set up to 256 MiB),
30-second timeout, one attempt and existing response
checks. The batch runs sequentially. Blocked rows do not prevent eligible rows
from running; blocked or failed rows produce a nonzero exit status. Each acquired
source has `payload.bin`, the content-addressed `receipt.json` and its exact
`selection.json`; `results.json` records the batch outcomes. Existing output
directories are refused. No upload, recurring schedule, unpacking, interpretation,
admission or coverage claim occurs. `single_api_response` never implies a complete
paginated collection, even when the request succeeds.

For catalogue URL changes also run the existing landing-queue and B0 generators:

```sh
uv run --no-sync python scripts/build_bronze_source_landing_queue.py
uv run --no-sync python scripts/build_bronze_source_index.py
uv run --no-sync python scripts/qualify_bronze_receipt_cohort.py
uv run --no-sync python scripts/qualify_stable_v1_measured_coverage.py
```

## Archive-all execution

The maintainer authorized archive-all execution on 30 October 2026. Run the
finite shared manifest across the complete current catalogue:

```sh
.venv/bin/python scripts/source_download_batch.py \
  --archive-all quality/source-batches/archive-all.json \
  --output build/archive-all-20261030/acquisition --execute
```

Every catalogue ID appears in `archive-all-results.json`. Configured eligible
batches execute; exact historical archives are reused with their original scope;
unconfigured sources retain `needs_source_review` and the existing reason/action.
Neither fixtures nor HTML landing pages qualify as bulk dataset archives.
`acquired_local` is distinct from public publication, and a completed inventory
scan is not an all-sources-archived claim. Existing successful batch folders are
resumed only after selection and payload hashes match; failures are retained
without implicit retries. Use a fresh explicit batch for a justified recovery.

Approved finite batches publish through `source-batch-publication.yml` on exact
main, using existing acquisition and publication machinery. Canadian payload
hashes are pinned to the already approved snapshots. New public bulk captures
are limited to the explicit batch inventories and documented rights. A dataset
already existing at the target causes failure rather than replacement. Inspect
intent, target revision and receipts before any recovery; never blindly rerun a
publication. Anonymous digest verification at the resulting revision is required.

The first order is Canada (DPD marketed and NOC), EMA spreadsheets, then Nova
Scotia formulary CSV. No API pagination is inferred, no linked documents are
followed, and no schedule is installed. Swiss remains unresolved. Australian
federation, Silver/Gold expansion and Stable v1 remain deferred. This source
archive execution is a new explicit user-authorized scope, not reopening those
milestones. See `quality/source-batches/` for the exact source URLs and rights.
