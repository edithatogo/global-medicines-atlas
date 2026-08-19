# External blocker resolution plan

Status: OSF cancelled; public/no-credential Hugging Face archive complete.

## Credential boundary

Do not use OSF credentials. OSF is deprecated. Never copy, print, commit, or
persist token values for any remaining gated service.

## Sequence

1. **OSF (cancelled)**
   - Do not complete OSF draft, licence, or submission work.
   - Historical registration `ej5nf` is superseded.
   - Persistent identity: in-repo protocol plus Zenodo `10.5281/zenodo.21734811`.

2. **Public/no-credential publication path (complete)**
   - Hugging Face catalogue revision
     `b25af36da32ffa3ddc5d525f1c568459d23f6e11` archived 85/96 sources.
   - Credentialed/restricted sources remain out of scope.

3. **Hosted maintenance gates (read-only or App-authorized)**
   - Verify Renovate App installation and Dependency Dashboard issue using the
     repository API; retain the local Renovate configuration as canonical.
   - Reconcile stable-v1 issue #40/#43 and close only evidence-backed child
     tasks. Do not treat green CI as stable-release promotion.

4. **Isolated remaining gates**
   - Stable-v1 promotion approval for a public stable release.
   - Production DR authority against live production systems.
   - Fresh-clone software reproduction already passed.

## Blocker policy

Unsigned stable promotion, unavailable production DR authority, or restricted
source bytes keep those isolated gates blocked. OSF and public/no-credential
derived-data archival are no longer open academic blockers. Safe local
validation and documentation continue in parallel; no gate is cleared by
inference.
