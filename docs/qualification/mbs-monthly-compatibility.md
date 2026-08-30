# Historical MBS monthly compatibility rehearsal

`global_medicines_atlas.mbs_compatibility` preserves the historical donor
request denominator and filename conventions without claiming those obsolete
endpoints are supported production sources. Source: `aus-health-data-scraper`
commit `931da0b9b6ae3e3cec0743568abb71a50d62b7cf`, `src/scraper.py` and
`src/main.py` (Apache-2.0; provenance retained in the donor inventory).

- Inclusive YYYYMM ranges handle year boundaries and reject invalid,
  reversed, or greater-than-1200-month ranges.
- Item identities retain leading zeroes, but must be 1–6 ASCII digits.
- Item-first then participant ordering and original `.html` names remain
  reproducible, with no more than 10,000 unique requests.
- The six historical January/February 2024 example requests reproduce six
  non-retryable HTTP 404 receipts, not a successful data update.
- The existing GMA acquisition implementation supplies destination policy,
  HTTP timeout, byte limits, staging and source/failure receipts. The rehearsal
  uses the `au-mbs` catalogue identity with an explicit historic surface.
- Requests are serial, separated by at least 0.1 seconds. Only failures marked
  retryable by the shared acquisition layer are retried, at most three times.
  HTTP 404/429 responses are not automatically hammered with retries.

`rehearse_probes` requires a synthetic `httpx.MockTransport`, an explicit reuse
decision, clock and sleeper. It cannot acquire live bytes. The fixed resolver
exists only for these synthetic transport tests, never for production routing.
Synthetic payload materializations belong under a temporary repository root's
`artifacts/mbs-compatibility`; no real payload was downloaded for this work.

`attempts` preserves every shared receipt in request/attempt order, including
zero-byte HTTP-success receipts. `downloaded_count` counts only nonempty
responses; `empty_count` counts empty successful responses; `failed_count`
counts targets with no nonempty response. These are transport observations,
not table-admission or coverage results. `data_acquired` is always false and
`qualification_status` remains `table_admission_pending` in this rehearsal.

## Remaining Phase 4 work

This is a regression foundation, not completion of the monthly scraper:

1. Admit each HTML table against a typed source/table schema, retaining
   heterogeneous tables separately and rejecting maintenance/error pages.
2. Preserve P7 selection and legacy XML profile behavior without bypassing
   the existing source-faithful MBS parser.
3. Generate deterministic projections and durable admission/source-health
   receipts; distinguish transport failures from table/empty-output failures.
4. Connect supported official releases and catalogue-driven scheduling to the
   hosted public Hugging Face publication path. Require anonymous archive
   verification before reporting an acquired update or removing temporary
   source bytes. No live scheduler is enabled by this change.

No local upload, repository archive, rights conclusion, clinical inference,
or medicine-domain projection is introduced.
