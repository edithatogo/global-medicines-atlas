# PBS RDF resource field-state qualification

The pinned PBS v3 member `sch-2026-04-01-r1.xml` has 18,208,758 field
occurrences across 5,163 schema paths. Successor field-state report r16 preserves
that denominator and partitions it as 3,086,366 interpreted, 15,122,392
`native_unresolved`, and zero unavailable.

The report interprets 1,159,282 previously unresolved fields as the generic
RDF/XML `rdf:resource` syntax role. The RDF/XML Recommendation specifies that
this attribute gives the IRI of an object node. The exact pinned field inventory
contains 1,167,610 `rdf:resource` fields across 370 paths; 8,328 fields already
have the narrower AMT-reference-resource interpretation and retain it.

The source-local URI screen reports 1,094,033 unique exact-literal candidates
and 73,577 references with no exact member definition. These remain diagnostics.
The new field-state rule does not validate individual URI values, resolve target
identities, interpret PBS predicate meaning, qualify domain or clinical
relationships, or emit edges. No source values were read or emitted by this
reconciliation.

Evidence:

- Report: `quality/qualifications/pbs-native-silver-field-reconciliation-20261028-r16.json`
- Screen: `quality/qualifications/pbs-native-reference-uri-screen-20261025-40120162365.json`
- Syntax basis: [W3C RDF 1.1 XML Syntax Recommendation](https://www.w3.org/TR/rdf-syntax-grammar/)
- Runtime implementation: `src/global_medicines_atlas/pbs_field_reconciliation.py`
- Focused regression: `tests/test_pbs_field_reconciliation.py`

This bounded role interpretation does not close PBS domain semantics, M-109,
the Australian federation gate, or Stable v1. Dates, prices, status, targets,
predicate meaning, currentness, and cross-era relationships remain subject to
their separate evidence and acceptance requirements.
