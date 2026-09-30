# Hugging Face estate audit: 2026-08-29

## Observed inventory

Authenticated CLI enumeration found:

- three private datasets;
- no private models;
- one private Space unrelated to GMA;
- two private, empty reserved collections; and
- public GMA, reimbursement, estate-registry, and other dataset surfaces.

Visibility is not a rights conclusion. The dispositions below use exact
manifests and the scope of Decision 0009.

| Surface at audit time | Revision/state | Disposition | Rationale |
|---|---|---|---|
| `edithatogo/global-medicines-atlas-international-open` | dataset revision `654f71c84cdb17b4032396bcbc961bef8757fb19`; 42 payload files | Publicized through exact hosted workflow as a legacy composite on 2026-08-29 | Its README and manifest are byte-identical to current public `global-medicines-atlas-international-permissive-20260821`; all payloads are already present in public GMA archives |
| `edithatogo/hpo-licensed-ontology-archive` | dataset revision `720aa679d8a8fcf051ca95672400e874c4490a71`; about 88.7 GB | Keep private | Mixed licensed terminology/source archive includes material outside the Australian authorization scope; public exposure is not appropriate |
| `edithatogo/rareburden-commons-source-archive` | dataset revision `ddf35f48f21dce831e346559b41549bd6188662d`; about 138 MB | Keep private | Unrelated rare-burden source archive with unresolved/restricted source roles |
| `edithatogo/gfjd-explorer` | private Space | Keep private in this track | Unrelated application; no GMA publication rationale was established |
| `Safety Science` | private empty collection | Keep private until populated | Empty reserved discovery shell; publicizing it provides no data |
| `Policy AUS` | private empty collection | Populate with exact Australian datasets, then make public | Directly aligned with this programme, but publication should occur with accurate members and notes |

## Exact legacy-composite comparison

Candidate:

- dataset: `edithatogo/global-medicines-atlas-international-open`
- revision: `654f71c84cdb17b4032396bcbc961bef8757fb19`
- manifest SHA-256:
  `d058b78789cd8c2d0a19467063890d32c0757add10998d307422c3ec1550df86`
- manifest payload entries: 42
- source IDs: 11

Public baseline:

- dataset:
  `edithatogo/global-medicines-atlas-international-permissive-20260821`
- observed revision:
  `87d3b54ac932018c276a1c50033ac287520cf85e`
- `README.md` and `manifest.json` are byte-identical to the private candidate;
- repository sibling paths match the candidate.

The 42-entry manifest comprises the ten-source international permissive cohort
plus twelve Open Medic ZIP/receipt pairs. A separate public Open Medic dataset
also exists at revision `d19f7a66e35c58c557615bffa456856b485b7edc`.
Making the candidate public therefore preserves a legacy composite identity; it
does not publish a new content cohort. Hosted run
[`33238912245`](https://github.com/edithatogo/global-medicines-atlas/actions/runs/33238912245)
completed the exact visibility transaction and verified all 42 payloads
anonymously. A separate token-free check then resolved the same revision as
public and non-gated with 45 expected siblings and the authorized manifest
digest. The durable JSON receipt is recorded on issue
[#340](https://github.com/edithatogo/global-medicines-atlas/issues/340).

## Collection improvements

The public `Health Economics and Outcomes Research` collection currently has a
stale note describing reimbursement-atlas as metadata-only/origin-unresolved.
The observed public dataset at revision
`17bad6aa14ade14b8882ef5464c90a8a7cb596aa` contains B0/B1/B2 and later-layer
records, although raw payload bytes are not present. The collection note should
state its actual federated HEOR role and distinguish records from raw-source
archives.

`Policy AUS` should become the primary discovery collection for the new MBS
source archive, PBS source archive, Australian benefits medallion dataset, GMA
catalogue entries, and the reimbursement-atlas consumer where relevant. The
same datasets may also appear in HEOR with different explanatory notes.

## Anonymous public re-observation: 2026-10-01

Two identical anonymous public Hub API scans observed 76 public datasets and
eight public collections. The public registry remained at revision
`8f4c5b03adebdc8cbe19d9f20b18745d4da1b83c`; its `catalog.json` digest is
`001cf4fee54862995e1e513fb6dba6e68fd85a458898e7c52cc2ec6407ab4adb`.

The catalog contains 52 entries: 47 marked public, three gated, and two
private. Compared with the anonymous public dataset listing, 26 current public
datasets are missing from the catalog. Two existing catalog access states
disagree with current public visibility/gating: `corpus-legislation-nz` is
currently public and ungated while the catalog says gated, and
`hermes-training-artifacts` is currently public while the catalog says private.
One public catalog entry, `gfjd-source-archive`, was not returned in the live
public dataset listing. It is retained in the catalog pending owner review;
this audit does not infer deletion or authorize removal. Two catalog rows
marked private were excluded from identity comparison, and no private dataset
identities were emitted.

The qualification at
`quality/qualifications/hf-public-registry-gap-20261001.json` contains exact
current revisions for the 26 missing public repositories and conservative
catalog-entry drafts, all validated against the `catalog.schema.json` pinned
to the observed registry revision. Those drafts leave family, role, origin,
payload state, rights, and Viewer readiness unassessed. They are proposals only.
This scan read no source payload bytes or values and made no registry or
collection mutation. External catalog publication and collection changes remain
explicit maintainer gates.
