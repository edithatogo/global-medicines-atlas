# Stable-v1 release approval handoff

The accountable maintainer's approval of `v1.0.0rc1` was limited to the
software-only prerelease. It does not authorize a stable tag, signing,
attestation, GitHub Release, or another external publication. The stable-v1
contract currently has three dependent technical gates open: Australian health
federation, current-scope Bronze, and M5 maturity. The final stable-release
approval is a fourth, separate human gate. The prerelease authority record
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

Only then ask the maintainer one decision: whether to authorize **that exact
stable software release**. Offer (1) approve the named commit, tag, artifacts,
licence scope and attestation method; (2) defer pending further evidence; or
(3) decline stable promotion and keep the prerelease. Approval of software
does not grant source-data publication, production deployment, or production
disaster-recovery authority. Record the maintainer's explicit answer and its
source before changing the release-approval gate.

After approval, produce the release through the protected hosted workflow and
read back the tag, release, attestations, digests, and clean consumer result.
Mark the gate passed only when both the exact approval and independently
observable publication receipts agree. If they differ, stop promotion and use
the withdrawal procedure.
