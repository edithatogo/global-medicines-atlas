# Existing MBS object gates and PBS privacy metadata

This check reconciles existing, digest-bound metadata only. It does not read
source or projection payloads, access participant or cohort-derived research
data, change a rights decision, admit an object, run a consumer or add or
publish a dataset. The [machine-readable report](../../quality/qualifications/australian-existing-mbs-pbs-object-gates-20261115.json)
records all eleven MBS identities and the exact evidence bindings.

This is a point-in-time assessment. A subsequent [hosted qualification](australian-mbs-july-frozen-v4-20261115.md)
admitted and reader-checked the July raw object at its approved frozen revision;
the other ten objects retain the boundaries described below.

## Eleven MBS objects

| Objects | Retained rights and lineage evidence | Remaining v4 boundary |
| --- | --- | --- |
| July 2025 schedule XML, one frozen path | The exact raw path, digest and size appear in the six-object maintainer rights attestation. Its receipt, B1 event, B2 reference and landed-unreviewed lineage are bound. | The historical six-table Silver candidate and its later separate admissions do not admit this raw object. Exact raw v4 roles and consumer authorization remain separate. |
| August 2026 schedule XML, two frozen paths | The canonical path and alias share the exact source digest and size; the retained source-release authority, raw lifecycle and separate anonymous readbacks are bound. | A prior v4.1 role assessment is candidate-only at revision `40891976…`; the frozen paths are at `243f9ff5…`. Its authority, location, discovery and v1 roles remain unbound, while other roles are partial or missing. It cannot be treated as an exact frozen-revision admission. |
| August Bronze projections, four frozen paths | Exact public-release rights were attested for these four paths and digests. A retained source-bound replay reproduces their output digests. | The attestation did not authorize v4 admission or consumer canaries. Product-specific v4 evidence, admission, consumer and independent-recovery checks remain separate. |
| August Bronze projections, four paths outside the frozen inventory | Exact public-release rights were attested at revision `42d73b6f…`; later retained metadata identifies the same paths and digests at `b925a8a8…`. Producer evidence and an in-memory footer-adjusted reproduction support the technical source-profile privacy assessment. | The historical writer was not run in that reproduction. The attestation did not authorize v4 admission or consumer canaries; exact-revision contract and recovery evidence remain separate. These four paths do not change the frozen denominator. |

All eleven are source-profile assessed non-sensitive, not exhaustively cleared
of every possible personal datum. None appears among the 14 recorded raw-v4
admissions, and this check establishes no separate v4 admission for them.
Rights attestations preserve the maintainer's recorded scope; their underlying
instruments were not independently located or reviewed. A rights attestation,
Bronze lifecycle state or candidate role is not a v4 admission.

## PBS privacy metadata

The comparison covers 1,722 previously unassessed PBS-related or reimbursement
objects: 1,707 schedule files, 12 reimbursement projections and three other
PBS source or derived candidates. It rechecks the 1,707 exact B1 metadata
records: all still say sensitivity and personal-data status are unknown and
publication requires review. Their digest-and-byte-count pairs are distinct.

The comparison binds the six separately assessed PBS utilisation objects to
their existing screen and source-specific context receipts. Two historical
CSV screens had flagged headers; their exact header context recorded aggregate
fields, and their prior assessments were not exhaustive personal-data
clearances. None of the 1,722 unassessed objects matches those six screened
objects by both digest and byte count. Even a content match would require an
appropriate exact-source assessment; this check automatically clears none.

The 1,707 schedule files remain 1,052 PDFs, 652 ZIPs and three CSVs. Public
location, filename, extension and redistribution rights alone do not establish
their privacy state. The 12 projections and the other three PBS candidates
also retain their existing unassessed dispositions. The underlying
[per-object privacy batch](australian-existing-archive-privacy-batch-20261115.md)
continues to hold the complete frozen and outside-object identities.

## Reproduction

With the qualified repo-local Python 3.15.1 interpreter:

```sh
build/federation-env/bin/python -m scripts.qualify_australian_existing_object_gates --check quality/qualifications/australian-existing-mbs-pbs-object-gates-20261115.json
```

The check rebuilds the retained metadata-only privacy, reimbursement and MBS
dossier reconciliations before comparing the stored report. Missing or
misbound identities and prior screen contexts fail closed. Independent
recovery, new v4 admissions and federation acceptance remain open.
