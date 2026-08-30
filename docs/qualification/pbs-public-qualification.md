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
read locally. The correction has not been dispatched. Any retry requires
reconciliation of its exact merged main commit and the unchanged read-only
scope below.

## Existing authority and immutable inputs

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

The 313 MB XML is processed with the existing finite ZIP/XML, entity, reference
index and batch limits. Parsing uses trees and multiple passes; this is not a
constant-memory or throughput claim. The qualification step has a 55-minute
timeout. Corpus-limit/runtime failure is evidence, not permission to weaken
bounds or infer coverage. Date conversion remains unselected.

## Durable aggregate receipt

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
