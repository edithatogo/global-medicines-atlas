# Frozen MBS raw lineage and replay candidates

This packet prepares v1 and v3 evidence for the three already assessed MBS
schedule paths in the frozen inventory. It uses the existing archive and
retained metadata only; it adds or publishes no dataset, accesses no
participant or cohort-derived data, and changes no rights decision.

The [lineage crosswalk](../../quality/qualifications/australian-mbs-frozen-raw-lineage-20261115/lineage-crosswalk.json)
binds each target at revision `243f9ff5…` to its exact hosted digest, the
prior source receipt, acquisition event, original B2 reference and scoped
rights evidence. The July B2 reference remains at revision `4d1dae48…`; the
August B2 reference remains at `abdf414c…`. The August alias is bound to the
same source digest and size, with its own exact target-path digest observation.
No historical reference, acquisition or producer record is rewritten.

The [v1 conformance candidate](../../quality/qualifications/australian-mbs-frozen-raw-lineage-20261115/v1-conformance.json)
contains three candidate artifacts and three **blocked** promotion decisions.
The [July](../../quality/qualifications/australian-mbs-frozen-raw-lineage-20261115/v3-plan-july.json),
[August](../../quality/qualifications/australian-mbs-frozen-raw-lineage-20261115/v3-plan-august.json)
and [August alias](../../quality/qualifications/australian-mbs-frozen-raw-lineage-20261115/v3-plan-august-alias.json)
v3 documents are plans, not replay execution receipts. Their metadata hashes
bind the respective crosswalk provenance, including the earlier B2 reference.
The July rights instrument remains maintainer-attested, not independently
reviewed; the existing permissions are not widened by this packet.

The existing replay executor now accepts only these three additional exact
schedule identities after regenerating and comparing each plan. On an
exact-main hosted dispatch it streams public, previously assessed bytes into a
bounded digest calculation without persisting or emitting them. It retains a
metadata-only registration receipt. A plan, test fixture or workflow definition
is not proof that a hosted replay has run. Successful replay also does not
complete v4 receipt closure, trusted admission, a consumer canary, independent
recovery or federation acceptance.

Validate the candidate packet using the repository-local Python 3.15.1:

```sh
build/federation-env/bin/python -m scripts.qualify_mbs_frozen_raw_replay --check
```

The PBS privacy dispositions remain unchanged. Unassessed objects are not read
by this packet.
