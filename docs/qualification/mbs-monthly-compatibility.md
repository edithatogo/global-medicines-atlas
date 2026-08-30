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

## Table and P7 qualification

`mbs_tables.parse_mbs_html_tables` validates each simple HTML table against an
explicit source-ordered `TableContract`. It keeps independent table IDs,
column names, nullable string cells, source ordinals and receipt provenance;
it never concatenates heterogeneous schemas. The deterministic per-table
Parquet projection retains these identities in its metadata. Maintenance pages,
empty tables, malformed nesting, schema drift and unbounded layouts fail closed.
The simple-HTML profile deliberately rejects rowspan/colspan layouts greater
than one; their raw bytes remain available for a separately tested profile.

`select_p7_records` preserves exact P7 filtering over the existing admitted
MBS `Data` batch. `parse_legacy_mbs_items` separately supports the donor fixture
`mbs/item` schema, retaining fields such as `FeeAmount` without renaming them
to official-release fields. Its explicit `donor-fixture-mbs-item-v1` schema era
prevents promotion of that fixture shape as an official current MBS release.

Rehearsal receipt IDs bind the target, retry ordinal and original receipt ID;
all attempts, including failures, are explicitly synthetic. Fixed-clock replay
therefore retains distinct attempts without misrepresenting live evidence.

## Remaining Phase 4 work

`mbs_admission.admit_mbs_html_tables` now binds each table contract, source
digest, acquisition event and decision clock to the existing Bronze admission
record. Profile failures are quarantined with no typed projections; mismatched
source bytes are rejected before any decision. Decisions use the shared
append-only `persist_admission_decision` store. Serialized outcomes reject
cross-source joins and cannot set `public_data_ready` to true.

`mbs_admission_health` uses the shared source-health receipt and escalation
contract for live-class acquisitions only. Its observation is at retrieval
time, leaves freshness unknown, and records table-profile failures separately
from successful usable-table processing. Synthetic rehearsals cannot enter
live health history. Neither technical acceptance nor health availability
establishes rights, current coverage, or anonymous public archive verification.

This is a regression foundation, not completion of the monthly scraper:

1. Connect these admission/health primitives to the hosted production runner
   and P7 projections; qualify additional HTML layout profiles as observed.
2. Persist admission/source-health receipts from that runner alongside B1/B2;
   primitive fixture tests alone do not prove a hosted acquisition.
3. Connect supported official releases and catalogue-driven scheduling to the
   hosted public Hugging Face publication path. Require anonymous archive
   verification before reporting an acquired update or removing temporary
   source bytes. No live scheduler is enabled by this change.

No local upload, repository archive, rights conclusion, clinical inference,
or medicine-domain projection is introduced.
