# Source monitoring and release evidence

## Trusted monitor history

The scheduled source-health workflow compares a report only with the newest
successful run of the designated source-health workflow on `main`. The
downloaded report must have a companion provenance record binding repository,
workflow path, branch, successful conclusion, run and commit identities,
monotonic observation identity, and the report SHA-256 digest. A mismatch
fails closed instead of silently accepting an unrelated artifact.

Source probes are metadata-only and bounded. Offline, denied, malformed, and
rate-limited sources become explicit unavailable observations. A health probe
does not infer medicine approval, funding, completeness, or source currency.
HTTP 429 responses are not retried by the scheduled observation: this avoids
amplifying regulator load, and a later scheduled run supplies bounded recovery.
Escalation receipts retain deterministic deduplication and consecutive-failure
state without retaining response payloads.

Hosted qualification remains necessary: the local contract cannot prove that
the scheduled workflow ran successfully, that the artifact is retained, or
that GitHub escalation and repository settings are active.

## Qualification versus approved release provenance

Manual workflow runs default to dry-run mode. Dry runs upload an artifact named
`dry-run-qualification-evidence-*`; they have neither attestation permission
nor release permission and are not release evidence.

Publication requests build and qualify an immutable candidate set first. The
protected `release-publication` job downloads that exact set, verifies every
entry in `SHA256SUMS`, and verifies the SHA-256 identity of `SHA256SUMS`
against the qualification-job output. Only after the protected environment
gate does the job receive keyless-attestation and release permissions. It then
attests the verified bytes and creates a draft release from the same files.

This checkout cannot prove environment reviewers, successful hosted
attestation, or draft-release creation. Those remain dated external gates.
