# Australian native field contracts v1

This is the structural foundation for Australian Silver/Gold, not a claim
that Silver tables, Gold edges or a public release have been completed.
Contracts live in `contracts/australian-source/v1`; the Python semantic
validators in `australian_source_contracts.py` supplement the JSON schemas.
The portable schemas enforce source/subject/dimension combinations and native
value/state consistency; Python additionally checks cross-record denominators.

## Reuse and scope

### Typed scalar prerequisite

`mbs_typed_values.convert_mbs_value` reuses the existing 40-field mapping.
It retains native text and presence state alongside a conversion outcome.
Identifiers, codes and descriptions stay strings, including leading zeros
and empty text. Numeric/date blanks, missing fields, nulls, invalid values,
and successful conversions remain distinct. Derived-fee expressions and
spreadsheet error strings are never evaluated.

Amounts use exact Python Decimal values with explicit AUD currency;
percentages retain their source magnitude (85 is not silently changed to
0.85). The strict decimal grammar accepts signed ASCII digits and an optional
fraction, not exponents, separators, currency symbols or surrounding spaces.
No quantization or rounding occurs, even under a low-precision Decimal context.
Arrow precision/scale admission remains a separate pending step.

Dates require an explicit format profile: strict YYYY-MM-DD (`iso`) or
DD.MM.YYYY (`mbs-dmy`). The latter follows the
[official MBS XML field specification](https://www.mbsonline.gov.au/internet/mbsonline/publishing.nsf/Content/FAQ-XML_Help),
last updated 4 March 2022 and checked 30 August 2026. The implementation
rejects impossible dates, mixed separators, non-padded fields and surrounding
whitespace; it does not infer locale. Scalar conversion v2 and Arrow metadata
record the profile/version. Synthetic tests cover every mapped date field,
leap years and ambiguous day/month values. Without a profile, nonblank dates
remain `unsupported_format`. Real-corpus qualification is still required;
format documentation alone does not prove every archived value conforms.
Callers still need era-specific evidence and exact B1/v4
lineage before producing qualified Silver tables. Scalar result objects are
internal conversion outputs, not independently validated interchange receipts.
No real payload acquisition, publication, promotion or dependency change is
part of this prerequisite.

### MBS XML Arrow candidates

`mbs_silver.iter_mbs_silver_batches` parses exact receipt-matched XML and emits
one selected service, hierarchy, description, fee, benefit or cap table in
source order. The six versioned schemas cover all 40 native XML fields.
Each field is a non-null struct containing native text, native presence state,
conversion status and a typed value. Its schema metadata records the original
XML path and explicit currency/type. All fields are emitted even when absent.
Repeated native item identifiers are retained as distinct source ordinals.

Every batch retains the exact source-receipt digest/content-addressed locator,
schema era, date-profile choice and source-record denominator. Embedded
provenance is restricted to a redacted retrieval URI, retrieval time and
rights/evidence enums. It deliberately excludes complete receipt bytes, HTTP
redirect/final locations, rights-reference URLs and arbitrary receipt metadata
that could contain credentials. URI redaction reuses the B1 projection helper.
Each row binds its native record ID and ordinal to B2 payload SHA-256 and B1
receipt SHA-256. The original receipt digest is not recomputed from a redacted
projection. Input bytes are checked against the receipt before any output.
Public v4 object locations and anonymous
verification remain the data-plane integration boundary; these candidates do
not constitute publication or promotion receipts.

Numeric columns use Arrow decimal128(38,9), compatible with the existing
columnar stack. Exact values outside its scale/precision become
`unrepresentable` with a null typed value and unchanged native text. No rounding,
percentage rescaling or error-string evaluation is performed. Tests include
low Decimal contexts and trailing-zero scale reduction without numeric loss.

The source parser is bounded to 9 MB and materializes the native XML batch;
the Arrow output buffer is limited to 1–4,096 rows. This is not an unbounded
streaming XML parser. Repeated calls for separate tables reparse the source;
full-corpus throughput and memory profiling remain pending. The fixed-format
Parquet round trip is deterministic within the locked runtime. Cross-version
byte equality is not claimed.

Real-source date-profile qualification, all four workbook annotation tables, PBS
typed tables, comparison events, public v4 qualification and promotion remain
unfinished. The module does not acquire or publish any source bytes.

### Legacy workbook cell candidates

`mbs_workbook_silver.iter_workbook_silver_batches` preserves every sheet and
cell from the bounded native XLSX parser. Empty sheets yield an empty,
schema-bearing batch, so absence of cells does not erase sheet identity.
Sheet names, paths, relationship IDs, dimensions and property presence remain
in metadata; cells retain their native properties, presence list, coordinates,
row/column addresses and exact source/receipt digests. Receipt metadata uses
the same credential-safe helper as the XML tables.

The storage-type interpretation follows the
[Open XML cell types](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.spreadsheet.cellvalues?view=openxml-3.0.1):
shared/inline strings stay strings, numeric values use exact decimal128(38,9),
booleans require 0/1, errors retain their codes, and date-tagged text remains
text. Formula text and cached results are both preserved, marked as cache
evidence, and never evaluated. Unknown types, missing values, empty nodes,
invalid numerics and unrepresentable precision/exponents remain distinguishable.
Extreme exponents are bounded before Arrow conversion; Decimal context traps
cannot admit a non-finite result. Negative/out-of-range shared-string indices
are rejected instead of using Python negative indexing.

These are cell-storage types, not an inferred domain mapping. Style-indexed
numeric serials are not silently interpreted as dates, currencies or amounts.
Legacy element/class/technology/disease/tissue and other annotations survive
as native cells, but an exact header/style/epoch profile and hosted real-source
qualification are still needed for harmonised annotation tables. Bounded
synthetic four-sheet tests do not prove the full archived workbook denominator.
No raw source acquisition, formula execution or public publication occurs here.

### Parser reuse

The implementation reuses the existing MBS native XML/workbook models, PBS
namespace and bounded parser policy, shared receipt-to-provenance validation,
Pydantic frozen models and existing test tooling. No dependency was added.
The existing canonical medicine contracts cannot represent MBS services without
semantic coercion, so they are not used as the service-table schema. The v4
federation implementation is a separate publication-identity layer and will
be integrated when these products have actual hosted receipts.

## What is preserved

- MBS: each native record receives one slot for each of the 40 known fields.
  An absent field is `missing_field`; a present field without a value is
  `null`; a present string, including whitespace or an empty string, is
  `value`. Item identifiers retain leading zeros. Every field has an explicit
  intended table and value type; derived fee expressions remain source text.
- Workbook: every sheet's name, relationship, path and dimension, plus every
  cell's coordinate, native type, style index, formula, raw value and display
  value. No formula is evaluated and no error is converted into zero or an
  absent record. Cells keep worksheet path and coordinate identity; per-column
  coverage stays separate for each sheet. Missing cells are not manufactured.
  The `au-mbs-p7-xlsx-v2` parser records explicit property-presence metadata:
  an absent formula/value/style differs from an empty XML node. Older cached
  workbook projections without this metadata must be reparsed from immutable
  B2 before the new inventory can assign presence states. Raw bytes are unchanged.
- PBS: every XML element's text and tail, every attribute and expanded QName,
  with sibling-indexed native addresses. Unknown elements are retained rather
  than dropped by the existing selected-item projection. Expanded names retain
  namespace identity, not lexical prefix spelling or namespace declarations;
  exact source bytes remain the only byte-reconstruction authority.

Every occurrence binds source ID, source SHA-256 and schema era. Coverage
counts native records and schema paths, including null/missing/value totals,
and hashes the ordered, canonical occurrence stream. This projection digest
is not the raw source digest. Mixed source/era inputs and duplicate native
addresses fail closed. The summary is structural, not a receipt proving
acquisition, rights, admission, currency or complete geographical coverage.

## Typing and semantic boundary

The MBS registry declares identifiers, source codes/text/dates, AUD decimals,
unit decimals and percentages. It does not yet parse or round values. Later
typed tables must retain the native string and conversion outcome, use exact
decimal arithmetic, distinguish a missing date from a cessation date, and
never infer a date format or timezone from an ambiguous value. Acquisition
time remains independent of source-effective time in B1 provenance.

Source-native table contracts permit only MBS service-benefit tables, PBS
funding/formulary item tables, or PBS terminology-reference tables. They do
not permit regulatory claims, candidate/reviewed mapping status or an
absence-as-negative interpretation. Gold candidates and review evidence need
their own later graph contracts; neither a native ID nor a type declaration
authorizes terminology redistribution or a clinical inference.

## Validation and limitations

Synthetic tests exercise all 40 MBS fields, four workbook sheets with
formula/error/null states, and all elements/attributes/mixed text in a PBS
fixture. Tests check schema regeneration, semantic rejection, source drift,
duplicate identities, snapshot mixing and Unicode/JSON value round trips.
No raw public dataset is downloaded locally by this qualification.

The iterators operate over already bounded parser inputs. The summary keeps
identity sets proportional to the native occurrence count to detect duplicates;
it is not a demonstrated constant-memory full-PBS pipeline. Large-corpus
profiling, typed Arrow/Parquet tables, exact B1/v4 lineage integration,
historical comparison and hosted publication remain explicit successor tasks.
These synthetic denominators do not substitute for running the new inventory
against each approved public source revision in GitHub Actions.
## Hosted legacy workbook storage qualification

The `Qualify archived MBS workbook storage` workflow reads the already-public
July 2024 workbook anonymously at the immutable revision recorded in
`australian-mbs-public-huggingface-20260829.json`. It requires an exact merged
main commit, validates the 87,727-byte payload and its SHA-256 before parsing,
and never writes raw bytes to the workstation or uploads a new dataset.

The summary contains per-sheet cell, formula, error and conversion counts;
native first-two-row header candidates; workbook properties (including an
explicit date1904 attribute when present); and native number-format and cell
format attributes. Absence of an attribute remains absence, not an inferred
epoch. Each batch must survive a metadata-aware Parquet round trip and match
the native cell denominator. The workbook-wide manifest retains empty sheets.

These are storage-qualification results, not approval of header meanings,
dates, currencies, source coverage or Gold relationships. The workflow emits a
bounded qualification artifact with its code commit and run URL. Record the
observed result in Conductor before using it to define domain mappings.
Synthetic tests exercise the same profiler and mock the network; they do not
prove that the real workbook has passed the hosted run.

### Observed storage result and header-mapping candidates

[Hosted run 33305281887](https://github.com/edithatogo/global-medicines-atlas/actions/runs/33305281887)
qualified the exact public workbook on 2026-08-30: 13,742 cells in four sheets,
four formula cells and two error cells. All cells survived metadata-aware
Parquet round trips. Thirty-six numeric values were unrepresentable at the
chosen decimal scale and remain preserved as native values, without rounding.
The workbook property element is empty; 13 cell formats reference only native
format IDs 0 and 49, with no custom number formats. No date epoch was inferred.
The metadata-only receipt is `quality/qualifications/mbs-workbook-storage-20260830.json`;
the [durable receipt](https://github.com/edithatogo/global-medicines-atlas/issues/341#issuecomment-5468037256)
records the raw and report identities.

`mbs_workbook_domain.iter_workbook_domain_batches` binds all cells to these
observed headers, retaining native row IDs and header coordinates. It reuses
the 40 existing MBS field destinations, adds seven legacy annotation fields,
and preserves the separate description and Declining List sheets. Unlabelled
cells, including the AV formula/error column, remain explicitly unmapped.
The exact four-sheet layout and header profile must match before any output.

These are header-based column mappings, not validated clinical annotations,
current-status assertions, flag-to-boolean conversions, or date/currency
harmonisation. Declining-list membership is only a source annotation, never
cessation evidence. The next hosted run also counts these mappings; synthetic
tests and the earlier storage run do not prove that new mapping execution.

The [extended run 33307737257](https://github.com/edithatogo/global-medicines-atlas/actions/runs/33307737257)
subsequently accounted for all 13,742 cells: 97 headers, 13,641 header-bound
cells and four unlabelled cells. The metadata-only receipt is
`quality/qualifications/mbs-workbook-header-mapping-20260830.json`. This
qualifies header binding, not semantic value interpretation or publication.

### Workbook domain-value candidates

`mbs_workbook_values.iter_workbook_value_batches` adds domain text, date,
decimal, currency, value-state and conversion-status columns alongside the
native cell and header lineage. It reuses the existing MBS scalar contracts.
Identifiers and source codes retain lexical strings; legacy annotations are
literal text, including blank or boolean-encoded flags, not clinical claims.
Formula caches retain `value_origin=formula_cache`; no formula is evaluated.

Known numeric OOXML cells reuse the bounded exact storage converter, including
scientific notation. Text-encoded amounts use the existing strict MBS scalar
grammar. AUD applies only to monetary field contracts; unrepresentable scale
or precision is reported without rounding. Errors, unsupported storage types,
missing value nodes and explicit nulls remain distinct.

Dates require an explicit text profile; numeric Excel serials remain
unsupported rather than guessed from styles or an epoch. The extended hosted
workflow leaves the date profile unselected and reports per-field outcomes
after this code merges. The documented XML `mbs-dmy` profile is not a
workbook-era qualification; dates stay native text with `unsupported_format`
until an independently evidenced workbook profile is available.
That real-source value qualification remains pending; the completed header
run does not establish value conversion, Silver promotion or a public v4
derivative.
# Workbook date-encoding observation

The existing hosted value profiler additionally reports versioned aggregate
date-encoding counts and per-field denominators. These distinguish native
headers, absent/null values, empty text, errors, numeric storage, native OOXML
date storage (`t="d"`, kept distinct from ordinary text), unsupported
storage, and three exact ASCII text shapes. The shape names describe character
widths and separators, not day/month order or calendar validity. For example,
`99.99.0000` has a two-two-four dot shape but is not certified as a date.

No trimming, Unicode digit coercion, Excel epoch interpretation or conversion
profile selection is performed. Only aggregate categories are added to the
metadata report; no date samples or raw source cells are emitted. Existing
native cells, unsupported conversion outcomes and source digest remain intact.
The same Actions-only qualifier will collect these additional observations
after the implementation merges; previous completed versions need not rerun.
Observation is a prerequisite, not independent workbook-era date qualification
or semantic promotion. No dataset upload or dependency change is introduced.

## PBS native-field Arrow prerequisite

`iter_pbs_silver_batches` exposes the existing receipt-bound PBS native-field
inventory as a versioned Arrow candidate table. Each row retains the complete
native occurrence contract, an ordered ordinal, a B2-digest-plus-field-path
identity, and the B1 receipt digest. Credential-safe receipt metadata is shared
with the MBS candidates. All batches use identical schema metadata.

This is a typed structural prerequisite, not domain-harmonised Silver or a
new evidentiary source of truth. Expanded XML names preserve namespace URIs,
while original prefixes, comments, entity spelling and other lexical details
remain in B2 bytes. Text and tail whitespace, empty attributes, duplicate
native IDs and unknown fields are retained. Missing elements do not create
invented rows; empty parsed text/tail slots remain null. The receipt must bind
the XML member itself, not its containing ZIP.

The inherited PBS parser uses finite byte/depth/element/text limits and keeps
the XML tree in memory. Only the additional row buffer is capped at 4,096
rows; this is not constant-memory streaming or real-schedule qualification.
Synthetic tests cover complete native-slot parity, identity/prefix invariance,
malformed envelopes, receipt mismatch, redacted metadata and deterministic
Parquet round trips across batch sizes. No dates, prices, funding status,
ARTG regulatory status or AMT/ATC relationships are inferred. PBS domain
tables, harmonised values, large-corpus qualification, v4 integration and
public derivatives remain pending. No dependency or acquisition change.

## PBS structural destination candidates

`iter_pbs_domain_batches` adds `mapping_target`, `mapping_status` and
`item_occurrence_id` to every native slot without changing or removing it.
Profile `pbs-adapter-structural-v1` covers the two root/item layouts exercised
by the existing PBS v3 adapter fixtures. Exact expanded names and ancestry
identify schedule metadata, item occurrences, block-container/DocBook
presentation text, restrictions, drug/mp/code reference structures, and
classification structures. A foreign namespace with a matching local name,
an unrecognised wrapper, or an unknown field does not inherit a known mapping.

Item lineage uses the B2 digest and occurrence path, not a supposedly unique
native item code. Duplicate IDs remain separate. The original ID attributes,
classification type attributes, text/tails, dates and reference strings remain
queryable in the native columns. `classifications` does not label every code
ATC; `amt_references` describes the adapter-established mp-reference structure,
not acquired terminology content or an authoritative crosswalk.

These structural destinations are candidate table partitions, not funding,
regulatory, clinical or current-status assertions. Price fields remain
unmapped until a source-specific field contract is established; native prices
are not dropped. Date/currency conversion, fuller presentation/price schemas,
real-corpus qualification and public v4 derivatives remain pending. No source
data was acquired or published for this synthetic-only slice.

## PBS native entity rows

`iter_pbs_entity_batches` groups consecutive native slots into one row per
XML element occurrence, including empty and unmapped elements. Each row
exposes the expanded name, native text/tail and states, literal `xml:id` and
its missing/value state, structural destination, parent entity ID and item
occurrence ID. Parent links preserve mixed-content structure without joining
or normalising descendant text. These are source tree links, not clinical or
terminology relationships.

The complete original mapped rows remain nested in `native_fields`; flattening
them in order reproduces the input inventory, including all attributes,
unknown fields, native prices/dates, B1/B2 identities and field addresses.
Duplicate `xml:id` values do not merge occurrences; absent IDs and explicit
empty IDs stay distinct. Reference code text/resources remain native, not
validated vocabulary or funding assertions.

Additional grouping is limited to 4,096 native fields and 1 MiB of compact
UTF-8 JSON field representations per element. Output batches are limited to
the requested 1–4,096 rows and 8 MiB of compact JSON entity representations.
These are encoded-payload budgets, not exact Python/Arrow resident-memory
limits; the inherited XML parser still holds a bounded source tree. Oversized
elements fail without truncation. Consumers must discard partial output if an
iterator raises. Synthetic tests cover cross-batch grouping, byte-budget
flushing, explicit rejection, duplicate/blank/missing IDs, empty elements,
mixed content and metadata-aware Parquet/native-field reconstruction.
Real-corpus qualification, domain-wide value harmonisation and public
derivative publication remain pending.

## PBS literal identifier/reference diagnostics

`iter_pbs_reference_batches` retains all entity columns and native slots and
adds the `pbs-adapter-literal-references-v1` profile. Only the existing
adapter fixtures establish contracts: item `xml:id` in the two supported
layouts; PBS drug-references-list/mp-reference/code text and the exact RDF
`resource` attribute; classification/code text with unqualified `type="ATC"`.
Other paths, namespaces and classification types remain explicitly unmapped.

`reference_value` and `reference_resource` preserve source spelling, including
whitespace and leading zeros. Their state columns distinguish absent, null,
value and not-applicable slots. `occurrence_count` counts identical nonempty
literal (kind, value, resource) tuples in one payload; missing/empty values
are not indexed and report zero. `distinct_resource_count` counts distinct
nonempty literal resource targets for that kind/value. No URI normalisation
occurs, and fragment references are not resolved against XML IDs.

`diagnostic` is unmapped, missing_value, empty_value, unique_source_literal,
duplicate_source_literal, missing_target, empty_target,
ambiguous_source_targets or unresolved. Item uniqueness means only literal
uniqueness among supported item occurrences in this payload, not global
identity or XML schema validity. Repeated references remain unresolved even
when their literals match; conflicting resource strings are source-local
diagnostics, not proof of distinct or equivalent terminology concepts.
Missing/empty value or target diagnostics take precedence over ambiguity;
the independent counts remain available. No vocabulary content is loaded.

Two entity passes allow forward-duplicate detection without retaining all
output rows. The index allows 100,000 distinct tuples and 16 MiB of compact
UTF-8 JSON tuple encodings; counters and target totals are updated once per
occurrence. The output buffer permits 1–4,096 rows and 8 MiB of compact JSON
row encodings. The inherited bounded XML tree and entity budgets still apply.
These are encoded-size budgets, not exact resident-memory bounds; the second
parse is an explicit throughput trade-off awaiting real-corpus qualification.
Overflow fails without truncation; discard partial output after any error.
Synthetic-only coverage does not qualify full schedules, source dates/prices,
funding/regulatory status, medicine equivalence, public derivatives or v4.

## PBS opt-in date candidates

`iter_pbs_date_batches` adds date-slot candidates to complete native entity
rows, independently joinable to reference candidates by `entity_id`. The
existing adapter identifies unqualified `effective-date` on the PBS root or
schedule document element, PBS root/info/DCTERMS valid text, and effective-date
on mapped PBS restriction elements. Exact expanded names and supported
ancestry are required; foreign attributes and unknown wrappers stay unmapped.
The adapter's fallback/first-value selection is deliberately not copied.
Every observed element survives, including repeated dates or duplicate item
IDs. Absent elements are not invented; an existing supported element missing
its date attribute reports missing_field with no fabricated source field ID.

The adapter/native inventory and fixtures establish locations, not a complete
official date grammar. No dates are converted by default. Selecting
`pbs-iso-date-candidate-v1` explicitly requests ASCII `YYYY-MM-DD` calendar
conversion to Arrow date32, with years 0001–9999 and valid month/day values.
This named candidate profile does not qualify a PBS source era or real corpus.
The stdlib calendar parser, PyArrow, native entities and receipt metadata are
reused; the MBS-specific field registry/DMY profile is not imposed on PBS.

`date_native_value`, `date_native_state` and `date_source_field_id` retain
literal spelling, presence and original slot identity. Conversion status is
unmapped, missing_field, null, empty_value, blank_value, profile_not_selected,
unsupported_format, invalid_date or converted. Whitespace-padded dates,
alternate formats, timestamps and offsets remain unsupported, without
trimming or timezone assumptions. Typed null never erases the native value.

`date_occurrence_index` is the element's native same-expanded-name sibling
position, and state is first_occurrence or repeated_occurrence (not_applicable
for unmapped elements). First means positional first, not unique, preferred,
or authoritative; repeated dates are not assumed erroneous. Parent/entity
identities distinguish positions under different parents. No duplicate is
collapsed and no schedule/restriction precedence, validity interval, current
listing, price, funding entitlement or clinical assertion is derived.

The inherited bounded parser/entity buffers remain; an additional 8 MiB
compact UTF-8 JSON row budget encodes typed dates as ISO strings. Output is
limited to 1–4,096 rows per batch. This is not constant-memory parsing or an
exact resident-memory cap; discard partial output after an error. Synthetic
and property tests are not real-corpus, publication or v4 qualification.

## Historical PBS archive/member identity prerequisite

`PbsXmlMemberBinding` is a deterministic, candidate-only provenance record,
not a new acquisition receipt or admitted Silver table. It retains the full
original `au-pbs-historical-xml` source identity, parent B1 receipt digest,
archive B2 digest/byte count, exact member path, member digest/byte count and
the explicit `zip-member-extraction` relationship. The parent receipt remains
the location for retrieval, rights and temporal evidence; its URI/document is
not copied into this binding. No source alias or rights grant is invented.

`build_pbs_xml_member_binding` revalidates the parent SourceReceipt (including
successful retrieval), requires the historical source/AUS jurisdiction and
matches exact archive bytes. `read_pbs_v3_member`, shared with the existing
archive adapter, applies the unchanged PBS ZIP policy: bounded archive and
uncompressed sizes, entry count, ratio and path depth, safe portable paths,
no duplicate entries, encryption or symlinks, and exactly one SCH-*.xml member.
The bridge validates the member with the existing bounded XML parser and PBS
root/namespace contract. Binding member paths are additionally limited to
4,096 characters. Bytes are read in memory; no network or filesystem writes.
The parser retains a bounded tree, not constant-memory streaming.

`validate_pbs_xml_member_binding` requires the binding, parent receipt, archive
bytes and separately supplied member bytes. It rebuilds the binding and
compares every field plus the member digest/size. Missing lineage, altered
parents, wrong sources, mismatched bytes, unsafe or ambiguous members fail
closed. Deserializing the model or knowing its digest is not byte verification.
Duplicate item IDs do not defeat byte identity; the selected-record adapter's
duplicate-item rejection is unchanged and remains a separate qualification.

The historical source is never relabelled `au-pbs`. Existing native/Silver
APIs still require their original source contract and reject the archive
receipt. A subsequent explicit source/member-aware table contract is needed
to consume this historical binding; callers must not fabricate an aliased
SourceReceipt. This prerequisite neither selects a date profile nor proves
corpus completeness, production admission, publication or federation v4.
