# PBS public query export comparison — 5 November 2026

The maintainer requested remaining custodial PBS checks and publication of missing
public data. This resumes only this bounded PBS cohort; it does not reopen general
federation, rights adjudication, release or private-study publication.

Owner: current chat 01a1aa8f-ba44-78f1-a79b-e14bd3e07236; worktree
`/Volumes/PortableSSD/GitHub/gma-pbs-historical-backfill`, branch
`codex/pbs-public-export-comparison`. Owned paths: this report, exact public-export
contract, publication adapter/tests, existing PBS harvest workflow and track
increment. Native scope: one append to the existing public PBS utilisation dataset.
No competing native publication was observed. Next operation: protected PR,
then exact-main dispatch and anonymous verification; restore disabled workflow state.

Four historical Services Australia SAS HTML query reports have `.xls` names.
They contain public aggregate services by item, processing year and patient
category. Requested windows end December 2023 or March 2024; observed rows start
1992 for two reports and 2007 for two. They are not participant records. The
committed allowlist binds their exact original bytes; no source data is in Git.
Original query endpoints/export instants are unavailable. A custodian-supplied
copy is not a fresh publisher download, and receipts preserve this distinction.

Comparison used the anonymously restored, digest-verified 1992–2014 item CSV ZIP
and both half-year item files for each year 2015–2024, at utilisation archive
revision `0eec875382d5bff7c1c618fd39ae29f5d7ede897`. State/month rows were summed
by item/year/patient category; 2024 was restricted to January–March. Export
subtotals and grand totals were excluded from item-level comparison. Across the
four reports, 3,920 cells match exactly; 850 explicitly zero cells have no source
row in the sparse archive. No nonzero cell is missing or different. Absence of a
row was not promoted to verified zero. Original reports therefore retain useful
explicit-zero and query-layout evidence and will be preserved separately.

| Report | Compared item/category/year cells | Exact matches | Explicit zero, no archive row |
|---|---:|---:|---:|
| PBS_Data_2034873169.9.xls | 1,925 | 1,537 | 388 |
| PBS_Data_2034873190.5.xls | 396 | 352 | 44 |
| PBS_Data_2031500299.3.xls | 636 | 562 | 74 |
| PBS_Data_2031500184.5.xls | 1,813 | 1,469 | 344 |

The September 2025 schedule ZIP/33 CSVs already match reimbursement-atlas.
The API SQLite cache has 14,353 item and 7,788 ATC rows, corresponding to that
reference snapshot; local null/number transformations mean byte/value equality
is not claimed. It is a rebuildable cache, not new utilisation history.
Enriched study Parquet has participant identifiers and dates and is excluded.
All three dated medicine extracts exactly match the 1,440 unique study
descriptions. The three dated ATC Feather files each have 92,923 participant
records and are excluded. Medicine lists are study-derived, not a
publisher medicine inventory. They remain private. Other study/linkage artifacts,
private summaries, logs, notebooks and participant extracts remain excluded.
The 3.1.12 XML schema ZIP is developer documentation/schema material, not
additional dispensing or schedule records; no schema publication is claimed.

Validation is bounded to exact cohort decoding, allowlist/digest/length checks,
expansion limits, duplicate/trailing input rejection, local upload refusal and
existing append-only publication machinery. Publication occurs in Actions only;
no credentials, private location paths or participant data enter dispatch inputs.
The workflow validates exact current main; the archive append uses an exact parent.
No existing object is deleted. Hosted verification must succeed before cleanup.

Stop after one verified append and workflow-state restoration. Native outcome is
recorded separately after execution, without a receipt-only successor PR.

Validation: 93 focused tests passed on observed Python 3.15.1; Ruff and context
validation passed. No local full profile required for this bounded adapter.

First hosted invocation at `40036ee1` failed before tests because the new test
file was absent from the explicit Test-Goblin inventory. Register it alongside
existing harvesting tests; validate the inventory locally and retain the failed
run separately. Final-head required CI remains mandatory.
