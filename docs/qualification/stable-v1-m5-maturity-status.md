# Stable-v1 M5 maturity status

As of the current bounded Bronze decision, all eight stable-v1 maturity
dimensions are at M5 and verified. The Bronze bounded qualification and M5
maturity gates pass. The overall stable-v1 contract remains blocked by two
separate gates: Australian health federation acceptance and explicit final
stable-release approval.

The Bronze report is [`quality/qualifications/bronze-maturity.json`](../../quality/qualifications/bronze-maturity.json).
It qualifies the hash-bound `bronze-bounded-public-scope-v1` horizon of 42
sources. The full 159-source public/no-credential catalogue universe remains
visible, with 117 sources retained in the
[future-source ledger](./bronze-bounded-scope-future-sources.md). Those sources
lack qualifying landing evidence; this is not negative medicines evidence and
does not grant acquisition or reuse rights. The narrower direct-receipt cohort
remains 29 sources, with 130 sources lacking a direct receipt, and is reported separately in the
[receipt cohort ledger](./bronze-future-source-list.md).

The scope basis is the maintainer-approved
[bounded-scope decision](../../quality/qualifications/bronze-bounded-scope-decision-v1.json).
The independent [`stable-v1-contract.json`](../../quality/qualifications/stable-v1-contract.json)
records the Bronze and M5 gates as passed while retaining the Australian
federation blocker and the human release-approval gate. A green M5 gate is not
a stable-release approval.

The machine-readable Bronze report records the exact source-code commit it
evaluated. Its report, bounded future-source ledger, and the stable-v1 contract
must be regenerated after any merge that changes their hashed inputs.

Current Bronze qualification source commit: `78e857839aad8298060c65eb5ef03a4e3114827a`.

## Current-main M5 reconciliation — 2026-10-17

The maturity model has eight blocking dimensions. Each is recorded at M5,
verified, and without blocker IDs in the current Stable v1 contract:

| Dimension | Current state | Qualification evidence |
| --- | --- | --- |
| Canonical evidence | M5 / verified | Independent canonical v1/v2 reproduction, deterministic migration and rollback, plus the Stable v1 evidence ledger. |
| Source coverage | M5 / verified | Bronze report: 42/42 approved bounded sources; the separate 159-source universe and its 117 deferred entries remain explicit. |
| Matching quality | M5 / verified | Independent fixture-process reproduction and the Stable v1 evidence ledger. |
| Provenance and rights | M5 / verified | Publication contracts, data licence policy, independent reproduction, and the Stable v1 evidence ledger. This does not grant rights for deferred sources. |
| Product accessibility | M5 / verified | Independent reproduction and the Stable v1 evidence ledger. |
| Security and supply chain | M5 / verified | Quality-hardening closure; Renovate output is observed. |
| Operations and recovery | M5 / verified | v0.8 operational evidence and independent synthetic restore/rollback rehearsal. Production disaster recovery is not qualified by that rehearsal. |
| Reproducibility and support | M5 / verified | Independent fixture-process reproduction, support documentation, and the Stable v1 evidence ledger. |

On the prior exact `main` commit
`7fe32a8830d9576ebcc4b431031d59e6809ef379`, the Bronze maturity generator
qualified the bounded horizon and reproduced the committed report's
substantive fields. The report is now rebound to that exact source commit. The
source-maturity catalogue projection regenerated identically, and the then
current direct-receipt cohort was 29 qualified / 128 without a direct receipt
(including 13 queue-landed sources). This paragraph preserves that exact-main
snapshot; the following catalogue refresh updates only current source identity
accounting.

### M-112 source identity catalogue refresh (2026-10-17)

