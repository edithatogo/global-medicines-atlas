# August MBS bounded semantic and consumer checks

The [check report](../../quality/qualifications/australian-mbs-august-bounded-semantics-consumers-20261116.json)
reconciles retained, value-free source and candidate Silver metadata for the
August 2026 MBS XML digest. It checks the 40 native field names against the
existing field contract and the structural field-lineage records for each of
the eight prepared Bronze projections. This is a metadata join, not a new
profile of the eight Parquet payloads.

The two historical aggregate profiles agree on field presence and null states
for all 40 fields. Their aggregate conversion counts differ only for six date
fields: the decrease marked `unsupported_format` matches the increase marked
converted. Aggregate counts alone do not prove a per-cell transition or
release-specific field meaning. Detailed counts remain in the linked existing
receipts; this report emits no source values or per-field observations.

The [current semantic status](mbs-xml-v3-field-semantics-status-2026-08.md)
supersedes the historical DMY report's acceptance flag. The earlier guide lacks
a complete release-linked change history; `ItemChange` and `EMSNCap` also have
documented wording or source conflicts. All 40 meanings therefore remain
provisional for the August release. This check does not transfer July 2025
semantics, establish current coverage, or accept M-109.

For the consumer check, each of the eight **synthetic identity probes** was
presented to the existing reader with the six retained, independently admitted
July 2025 Silver records available. The reader rejected all eight before a
network request. As a separate negative test, one July admission was rekeyed
in memory to each probe's contract digest; the reader still rejected the
different subject identity before I/O. That rekeying is a test, not a new or
modified admission. The checks do not read any projection or prove a real
payload consumer canary.

Run `python -m scripts.check_mbs_august_semantics_consumers --check` with the
repository-local Python 3.15.1 interpreter. Focused tests cover inconsistent
presence, date profiles, transformations, semantic status and admission
metadata, and run the check with networking disabled. The two `f9f9`
independent-replica prerequisites, all eight admission and actual-consumer
gates, the no-acquisition instruction, and privacy and rights decisions
remain unchanged. No participant or cohort-derived data was accessed.
