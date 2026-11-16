# V1 source and Bronze projection profile

This additive, versioned profile complements the immutable v1 vocabulary. It
binds a schema- and semantics-validated v1 B1-to-B2 **raw source** document to a
separate, source-faithful B2-associated projection. The derivation is within
one stratum and is not a medallion promotion. The profile preserves the distinct
raw-reference and original producer acquisitions; a shared content digest does
not make them the same acquisition or rewrite their chronology.

`verify_v1_projection_profile` requires independently supplied exact identities,
metadata bytes, pinned schemas, 85 expected v2 mappings, original producer
receipt, B1/B2 references, source acceptance and the existing scoped rights
evidence. It checks the recorded limits on the source and projection rights
attestations. The profile does not create a rights decision, clear output
privacy, or admit a projection. V4 receipt closure and independently configured
trust are separate; consumers must opt into this profile explicitly.
