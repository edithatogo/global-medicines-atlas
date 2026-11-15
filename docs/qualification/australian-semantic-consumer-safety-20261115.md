# Australian semantic and consumer-safety checks

This bounded check uses retained qualification metadata and synthetic consumer
fixtures. It adds no datasets or source values, reads no participant or
cohort-derived research data, performs no admission or publication, and does
not qualify the Australian federation for release.

## Semantic evidence

The frozen [field contract](../../quality/qualifications/australian-benefits-release-field-contract-20261028.json)
requires observed fields to remain interpreted, native unresolved, or
unavailable, and does not treat missing evidence as a negative fact. Its
evidence-bound PBS [field reconciliation](../../quality/qualifications/pbs-native-silver-field-reconciliation-20261028-r19.json)
partitions 18,208,758 source fields into 3,096,735 interpreted, 15,112,023
native unresolved, and zero unavailable. The interpreted state includes
bounded source roles and lexical rules; it does not qualify general PBS domain
meanings, clinical eligibility, current listing status, patient rates or
semantic relationships. Pointer and literal matches remain structural evidence.

The retained [MBS workbook column qualification](../../quality/qualifications/mbs-historical-workbook-source-column-semantics-20261028.json)
binds 728 header roles across 91 workbook profiles. It leaves all 310,176,929
non-header values native unresolved, including their era-dependent meanings.
Header qualifications do not make those cells or historical pooling qualified.
Neither this review nor the new consumer checks reads those workbook payloads.

## Consumer evidence

The previous [public MBS consumer receipt](../../quality/qualifications/australian-mbs-silver-consumer-recheck-20261115/hosted-43651971792/admission-remote-read.json)
records six exact admitted July 2025 Silver objects at revision
`3d2d528439bddf6f42e8e700c88917f0960a9f38` and 24 successful API, CLI JSON,
CLI JSONL and Atlas checks. The stored receipt was checked against its
independent bindings and the earlier exact-object identities. An earlier
[hosted run](https://github.com/edithatogo/global-medicines-atlas/actions/runs/40653807510)
also compared browser-rendered cells. These receipts cover those six public
objects and do not establish source completeness or new admissions.

The source-structure view now explicitly says that a semantic overlay has not
been applied. Its API and CLI JSON responses, JSONL summary and Atlas wording
preserve that distinction; a source-native `state` is not a field's semantic
interpretation. The canary compares the API with CLI JSON and the JSONL
records and safety summary, repeats the bounded export for byte stability, and
checks the Atlas rows and warning. Cache-specific receipts may differ between
independent verified resolvers, so they are not equated. The canary continues to
bind the object, contract, semantic manifest and query identities. The Atlas
warning has a dedicated marker, so matching words in a source row cannot stand
in for the warning itself.

Focused synthetic tests check native null and presence values, offline
unavailability, source identity, pagination, and mismatched status, view,
offset, row count, comparison validity and semantic-overlay declarations.
Before the fix, the canary accepted six altered JSONL summaries and did not
compare CLI JSON; the altered record type was already rejected. The synthetic
checks also reject malformed, empty, non-object and non-finite export output.
They do not demonstrate actual PBS or workbook consumer delivery.

## Remaining limits

The six retained MBS receipts predate this source-structure change and are not
a real-data validation of it. Actual native-field canaries require an exact
privacy-qualified, rights-qualified and admitted derived output. The PBS
candidate and historical workbook candidates do not acquire that status from
these tests; their relevant privacy and admission checks remain separate.
An interpreted field count is not a blanket semantic or relationship
qualification. M-109, M-111 and the wider M-106 through M-112 federation gates
remain blocked, as do the applicable independent-recovery requirements.
