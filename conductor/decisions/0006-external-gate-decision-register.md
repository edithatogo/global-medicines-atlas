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

**Status:** pending dependent technical qualification and then an explicit
maintainer decision. `v1.0.0rc1` is tagged and attested, but its authority is
prerelease-only. See the
[candidate handoff](../../docs/qualification/stable-v1-release-approval-handoff.md)
for the evidence and exact-commit binding required before requesting approval.

Decision: authorize signing/attestation of a stable release.

**Recommended:** require a maintainer-controlled signing key or approved OIDC attestation, exact commit binding, and independently verifiable receipts.

- **Option A — Recommended after technical gates pass:** approve the named
  commit, tag, software artifacts, licence scope, and attestation method;
  release through protected CI and withdraw if identity or provenance differs.
- **Option B:** defer approval pending more evidence; keep stable promotion
  blocked while qualification continues.
- **Option C:** decline stable promotion; retain the existing prerelease and
  do not publish a stable artifact.

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

## D-006-07 — M-105 donor chronology exception

**Status:** maintainer disposition recorded (2026-09-29). The complete donor
artifact parity inventory was reconciled after both compatibility repositories
were archived. That evidence cannot establish the requirement's original
pre-archive sequence.

Decision: acknowledge and document the chronology exception, keep M-105
blocked, and continue M-106–M-112 independently. This is not a waiver, does
not relabel post-archive evidence as pre-archive parity, and does not change
the M-105 acceptance criterion.

- **Option A — Recommended and selected:** preserve M-105 as blocked with an
  explicit chronology exception; continue independent federation evidence.
- **Option B:** waive or amend the sequence requirement and reconsider M-105
  only under a separately reviewed qualification change. Not selected.
- **Option C:** reopen further parity work. This cannot repair the historical
  ordering and was not selected.

## D-006-08 — M-106 rolling-series scope

**Status:** maintainer selected unchanged authorization scope (2026-09-29).
The official rolling 12-month page and its linked workbook filename disagree
on the ending period, and the rolling-series category is absent from the
current Australian MBS utilisation publication authorization.

Decision: keep the existing approved categories unchanged, do not acquire,
retain, or publish the rolling-series workbook, and wait for a corrected link
or substantive source-owner clarification before reconsidering source
qualification. M-106 remains blocked; the independent already-authorized
annual-series route remains governed by its existing authorization and
transport constraints.

- **Option A — Recommended and selected:** keep scope unchanged and await a
  corrected authorized link or agency clarification. Do not acquire or publish
  rolling-series data under the current approval.
- **Option B:** seek a separately approved authorization extension for the
  rolling-series category. Not selected; no scope extension is requested by
  this decision.
- **Option C:** treat the page's stated period as conclusive and acquire the
  linked file under the annual-series category. Not selected because the
  attachment period is unresolved and the category is not enumerated.

This decision is not a licensing conclusion, does not expand rights, and does
not establish any workbook contents, period denominator, or patient count.

## D-006-09 — Sweden Socialstyrelsen aggregate acquisition

**Status:** selected (2026-09-29). The maintainer approved source-generated
aggregate API result acquisition and internal retention under explicit query
caps. Person-level data, broad bulk downloads, public release, and external
publication remain excluded.

- **Selected:** acquire and retain only bounded aggregate API responses,
  preserving exact parameters, retrieval time, source version, digest, and
  attribution; enforce 70,000 cells and 100 ATC codes per query.
- Catalogue-only was not selected. This decision is not a project licensing
  conclusion and does not establish complete Swedish utilisation coverage.

See [the dated decision receipt](../../quality/qualifications/sweden-socialstyrelsen-acquisition-decision-20260929.json).

## Autonomous continuation

While decisions remain open, the agent may validate schemas, run tests, prepare receipts, reconcile documentation, and review hosted state. It must not install Apps, redistribute restricted data, sign or promote a public stable release, or claim production qualification without the relevant decision and durable evidence. OSF is deprecated and must not be treated as an open submission gate.
