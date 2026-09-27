# Australian donor parity gap, 2026-09-27

M-105 remains blocked. The pinned inventory covers 54 tracked blobs (16 graph,
38 scraper), including every Python function and both workflows. The later
delta review covers two changed graph paths and eight changed scraper paths.
The two donor heads and complete histories were subsequently preserved and
anonymously restored at the exact public revision recorded by the archival
receipts. Those receipts close history preservation and the separately approved
archive actions; they do not prove behavioral parity for every donor artifact.

The [pinned inventory](../../quality/qualifications/australian-health-donor-inventory.json)
uses broad dispositions such as `adapt_or_replace_with_tests` and
`preserve_provenance`. The new [M-105 disposition matrix](../../quality/qualifications/australian-donor-m105-dispositions.json)
maps all 54 baseline blobs and ten later changed paths to M-105's final
six-value vocabulary, preserving exact Git identities and baseline payload
digests. This is a complete **classification**, not a parity qualification.
Ten baseline executable files (four graph source files, four scraper
source/test files, and two scraper workflows) and five later changed paths
remain explicitly `pending_behavioral_parity`. The donor's broken MBS parser
is now bound to the exact pre-archive 5,989-record/40-field qualification of
its replacement, including the rejected `MBSItem` shape. The existing [donor assessment](../../conductor/tracks/australian_health_source_consolidation_20260829/donor-assessment.md)
maps their intended functions to successor behavior, but does not bind each
file/function to a passing parity result. In particular, scraper async caller
responsiveness is retained as legacy behavior, not proven API parity. The ten
later changed paths need exact GMA evidence for the five behavior-bearing
rows; the earlier delta receipt's
`current_head_history_preserved=false` was a pre-publication observation and
must not be read as current archival state.

The next acceptance slice is to attach a GMA successor and behavioral test to
each remaining pending row, and byte-level public receipt to each data/legacy row. Keep roadmap-only work
labelled successor intent, zero-byte placeholders as legacy evidence, and
restricted terminology outside public data scope. Run the matrix against the
inventory and delta denominators with missing/duplicate and unsupported-parity
negative controls. Only then reconsider M-105; M-106–M-112 and the federation
gate remain independent.

The archival chronology cannot be retroactively described as pre-archive M-105
parity. The separate maintainer approvals and observed archives are recorded in
the [scraper](../../quality/qualifications/scraper-archival-20260906.json) and
[graph](../../quality/qualifications/graph-archival-20260906.json) receipts.
