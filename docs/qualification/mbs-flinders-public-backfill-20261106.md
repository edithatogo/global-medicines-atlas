# MBS custodial public-report backfill — 6 November 2026

The maintainer requested comparison of Flinders OneDrive MBS files, including the
1993 tranche, against HF and publication of missing public data. Participant and
study-derived records remain excluded. This is a bounded extension of the source
consolidation track, not general federation or release acceptance.

Owner: chat 01a1aa8f-ba44-78f1-a79b-e14bd3e07236, worktree
`/Volumes/PortableSSD/GitHub/gma-pbs-historical-backfill`, branch
`codex/mbs-flinders-public-backfill`. Owned paths: this report, exact public-pack
contract, bounded publisher/tests, existing MBS harvest workflow and track
increment. Native scope: read-only selected MBS source collections; append only
reviewed public report packs to the existing MBS utilisation archive. Shared
Microsoft CLI selection is preserved. No participant data or access-bearing URLs
may enter Git, dispatch inputs, HF, receipts or public documentation.

Current operation: retrieve and classify original public report responses through
the qualified same-client SharePoint read route, compare with pinned HF objects,
freeze digest-approved packs, qualify the publisher and integrate through required
CI. Stop after exact-main hosted publication, anonymous verification and restoration
of the workflow's prior state. Private source transport and detailed inspection
remain outside the repository. Original source bytes must be retained until a
hosted anonymous-verification receipt permits temporary-byte cleanup.

## Frozen public cohort

The complete eight report-folder inventories contain 34,875 eligible HTML entries.
There are 12,968 actual source reads with size/SHA-256 checks and 21,907 entries
matched only by OneDrive size/QuickXor metadata to a downloaded no-services
response. The latter are explicitly metadata-only: no individually verified
bytes, reconstructed copies or zero-count observations are asserted for them.
Five incomplete local downloads from a disk-space failure were recovered against
the exact recorded size and SHA-256 before freezing the cohort. Shared Microsoft
profile selection was unchanged after the reads.

Twelve additional native public pages were read from the registrant-page and saved
MBS group-report collections. The frozen pack contains **2,350 logical reports,
2,347 distinct immutable HTML objects**, retaining original bytes and public
filenames in a digest-shared ZIP index. Its native tables contain **146,468 grid
rows including headers and totals**; this is not a normalized observation count.
Explicit native monthly labels span **July 1993–April 2025** (382 distinct labels).
Report/item identifiers, processing month, state, age range, gender, service counts
and benefit amounts are retained where present; standard reports have their own
source layouts. Signed amounts and native age labels are preserved.

Query parameters identify 1,949 services reports and 61 benefits reports; the
remaining 340 are standard/group reports. The folder labelled “Benefit Data - Age
Gender - 202504” contains predominantly **services** queries. Folder names are not
used as measure assertions. Query/processing periods, source-modified timestamps,
collection labels and hosted materialization dates remain separate.

Excluded from publication: 9,112 downloaded no-services responses; 583 unqualified
error/login pages; 932 pages with private/access-bearing markers (principally SAS
error/session output); three additional public server errors; and the 21,907
metadata-only matches. Those exclusions are not zero services or evidence of
statistical coverage. The derived registrant forecast CSV, four derived root
files, two different combined Feather versions and a combined demographic table
remain private. In particular, the 1,125,223-row combined demographic table has no
item identifier despite its historical date range; it is not used as an item-level
source substitute. Participant/linkage and study-derived data are excluded.

## Comparison with existing HF

The pinned utilisation baseline is revision
`00b29a457ed209a779330466494e46a06743e0ae`: 14 raw payloads plus 14 B1
receipts. It already contains item/state/age/gender demographic workbooks from
1993, broader group archives and 2016 releases. It is incorrect to claim that all
1993 or item-level data were missing. The separate MBS source archive contains
schedule/fee/source material; no equivalent native public-query report pack was
identified there. All 28 utilisation baseline objects must remain unchanged.

The December 1993 Item 73287 benefits sample has 176 state/age/gender cells.
Against the archived 1993 Q4 workbook, 78 match exactly; 95 explicit source zeros
lack sparse workbook rows; three nonzero cells have an unresolved age-label
alignment (`>=85` in HTML versus `>85` in the workbook). No differing values occur
among exact-label matches. Those three cells are not declared novel observations,
and absence of a sparse row is not independently interpreted as zero. The full
cohort has not been reconciled cell by cell. Later native monthly reports extend
to April 2025, beyond the baseline utilisation payload periods ending in 2016.

The pack preserves missing native report representations and later reports. It
makes no complete-series, complete-item, semantic admission, rights-review,
clinical or policy claim. The public Medicare statistics endpoint returned HTTP
503 during this comparison, so these are explicitly historical custodial copies,
not a claim of fresh publisher acquisition. Original public disclaimers remain.

## Hosted publication and focused qualification

The metadata-only contract is
[mbs-public-packs-20261106.json](../../quality/qualifications/mbs-public-packs-20261106.json).
No source bytes, participant files or private access URLs enter Git. A bounded
XZ transport is split into 34 digest-approved Actions artifacts. Staging jobs have
no HF token and cannot mutate HF; the single publisher checks successful exact-head
workflow identities, artifact layouts and every segment digest before expanding
and checking the exact reviewed input and deterministic ZIP digests. Signed
artifact redirects receive no GitHub bearer. No source is uploaded from a local
machine to HF. Publication appends only the approved pack and B1 receipt to the
existing public archive with an exact parent, never creates a dataset or deletes
objects. An unchanged pack reuses its original B1 receipt.

Focused tests cover byte preservation, unsafe aliases, digest/length/member-count
substitution, bounded decompression, local-mutation rejection, segment approval,
baseline preservation, immutable no-op receipts and final audit completeness.
Local evidence: 19 publisher tests, 89 existing harvesting tests, four PBS transport
tests and 38 publication/workflow regression tests passed on CPython 3.15.1.
Ruff, script BasedPyright, affected Ty checks and context validation passed.
The entire frozen transport decoded and staged locally with the approved ZIP
SHA-256 and byte count. Local publication was rejected before credential access.
One initial test selector named a nonexistent file and ran no tests; the corrected
existing publication/workflow selectors passed. Required protected CI precedes merge. Native publication and full anonymous
archive verification remain pending until their observable hosted receipts exist.
The workflow's prior state is `disabled_manually`; restore it after completion.
Temporary source bytes are retained until hosted verification permits cleanup.

PR #1416 review: retained the existing MBS harvester path (tracked file verified)
and the bytes-returning stage reader (the core explicitly accepts bytes or a
bytes/URL pair; the whole frozen pack staged successfully). Those two automated
findings were false positives; their review-thread metadata was resolved without
standalone comments. Initial policy CI correctly required an explanatory comment
for the new Actions read permission; added the artifact-only purpose without
changing or suppressing the gate. Final-head protected checks remain required.
