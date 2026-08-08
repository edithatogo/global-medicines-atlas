# External-gate execution plan

Status: ready for autonomous execution up to explicit authority gates.

This plan addresses the remaining open issues without treating local tests,
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

## Phase 2 — OSF final preview and submission (#70)

Entry criteria: private draft `6a6dca79265e7ef20ac266e1` has all 16 required
response keys and 17 total responses.

1. Use the authenticated `osf-cli` bearer-token session already available from
   the surrounding project environment. Inspect identity only; never print,
   persist, or commit token values.
2. Perform a final visual/semantic preview of title, scope, ethics wording,
   foreknowledge, study type, blinding, data management, citations, and
   attached package digest.
3. Present the maintainer with one decision: approve submission, request
   revisions, or defer pending institutional confirmation.
4. Only after explicit approval, submit the draft through the OSF CLI/API.
5. Verify the resulting registration identifier, public/embargo state, landing
   page, package digest, and API receipt.
6. Update issue #70, `external-publication-receipt.md`, the publication identity
   registry, and the academic Conductor evidence.

Stop condition: no submission, public release, embargo change, or source-derived
dataset attachment without explicit approval and a durable receipt.

## Phase 3 — Source rights and live qualification (#50, #51, #54)

For each source, execute independently:

1. Identify authoritative API/bulk endpoint and terms/licence.
2. Record access mode, retrieval timestamp, jurisdiction, schema fingerprint,
   checksum, and coverage denominator.
3. Obtain a rights/redistribution decision before retaining or publishing data.
4. Run adapter parity and fixture-to-live comparison without conflating
   regulatory approval with funding/formulary status.
5. Append a source receipt or an explicit blocked receipt.

Initial order: NZULM/NZMT, PBS, Drugs@FDA, EMA, PMDA, NHS dm+d, and Canadian
DPD. Restricted or unclear sources remain catalogue-only.

## Phase 4 — Product and release gates (#40, #43, #61)

1. Reproduce the release from the canonical remote commit.
2. Obtain signing and attestation evidence; unsigned artifacts remain
   prerelease-only.
3. Obtain production deployment, health/readiness, live provenance, browser
   accessibility, and responsive-interaction receipts.
4. Execute an authority-approved production DR rehearsal with RPO/RTO evidence.
5. Record post-release monitoring observations before stable promotion.

## Governance and sequencing

The order is Renovate verification, OSF preview, source-rights qualification,
then deployment/release promotion. Local implementation and validation may
continue in parallel. External publication, rights, signing, deployment, and
institutional ethics decisions are never inferred from CI or credentials.

## Decision register

The detailed option, contingency, rationale, and recommendation register is
maintained in
[`conductor/decisions/0006-external-gate-decision-register.md`](../../conductor/decisions/0006-external-gate-decision-register.md).

The source-derived dataset batch decision and source-level approval matrix is
maintained in
[`conductor/decisions/0008-source-derived-dataset-licensing-batch.md`](../../conductor/decisions/0008-source-derived-dataset-licensing-batch.md).

The only immediate maintainer decisions are:

- authorize Renovate App installation, if the App is absent;
- approve, revise, or defer OSF submission after preview;
- approve source-specific redistribution licences where required; and
- approve signed release and production qualification evidence.

Each decision must identify its scope, authority, date, affected artefacts, and
receipt location.
