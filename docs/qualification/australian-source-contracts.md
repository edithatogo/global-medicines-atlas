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

Dates require an explicit format profile. The only implemented profile is
strict YYYY-MM-DD (`iso`), tested with synthetic data. Without a profile,
nonblank dates remain `unsupported_format`; no locale or production schema-era
format is guessed. Callers still need era-specific evidence and exact B1/v4
lineage before producing qualified Silver tables. Scalar result objects are
internal conversion outputs, not independently validated interchange receipts.
No real payload acquisition, publication, promotion or dependency change is
part of this prerequisite.

### Existing components

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
