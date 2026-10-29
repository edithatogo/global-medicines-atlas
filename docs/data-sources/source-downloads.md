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

## Completion boundary for this change

Done means the all-source URL table regenerates, selected sources use the shared
acquirer, blocked and failed rows remain explicit, and focused tests and protected
CI pass. It does not mean all sources have been acquired or all APIs enabled.
Swiss/EMA remains the only authorized live acquisition batch. The existing EMA
local candidate is reused; this implementation does not fetch it again. Swiss
still needs a reliable official export identity and applicable data rights.
The exact EMA publication decision remains separate; the batch command cannot
publish. Australian federation, Silver/Gold expansion and Stable v1 stay deferred.
