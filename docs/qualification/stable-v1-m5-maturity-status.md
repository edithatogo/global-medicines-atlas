# Stable-v1 M5 maturity status

As of the current bounded Bronze decision, all eight stable-v1 maturity
dimensions are at M5 and verified. The Bronze bounded qualification and M5
maturity gates pass. The overall stable-v1 contract remains blocked by two
separate gates: Australian health federation acceptance and explicit final
stable-release approval.

The Bronze report is [`quality/qualifications/bronze-maturity.json`](../../quality/qualifications/bronze-maturity.json).
It qualifies the hash-bound `bronze-bounded-public-scope-v1` horizon of 42
sources. The full 157-source public/no-credential catalogue universe remains
visible, with 115 sources retained in the
[future-source ledger](./bronze-bounded-scope-future-sources.md). Those sources
lack qualifying landing evidence; this is not negative medicines evidence and
does not grant acquisition or reuse rights. The narrower direct-receipt cohort
remains 29 sources and is reported separately in the
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

## Current-main M5 reconciliation — 2026-10-05

The maturity model has eight blocking dimensions. Each is recorded at M5,
verified, and without blocker IDs in the current Stable v1 contract:

| Dimension | Current state | Qualification evidence |
| --- | --- | --- |
| Canonical evidence | M5 / verified | Independent canonical v1/v2 reproduction, deterministic migration and rollback, plus the Stable v1 evidence ledger. |
| Source coverage | M5 / verified | Current-main Bronze report: 42/42 approved bounded sources; the separate 157-source universe and its 115 deferred entries remain explicit. |
| Matching quality | M5 / verified | Independent fixture-process reproduction and the Stable v1 evidence ledger. |
| Provenance and rights | M5 / verified | Publication contracts, data licence policy, independent reproduction, and the Stable v1 evidence ledger. This does not grant rights for deferred sources. |
| Product accessibility | M5 / verified | Independent reproduction and the Stable v1 evidence ledger. |
| Security and supply chain | M5 / verified | Quality-hardening closure; Renovate output is observed. |
| Operations and recovery | M5 / verified | v0.8 operational evidence and independent synthetic restore/rollback rehearsal. Production disaster recovery is not qualified by that rehearsal. |
| Reproducibility and support | M5 / verified | Independent fixture-process reproduction, support documentation, and the Stable v1 evidence ledger. |

On exact `main` commit
`f160a0235c66c425150f90b4cdc6ea3d55365b5b`, the Bronze maturity generator
qualified the bounded horizon and reproduced the committed report's
substantive fields. The report is now rebound to that exact source commit. The
source-maturity catalogue projection regenerated identically, the direct
receipt cohort remains 29 qualified / 128 without a direct receipt (including
13 queue-landed sources), and the Stable v1 contract reconciliation was
idempotent. The full-universe gap remains 115 sources; no evidence here turns
those gaps into negative medicines evidence.

The contract has 84 verified requirements and eight blocked Australian
requirements (M-105–M-112). Fifteen of 17 release gates pass, including the
Bronze and M5 gates. The two unresolved acceptance gates remain:

| Gate | Accountable party | State and exact acceptance evidence still needed |
| --- | --- | --- |
| Australian health federation | Dependent Australian workstreams; the sole maintainer for source-specific rights/admission decisions and federation acceptance; relevant source owners for external evidence | Blocked. The [acceptance matrix](./australian-health-federation-acceptance.md) lists M-105–M-112 individually. It records the M-105 donor-parity chronology exception without waiver; outstanding distinct-participant evidence and source-owner/rights clarification for M-106; unavailable Health.gov historical workbooks for M-107; pinned public derived products for M-108; source-era semantics for M-109; qualified Gold evidence graphs for M-110; pinned API/CLI/atlas/export canaries for M-111; and for M-112 the exact-denominator per-object rights and B1/B2 lineage, anonymous digest readback, v4 admission, and consumer canaries. Future-source dispositions alone do not satisfy acceptance. |
| Stable v1 release approval | Sole maintainer | Blocked. The evidence must include explicit approval for the final `1.0.0` stable promotion. Current `v1.0.0rc1` authority is prerelease-only; no stable-release approval or signed stable asset is recorded. |

Production disaster-recovery authority is separately recorded as
`not_claimed`, outside the Stable v1 acceptance-gate set. The existing local
synthetic restore evidence does not qualify production controls. Passing the
software support and operations dimensions does not assert independent
production backup storage, approved retention/deletion authority, RPO/RTO,
crash consistency, or a named recovery operator. A production authority
receipt would need to specify those controls and evidence a successful
independent restore.
