# Frozen July MBS raw v4 qualification

The [candidate contract](../../quality/qualifications/australian-mbs-july-frozen-v4-20261115/contract.json)
is for one previously assessed July 2025 raw MBS XML object at immutable
archive revision `243f9ff5498816af6e4d9ae4db60528728f01834`. It adds no
source or dataset and does not change the frozen inventory.

The contract combines the exact source receipt, B1 event and B2 reference,
existing maintainer-attested exact-scope rights, v1 candidate conformance,
the successful exact v3 replay and the later anonymous digest observation.
The source-era and legacy-cohort values reuse the already-qualified July Silver
consumer contract for the same source acquisition. This is not a new claim
about an August release's field meanings.

The publication role identifies the hosted metadata append that created this
exact archive revision while preserving the existing object. It does not say
the metadata append originally acquired or uploaded that object. Its retained
inventory also supplies a historical primary-restore candidate. The later
three-object in-memory reconstruction independently verifies this primary copy;
neither operation establishes an independent replica or an RPO/RTO.

A local metadata-only check fetched and digest-verified 13 receipt roles from
10 distinct public metadata locations, then passed the independently
configured admission check for the candidate contract. It did not read the
source payload or exercise the consumer. Contract SHA-256:
`8c2032a7831b263f2792a9283759a96b9b91875cef8a685f4e010d84051664b9`.

The dispatch-only hosted workflow is prepared to repeat receipt closure and
admission on exact merged main, then exercise the existing bounded
`FederatedReader` against the already assessed July object. The workflow and
synthetic tests alone are not a hosted admission or a consumer result. Its
receipt will contain metadata only; no source values or participant or
cohort-derived data are emitted, and no dataset is published.

The August raw objects and all four frozen projections still require their own
v4 contracts and evidence bindings. Their historical candidate source-era and
projection evidence does not establish release-linked field semantics. The
four outside projections retain the separately documented historical-writer
limitation. Independent recovery and overall federation acceptance remain open.

## Reproduction

```sh
build/federation-env/bin/python -m scripts.qualify_mbs_july_frozen_v4 --check
```
