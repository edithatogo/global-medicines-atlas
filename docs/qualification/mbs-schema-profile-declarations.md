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
object. `bind_mbs_profile_to_federation` therefore produces a separately
versioned, content-bound read-side binding without modifying the v4 record or
relabeling its payload. The binding preserves the source release in v4
`schema_era` and carries the comparison schema profile separately. Its status
remains `declared`; it is not admission, qualification, rights evidence or an
export/publication instruction.

Native comparisons additionally permit a `historical` cohort, while federation
v4 accepts only `legacy`, `current` and `synthetic`. The consumer rejects
`historical` and every other unsupported value rather than silently converting
it to `legacy` or `current`. Evolving that cohort vocabulary still requires a
new compatible federation contract; this read-side canary does not do so.
