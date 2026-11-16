# Frozen MBS projection roles and PBS privacy review

The [role assessment](../../quality/qualifications/australian-mbs-frozen-projection-roles-20261116/role-assessment.json)
covers the four August MBS Bronze projections in the frozen revision. It uses
retained, hash-bound metadata and fixed producer-code blobs; no source or
projection payload, participant or cohort-derived data was read. No dataset
was acquired or published.

## MBS role bindings

Each exact object has 85 validated v2 field-lineage records in the existing
shared v2 receipt. The assessment checks the record contents, source and output
digests, producer revision, rights reference and full object identity. The
field mappings are source-structure lineage, not acceptance of every field's
meaning or an output privacy decision.

For each object, the existing v3 registration plan is reconstructed and
schema-validated in memory. Its serialized digest and deterministic registration
match the previously retained metadata replay. This binds the existing replay
report to the object; it is not a source or Parquet replay and the report is not
a byte-closed v4 plan receipt. Full plan JSON was tested locally but triggered
the existing generic-secret rule on hash fields, so it was removed and is not
retained. The scanner was not suppressed or changed.

The pinned v1 schema has no representation for a rebuildable Bronze projection.
The original XML is raw B2; its derived Parquet projections are not. The new
v1 semantic checks reject a projection labelled as raw B2. The retained
source-side v1 document is schema-valid, but its three blocked promotion
records name B2 subjects while their target is Silver. They therefore fail the
repository's target-layer semantic rule. The historical receipt is unchanged;
it must not be presented as projection-specific v1 conformance. Existing raw
admission and its receipt history have not been retroactively changed. A
supported projection-specific v1 role and any necessary correction to the
source-side historical interpretation still require a contract-level solution.

## MBS output privacy

The original source receipts classify the source as non-sensitive. The two
fixed historical producer versions preserve native XML child text in their
Parquet fields, and the P7 selection filters by group rather than by content.
A synthetic free-text marker test demonstrates this behavior for the current
producer path; the historical code blobs and corresponding text-handling path
were checked separately. This neither establishes the presence of personal
information nor screens the frozen outputs. Output sensitivity remains unknown,
and all four objects remain blocked from admission and live consumer use.

## PBS review

The retained two-build reconciliation binds the reproduced April 2026 Silver
output to its exact source-member digest and producer commit. The historical
producer code and build receipt show that the native core includes values, not
just field names or paths. The existing source-member schema context has 5,163
paths; that structural context does not screen those values. This exact Silver
output's privacy status therefore remains unknown. The conclusion does not
transfer to the separate Bronze projection, the September API ZIP or its 33
members, or any other object. All previously unassessed PBS-related paths
retain their prior dispositions.

## Remaining gates

The four projections still need a supported v1 role, output-specific privacy
clearance, durable v3 role bytes accepted by the existing scanner, complete v4
receipt roles and independently trusted admission. Actual consumer canaries
and independent recovery remain separate. No permission to read or publish
payloads follows from this metadata work.

Reproduce the metadata and fixed-code checks with the repository-local Python
3.15.1 interpreter and retained Git history:

```sh
build/issue-env/bin/python -m scripts.qualify_mbs_frozen_projection_roles --check
```
