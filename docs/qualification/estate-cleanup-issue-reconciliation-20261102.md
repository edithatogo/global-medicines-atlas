# Repository estate and issue reconciliation — 2 November 2026

The maintainer authorized retirement of reconciled branches and worktrees,
preservation of unique work, closure of completed issues and continued bounded
implementation. This batch addresses repository maintenance and governance;
it grants no dataset publication, rights, clinical or stable-release authority.

The [machine-readable reconciliation](../../quality/qualifications/estate-cleanup-issue-reconciliation-20261102.json)
records all 15 issue dispositions and the additional seven tip comparisons.
The prior 100-tip audit and recovered work remain integrated through PR #1393.

## Preservation and cleanup

A complete Git bundle was verified before deletion. All five dirty lanes have
binary working/index patches, an index copy, exact changed/untracked source
files and SHA-256 manifests in the local recovery directory. The primary lane
also has an ordinary path-scoped Git stash. No restricted payload, credential,
private native binding or in-flight native operation was moved or published.

Retired 41 worktree directories and five missing registrations. Deleted 648
local refs and 32 remote branches using frozen-tip evidence and exact remote
leases. The initial 648 local refs grew by the maintenance branch and the
preservation name for stale local main; two active refs remained after cleanup.
Local main's divergent commit was a byte-equivalent patch to merged PR #564.
The primary checkout now follows current main and is clean. Temporary active
repair worktrees are retired after their PRs merge.

The verified recovery bundle is local at
`/Volumes/PortableSSD/GMA-recovery/reconciled-estate-20261102/retired-estate.bundle`.
Its SHA-256 is
`394f6554a9fc87e34d3a730bc6a5926d6f82380c392495a6b47149f72b3fa934`.
Original dirty files and all prior stashes remain recoverable there.

## Issue decisions

| Issues | Disposition |
| --- | --- |
| #81, #82 | Close with integration: required repository hardening is evidenced; child #80 was already closed. |
| #14 | Close only after Renovate patch PR #1394 passes protected CI and merges. |
| #491 | Retain the standing dependency dashboard. |
| #339–#342 | Retain incomplete donor parity, semantics, federation/admission, recovery and live consumer requirements. |
| #170 | Retain original landing scope beyond the qualified 42-source horizon. |
| #51, #54, #61 | Retain source rights/access and external production qualification gates. |
| #40, #43, #44 | Retain incomplete stable-release and programme acceptance. |

Repository merge methods now conform to the existing squash-only contract.
The active deletion/force-push ruleset and strict protected checks remain in
place, with zero required human approvals. Renovate's current dashboard and
PR #1394 verify that the hosted app is active. Codecov's real OIDC workflow and
protected commit statuses remain intact; no competing Dependabot workflow
remains.

The [fresh governance receipt](../../quality/qualifications/hosted-governance-reconciliation-20261102.json)
verifies repository controls while reporting project metadata as unavailable
under the retained CLI profile's missing `read:project` scope. The historical
snapshot remains immutable for its existing regression tests. No authentication
scope was expanded, and partial governance is not stable-release acceptance.

A regression first reproduced the collector's incorrect classification of
`INSUFFICIENT_SCOPES`. The fix classifies only homogeneous access denials as
permission-unavailable; mixed operational errors still fail. The six focused
regression cases are included in 83 passing governance/domain/experiment checks. Renovate's
first patch PR exposed a stale deterministic monitoring digest; regenerating
its existing receipt repairs that failure, with all 12 monitoring tests passing.

The dated local coordination assignment is chat
`01a19600-56dd-73a2-9ff5-4a2484a54493`, working in
`/Volumes/PortableSSD/GitHub/.codex-worktrees/pbs-hosted-publication-20261029`.
It owns this maintenance packet, the bounded governance diagnostic fix and
integration of PR #1394. The introducing PR, native readbacks and retained
receipts provide the durable audit identity. Prior assignments remain history.

Maintenance PR #1395 merged at `fb67be2c8b97745be8ac1f25c93e07bdc5b66f1f` after 39 passing checks
and one optional manual skip, closing #81/#82. Dependency PR #1394 carries
this final receipt with its substantive action update; no receipt-only
successor PR is required. Its protected merge closes activation issue #14.
