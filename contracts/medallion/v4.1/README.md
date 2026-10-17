# Public dataset federation v4.1

This additive schema version preserves the immutable v4.0 contract and makes
field-level lineage applicability explicit. It allows `v2_field_lineage` to be
null only for an immutable raw Bronze B2 object, with the required state
`not_applicable_raw_b2`. Every other object still requires a field-lineage
receipt and the state `provided`.

This exception reflects the layer boundary: a raw B2 source object has not been
transformed into fields, so inventing an identity field map would claim a
transformation that did not occur. The exception supplies no rights, source
coverage, acquisition, receipt, promotion, admission, or publication authority.
All other v4.0 authority, location, publication, verification, rights,
discovery, v1/v3 lineage, recovery, cache, and consumer requirements remain
unchanged.

The schema digest is
`03acfbafd80daf0b8b768f7814dbb29a9bd13e7c9d5d68797b30261da29770c6`.
Consumers must pin this exact schema and validate the entire contract and its
referenced receipts independently. The fixture is synthetic and grants no
publication or clinical authority.
