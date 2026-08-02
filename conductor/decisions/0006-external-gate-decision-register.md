# External gate decision register

This register implements the decision-request contract in `conductor/autonomy.md`. Routine work continues autonomously; only authority or consequential gates interrupt execution.

## D-006-01 — Renovate App authorization

Decision: authorize the Renovate GitHub App for this repository.

**Recommended:** repository-scoped authorization. It enables the validated `renovate.json` and Dependency Dashboard without adding a second dependency-management system.

- **Option A — Recommended:** authorize repository-scoped Renovate. Contingency: verify the dashboard and first PR; revoke if scope or policy is wrong.
- **Option B:** authorize organization-wide Renovate. Contingency: record affected repositories and review estate-wide blast radius first.
- **Option C:** defer. Contingency: keep configuration validated but leave onboarding blocked.

## D-006-02 — OSF submission

Decision: submit the completed private OSF draft.

**Recommended:** approve submission after visual review; all required fields are populated, but submission creates a durable external record.

- **Option A — Recommended:** approve submission. Contingency: keep public or embargo state unchanged until the receipt is verified.
- **Option B:** request wording or ethics revisions. Contingency: revise the private draft and rerun schema validation.
- **Option C:** defer pending institutional confirmation. Contingency: retain the private draft and continue non-OSF work.

## D-006-03 — Source rights and redistribution

Decision: approve rights disposition per source for current payloads and derived outputs.

**Recommended:** approve only source-specific, evidence-backed dispositions; unclear sources remain catalogue-only.

- **Option A — Recommended:** approve rights-cleared sources individually. Contingency: acquire, checksum, and publish only the approved scope.
- **Option B:** permit internal restricted processing without redistribution. Contingency: exclude payloads from HF, Zenodo, and OSF.
- **Option C:** defer or reject. Contingency: preserve catalogue metadata and fixtures; live qualification remains blocked.

## D-006-04 — Stable release signing and attestation

Decision: authorize signing/attestation of a stable release.

**Recommended:** require a maintainer-controlled signing key or approved OIDC attestation, exact commit binding, and independently verifiable receipts.

- **Option A — Recommended:** sign and attest the qualified commit. Contingency: revoke or withdraw if digest or provenance differs.
- **Option B:** publish unsigned prerelease only. Contingency: keep stable promotion blocked and label artifacts prerelease.
- **Option C:** defer release. Contingency: continue qualification without publication claims.

## D-006-05 — Production deployment and accessibility

Decision: authorize a production deployment qualification window.

**Recommended:** use an isolated deployment with public health/readiness, live provenance, and browser accessibility receipts.

- **Option A — Recommended:** qualify the intended production deployment. Contingency: roll back to the last qualified artifact on failed checks.
- **Option B:** qualify staging only. Contingency: keep production claims and stable promotion blocked.
- **Option C:** defer deployment. Contingency: maintain local/API qualification.

## D-006-06 — Production disaster recovery

Decision: authorize a production DR rehearsal and accept its scope.

**Recommended:** approve a bounded rehearsal with explicit RPO/RTO, storage, retention, rollback, and notification authority.

- **Option A — Recommended:** execute and accept the bounded rehearsal. Contingency: quarantine and restore the last verified snapshot on failure.
- **Option B:** execute staging/synthetic rehearsal only. Contingency: keep production DR unqualified.
- **Option C:** defer. Contingency: retain synthetic local evidence only.

## Autonomous continuation

While decisions remain open, the agent may validate schemas, run tests, prepare receipts, reconcile documentation, and review hosted state. It must not install Apps, submit OSF registrations, redistribute restricted data, sign or promote releases, or claim production qualification without the relevant decision and durable evidence.
