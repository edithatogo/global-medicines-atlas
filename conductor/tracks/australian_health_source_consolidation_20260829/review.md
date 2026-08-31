# Consolidation acceptance review

Reviewed 2026-08-30 against the pinned donor denominator and merged main
`c1f51f637106bdd12067ee8f6d19aa42f3fd9070`. This is an evidence review, not an
independent human approval, clinical assessment, or blanket publication grant.

| Criterion | Evidence and disposition |
| --- | --- |
| AC-01 inventory | PR #350 and the schema-validated donor inventory cover tracked files, functions, workflows, placeholders and all eight roadmap commitments. PR #366 maps successor commitments without claiming their implementation. |
| AC-02 XML | MBS domain commit `4871201` and its ledger qualification preserve all 5,989 legacy records, variable native fields and exact raw digest; public donor revision `4d1dae488ac43522f20e8320a8b2a56bf9138341` retains the original XML. |
| AC-03 workbook | Same public revision preserves the exact 87,727-byte workbook. Four-sheet adapter/profile qualification preserves formula/error and schema-era state; it is not replaced by the current P7 subset. |
| AC-04 PBS | Merged PBS v3 safety, namespace and source-native contracts; PR #362 bounded inspector; public revision `31ec854ef9fc82f30a0dbe743fdf50a2e5bd24a7` retains ZIP/XML, Parquet and receipts. |
| AC-05 compatibility | PR #364 bounded historical requests, six-404 regression and separate typed HTML/P7 projections; PR #365 durable admission and live-only health; PR #367 hosted exact-release acquisition. Historical participant endpoints remain compatibility fixtures, not acquired coverage. |
| AC-06 regressions | Donor inventory and MBS/PBS negative tests retain syntax/tag/path defects, empty placeholders, malformed/hostile inputs and heterogeneous table boundaries. |
| AC-07 semantics | MBS service-benefit, PBS funding/formulary and terminology references remain separate from regulatory/clinical assertions. No graph candidate is promoted by consolidation. |
| AC-08 public raw | Hosted donor, PBS and August MBS receipts are in the append-only ledger. Current MBS revision `75f9f20a36ddb829dfe0ca88660664570782be02` preserves all 11 prior paths and adds eight verified objects. Raw data was not downloaded locally for this release. |
| AC-09 notices/gate | Graph PR #5 and scraper PR #4 are merged; pinned complete donor histories remain public. Both repositories were independently observed unarchived. Final archive approval remains pending. |
| AC-10 qualification | PR #367 reviewed head `184a9b4`: 38 successful checks. Reconciliation: 122 focused tests and context validation pass. Local full implementation run had 2,793 passes, three failures and one skip; two failures are exact-interpreter requirements and one is the unchanged latency budget. Hosted Linux lanes pass; local full success is not claimed. |

## Review findings resolved

- PR #367: only qualified official XML inherits exact-file permission;
  the independent sensitivity gate is enforced; normalized receipts have
  distinct content-derived identities; HF caches remain inside verified
  hosted cleanup boundaries.
- PR #368: corrected the new receipt's recording time to precede the commit
  containing it. Previously merged append-only records were not rewritten.

## Remaining boundary and next route

The 2026-08-31 metadata-only donor refresh found post-baseline changes at graph
`3993e5e` (two documentation paths) and scraper `009e805` (eight paths, including
executable code and tests). The original review remains a pinned-baseline
checkpoint, not current-head preservation proof. The metadata delta contract
and disposition inventory are being added; exact hosted preservation receipts
for both later heads remain prerequisites to archival. Scraper async caller
responsiveness is retained as a legacy interface, not claimed as GMA API parity.

The final donor GitHub archival decision is outstanding. Track status remains
`in_progress`; no donor archival or whole-programme completion is claimed.
The next safe implementation route is the dependent public data-plane contract
track, then Australian Silver/Gold and federated Platinum. Restricted ontology
acquisition, future-file publication and promoted frontier dependencies retain
their own gates. Donor roadmap functionality is accounted for by those tracks,
not already delivered by this consolidation checkpoint.
