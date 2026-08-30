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

## Hosted enumerated-release pipeline

`mbs_release.stage_mbs_release` reuses the catalogue identity, destination
policy, bounded HTTP acquisition, pinned reuse decision and Bronze admission
contracts. The separately approved 1 August 2026 official XML release is bound
to its exact source URL and approval receipt in
`quality/qualifications/mbs-current-release-contract.json`. This approval does
not authorize other release files. The original catalogue's July 2025 surface
and all legacy objects remain intact.

The hosted workflow `.github/workflows/australian-mbs-release.yml` can run by
exact-head dispatch and monthly revalidation of this enumerated contract. It
does not silently discover or authorize future releases. Transport failures
produce B1 attempts; nonconforming/empty successful responses remain quarantined
in hosted staging and do not inherit the exact XML publication permission.
Only qualified official MBS XML receives the independent non-sensitive/public
classification. Accepted releases produce deterministic
native-field Parquet and a separate P7 projection, with no heterogeneous CSV
concatenation or medicine-domain assertion.

`mbs_publication.publish_mbs_stage` only appends to the existing public,
non-gated MBS dataset using a compare-and-swap parent revision. It rejects
local use, synthetic or mismatched receipts, missing rights, altered bytes,
unmanifested files, path/symlink escapes and differing pre-existing objects.
Explicitly anonymous reads verify every staged object and the exact new
revision. The workflow records that receipt on issue #340 before deleting
its own bounded temporary staging/restore/cache directories. Quarantine blocks
raw publication; transport-failure metadata can be archived without a data-update
claim. Neither case reports a successfully acquired release.

The approved August release was published by [hosted run 33296983154](https://github.com/edithatogo/global-medicines-atlas/actions/runs/33296983154)
from merged commit `435527a630d055056985372aba1620bcf7340da4`.
The [durable anonymous-verification and cleanup receipt](https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-5467154799)
records 6,046 admitted records, eight verified objects and all 11 legacy paths
preserved at public HF revision `75f9f20a36ddb829dfe0ca88660664570782be02`.
Its source-native P7 projection contains 165 records. Raw XML is 8,293,331 bytes,
SHA-256 `c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565`.
The immutable staging manifest deliberately retains `data_acquired=false`:
only the later hosted all-object verification receipt asserts acquisition.
No raw current-release payload was downloaded to the workstation.

## HTML admission and health

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

## Remaining integrated verification

The enumerated release has observed hosted execution. Remaining boundaries:

1. Monthly scheduling revalidates this same approved release; it does not
   discover or authorize a future release automatically.
2. Qualify additional HTML layout profiles only as observed. Historical
   item/participant endpoints remain compatibility fixtures, not evidence of
   live participant-count coverage.
3. New release files require their own explicit source/file/destination
   authorization before the monthly contract advances.

No local upload, repository archive, general licence conclusion, clinical inference,
or medicine-domain projection is introduced.
