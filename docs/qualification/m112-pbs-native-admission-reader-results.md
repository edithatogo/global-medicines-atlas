# Exact six-object PBS raw admission and reader results

All six existing PBS raw objects passed trusted v4 admission and bounded
production-reader canaries on exact main
`10b104417ccb37da6ec20b8e7151c6486a787eec`. Each was dispatched once; all native
runs, jobs and metadata artifacts passed. The
[cohort manifest](../../quality/qualifications/australian-m112-pbs-v4-admission-readers-20261028/manifest.json)
binds the exact identities, contract and receipt digests, native run/job
observations and artifact identities. It verifies 191,047,619 source bytes,
remote and consumer-stream digest agreement and zero reader-cache bytes after
close. No source payload or data value was downloaded to the workstation.

| Existing object | Successful native run |
| --- | --- |
| Expenditure workbook 2023–24 | [40691968215](https://github.com/edithatogo/global-medicines-atlas/actions/runs/40691968215) |
| Expenditure workbook 2024–25 | [40692208170](https://github.com/edithatogo/global-medicines-atlas/actions/runs/40692208170) |
| Date-of-supply CSV 2024–25 | [40692360821](https://github.com/edithatogo/global-medicines-atlas/actions/runs/40692360821) |
| Date-of-supply CSV 2025–26 | [40692757372](https://github.com/edithatogo/global-medicines-atlas/actions/runs/40692757372) |
| Item-to-drug map | [40692888934](https://github.com/edithatogo/global-medicines-atlas/actions/runs/40692888934) |
| Multiyear date-of-supply workbook | [40693427540](https://github.com/edithatogo/global-medicines-atlas/actions/runs/40693427540) |

The [effective frozen raw reconciliation](../../quality/qualifications/australian-m112-effective-raw-delivery-reconciliation-20261028.json)
joins these six admissions to the unchanged eight-object MBS baseline:
**14 raw admissions, 14 admitted-object reader canaries, 1,745 deferred objects,
and the same frozen denominator of 1,759**. All fourteen path/revision identities
are members of that inventory and the two cohorts are disjoint. The separately
qualified six-table MBS Silver cohort is not added to the raw-object count.
Dated eight-object reports and candidate/rights snapshots remain immutable
historical evidence rather than being rewritten after admission.

These admissions retain unqualified native schemas and null effective dates.
They do not qualify PBS domain meanings, vocabulary membership, patient rates,
Silver/Gold/Platinum derived outputs or API/CLI/Atlas table semantics. Primary
restoration and cache cleanup do not establish independent recovery. Existing
exact six-object rights attestation is reused without independently reviewing
its instrument or widening its scope. Federation and Stable v1 remain blocked.

## Code qualification and local limitation

PR #1365 merged after 38 exact-head checks passed, including Codecov and the
protected Linux lanes. Two first-attempt jobs passed their work but failed
artifact upload with `The server is busy.` Failed artifact absence was checked
and one failed-job-only retry succeeded; the head did not change. All six
source-qualification dispatches were separate, single-send native runs.

The one local full Test-Goblin attempt passed package consumers, typing and
9,386 coverage tests (four capability skips), with 97.06% coverage. macOS
mutmut completed as advisory. The attempt terminated with exit 138 during
pytest-gremlins at 108/1118, so no local full pass is claimed. A transient
executable failure was observed; Python 3.15.1 and the exact CLI policy test
subsequently passed without environment recreation. The cause was not
established, and the full suite was not restarted. This evidence follow-up
uses focused validation and reuses the exact-head hosted results.
