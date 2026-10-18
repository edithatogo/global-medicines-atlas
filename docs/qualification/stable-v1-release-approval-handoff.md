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
