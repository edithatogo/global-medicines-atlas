# Stable v1 blocker audit — 2026-09-13

Audited local and remote main:
`694c47650226a5b6853b94011b899f77a60bbe82`.
Stable v1 remains unqualified. The signed stable release task is incomplete.
The five acceptance gates in the authoritative contract remain open; no gate
has been waived by the request to complete the track.

## Current evidence and closure requirements

| Gate | Observation | Required closure evidence |
| --- | --- | --- |
| Renovate output | All-state issue enumeration found no Renovate-authored issue or PR; searches for both the generic and configured dashboard titles found none. The existing receipt records maintainer-confirmed activation. | An authentic Renovate dashboard or update PR after successful App execution. Configuration presence and a manually created issue cannot satisfy this gate. |
| Bronze current public scope | Fresh repository evaluation counts 174 catalogue sources, 157 in scope, two fixture-only, 15 excluded and 138 lacking landing evidence. The old 136-source plan count is not the current evaluator result. | Source-specific rights, immutable payload/receipt or permitted reference, admission and restoration evidence for the complete approved denominator. |
| Australian health federation | Existing source publication receipts do not complete the unfinished Silver/Gold, data-plane and Platinum implementation and qualification tasks. | Exact producer/admission/distribution integration, semantic and product qualification, and verified public revisions required by the dependent plans. |
| M5 maturity | Source coverage and security/supply-chain dimensions remain M4 in the contract. | Evidence-backed completion of their prerequisites and a regenerated qualification contract. |
| Stable release approval | The recorded release authority covers `v1.0.0rc1` only. | Maintainer approval bound to a qualified stable candidate, followed by hosted release and independent consumer verification. |

Production disaster-recovery authority remains separate from software release
acceptance. No live production recovery is claimed.

## MBS harvest evidence

[Hosted run 34358783818](https://github.com/edithatogo/global-medicines-atlas/actions/runs/34358783818)
completed successfully at the audited main commit. Its
[GitHub Actions cleanup receipt](https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-5603102743)
records dataset `edithatogo/australian-mbs-utilisation-archive`, revision
`7f8f6b7e973a0b5f68d6ddff9dfea6a0db61b697`, 28 verified files, anonymous digest
verification passed and temporary source bytes removed. It also records
`coverage_status: partial` and three failed health.gov.au workbooks after
120-second timeouts. The hosted receipt was observed; payloads were not
downloaded or independently rehashed during this audit.

HTTP/1.1, longer timeouts, client hints and pacing have already been attempted.
Repeating a green harvest does not establish complete coverage. The outstanding
quarterly, annual and year-to-date workbooks need a supported source-delivery
path and fresh hosted acquisition evidence.

## Source decision boundary

The versioned Nordic authorization still records independent pending decisions
for Denmark, Norway and Sweden. Denmark's prepared scope is source-generated
aggregate utilisation exports with exact query parameters, attribution and
labelled transformations, for acquisition and internal retention only.
Public release and external publication are separate. The existing rights
preflight is dated 2026-08-21; a fresh read of its official terms PDF was
unavailable in this audit. The maintainer decision is requested without
inferring approval from public accessibility or generic continuation.

## Verification repairs

The first full Test-Goblin run stopped because Ruff traversed the populated,
pinned Conductor submodule. Excluding that exact upstream directory from the
Atlas formatter/linter preserves its upstream policy while retaining checks on
Atlas-owned source, scripts and tests.

The Bronze qualification CLI wrote a valid report and then raised `ValueError`
when formatting a relative output path or an absolute output outside the
repository. The success message now prints the requested path directly.
Both custom-path regression cases failed before the fix; the combined Bronze
and Stable v1 contract suite subsequently passed 32 tests. A custom-path report
then completed successfully and still reported Bronze as blocked.

Full-harness and hosted validation outcomes are recorded append-only in the
Stable v1 track evidence ledger. Focused tests do not replace those outcomes.
