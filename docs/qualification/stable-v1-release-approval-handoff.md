# Stable-v1 release approval handoff

The accountable maintainer's approval of `v1.0.0rc1` was limited to the
software-only prerelease. On 2026-10-18, the maintainer separately approved a
conditional software-only `v1.0.0` promotion. The approval is recorded in
`quality/qualifications/stable-v1-promotion-approval-20261018.json`. It applies
only after every qualification gate passes and the exact candidate artifacts,
hosted checks, and attestation are verified. The Australian health federation
gate remains blocked, so the stable tag, signing, attestation, GitHub Release,
and external publication remain unperformed. The prerelease authority record
must remain unchanged.

## Readiness before the decision

When the dependent gates have independently passed, prepare a candidate bound
to one exact commit. Reconcile the requirement and maturity matrices, source
receipts, rights and licence scope, support and residual-risk registers, clean
consumer results, and protected hosted checks at that commit. Record the
proposed stable tag, exact artifact digests, signing or OIDC attestation method,
rollback/withdrawal procedure, and any remaining limitations in a new
candidate-specific handoff. A passing local build or the existing prerelease
is insufficient evidence for this decision.

The conditional promotion authorization already covers the software-only
`v1.0.0` tag when these readiness conditions pass. Bind the exact commit,
artifact digests, licence scope, and attestation method in the release
workflow; do not broaden the approved scope. This approval grants no
source-data publication, production deployment, or production
disaster-recovery authority. If the release scope changes, obtain a new
maintainer decision before promotion.

After the readiness conditions pass, produce the release through the protected
hosted workflow and read back the tag, release, attestations, digests, and clean
consumer result. Keep the approval gate passed once the conditional approval is
recorded, but keep Stable v1 qualification blocked until all independent gates
pass. Mark the release complete only when the exact approval scope and
independently observable publication receipts agree. If they differ, stop
promotion and use the withdrawal procedure.

## Current work ownership — 29 October 2026

This operational assignment does not change release approval or its conditions.
Earlier approvals and assignments above remain historical evidence.

- Chat: `01a10ee2-71a5-7c03-ae11-2ba1d2ebce11`,
  **Medicines Atlas — Release — Federation and native-field delivery**.
- Role: repository integrator for this approved no-new-sources completion lane;
  one writer for this checkout and the shared track/evidence changes in its PR.
- Actual checkout:
  `/Users/doughnut/.codex/worktrees/stable-v1-federation-gate/global-medicines-atlas`.
