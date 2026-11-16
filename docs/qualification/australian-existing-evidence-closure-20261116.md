# Existing MBS admission, PBS privacy and recovery evidence

This [machine-readable reconciliation](../../quality/qualifications/australian-existing-evidence-closure-20261116.json)
uses only hash-bound repository metadata. It does not read source or projection
payloads, participant or cohort-derived data, acquire or publish datasets, or
change privacy, rights, admission or recovery decisions.

## Eight August MBS projections

Each dossier now separates its exact object identity and prior digest check,
source event and B2 reference, source receipt, rights attestation, structural
field lineage, metadata replay, recovery and consumer evidence. Four
projections are in the frozen inventory and four are outside it; this work does
not change that inventory.

For the four frozen projections, the [historical primary-restore reconciliation](australian-mbs-frozen-primary-history-20261115.md)
matches the exact dataset, revision, path, digest and size to the earlier
anonymous full-inventory restore. The restore predates a later source-event
record; the chronology is unchanged. The four outside projections are not
covered by that restore receipt. Their earlier publication receipts and
manifests bind their path, digest and size at earlier revisions; a later
separate digest receipt covers the selected revisions. Neither is an
independent replica.

The v4.1 roles remain distinct. Source event, B2 reference and receipt metadata
are bound; v2 field lineage is an identity-bound structural candidate; the v3
replay covers registration metadata, not a payload replay. A projection-specific
v1 conformance role, real v4 receipt closure, discovery and cache roles,
output-specific privacy and independent trust remain open. The existing raw-B2
v1 helper is not evidence of projection conformance. A synthetic contract
check confirms that a Bronze projection requires v2 field lineage and cannot
use the raw-B2 exception or an unknown sensitivity as clearance.

All eight retain prior synthetic refusal checks and lack actual payload
consumer canaries or v4 admission. The two `f9f9` outputs additionally require
their independently verifiable replica before admission. The four outside
outputs retain the historical-writer/footer qualification, and the exact-object
rights attestations do not authorize a consumer canary or admission.

## PBS privacy assessment context

Of the 1,722 previously unassessed PBS-related and reimbursement paths, **312
distinct paths** match the earlier official schedule crosswalk by exact dataset,
revision, path, digest and byte count: 311 reimbursement paths and one PBS
source-archive path. These correspond to 312 matched link occurrences and 313
candidate occurrences because one link has two retained candidates. The
remaining 1,410 paths are outside this particular link join; that is not a
finding that they lack other provenance.

All 312 remain blocked for privacy. The retained reimbursement acquisition
metadata records sensitivity and personal-data status as unknown. For the
separate PBS source-archive object, selected evidence does not establish
privacy, and its earlier rights-record conflict remains separate.

Two April 2026 archive aliases match the same previously profiled XML member.
Its 5,163 schema paths are structural context for that member, not an
assessment of values or every archive member. The exact September 2025 API ZIP
has 33 recorded member names, eight with selected review tokens; filename
triage is not content screening. None of the three path-level context matches
clears an archive, permits a payload read, or determines the sensitivity of a
participant or cohort.

## Recovery and consumer verification

Focused local tests exercise synthetic backup/restore/rollback, refusal of
unadmitted or mismatched consumer identities, and the raw-source no-read
boundary. These are software checks, not an independent disaster-recovery
rehearsal or an actual consumer canary for the eight projections. The previous
four-object primary restore remains historical evidence; the four other
projection identities, independent administrative and geographic separation,
target authority, RPO and RTO remain unqualified.

The offline report is reproducible with the repository-local Python 3.15.1
interpreter:

```sh
build/issue-env/bin/python -m scripts.reconcile_australian_existing_evidence --check
```
