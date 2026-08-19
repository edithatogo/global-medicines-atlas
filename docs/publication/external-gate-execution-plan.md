# External-gate execution plan

Status: OSF cancelled; public/no-credential Hugging Face archive complete;
remaining isolated gates are stable-v1 promotion and production DR authority.

This plan addresses remaining open issues without treating local tests,
configuration, or credentials as evidence of hosted authorization.

## Phase 1 — Renovate onboarding (#14)

Entry criteria: `renovate.json` validates, `main` is protected, and no open
Renovate PR or Dependency Dashboard is visible.

1. Verify the GitHub Renovate App installation at the owner/repository scope.
2. If absent, obtain maintainer authorization to install or authorize the App.
3. Verify the first Dependency Dashboard issue and its repository association.
4. Verify the first Renovate PR, its checks, automerge policy, and update type.
5. Record App installation, dashboard issue, PR, and hosted-check URLs in the
   issue and external qualification register.

Stop condition: do not add Dependabot, weaken branch protection, or claim
Renovate activation from the local configuration alone.

## Phase 2 — OSF (deprecated)

OSF is deprecated. Do not complete OSF licence resolution or OSF submission.
Historical registration `ej5nf` is a superseded receipt. Persistent protocol
identity: in-repo artefacts plus Zenodo DOI `10.5281/zenodo.21734811`. Close
issue #70 as cancelled/deprecated.

## Phase 3 — Source rights and live qualification (#50, #51, #54)

The public/no-credential Hugging Face catalogue archive is the completed
publication path for that class (PR #173, revision
`b25af36da32ffa3ddc5d525f1c568459d23f6e11`; 85/96 sources archived).
Credentialed and restricted sources remain out of scope: NZULM, AMT, PBS
embargo, dm+d/TRUD, EMA PMS, SPOR, and the other skipped sources listed in
`docs/publication/data-layer-archive-receipt.md`.

Live payload qualification for credentialed sources remains a separate
operational track and is not an academic-protocol blocker.

## Phase 4 — Product and release gates (#40, #43, #61)

Isolated remaining gates:

1. Stable-v1 promotion approval. `v1.0.0rc1` is tagged and attested. Do not
   invent a public stable release.
2. Production disaster-recovery authority for live production systems.
   Fresh-clone software reproduction already passed.

## Governance and sequencing

The order is Renovate verification, then isolated release/DR gates. OSF is not
in the sequence. Local implementation and validation may continue in parallel.
External publication of restricted bytes, signing a stable release, and
production DR authority are never inferred from CI.

## Decision register

The detailed option, contingency, rationale, and recommendation register is
maintained in
[`conductor/decisions/0006-external-gate-decision-register.md`](../../conductor/decisions/0006-external-gate-decision-register.md).

The only immediate remaining maintainer decisions are:

- authorize Renovate App installation, if the App is absent;
- approve a public stable release distinct from `v1.0.0rc1`; and
- authorize production disaster-recovery rehearsal against live systems.

Each decision must identify its scope, authority, date, affected artefacts, and
receipt location.
