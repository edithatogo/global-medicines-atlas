# V3 metadata-registration receipt

This additive receipt commits to the exact serialized v3 plan, deterministic
registration and metadata for one projection. It pins the prior replay report,
field-lineage report, producer source references and the code used to reconstruct
the plan. The original v3 schema is unchanged.

The full plan is reconstructed in memory from those pinned inputs, checked
against the v3 schema and its original digest, and semantically verified against
the receipt and independently supplied object identity. The receipt does not
contain or encode a full plan, source payload, projection rows or source values.
The recipe and all required metadata/code bytes must be available to the
consumer; the receipt alone is not a standalone v3 plan.

`verify_v3_registration_receipt` establishes metadata-registration evidence
only. It does not replay payload bytes, authorize publication, clear privacy or
admit an object. The existing scanner remains unchanged and unsuppressed.
