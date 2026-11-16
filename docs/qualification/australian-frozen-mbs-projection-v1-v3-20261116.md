# Frozen MBS projection v1 and v3 roles

The [qualification](../../quality/qualifications/australian-mbs-frozen-projection-v1-v3-20261116/qualification.json)
provides a local, value-free v1 projection profile and durable v3
metadata-registration receipt for each of the four August MBS projections in
the frozen revision. No source or projection payloads, participant data or
cohort-derived data were read, acquired or published.

## V1 projection profile

The pinned v1 vocabulary remains unchanged. A new
[source v1 document](../../quality/qualifications/australian-mbs-frozen-projection-v1-v3-20261116/source-v1-conformance.json)
restates the **already accepted raw source** as an adjacent B1-to-B2 decision;
it passes the original v1 schema and the repository's promotion semantics. It
is not a new source admission. The existing raw parser decision remains
`unreviewed`, and the source rights remain maintainer-attested for their exact
scope, with the instrument not independently reviewed.

A separate [v1 projection profile](../../contracts/medallion/v1-projection/README.md)
binds that raw source and its new v1 document to each exact projection, its
producer code and acquisition, the exact scoped projection-rights attestation,
and all 85 v2 field-lineage mappings. The raw reference acquisition was
recorded later than the original producer acquisitions. Their equal source
content digest does not make those acquisitions interchangeable. The 99fa
producer's reconstructed metadata remains identified as reconstructed.

This describes a same-stratum derivation, not a promotion or a claim that the
Parquet bytes are raw evidence. The historical source v1 document and the raw
v4 contracts that referenced it remain unchanged: its three target-layer
semantic mismatches are not retroactively repaired by the new document.

## Durable v3 metadata receipts

Each [v3 registration receipt](../../contracts/medallion/v3-registration/README.md)
pins its exact projection, source and producer references, the prior replay
report, field-lineage report, reconstruction code, full reconstructed-plan
digest and deterministic registration digest. A verifier reconstructs the
original v3 plan in memory, validates the original v3 schema and semantics,
and checks the plan and registration against independently supplied expected
identities. The full plan is not stored or encoded in the receipt. Reproduction
requires the pinned code and metadata; the compact receipt is not a standalone
v3 plan or a payload replay. The receipts pass the existing secrets scanner
without a suppression or configuration change.

The new verifier can bind all of these bytes to a **synthetic** v4 contract and
reject substituted identities or missing profile evidence. That proves the
local role-binding behavior, not a real v4 contract, independent trust,
consumer canary or admission for any of the four outputs.

## Privacy context and remaining gates

The historical MBS producer preserved the source URI in output metadata. The
two retained source receipts for these four objects have HTTPS URIs without
user-info, query or fragment components; this check did not inspect output
bytes or prove their values safe. Source classifications remain source-only.

For the separate April PBS Bronze projection, retained source-receipt metadata
and the prior lineage report agree on the source receipt and parser decision.
The source receipt's retained readback does not include a sensitivity field;
it does not establish the absence of such a field in the original receipt.
Source rights and parser acceptance do not clear the output's privacy. The PBS
Bronze output, the previously assessed reproduced PBS Silver output and all
other unassessed PBS objects retain their existing unknown dispositions.

The four MBS projections still need output-specific privacy clearance, complete
real v4 receipt closure and independent trust, followed by separately authorized
consumer checks. Independent recovery and broader federation acceptance remain
separate. The new receipts do not authorize a payload read or dataset publication.

Reproduce with the repository-local Python 3.15.1 interpreter and the pinned
historical Git code available:

```sh
build/issue-env/bin/python -m scripts.qualify_mbs_frozen_projection_v1_v3 --check
```
