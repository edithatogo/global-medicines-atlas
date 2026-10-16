# M-108 Australian derived-product reconciliation — 2026-10-17

## Result

M-108 remains **blocked**. A current anonymous metadata readback identifies
four accepted Bronze parser executions and the public July 2025 MBS Silver v4
candidate. Three of the accepted Bronze executions are distinct August 2026
MBS acquisitions of the same source content; their acquisition identities and
source-Parquet and P7 output digests differ. The fourth is the April 2026 PBS
projection. A further public MBS projection prefix has Parquet outputs and a
manifest but no admission sidecar, so it is recorded separately and is not
counted as accepted.

None of the four accepted Bronze executions has typed federation-v4 admission,
output-specific v4 rights, a product-specific v4 card, and independent
replica evidence. The MBS Silver package remains candidate-only. Bronze parser
acceptance, `source_receipt.rights_state = permitted`, and a directory called
`v4` do not establish those gates.

The prior [2026-10-05 inventory](australian-m108-derived-products.md) remains
as the historical snapshot. The current exact identities are recorded in the
[2026-10-17 machine-readable inventory](../../quality/qualifications/australian-m108-derived-products-20261017.json).

## Current public archive heads

Anonymous Hugging Face API readbacks at the recorded observation time
confirmed these public, non-gated heads:

| Archive | Immutable head | Current relevant contents |
| --- | --- | --- |
| `australian-mbs-source-archive` | `3d2d528439bddf6f42e8e700c88917f0960a9f38` | Three accepted August MBS Bronze acquisitions, one additional unadmitted projection, and the July 2025 Silver v4 candidate. The 28-object root manifest and its append receipt are linked in the inventory. |
| `australian-pbs-source-archive` | `48fd7345fb09277bb5b85644dba72804633a2abb` | One accepted April 2026 PBS Bronze projection. |
| `australian-mbs-utilisation-archive` | `be94e1c69a55b598598ab362b7dbf7ac4f0bf19c` | Raw objects and receipt sidecars; no derived Parquet tables under Bronze. |
| `australian-pbs-utilisation-archive` | `9f1d53cd50eea251b326da42a96f3ac72ebce97a` | Raw objects and receipt sidecars; no derived Parquet tables under Bronze. |

All four archive API responses reported `private=false` and `gated=false`.
The readback used public dataset/tree metadata and manifest, admission, and
source-receipt sidecar JSON. It did not download raw source or Parquet payload
bytes, change visibility, or publish anything.

## Accepted Bronze executions and the unadmitted projection

The current MBS tree contains three accepted parser admissions for the same
content ID `c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565`.
Their acquisition IDs are distinct, all three admission records say
`reviewer_status: unreviewed`, and their source-Parquet and P7 Parquet digests
are different. The third accepted acquisition, under prefix
`d78170f1944e8c209833b86193d403b12553a3932579dc571ff10f8485a6483b`, was not
included in the 2026-10-05 inventory. Its exact acquisition, decision,
source-receipt, manifest, and output identities are now recorded in the
machine-readable inventory.

Each accepted MBS source receipt records `permitted`, but that is a
source-level rights state. No output-specific federation-v4 rights receipt or
typed federation admission is present for any of the three MBS projections.
The PBS projection has the same separation: its Bronze parser decision is
accepted and its source receipt records `permitted`, but it has no product
specific v4 admission or output-rights receipt.

The current MBS archive also contains a separate prefix ending in
`f9f9af5a152ea74c25a617102e3cf271054ef78867ed0eb84fb69822b6767d63`. Its
`mbs-release-v2` manifest lists source and P7 Parquet outputs, while the
manifest has no admission state and the prefix has no `admission.json`. It is
recorded as a public **unadmitted** observation outside the accepted-product
count. Its public presence does not qualify it for M-108 or establish a
negative source result; its admission, lineage, and rights disposition remain
unresolved.

## MBS Silver v4 candidate

The July 2025 candidate remains at
`silver/mbs/v4/2025-07-v3`, originally published at immutable revision
`ba82cd1d0f9b0f28514df431b8da3a6c207d76fa`. The durable hosted receipt
records anonymous digest verification of all nine objects. The current MBS
archive tree still exposes those nine objects, and the six Parquet LFS digests
and byte counts match the candidate manifest; its SHA-256 remains
`bbdb1bdac49fc1a7f8399ca02cf52a9b0e3a1fbc31e472e3957f1d278ab39a59`.

The product qualification remains `candidate_only`. No typed federation-v4
admission, product-specific card, output-specific derived-rights receipt, or
independent-replica evidence was found. The source receipt's `permitted` state
and the authorization basis in the manifest do not establish that derived
rights scope. No licensing conclusion is added here.

## Remaining acceptance work

For every product to be admitted, bind complete B1/B2 lineage and exact output
digests to a source-specific rights/reuse decision and typed federation-v4
admission. Add a product-specific card and exact immutable manifest, then use
the authorized protected-main publication workflow and record anonymous
per-object restore receipts. Collection membership and replica/recovery
evidence remain separate requirements. The public projection with no
admission sidecar needs an explicit disposition before it can be considered
for admission.

No newly admitted product or publication resulted from this audit. M-108,
M-109, and M-112 remain incomplete; this reconciliation does not accept any of
them.
