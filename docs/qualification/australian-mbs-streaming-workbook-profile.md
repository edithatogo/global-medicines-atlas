# Proposed MBS utilisation streaming workbook profile

Status: implemented and hosted-qualified for the two exact workbooks;
source-specific semantic validation and admission remain pending.

The March and June 2016 demographics workbooks reached the existing 128 MiB
ZIP-directory expanded-size guard. The independently verified diagnosis is
`quality/qualifications/australian-mbs-workbook-diagnostic-receipt-20261005.json`
(SHA-256 `767063f81e760bcf93b3618f93d08d3582ad1c649e79970f8ac0b440b87c6c67`).
At that diagnostic checkpoint, exact expanded sizes and later package or
worksheet validity were unknown. The hosted outcome below records subsequent
streaming structural evidence.
This proposal cannot retrospectively change either recorded failure.

## Scope and reuse

The separately named `mbs-utilisation-streaming-xlsx-v1` profile selects
only the two digest-bound references selected by `failed_workbook_paths`.
Retain the pinned original archive revision and preflight bindings. Do not
change `validate_xlsx_payload`, the default archive policy, the ten existing
profile passes, or either oversized ZIP hold. Never fall back automatically
from the existing profile to the new one.

Reuse `verify_zip_file` for compressed identity, paths, encryption, symlinks,
duplicate members, decompression ratio, actual expanded sizes and CRC checks.
The existing `au_mbs_workbook` adapter is a P7-specific materialising parser:
it reads complete XML members, shared strings and cells into memory and must
not be reused for these utilisation workbooks. No new dependency is needed
for archive verification; XML streaming must reject DTD/entity declarations
through the parser itself, including declarations split across read chunks.

## Proposed hard budgets

| Resource | Bound | Enforcement |
| --- | --- | --- |
| Compressed workbook | 32 MiB | Exact digest/size and streamed download/hash |
| Archive entries | 10,000 | ZIP directory validation before member reads |
| Individual expanded member | 512 MiB | Declared size and actual streamed byte count |
| Total expanded workbook | 1 GiB | Declared size and actual aggregate byte count |
| Decompression ratio | 200 | Existing archive safety validation |
| Member path depth | 16 | Existing archive safety validation |
| Read chunk | 1 MiB | File-backed reads; no whole worksheet read |
| Package metadata XML | 8 MiB per member | Before parsing and while reading |
| XML nesting | 64 | Streaming parser event depth |
| XML elements | 20 million per workbook | Aggregate streaming event count |
| XML character data | 1 MiB per element | Incremental character-data counter |
| Worker memory | 2 GiB | Linux address-space limit before parsing |
| Worker duration | 120 seconds per object | Parent subprocess timeout |

These are proposed ceilings, not measured requirements or proof either object
fits. The 1 GiB expanded ceiling deliberately limits the new profile below
the default ZIP policy's 2 GiB ceiling. Failure at any ceiling remains a
resource hold; no retries with larger limits. Preserve the staged reference
when digest verification or durable receipt persistence is inconclusive.

## Validation and receipts

First verify immutable identity and complete ZIP integrity. Then stream XML
from `ZipFile.open` without extraction. Parse required content types,
workbook and workbook relationships within metadata budgets; require expected
namespaces and roots, at least one sheet, unique relationship IDs and safe
internal worksheet targets that exist in the verified inventory. Reject
external worksheet targets and unsupported package structures with fixed
public-safe codes. Stream each selected worksheet to EOF, checking namespace,
root, well-formed XML and the aggregate budgets. Do not retain a tree, shared
string table, cell values or formulas. A SAX-style handler with incremental
counters avoids retaining large rows or text nodes; parser exception text
must never be emitted into public receipts.

This is structural validation only. Shared-string indices, cell typing,
source-specific headers, period interpretation, funding semantics and
processing admission require separate evidence. Emit the profile name,
fixed limits, exact source reference, observed aggregate expanded bytes,
member-inventory digest, worksheet and element counts, fixed outcome code
and execution identity. Emit no worksheet names, native cell values or raw
exception text. Infrastructure or timeout failures are inconclusive rather
than structural rejection. Persist and independently read back each outcome
before deleting digest-verified temporary source bytes.

## Implementation acceptance gates

1. Synthetic tests exercise genuinely incremental reads, split DTD/entity
   declarations, deeply nested XML, oversized character data, aggregate
   budgets, missing/unsafe relationships, malformed trailing XML, CRC failure
   and timeout/infrastructure classification. Assert no cell values appear in
   receipts and existing default limits remain unchanged.
2. Run focused tests, one broader affected check, routine checks and one full
   profile after the final production change. Protected Linux CI must pass.
3. Merge the implementation, then dispatch a dedicated main-only hosted run
   for the two pinned references, using the existing protected environment,
   shared acquisition concurrency and anonymous transport. Do not retest the
   other twelve objects or publish a derived dataset.
4. Independently read back the two outcomes and summary. Reconcile the track
   only to observed results. Structural success alone grants no admission;
   a new resource hold or inconclusive result keeps recovery open.

Implementation: `src/global_medicines_atlas/mbs_streaming_workbook.py`,
with dedicated `.github/workflows/australian-mbs-workbook-streaming.yml`.
The worker keeps all existing default profiles unchanged.

Hosted run [37243073339](https://github.com/edithatogo/global-medicines-atlas/actions/runs/37243073339)
passed both exact workbooks. The [independent receipt readback](../../quality/qualifications/australian-mbs-workbook-streaming-receipt-20261005.json)
records actual expanded bytes of 203,631,529 (March) and 220,739,864 (June),
two worksheets each, three durable receipts and both cache removals.
No other cohort objects were retested and neither workbook is admitted.