- Branch: `codex/bounded-native-field-delivery-20261029`, based on merged
  `d77d4ec53aa674d6231aaa59711751ba7f6fbb48` (PR #1368).
- Owned source paths: `src/global_medicines_atlas/{platinum_query.py,platinum_structure.py,platinum_v2_api.py,cli.py,atlas.py}`,
  `src/global_medicines_atlas/templates/atlas_federated_source_structure.html`,
  and the affected `test_platinum_query.py`, `test_platinum_structure.py` and
  `test_product_cli.py` tests. Owned evidence includes the exact PBS run's
  `quality/qualifications/pbs-independent-pipeline-builds-20261029/` receipts,
  its qualification documentation, and the Silver/Gold, data-plane and Platinum
  track append records in this scoped PR.
- Native scope: PBS qualification run `40700877242` is terminal success; retain
  and compare its receipts without redispatching. The new serialized candidate
  differs from the older exact rights-attested output. No publication,
  admission, new rights conclusion or real derived consumer success follows.
- Active local operation: Test-Goblin full profile, tool session `44577`,
  parent PID `81814`, Python PID `81821`, verified in the checkout above.
  Preserve that operation and its environment until terminal. Source byte pins
  are retained in `/tmp/gma-native-field-delivery-tested-source-20261029.json`;
  the log is `/tmp/gma-native-field-delivery-full-20261029.log`.
- Next operation: finish the review and focused malformed-selector correction,
  reconcile milestone evidence, preserve an exact scoped commit, and open one
  PR for protected checks. At a safe terminal checkpoint, reconcile the app's
  managed-worktree attachment without copying another checkout or moving native
  journals. Other chats must use separate worktrees and return terminal scoped
  evidence; they must not write these shared paths concurrently.

The primary checkout's existing dirty Bronze evidence and untracked skill
wrappers remain untouched. No hook, index, lock, environment, dependency,
runtime, authentication or submodule ownership is transferred by this entry.

### Ownership checkpoint

The `44577` full-profile operation reached terminal exit 1 after 9,412 passes,
four failures and four skips. Two failures were the Atlas keyboard-order test
expectations after adding the view selector; two were local performance-budget
measurements (`PERF-QUERY` and `PERF-EXPORT-PAGE`). The initial full-profile
source pins remain retained; the query source was subsequently changed for the
separately reproduced malformed-selector correction, and the keyboard test was
updated. Failure-only verification is owned by this chat and remains in flight.
Do not describe the earlier full run as a pass on the corrected source.

At the terminal checkpoint, two attempts to attach this exact existing worktree
with the app's managed-worktree tool returned `thread attachment identity count
exceeds 100`. No checkout or application state was reset or moved. Continue at
the explicit checkout path above using ordinary Git with hooks enabled; do not
claim successful app registration or remove existing attachments. This is an
attachment-limit result, not the separate non-Git-parent fallback case.

The single failure-only follow-up completed: both Atlas keyboard cases and one
release fixture passed. The other release fixture still exceeded its local
`PERF-QUERY` p95 budget (572.554 ms against 250 ms); the original run had also
observed 542.927 ms for that budget. The second original release failure was
`PERF-EXPORT-PAGE` at 1,112.131 ms against 1,000 ms. No threshold was changed
and no further local retry was made. Protected Linux checks remain pending for
the eventual PR. The earlier full profile stopped at coverage and did not
establish the subsequent full-profile stages on this local run.

### Offline research-package implementation lane

The same integrator chat `01a10ee2-71a5-7c03-ae11-2ba1d2ebce11` owns branch
`codex/offline-research-output-20261029` in the same explicit checkout. It is
stacked on `98e3c5c2ac0a91062879e17f20e7b01df4a666f9` while PR #1369 runs
protected checks. Owned source scope is the research export package, crate and
lineage contracts and their exact affected tests. The shared track and this
handoff remain under the same integrator; no other chat is assigned these paths.

Native scope is local synthetic package construction and verification only.
The next operation is to add a versioned local content-addressed output
reference and verify its exact sidecar digest while retaining the existing
public-URL contract. No source, credential, publication or other native write
is implied. The previous native-field assignment and its captured evidence
remain history above.

### Bounded software completion lane — 29 October 2026

The maintainer explicitly selected bounded software completion and deferred
unfinished Australian federation qualification. This changes scheduling only;
the conditional Stable v1 promotion and every blocked federation requirement
retain their existing conditions.

- Chat: `01a18773-f302-7e83-ba8c-816fcea9d3f1`,
  **Global Medicines Atlas — Completion — Simplify delivery**.
- Worktree:
  `/Users/doughnut/.codex/worktrees/gma-streamlined-completion/global-medicines-atlas`.
- Branch: `codex/streamlined-completion-20261029`, based on `fc8c41530`.
- Owned scope: this branch's contributor/agent workflow, roadmap and
  system-completion scheduling edits, plus the bounded software verification
  entry. No runtime, dependency, hook or submodule changes are assigned.
- Native scope: read-only inspection of existing PR/check state; local
  representative tests and clean package consumers. No data publication,
  admission, authentication renewal or release operation.
- Existing integrator `01a10ee2-71a5-7c03-ae11-2ba1d2ebce11` retains main,
  PR #1377 and PBS publication/admission scope. Its latest terminal chat turn
  reported the pending hosted gremlins job. This lane does not redispatch or
  duplicate its operations or change its checkout.
- Next operation: verify the bounded software packet, preserve one scoped
  commit and technical PR, and provide terminal evidence for integration.
  Historical track acceptance and previous assignments remain unchanged.

### Swiss/EMA bounded Bronze lane — 29 October 2026

Chat `01a18773-f302-7e83-ba8c-816fcea9d3f1`, **Global Medicines Atlas —
Bronze — Swiss and EMA downloads**, owns branch `codex/swiss-ema-bronze-batch`
in `/Users/doughnut/.codex/worktrees/gma-streamlined-completion/global-medicines-atlas`.
The prior software milestone is complete. The user authorized only this small
direct-download batch. Owned paths are its qualification document and receipt
folder, local `build/swiss-ema-bronze-20261029/` staging, and this scoped track
append. Native scope is public read-only discovery and one local EMA retrieval.
No other chat's native object or authentication scope is acquired. Next operation:
finish the preparation packet and pause for exact EMA publication approval;
Swiss remains explicitly blocked. No schedule or public dataset write is active.

### Shared URL configuration follow-up — 29 October 2026

The same chat and worktree, now titled **Global Medicines Atlas — Bronze —
Shared source downloads**, own the user-requested shared URL follow-up on
`codex/swiss-ema-bronze-batch`: `scripts/source_download_batch.py`, the generated
URL CSV/runbook, the exact EMA catalogue URL and derived B0/landing projections,
focused acquisition tests and this track receipt. The primary checkout and its
other writer remain untouched. Native scope is offline generation and synthetic
network tests; no additional live source acquisition, publication or schedule.
Next operation: finish the updated PR's protected CI and integrate this bounded
packet. Existing Swiss and EMA publication blockers retain their dispositions.

### EMA publication and next small batch — 30 October 2026

Chat `01a18773-f302-7e83-ba8c-816fcea9d3f1` owns the same managed worktree on
`codex/ema-publication-next-batch`, based on merged main `b84fabae`.
The maintainer now explicitly authorizes EMA publication and another small
straightforward source batch. Native write scope is only public dataset
`edithatogo/global-medicines-atlas-ema-bronze-20261029`, through Actions, with
unchanged approved EMA source bytes and exact three-file readback. The approved
payload is already retained in Actions run `40873191471`; its digest matches the
local candidate. Next-source acquisition is bounded to two Health Canada bulk
files after rights and reuse checks; no next-batch public write or schedule.
Swiss and federation are read-only blocker assessments. Other writers and native
scopes remain unchanged. Next operation: prepare the hosted exact-snapshot
publication and execute the shared download command for the bounded next batch.

### Archive-all execution — 30 October 2026

The same chat/worktree owns `codex/archive-all-execution`, based on merged
`a83c34a3`. EMA is public at `3aaa509d4b8d5b3f594caaeb0fab2ad99fec3c61`
(Actions `40927685330`, three anonymous digests verified). The maintainer now
requests archive-all execution, expressly approves the two Canadian files for
publication, and authorizes remaining straightforward-source batches. This lane
owns the shared batch runner, finite batch manifests, archive-all outcome ledger,
and hosted batch publisher. Native writes remain Actions-to-HF only, exact
approved inventories; no schedules, credentials, federation, Silver/Gold or
other writer's objects. Next: integrate reusable batch publication and publish
Canada first, then execute eligible remaining batches. Every catalogue ID must
receive an explicit outcome; blocked entries cannot count as archived.
