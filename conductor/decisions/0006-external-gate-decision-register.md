# External gate decision register

This register implements the decision-request contract in `conductor/autonomy.md`. Routine work continues autonomously; only authority or consequential gates interrupt execution.

## D-006-01 — Renovate App authorization

Decision: authorize the Renovate GitHub App for this repository.

**Recommended:** repository-scoped authorization. It enables the validated `renovate.json` and Dependency Dashboard without adding a second dependency-management system.

- **Option A — Recommended:** authorize repository-scoped Renovate. Contingency: verify the dashboard and first PR; revoke if scope or policy is wrong.
- **Option B:** authorize organization-wide Renovate. Contingency: record affected repositories and review estate-wide blast radius first.
- **Option C:** defer. Contingency: keep configuration validated but leave onboarding blocked.

## D-006-02 — OSF submission

**Status:** cancelled / deprecated (2026-08-19). OSF is not a live publication
identity. Historical registration `ej5nf` remains a superseded receipt. Do not
complete OSF licence resolution or OSF submission. Persistent protocol identity:
in-repo artefacts plus Zenodo DOI `10.5281/zenodo.21734811`.

Decision: do not submit or continue OSF registration work.

**Recommended:** cancel OSF as a current gate.

- **Option A — Recommended:** deprecate OSF and keep Zenodo plus in-repo protocol artefacts as the persistent path.
- **Option B:** retain OSF as a historical receipt only, with no further licence or submission work.
- **Option C:** was previously to submit the private draft; that option is withdrawn.

## D-006-03 — Source rights and redistribution

**Status:** public/no-credential path complete (Hugging Face catalogue revision
`b25af36da32ffa3ddc5d525f1c568459d23f6e11`, 85/96 sources archived). Credentialed
and restricted sources remain out of scope and are not an academic or OSF
blocker.

Decision: approve rights disposition per source for current payloads and derived outputs.

**Recommended:** treat the public/no-credential Hugging Face archive as the completed publication path for that class; keep credentialed/restricted sources out of scope.

- **Option A — Recommended:** public catalogue-only publication for no-credential sources. Contingency: do not attach restricted payloads.
- **Option B:** permit internal restricted processing without redistribution. Contingency: exclude payloads from HF and Zenodo.
- **Option C:** defer or reject bulk derived-data publication. Contingency: preserve catalogue metadata and fixtures; credentialed sources remain unpublished.

## D-006-04 — Stable release signing and attestation

**Status:** isolated remaining human gate. `v1.0.0rc1` is tagged and attested.
This is not a public stable v1 release. Do not invent credentials or cut a
stable release without maintainer approval.

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

**Status:** isolated remaining external gate. Fresh-clone software reproduction
and synthetic recovery rehearsal passed. Production DR that needs live
production systems or credentials is not executed and does not block academic
or OSF-deprecation work.

Decision: authorize a production DR rehearsal and accept its scope.

**Recommended:** approve a bounded rehearsal with explicit RPO/RTO, storage, retention, rollback, and notification authority.

- **Option A — Recommended:** execute and accept the bounded rehearsal. Contingency: quarantine and restore the last verified snapshot on failure.
- **Option B:** execute staging/synthetic rehearsal only. Contingency: keep production DR unqualified.
- **Option C:** defer. Contingency: retain synthetic local evidence only.

## Autonomous continuation

While decisions remain open, the agent may validate schemas, run tests, prepare receipts, reconcile documentation, and review hosted state. It must not install Apps, redistribute restricted data, sign or promote a public stable release, or claim production qualification without the relevant decision and durable evidence. OSF is deprecated and must not be treated as an open submission gate.
