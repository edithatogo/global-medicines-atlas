# Bounded native-field consumer delivery

PBS native packages retain a list of source fields on each entity. The existing
scalar query projection could read entity columns but could not return those
nested field observations. The additive `fields` view exposes them through the
same admitted resolver and query receipt path; it does not interpret values.

The shared query contract accepts an optional `field_collection` containing a
single allowlisted column identifier. It verifies the Parquet column is a list
of structs before reading field rows. DuckDB and Polars apply projection,
field predicates, row limits and the existing result-byte/runtime budgets.
Empty or null collections produce no invented observations. A field's native
null remains a field row. Bounded offsets expose subsequent observations in
the pinned object's scan order; the API, CLI and Atlas accept offsets from zero
to 100,000,000. Filters apply before the offset. Consumers should retain the
same object digest and engine across pages, and treat an empty page as the end
of that bounded result. The offset is included in every nonzero or field-view
query digest. Nested collection values remain unsupported scalar
results rather than being silently stringified or dropped.

The default record query keeps its exact v1 canonical query representation.
Collection queries use v1.1 and include the collection name in the query digest.
Source-structure results also declare `view=records` or `view=fields`.

## Existing consumer surfaces

- CLI: add `--view fields` to `source-structure`, with native field names selected
  using repeated `--column` options and `--offset` for later pages. The default
  remains `records` at offset zero.
- Atlas: select “Native source fields” in the evidence-view selector. Source
  values remain escaped HTML; identity, coverage limits and receipts remain
  visible.
- API: an operator may supply the same `SourceStructureLookup` to `create_v2_app`
  and query `/api/v2/source-structure/{resource_id}` with repeated `columns`,
  `view=fields`, `limit`, `offset` and optional `offline`. An unconfigured service returns
  503. Unknown resources, invalid requests and unavailable reads retain bounded
  non-leaking responses. This adds no operator trust or dataset automatically.

The 100-row source-structure limit and existing admission, digest, cache and
source-structure identity checks remain in force. The view exposes native
presence/value observations; a native `state` is not a semantic interpretation
state. Qualified semantic overlays remain independently bound. It establishes
no current status, payable benefit, patient rate, vocabulary meaning or link.

Synthetic fixture tests establish implementation behavior only. Real derived
consumer qualification still requires an exact admitted output and bounded
API, CLI, Atlas and export canaries. No such real qualification is claimed here.

## Research-package follow-up

The current metadata-only research package requires an HTTPS output distribution
and a lineage output URL containing the declared revision. Its clean-room
verifier checks canonical metadata and digest relationships; it does not fetch
those URLs or establish that a public output exists. Consequently a fabricated
or prospective URL cannot qualify an actual export, and requiring one blocks
local package qualification even when public publication is outside scope.

A bounded offline output reference needs its own explicit contract and digest
verification before this lane can close. Preserve the existing public URL rules
for published distributions, and bind any local result to the actual qualified
query and source revisions. The existing two-row JSONL consumer canaries alone
are not a deterministic research package.

The existing elapsed-time budget is checked after the query returns; it is not
a preemptive cancellation deadline. The 100-row source-structure limit bounds
rows returned, and the result-byte budget is checked before a response is
issued. Real-source performance and semantic field-state overlays still need
qualification against an admitted derived output.
