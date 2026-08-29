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

| Private surface | Revision/state | Disposition | Rationale |
|---|---|---|---|
| `edithatogo/global-medicines-atlas-international-open` | dataset revision `654f71c84cdb17b4032396bcbc961bef8757fb19`; 42 payload files | Publicize through exact hosted workflow as a legacy composite | Its README and manifest are byte-identical to current public `global-medicines-atlas-international-permissive-20260821`; all payloads are already present in public GMA archives |
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
does not publish a new content cohort. Hosted token-free digest verification is
still required before the visibility outcome is recorded complete.

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
