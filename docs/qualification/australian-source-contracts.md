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

### Reused parser foundations

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
