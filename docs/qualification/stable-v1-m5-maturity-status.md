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
remains 28 sources and is reported separately in the
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

The current maturity projection evaluates exact merged `main` commit
`5f61bf7fb874a07e6294a38a9f2160be5c789735`.
