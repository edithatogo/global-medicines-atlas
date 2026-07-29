# International resource information schema

Version 5 of the governed source catalog describes both access mechanics and
the information each resource can contain. Its normative JSON Schema is
`schemas/international-resource-v5.json`.

Each source explicitly declares:

- `information_domains`: identity, regulatory, funding, formulary,
  terminology, clinical-documentation, safety, pricing, reimbursement, or
  HTA-decision content;
- `record_entities`: source-native entities such as substances, products,
  packages, approvals, listings, documents, prices, or decisions;
- `status_semantics`: separate meanings for authorisation, reimbursement,
  subsidy, formulary inclusion, price listing, recommendation, terminology,
  and documents;
- `geographic_scope` and `population_scope`;
- `languages`, using controlled BCP 47 primary-language labels and `und` when
  available evidence does not establish a language;
- `change_semantics`: current state, snapshot, append-only history, delta,
  mixed, or unknown;
- `available_fields`: conservative field labels supported by the source
  description and format;
- `qualification_state`: `declared`, `documentation_verified`,
  `fixture_verified`, or `live_verified`, with explicit
  `qualification_references` for every state above `declared`.

Cross-field validation rejects contradictions between source dimension,
information domains, record entities, status semantics, and available fields.
These labels remain discovery metadata. They do not claim that every record
contains every labelled field, and they do not elevate a declaration to
parser, live-receipt, or production-qualified status.

## Capability evidence

`builtin_source_capabilities()` is the executable capability registry. Stable
`module:symbol` identifiers map each implementation to exactly one catalog
source ID and distinguish acquisition, fixture parser, source-qualified parser,
synthetic fixture, canonical projection, live receipt, and production
qualification.

The registry is fail-closed. Fixture parsers do not advance catalog integration
maturity. Source-parser and canonical-projection claims must agree with the
catalog's evidenced integration layer. A parser does not imply a live receipt,
and a live receipt does not imply production qualification.
