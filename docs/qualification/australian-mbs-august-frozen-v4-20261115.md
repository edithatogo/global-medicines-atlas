# August 2026 MBS frozen raw v4 candidates

Two distinct paths in the frozen M-112 inventory carry the same classified
August 2026 MBS schedule XML: the content-addressed path and its historical
alias. Both are pinned to dataset revision
`243f9ff5498816af6e4d9ae4db60528728f01834`, SHA-256
`c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565`,
and 8,293,331 bytes. The [canonical contract](../../quality/qualifications/australian-mbs-august-frozen-v4-20261115/canonical-contract.json)
and [alias contract](../../quality/qualifications/australian-mbs-august-frozen-v4-20261115/alias-contract.json)
retain separate exact path identities and their own replay receipts.

## Source-profile boundary

The v4 `schema_era` value is the source release revision `2026-08-01`; it is
not a qualified comparison schema. The producer declares `current` only as the
later side of the previously documented July–August 2026 predecessor comparison.
The contract links the digest-bound comparison receipt. This is not a claim
that the August schedule is current today, or that another comparison is valid.
The v4 source object has no dedicated comparison-scope field, so consumers must
consult this limitation and must not infer current status from that label.
Release-linked field semantics remain unaccepted, as recorded in the
[semantics status](mbs-xml-v3-field-semantics-status-2026-08.md).

## Evidence and current result

The exact source receipt classifies these schedule bytes as non-sensitive; the
existing maintainer attestation covers the source category, without a new
licensing conclusion. Prior value-free v1/v3 lineage, digest, discovery and
primary-recovery metadata are bound for each path. The historical primary
snapshot was recorded before the later B1 event; the later digest verification
is retained separately and does not rewrite that chronology. The primary copy
is not an independent replica.

Each candidate closed 14 receipt roles at 11 distinct locations and passed
independently configured trusted-profile admission. The [exact-main hosted
workflow](https://github.com/edithatogo/global-medicines-atlas/actions/runs/43705630353)
then passed the remote reader and streamed digest checks for both paths; the
reader cache was empty after close. Its value-free receipt and native artifact
digest were independently verified. The [frozen ledger](../../quality/qualifications/australian-m112-effective-raw-delivery-reconciliation-20261115-august.json)
counts both paths separately. No source values were interpreted or emitted, no
participant or cohort-derived data was accessed, and no dataset was acquired
or published.

The four frozen and four outside-inventory August Parquet projections retain
their separate lineage, semantics, product-admission and consumer gates. These
raw candidates do not admit them or close M-108, M-109 or M-112.

## Reproduction

With a qualified repo-local Python 3.15.1 environment, run
`python -m scripts.qualify_mbs_august_frozen_v4 --check` and the focused
`tests/test_qualify_mbs_july_frozen_v4.py` tests. The separate
`australian-mbs-august-frozen-v4.yml` workflow is manual, requires the exact
merged main commit, and performs a bounded reader check only on the two
already-classified archived paths. It does not publish a dataset.
