# Australian archive privacy batch

At the time of this batch, it recorded an individual privacy disposition for
the 1,745 objects
deferred from the frozen M-112 raw-delivery ledger and five previously
identified outputs outside that inventory. The [machine-readable report](../../quality/qualifications/australian-existing-archive-privacy-batch-20261115.json)
binds each disposition to its dataset, revision, path, byte count and digest.
The 14 existing raw admissions are unchanged and are not counted again.

| Batch | Objects | Privacy disposition |
| --- | ---: | --- |
| Exact classified July and August MBS schedule source bytes | 3 frozen paths | Source-profile assessed non-sensitive |
| Frozen August MBS projections with prior exact-byte replay | 4 | Source-profile assessed non-sensitive |
| August MBS projections outside the frozen inventory | 4 | Source-profile assessed non-sensitive after footer-adjusted reproduction |
| MBS Silver outputs already assessed under separate contracts | 6 frozen paths | Prior assessment retained; no new admission |
| Existing PBS schedule files with unassessed B1 records | 1,707 | Remain unassessed |
| Reimbursement-atlas medallion projections | 12 | Remain unassessed |
| Historical MBS ZIPs with prior member-format profiles | 5 | Remain unassessed |
| MBS demographic workbook with a prior candidate profile | 1 | Remains unassessed |
| Other frozen MBS schedule files | 5 | Remain unassessed |
| Frozen PBS source and projection | 2 | Remain unassessed |
| Reproduced PBS Silver output outside the frozen inventory | 1 | Remains unassessed |

Thus 11 objects have a new technical privacy assessment: seven inside and four
outside the frozen inventory. Another 1,732 frozen objects and one additional
output remain unassessed. The six earlier MBS Silver profiles are neither new
assessments nor additional raw-ledger admissions.

A subsequent exact July MBS admission reduced the deferred total to 1,744;
the [current ledger](../../quality/qualifications/australian-m112-effective-raw-delivery-reconciliation-20261115.json)
preserves this batch as a historical assessment. PBS privacy dispositions are
unchanged by that MBS admission.

## Basis of the MBS assessments

The July and August schedule source receipts classify their exact content as
non-sensitive. Three frozen paths match those source digests and byte counts.
The four frozen August projections also have a prior exact-byte in-memory
replay from the classified source and receipt-bound schedule transformation.

For the four outputs outside the frozen inventory, this batch read the
previously classified, already-archived August MBS schedule **in memory** and
checked its digest before parsing. It regenerated each output with the
repository's Python 3.15.1 and PyArrow 26.0.0. The unmodified regenerated
digests differed from the archived digests. Both historical producer locks
pin PyArrow 25.0.0; replacing the one equal-length writer-version marker
within each regenerated Parquet footer produced all four exact archived
digests. The [value-free replay receipt](../../quality/qualifications/australian-privacy-batch-20261115/mbs-outside-frozen-replay.json)
records the original mismatches, footer positions and matching digests.

This is a footer-adjusted reproduction; it did not execute the historical
PyArrow 25 writer. A bounded binary-only resolution check found no usable
PyArrow 25 wheel for Python 3.15.1 in this macOS environment; no older Python
was used. The source and reconstructed outputs were not saved, and no source
rows or values were emitted. The source receipts, producer code and
reproduction support a technical source-profile assessment. It is not an
exhaustive privacy clearance or a claim that every possible personal datum
has been individually screened. No participant or cohort-derived data was
accessed.

## Remaining decision batches

The 1,707 PBS source files comprise 1,052 PDFs, 652 ZIPs and three CSVs. Five
of the PDFs have archived publisher URLs; the rest use the publisher's
schedule path directly. Their exact acquisition records still say sensitivity
and personal-data status are unknown. A publisher URL, file extension, public
location or rights attestation does not establish a privacy classification.
The five historical MBS ZIPs have existing digest-bound member-format profiles,
including the tranche beginning in 1993. One demographic workbook has a prior
candidate profile. Those results do not establish privacy for every archive
member or workbook component. The 12 reimbursement projections and the other
unassessed files likewise need source-specific evidence. The machine-readable
report retains each one separately, rather than treating a category as a
blanket clearance.

The practical next step is to identify existing source-specific privacy
evidence or prepare a bounded screening method for each group. Until then,
unknown objects remain blocked from payload reads and consumer use. A privacy
assessment does not decide redistribution rights, authorize a new dataset
publication, create a v4 admission, complete consumer checks, establish an
independent replica or accept the Australian federation.

## Reproduction

Use the repository's qualified Python 3.15.1 environment to validate the
metadata-only batch:

```sh
build/federation-env/bin/python -m scripts.qualify_australian_privacy_batch --check quality/qualifications/australian-existing-archive-privacy-batch-20261115.json
```

Re-running `scripts.reconcile_mbs_privacy_replay` is a separate, explicitly
invoked read of the exact already-classified public MBS schedule; it retains
only the value-free report. It requires local access to the two historical Git
commits to verify their lock files. The earlier dossier remains a historical
snapshot; this assessment supersedes its four output-privacy dispositions
only, without changing its admission, rights or recovery boundaries.
