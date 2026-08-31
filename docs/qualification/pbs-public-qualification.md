# Pinned public historical PBS qualification

The prepared `pbs-historical-qualification.yml` workflow performs read-only
structural/storage qualification, not acquisition from a new source, dataset
publication, date-era qualification or semantic promotion. The first authorized
[run 33334961106](https://github.com/edithatogo/global-medicines-atlas/actions/runs/33334961106)
at `a65469cf40c92ad895b82cee915133749cb2d6ca` failed. Its
[durable failure receipt](https://github.com/edithatogo/global-medicines-atlas/issues/341#issuecomment-5471203363)
did not identify the failure stage. A metadata-only probe subsequently
reproduced rejection of the Hub GET cache redirect for both manifest and B1:
the response used an encoded nested path and an encoded original-path query
key with an empty value. This is a client redirect compatibility defect, not
evidence of an upstream defect or successful corpus qualification. The corrected
metadata-only recheck passed public-state, manifest and original B1 digest/size
and identity validation using the same DNS-pinned transport. No ZIP/XML was
read locally. Any further retry requires
reconciliation of its exact merged main commit and the unchanged read-only
scope below.

The corrected [run 33336369595](https://github.com/edithatogo/global-medicines-atlas/actions/runs/33336369595)
at `3ca5b6e003796cbff04d9207362d860b638983da` completed the manifest stage but
failed at `receipt-read` with category `transport`; its
[durable receipt](https://github.com/edithatogo/global-medicines-atlas/issues/341#issuecomment-5471361027)
does not identify the transport subclass. A subsequent metadata-only check
passed manifest and B1 digest/size/model validation. That observation supports
bounded transport recovery, not a conclusion about the original exception's
subclass or a corpus qualification claim.

The transport-recovery [run 33337502925](https://github.com/edithatogo/global-medicines-atlas/actions/runs/33337502925)
at `f7550d5f84b6a831cd99c3b6882c0d33c4b0c939` timed out after the unchanged
55-minute qualification limit. Its [fallback receipt](https://github.com/edithatogo/global-medicines-atlas/issues/341#issuecomment-5471752828)
has digest `65de9385f5b3414976aeb7c14e14ac6b02a2cf31957b81bf42e93b10f712cd21`.
It supplies no last-stage evidence: `transport_retry=null` in that fallback does
not establish whether recovery was attempted. No corpus qualification resulted.
The checkpoint correction below is synthetic-tested; no further dispatch or
timeout increase is implied.

## Existing authority and immutable inputs

The checkpoint-enabled [run 33379551308](https://github.com/edithatogo/global-medicines-atlas/actions/runs/33379551308)
at reviewed merge `6550c15d426d91f68ee0765902a09fb7bea8f606` failed at
`public-before/transport-connect` after consuming its one allowed retry.
Its [durable receipt](https://github.com/edithatogo/global-medicines-atlas/issues/341#issuecomment-5476646551)
has digest `0056ce489cad1bbcf0d97357de0cc3a894b223a8b36fd63bd43bd61dc10bc2d8`.
No source-file read or corpus projection was reached. A same-guarded local
metadata-only check passed afterward; that does not establish the cause of the
Actions connection error. No repeated dispatch or timeout increase followed.

Investigation separately reproduced loss of OS DNS address preference because
the system resolver deduplicated through an unordered set. Order-preserving
deduplication retains every address for private-network checks and still makes
one IP-bound connection attempt. It is a deterministic resolver correction,
not a demonstrated explanation or recovery of either hosted failure.

The existing public dataset is `edithatogo/australian-pbs-source-archive` at
revision `31ec854ef9fc82f30a0dbe743fdf50a2e5bd24a7`. Anonymous metadata inspection
confirmed `private=false` and `gated=false`; the harness checks both again before
and after retrieval. Authority is Decision 0009 and the existing
[publication receipt](https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-5466488482)
from run `33290449753`, not a new source/destination approval.

| Object path | Bytes | SHA-256 |
| --- | ---: | --- |
| `manifest.json` | 7513 | `e6c9abbc62bd44fc47049306a92cc8efc9700031908586262c2b82a907546460` |
| `bronze/2026-04-01/source-receipt.json` | 3143 | `a5eb06cf7e655eb0e0d8fe5d244297721ebede51e96c237333f7dffd76e1ccd1` |
| `raw/2026-04-01/2026-04-01-XML-V3.zip` | 11156706 | `f3e7af3610637b85577d0518ef50d3be9e692888e9acd3b5897d313706365c20` |
| `bronze/2026-04-01/sch-2026-04-01-r1.xml` | 313437585 | `73d34185fe6ae7fd9a788a68448e20934b38553d42361117faa96cdb07f54f43` |

Only manifest, original B1 receipt and ZIP are downloaded. The XML member
`sch-2026-04-01-r1.xml` is extracted from the verified ZIP in memory and checked
against the pinned public member identity. The original
`au-pbs-historical-xml` receipt is restored, never recreated or relabelled.
No source ZIP/XML was downloaded locally during harness preparation; only
public metadata and ZIP HEAD responses were inspected.

## Retrieval and runtime boundaries

The entry point rejects non-Actions, wrong-repository, non-main, malformed run
identity and nonmatching exact-commit calls before HTTP. The workflow uses the
checked-out dispatch SHA and never accepts arbitrary source URLs or revisions.
HTTP is anonymous with environment proxies and automatic redirects disabled,
cookies cleared, identity content encoding required, bounded byte counts and a
300-second retrieval deadline. Existing DNS-pinned transport rejects unsafe IP
destinations. Redirects allow only exact pinned Hub/cache paths and the observed
`us.aws.cdn.hf.co` delivery host; signed delivery URLs are never logged.
Hub cache redirects may use exactly the original pinned file suffix or its
single canonical percent-encoded form. An original-path query component is
admitted only once, only on that cache path, and only when its key equals the
canonical encoding of the exact original resolve path and its value is empty
(bare key or explicit `=`). Named query keys remain `download` and
`etag`, without duplicates. Mutable/unrelated paths, traversal, double encoding
and unknown query keys remain rejected. No host or revision was added.

One retry budget is shared across the entire run. Only HTTPX connection/read
errors and remote-protocol errors may consume it; timeout exceptions, HTTP
status rejection, decoding/local-protocol errors, policy/redirect failures and
digest/size failures are not retried. A one-second backoff requires time left
in the original 300-second deadline, checked both before and after waiting.
The failed response is closed and its partial bytes discarded; the full read
restarts at the original pinned URL through the same redirect and DNS guards.
Each attempt retains the original byte/hop limits; the one extra attempt is
the only additional request-chain allowance, not an unbounded retry loop.

`transport_retry` records the fixed stage/category of the initial transient
failure that consumed the run-wide recovery budget, on success or failure.
The additive `transport_diagnostics` object separately records `retry_cause`
and `terminal_cause`. The former is null without a consumed retry; the latter
is null in successful and incomplete receipts. Available diagnostic codes are
`dns`, `tls-certificate`, `tls`, `connection-refused`, `network-unreachable`
and `unknown`. At most eight explicitly chained exception objects are examined,
with cycle detection, using only exception types and fixed integer errno
buckets. Exception messages, implicit context, request URLs, IP addresses,
certificate details and credentials are never included. Unrecognised or
discarded causes remain `unknown`, including an unavailable failure receipt.

These observations do not change failure categories, retry eligibility,
connection attempts or deadlines. In particular, a direct resolver DNS error
retains the existing `unexpected` category and is not newly retried. Synthetic
tests qualify diagnostic behavior only; these new codes do not retrospectively
establish the cause of an earlier hosted failure or prove its recovery.
It records backoff initiation, not proof that a second read completed (the
deadline may expire during backoff). An observed unused budget is `null`;
in a generic failure-only fallback, `null` instead means unavailable evidence.
Transport failure categories now distinguish connection, read, remote/local
protocol and decoding failures without exception text or connection details.

The 313 MB XML is processed with the existing finite ZIP/XML, entity, reference
index and batch limits. Parsing uses trees and multiple passes; this is not a
constant-memory or throughput claim. The qualification step has a 55-minute
timeout. Corpus-limit/runtime failure is evidence, not permission to weaken
bounds or infer coverage. Date conversion remains unselected.

## Durable aggregate receipt

Before each stage and projection phase, and after each verified projection
batch, the CLI atomically replaces the same bounded JSON receipt with an
`incomplete` checkpoint. The denominator walk also checkpoints every 65,536
fields and at its end. Only fixed stage/phase codes, completed batch/row
counters and elapsed monotonic milliseconds are included. For the denominator,
`rows` counts native fields and `batches` is zero. Counters reset per phase;
they are processed-prefix diagnostics, not qualified corpus denominators.
The reference phase includes its index-building pass before its first emitted
output batch; a zero-batch checkpoint cannot distinguish substeps inside it.
Parsing/binding stages likewise remain coarse-grained.

Retry-budget consumption is checkpointed before backoff. Ordinary failure
receipts retain the latest progress; a process killed at the step timeout
leaves the last atomically completed checkpoint for the existing `always()`
issue/artifact steps. An interruption between writing the temporary file and
replacement preserves the previous receipt. Only the final completed report
can say `passed`. Checkpoints do not resume computation, assert completion of
the active stage, survive loss of the runner itself, or guarantee issue posting
if GitHub is unavailable. Temporary receipt files contain metadata only and
are not included in the artifact.

The CLI emits only bounded aggregate counts, digests, pinned object identities,
UTC observation times, exact workflow commit/run identity and the original
publication-receipt link. A canonical compact-JSON SHA-256 binds the report in
its envelope. Errors emit a fixed failure receipt without exception text,
sample source values, credentials or signed URLs. No raw source files or
Parquet products are written to disk by the qualifier.

Failure receipts additionally contain allowlisted `failure_stage` and
`failure_category` codes. Stages distinguish context and transport setup,
public-state checks before/after retrieval, manifest/B1/ZIP reads, manifest/B1
validation, member extraction/binding, projection qualification and report
serialization. Categories distinguish validation/structure, transport/timeout,
destination policy/redirect, HTTP status, encoding, byte limits, pin mismatch
and unexpected errors. They are selected from exception types or explicit
control failures, never exception text, HTTP bodies, headers or source values.
Unknown errors and the workflow's failure-only fallback retain `unavailable`
codes instead of guessing a stage. Codes are checked again when the receipt
is serialized. Failure diagnostics do not bypass any original guard or limit.

An `always()` step posts the complete bounded receipt to issue #341, creating
a fixed failure receipt if the qualification step left none. Posting failure
fails the workflow; the receipt is also retained as a 30-day Actions artifact,
but that artifact is not the sole durable record. `issues: write` is used only
for this metadata receipt; no HF credential or HF write operation is present.
Raw bytes remain durable in the existing public HF revision, not in the repo
or developer workstation. A successful report qualifies only the observed
structural/storage transformations; public Silver delivery, complete domain
semantics and independently justified date profiles remain separate.

## Synthetic scalability diagnosis

A local CPython 3.14.7 cProfile run used synthetic schedule XML with 100 and
1,000 repeated `<item><code>i</code><name>Synthetic i</name></item>` elements,
the existing test ZIP/receipt builders and unchanged five-projection qualifier.
The member sizes were 5,335 and 54,835 bytes; the field denominators were 602
and 6,002. Profiled elapsed times were 8.554 and 43.675 seconds on a shared
workstation; these are not stable benchmarks or extrapolated corpus throughput.
At 1,000 items, 114,038 JSON `dumps` calls accumulated 10.921 seconds and
the entity-building route accumulated 17.808 seconds (overlapping cumulative
times must not be added). Arrow/Python row conversion and repeated nested
serialization are useful optimization targets. Receipt hashing was not the
dominant measured cost. This synthetic shape is not the real corpus, and does
not explain its timeout stage without progress evidence.

Next: profile the individual conversion/encoding passes at fixed synthetic
denominators, add exact-output and call-count regression tests, and optimize
proven redundant work without removing independent lineage, parser limits,
reference index bounds, native digest checks or Parquet roundtrips. No cache of
unvalidated caller inputs or increase to the hosted limit is authorized by this
diagnosis. New dependencies are unnecessary for these measurements.

### Native-buffer-preserving domain annotations

The shared domain transform now decodes only `record_id` and `source_sha256`
for its unchanged mapping function. It constructs three new annotation arrays
and retains every original Arrow array, including null buffers, slice offsets
and historical lineage. It does not cache mappings across rows or inputs, skip
source validation, remove reference passes, or relax a parser/index/batch limit.
Ordinary and historical empty, one-row and nonzero-offset batches match the
former row-materializing algorithm exactly, including schema metadata. Tests
also assert buffer-address equality and one two-column mapping call per row.
A sliced array can retain its parent allocation; this is not a new bound on
total resident memory or a promise to compact slices.

The fixture-only `tests/profile_pbs_domain.py` retains the former algorithm as
a measurement/parity oracle, not a second production route. It constructs
100/1,000 synthetic pharmaceutical items (702/7,002 native rows; 1/7 batches)
and measures five alternating paired samples after validating exact parity.
On local CPython 3.14.7, unprofiled median seconds were 0.007576/0.189243 for
the row reference and 0.002714/0.034720 for native-buffer reuse. A separate
Scalene CPU-profiled run measured 0.013332/0.201196 versus 0.004721/0.088144.
These shared-host microbenchmarks vary materially with load and profiler
overhead; they are not a corpus throughput budget or proof of timeout recovery.
The deterministic regression gate is eliminated native-buffer reconstruction
with exact contract parity, not a fragile wall-clock threshold.

Reproduce the bounded fixture experiment from the repository root:

```sh
PYTHONPATH=.:src:tests uv run --locked --group test python tests/profile_pbs_domain.py
PYTHONPATH=.:src:tests uv run --locked --group test --group profiling python -m scalene run --cpu-only --profile-all --outfile /tmp/pbs-domain-profile.json tests/profile_pbs_domain.py
```

No raw public PBS payload is involved. The actual corpus remains unqualified.
The 55-minute limit remains unchanged.

### Reusing exact native-field size measurements

Entity accumulation already measures every native field with compact UTF-8
JSON. The enclosing entity now reuses those lengths instead of serializing
the nested fields a second time: encode the metadata with an empty array,
then add each field length and the `N - 1` separating commas. Groups are
nonempty; the empty array already accounts for both brackets. Encoder options,
element and batch budgets, output rows, schemas and lineage are unchanged.
This is encoded-byte accounting, not a bound on Python/Arrow resident memory.

Regression tests verify exact ordinary/historical boundary acceptance and
one-byte-over rejection, randomized Unicode/null parity with full JSON,
one encoding per native field, and existing batch/Parquet round trips.
`tests/profile_pbs_entity_size.py` compares both accounting paths on synthetic
100/1,000-item archives after source-bound construction. Parsing and Arrow
conversion are outside these timings; both paths include initial field sizing.
It emits five alternating paired wall/CPU samples and checks every entity's
exact byte count. Shared-host wall timings are noisy, not a corpus SLA.
Local CPython 3.14.7 process-CPU medians were 0.012648/0.124881 seconds for
double encoding versus 0.008459/0.082438 for reuse (301/3,001 entities).
Wall medians were 0.091567/1.122450 versus 0.021989/0.954579 seconds; wide
sample variation reinforces using call-count and byte parity as regression
gates, not a fixed speedup promise. No runtime dependency was added.

```sh
PYTHONPATH=.:src:tests uv run --locked --group test python tests/profile_pbs_entity_size.py
```

Next: reconcile measured improvements and final-head checks before deciding
whether a checkpoint-enabled pinned hosted qualification is justified. Neither
optimization qualifies the real corpus or authorizes new payload publication.
