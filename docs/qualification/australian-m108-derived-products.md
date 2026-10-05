# M-108 Australian derived-product reconciliation — 2026-10-05

## Result

M-108 remains **blocked**. The anonymous public estate exposes three accepted
Bronze projection executions (two MBS executions for the same August 2026
release, and one April 2026 PBS execution) plus the previously published July
2025 MBS Silver v4 candidate. None has a typed federation-v4 admission joined
to an output-specific rights receipt, complete product card, exact immutable
v4 identity, and independent recovery evidence. The Bronze admission records
are parser decisions; they are not federation admission. The Silver package's
`product_version: 4` is not itself a typed v4 admission.

The exact identities and status flags are recorded in the
[machine-readable inventory](../../quality/qualifications/australian-m108-derived-products-20261005.json).
The inventory records four reviewed products. It is deliberately not an empty
denominator and does not mark the track complete.

## Live objects reviewed

Anonymous Hugging Face API readbacks on 2026-10-05 confirmed these public,
non-gated archive heads:

| Archive | Current immutable head | Derived product observed | Admission and rights result |
| --- | --- | --- | --- |
| [`australian-mbs-source-archive`](https://huggingface.co/datasets/edithatogo/australian-mbs-source-archive) | `44b25bfd87e44998c7c1da4c3930ad4447e9246f` | August 2026 Bronze source and P7 Parquet from two accepted acquisition executions; July 2025 Silver v4 candidate | Both Bronze parser decisions say `accepted`, but reviewer status is `unreviewed`; no federation-v4 admission is present. Their B1 receipts say `permitted` under the exact MBS release publication receipt, but those receipts do not bind derived v4 rights. The July 2025 Silver candidate is not admitted. |
| [`australian-pbs-source-archive`](https://huggingface.co/datasets/edithatogo/australian-pbs-source-archive) | `48fd7345fb09277bb5b85644dba72804633a2abb` | April 2026 PBS v3 source-faithful Bronze Parquet | Bronze parser decision says `accepted`, reviewer status `unreviewed`; B1 rights state says `permitted` and references issue #340. No federation-v4 admission or output-specific v4 rights receipt is present. |
| [`australian-mbs-utilisation-archive`](https://huggingface.co/datasets/edithatogo/australian-mbs-utilisation-archive) | `f1c75a0465d8cc22841c498274360753d0aab365` | Raw objects and B1 receipts in the reviewed tree | No admitted derived table product was identified. |
| [`australian-pbs-utilisation-archive`](https://huggingface.co/datasets/edithatogo/australian-pbs-utilisation-archive) | `9f1d53cd50eea251b326da42a96f3ac72ebce97a` | Raw objects and B1 receipts in the reviewed tree | No admitted derived table product was identified. |

### MBS Silver v4 candidate

The candidate is already public under
`silver/mbs/v4/2025-07-v3` in the MBS source archive. Its original hosted
publication revision is
[`ba82cd1d0f9b0f28514df431b8da3a6c207d76fa`](https://huggingface.co/datasets/edithatogo/australian-mbs-source-archive/tree/ba82cd1d0f9b0f28514df431b8da3a6c207d76fa/silver/mbs/v4/2025-07-v3).
The durable [hosted publication receipt](https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-5859624790)
records anonymous digest verification of all nine objects. At current head
`44b25bfd87e44998c7c1da4c3930ad4447e9246f`, the anonymous tree still contains
the same nine objects and all six Parquet LFS digests and byte counts match
the v4 candidate manifest. The manifest SHA-256 is
`bbdb1bdac49fc1a7f8399ca02cf52a9b0e3a1fbc31e472e3957f1d278ab39a59`; the six
table byte identities are bound in the inventory. This is a current metadata
readback joined to the original byte-verification receipt; this reconciliation
did not download Parquet or source payload bytes.

The candidate manifest binds MBS product version 4, producer commit
`decdeca1f3724405b0e085eb77d8ff11b6944ef9`, the source B1 receipt, and an
authorization basis. The public qualification still declares `candidate_only`
and no v4 admission has occurred. The dataset-level README describes the raw
MBS archive and pinned donor history, not this derived candidate. No
product-specific card is present under the v4 prefix. The source receipt's
`permitted` state and the referenced MBS authorization are retained as source
evidence; this audit makes no new licensing conclusion that they suffice for
the derived output.

### Bronze projections

The August 2026 MBS archive has two retained acquisition prefixes for the same
source content digest. Each has an accepted Bronze parser decision and a
source receipt recording `permitted`; their `source.parquet` and `p7.parquet`
digests differ by acquisition. Both still lack a federation-v4 identity,
typed v4 admission, and output-specific v4 rights binding. The PBS archive
contains one accepted April 2026 `pbs-v3-source.parquet` projection. Its source
receipt records `permitted`, and the archive README describes receipt-bound
Bronze projections, but the product has no exact v4 identity, v4 admission,
or output-specific rights receipt. In all three cases `reviewer_status` on the
Bronze admission is `unreviewed`.

## Publication and next acceptance evidence

No new public write or visibility change was performed. The reviewed objects
are already public, and re-publishing a candidate would not supply the missing
authority or admission evidence. Any new product publication must use its
authorized protected-main GitHub Actions workflow, bind an exact approved
manifest, anonymously restore every object by immutable revision, compare all
digests and byte counts, and persist the durable readback receipt before
cleaning hosted temporary bytes.

To close M-108, first bind every eligible producer output to a complete B1/B2
lineage and output-specific rights/reuse decision; obtain typed federation-v4
admission without retroactively relabelling candidate archives; add a
product-specific data card and exact immutable manifest; then publish and
verify through the hosted workflow. Collection and independent-replica
evidence must be recorded under the public data-plane track. M-109 real-corpus
promotion and M-112 live federation/admission remain prerequisite evidence for
the Australian products; no Gold or Platinum output is inferred from these
public archives.
