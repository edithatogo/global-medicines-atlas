# International resource information schema

Version 4 of the governed source catalog describes both access mechanics and
the information each resource can contain. Its normative JSON Schema is
`schemas/international-resource-v4.json`.

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
  description and format.

These labels are discovery metadata. They do not claim that every record
contains every labelled field, and they do not elevate a declaration to
parser, live-receipt, or production-qualified status.

## Capability evidence

`builtin_source_capabilities()` is the executable capability registry. Stable
`module:symbol` identifiers map each implementation to exactly one catalog
source ID and distinguish acquisition, parser, synthetic fixture, canonical
projection, live receipt, and production qualification.

The registry is fail-closed. A parser does not imply a live receipt, and a
live receipt does not imply production qualification. Dedicated conformance
tests import every declared implementation and validate its single catalog
mapping.