The B0 catalogue now includes both already-reconciled MBS source identities:
demographics and group statistics. The exact 14-object approval still covers
only 10 demographics and 4 group-statistics objects; no broader rights or
source coverage is inferred. The catalogue has 176 source identities. The
bounded Bronze horizon remains 42/42, while the current 159-source public
universe has 117 deferred. The receipt-backed cohort is 29 sources with 130
lacking a direct receipt. M5 remains qualified on its bounded Bronze
contract; source rights, M-112 native lifecycle, and federation acceptance are
unchanged.
The regenerated Bronze maturity report evaluates the source commit recorded
in its current qualification. Its bounded-scope counts are 42 active sources,
159 public sources, 117 deferred, and 29 directly receipt-backed.

The current reconciled contract has 84 verified and 8 blocked requirements.
Within the Australian denominator, M-105 remains blocked under the current
maintainer disposition because required pre-archive parity evidence cannot be
established retroactively; M-106–M-112 also remain blocked. The prior D-006-10
chronology waiver remains historical and is not used for current acceptance.
Sixteen of 17 release gates pass, including
the conditional Stable v1 release-approval gate and the Bronze and M5 gates.
Australian health federation is the remaining unresolved qualification gate:

| Gate | Accountable party | State and exact acceptance evidence still needed |
| --- | --- | --- |
| Australian health federation | Dependent Australian workstreams; the sole maintainer for source-specific rights/admission decisions and federation acceptance; relevant source owners for external evidence | Blocked. The [acceptance matrix](./australian-health-federation-acceptance.md) lists M-105–M-112 individually: M-105 is blocked under D-006-12 because required pre-archive parity evidence cannot be established retroactively; M-106–M-112 remain blocked on their listed denominator, source, rights, semantic, lineage, product, and admission evidence. Future-source dispositions alone do not satisfy federation acceptance. |
| Stable v1 release | Sole maintainer | Conditional software-only `v1.0.0` promotion approval is recorded in D-006-11 and the release-approval gate has passed. Promotion remains unexecuted until all qualification gates pass and the exact candidate, protected checks, and attestation are verified. Australian federation remains blocked; no stable tag, signed asset, attestation, or release has been produced. |

Production disaster-recovery authority is separately recorded as
`not_claimed`, outside the Stable v1 acceptance-gate set. The existing local
synthetic restore evidence does not qualify production controls. Passing the
software support and operations dimensions does not assert independent
production backup storage, approved retention/deletion authority, RPO/RTO,
crash consistency, or a named recovery operator. A production authority
receipt would need to specify those controls and evidence a successful
independent restore.

## Current-main M5 reconciliation — 2026-10-23

On exact `main` commit `78e857839aad8298060c65eb5ef03a4e3114827a` (PR #1287),
the Bronze maturity generator re-qualified the bounded horizon and rebound the
committed report's provenance to that commit. The substantive qualification is
unchanged from the 2026-10-17 exact-main rebind and the 2026-10-18 contract
count reconciliation: 42/42 approved bounded sources,
a 159-source public/no-credential universe with 117 deferred entries, and the
separate 29-source direct-receipt cohort with 130 sources lacking a direct
receipt. No count in this refresh promotes a deferred source, grants rights or
turns a missing receipt into negative medicines evidence.

The bounded future-source ledger, the source-maturity catalogue projection and
the M5 Bronze refresh are unchanged. The current Stable v1 contract records 84
verified and 8 blocked requirements following the M-105 status reaffirmation in
D-006-12; eight of eight blocking dimensions remain at M5/verified, and 16 of
17 release gates remain passed. Australian health federation remains the
single unresolved qualification gate. The prior 85/7 requirement count
preserves the 2026-10-23 pre-reaffirmation snapshot and is not current. The
conditional D-006-11 software-only `v1.0.0` approval has not been exercised and
no stable tag, signed asset, attestation or release exists. Production
disaster-recovery authority remains separately `not_claimed` and outside the
Stable v1 acceptance-gate set.

Rebinding this page is enforced by
`tests/test_stable_v1_qualification_contract.py::test_stable_v1_status_page_matches_current_bronze_report_provenance`,
which fails until the page records the report's current source commit. That
acceptance test failed on the regenerated report before this page was rebound
and passed afterwards; the focused qualification selection then reported 280
passed.
