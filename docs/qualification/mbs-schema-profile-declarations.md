# Opt-in MBS schema-profile declarations

`iter_profiled_mbs_silver_batches` adds only the namespaced
`gma.mbs.schema_profile.v1` JSON metadata entry to a newly generated candidate
batch. Every existing field, value, occurrence, date-conversion choice and
metadata entry remains unchanged. Calling the existing MBS Silver producer
continues to produce its original representation; no public artifact is rewritten.

The declaration binds the exact B1 and B2 digests, source release revision and
caller-supplied comparison schema profile. Status is always `declared`, never
qualified. The source release label is checked against receipt `catalog_version`;
it is not an immutable content revision. The B1/B2 digests supply the exact
content binding. The legacy `schema_era` metadata remains intact and is identified
as a source-release label within this explicitly versioned declaration.

The wrapper revalidates copied declaration/receipt models, the generated column
schema, each batch's metadata and every row's B1/B2 lineage. Conflicting profile
metadata is rejected. Declaration JSON is bounded to 40 KiB. Existing parser and
batch limits remain unchanged; this is not a total process-memory guarantee.

Same-schema releases may share an explicitly declared profile while retaining
different release labels and digests. The label does not qualify an XML schema,
choose a date convention, establish source completeness or authorize publication.
All tests use synthetic in-memory source bytes. The wrapper has no acquisition,
upload or filesystem-writing behavior.

## Federation boundary

Federation v4 does not accept these declaration fields in its closed source
object. A future export requires a separately versioned declaration artifact and
consumer contract/canary; do not modify old v4 records or relabel their payloads.
Native comparisons additionally permit a `historical` cohort, while federation
v4 accepts only `legacy`, `current` and `synthetic`. An exporter must reject an
unsupported cohort until an explicit versioned mapping exists, never silently
convert `historical` to `legacy` or `current`. No exporter is added here.
