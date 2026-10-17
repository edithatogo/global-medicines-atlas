# M-108 Australian derived-product reconciliation — 2026-10-17

## Result

M-108 remains **blocked**. The latest anonymous metadata readback identifies
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
as the historical snapshot. The machine-readable inventory was refreshed
after the 2026-10-17 exact-page MBS harvest; its first readback is retained as
the `previous_observation` and the latest exact identities are recorded in the
[2026-10-17 machine-readable inventory](../../quality/qualifications/australian-m108-derived-products-20261017.json).

## Current public archive heads

Anonymous Hugging Face API readbacks at the refreshed observation time
confirmed these public, non-gated heads:

| Archive | Immutable head | Current relevant contents |
| --- | --- | --- |
| `australian-mbs-source-archive` | [`da83cad9116e2f9a5b927be7b080e9a5e5ea6998`](https://huggingface.co/datasets/edithatogo/australian-mbs-source-archive/tree/da83cad9116e2f9a5b927be7b080e9a5e5ea6998) | Three accepted August MBS Bronze acquisitions, one additional unadmitted projection, the July 2025 Silver v4 candidate, and the current 212-object root manifest. Relative to the prior exact observation at `52ad5c31cfe101c487a4c7a9c382540642e6110a` (40 objects; SHA-256 `9f9dbe6f5ccf3a6119177bbcbb5d942ce9e9db5ea35d2142c7696a3139cab796`), the current manifest SHA-256 is `68e6bb97ee43117b860ff1c57e625a00075c734e933d08b3cd67de673432d055`; metadata comparison found 172 additions, no changed existing rows, and no removals. The final exact-page append is [run 39000296702](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39000296702), with [publication](https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-6229285185) and [cleanup](https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-6229285346) receipts. |
| `australian-pbs-source-archive` | `48fd7345fb09277bb5b85644dba72804633a2abb` | One accepted April 2026 PBS Bronze projection. |
| `australian-mbs-utilisation-archive` | `be94e1c69a55b598598ab362b7dbf7ac4f0bf19c` | Raw objects and receipt sidecars; no derived Parquet tables under Bronze. |
| `australian-pbs-utilisation-archive` | `9f1d53cd50eea251b326da42a96f3ac72ebce97a` | Raw objects and receipt sidecars; no derived Parquet tables under Bronze. |

All four archive API responses reported `private=false` and `gated=false`.
The readback used public dataset/tree metadata and manifest, admission, and
source-receipt sidecar JSON. It did not download raw source or Parquet payload
bytes, change visibility, or publish anything during this reconciliation. The
MBS manifest delta is metadata reconciliation of the already published
harvest; its hosted receipt separately proves payload digest verification and
temporary-byte cleanup. These added Bronze source objects do not change the
M-108 derived-product admission, rights, card, or replica findings.

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

## August 2026 MBS six-table operation assessment

This is the consolidated M-108/M-109 handoff for the exact 2026-08-01 MBS
release. The pinned source is
`raw/mbs/releases/2026-08-01/c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565.xml`
in `edithatogo/australian-mbs-source-archive` revision
`da83cad9116e2f9a5b927be7b080e9a5e5ea6998`; its SHA-256 is
`c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565`
(8,293,331 bytes). Exact-main read-only qualification run
[39032003723](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39032003723)
matched the official release and covered all 6,046 records, 40 fields and
241,840 field occurrences. It reports zero source-presence/projected-state
mismatches across the 40 fields. The earlier run
[39029209737](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39029209737)
provides DMY candidate diagnostics; PR #1110 withdrew that run's original
field-semantic acceptance interpretation. The current run retains
`field_semantics_accepted: false`, the release-linked history blocker, and
candidate-only date grammar. Neither run retained source values or bytes, and
neither produced Parquet outputs or publication authority.

The proposed six outputs, if separately qualified and authorized, belong in
the existing public source-archive dataset under the new product prefix
`silver/mbs/v4/2026-08-01-v3/`:

| Output | Candidate row count | Field occurrences | Candidate lineage digest |
| --- | ---: | ---: | --- |
| `services.parquet` | 6,046 | 78,598 | `06fdb5d470177dcaf87925be9c7691a7d69c66141be8607028e2e131420feaad` |
| `hierarchy.parquet` | 6,046 | 24,184 | `82a3000e944e9e687035e71f457b42c424a24586f175586041c4174af5ca56cf` |
| `descriptions.parquet` | 6,046 | 18,138 | `afc5c26b4a89b07e3b969a363c70f6756c5556d830d2772cb4010c36ac06940c` |
| `fees.parquet` | 6,046 | 36,276 | `2e6cb8bcd5ef6ee127fa35f9d1e069b4eb31e708f2430806724205d0d6bd4e32` |
| `benefits.parquet` | 6,046 | 30,230 | `06ee4593e207d5790a77dd85c3389bdeb88218a421c7a3c04df8387d918b126d` |
| `caps.parquet` | 6,046 | 54,414 | `8903ecd80a611ff747a7b26e8846ac00c79fadfbbe996f3ac944c344bd658b02` |

These are candidate lineage digests, not output-file digests. No six-table
Parquet outputs have been generated or admitted for this August release. A
future product package also needs its exact manifest, qualification, source
receipt and product-specific data card. The prefix and paths above are a
proposal, not a committed identity or publication.

The maintainer receipt
[5467052330](https://github.com/edithatogo/global-medicines-atlas/issues/339#issuecomment-5467052330)
authorizes archiving the exact official XML into the named raw-source archive
through GitHub Actions with anonymous digest verification. It does not give a
source-specific decision for distributing these six derived Parquet outputs.
The current source receipt's `permitted` state and Decision 0009 do not fill
that product-specific gap. Before output generation or publication, obtain
release-linked field/schema history or source-owner clarification, reconcile
the three distinct August Bronze acquisition projections to one exact B1/B2
lineage, and record the maintainer's derived-output rights and admission
decision against the six exact output digests. Keep M-108 and M-109 blocked
until their respective gates pass.

Preservation and reversal boundary: leave the pinned XML, B1 receipt, root
manifest, all three accepted Bronze acquisitions, the unadmitted projection,
and the July Silver candidate untouched. Do not overwrite a public revision or
delete raw evidence. If a future authorized derived release must be withdrawn,
append a new withdrawal/supersession record, remove its active discovery and
consumer pointers, and retain the published revision, output digests, and
receipts as immutable history; public bytes already copied by others cannot be
recalled. The smallest next action is to obtain the exact-release versioned
MBS predecessor comparison specified in the [M-109 source-era register](australian-m109-source-era-register.md#august-2026-mbs-predecessor-comparison-plan).
This read-only comparison can verify source identities and characterize
aggregate differences; it cannot by itself establish field semantics or
authorize the derived outputs. If complete, the remaining semantic evidence is
versioned field/schema history or source-owner clarification. Do not rerun the
completed 390292/390320 diagnostics while this separate comparison is being
prepared.
