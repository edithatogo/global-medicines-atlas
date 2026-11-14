# Existing-archive federation evidence — 15 November 2026

This bounded reconciliation uses the already archived public data and existing
receipts. It does not acquire a new source, publish a dataset, change a rights
decision or admit a federation object. The
[machine-readable reconciliation](../../quality/qualifications/australian-federation-existing-archive-reconciliation-20261115.json)
binds the supporting repository files by SHA-256 and records the exact public
archive revisions, manifests and object identities used below.

## Existing workbook and AIHW publication

At the pinned MBS utilisation revision, the anonymous manifest has 443 entries.
Its annual workbook and acquisition receipt match the source and receipt
identities in the [separate workbook qualification](mbs-annual-public-workbook-20261115.md).
The workbook's patient sheet contains 2,202 classified aggregate rows and 17
financial-year labels, 2009–10 to 2025–26. Its source definition and value
shapes do not qualify cross-group distinct-patient counts, suppression or an
item-level denominator. No patient observation values were retained in this
qualification.

At the pinned PBS utilisation revision, the anonymous manifest has 1,078
entries and identifies the recovered monthly ATC2 ZIP and its B1 receipt.
The retained [hosted publication receipt](../../quality/qualifications/aihw-atc2-publication-20261114-43565582684.json)
records verification of that new pair, preservation of the preceding 1,076
objects and zero participant files. The manifest's SHA-256 of its exact file
bytes and the hosted receipt's SHA-256 of canonical sorted compact JSON are
different representations and are recorded separately. The old September
2025 workbook edition is still unidentified; the archived recovered edition
covers January 2015 to September 2026.

## Frozen inventory and consumers

The 13 November identity comparison matched all 1,759 frozen paths against
the then-pinned public metadata. It is retained as historical evidence, not
represented as a fresh 15 November scan. The effective raw delivery ledger
records 14 admitted objects and 14 corresponding reader checks, with 1,745
objects deferred. The six previously admitted July 2025 MBS Silver tables and
their [consumer evidence](../../quality/qualifications/platinum-actual-consumer-reconciliation-20261028.json)
are separate from those raw counts. The April 2026 PBS Silver output is not
v4-admitted. Archive presence, reader tests and role checks do not themselves
grant admission or establish complete coverage.

Hosted read-only run [43608538996](https://github.com/edithatogo/global-medicines-atlas/actions/runs/43608538996)
subsequently replayed the six existing July MBS Silver tables on base main
`946757ccdf5b21130811233f285807f5307ea209`. All six passed source-value,
schema, native-field and deterministic-replay comparisons. Its
[retained qualification](../../quality/qualifications/shared-mbs-silver-delivery-20261115-43608538996/qualification.json)
hash-binds the six value-free role reports in the same directory. The cache
exercise was in memory and the objects were restored from the primary archive;
this is not evidence of independent backup recovery. The run did not publish
or admit an object.

All original M-105 to M-112 requirement states remain blocked. In particular,
the workbook source note does not close M-106, and the preserved identity and
consumer evidence does not close M-112's per-object, independent recovery and
remaining role requirements. Participant and cohort-derived data were not
accessed or published in this tranche.
