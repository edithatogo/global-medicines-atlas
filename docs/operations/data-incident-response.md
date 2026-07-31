# Data incident response

## Scope and reporting boundary

Use the public data-incident form for incorrect, stale, misleading, incomplete,
or insufficiently evidenced medicine data that contains no confidential
information. Report exploitable integrity vulnerabilities, credentials,
private source material, or sensitive data through the private process in
[SECURITY.md](../../SECURITY.md).

## Severity

- P0: credible patient-safety, confidentiality, or active compromise risk;
  stop affected publication and use private security coordination.
- P1: materially false regulatory, funding, identity, provenance, or current
  status claim in a released or served artifact.
- P2: bounded stale, incomplete, conflicting, or transformation defect with no
  demonstrated consequential use.
- P3: documentation, metadata, or presentation defect that does not alter the
  underlying evidence.

## Response procedure

1. Preserve the report, affected release/snapshot identifiers, jurisdiction,
   source receipts, valid time, observed time, and reproduction evidence.
2. Classify severity and route private security material away from public
   issues.
3. Contain by blocking promotion, quarantining suspect inputs, and identifying
   every derived artifact bound to the affected digest.
4. Correct through reviewed source reacquisition, parser/adapter repair,
   reprocessing, and deterministic regeneration; never overwrite provenance.
5. Validate regression tests, evidence dimensions, temporal state, coverage,
   and consumer-visible outputs.
6. Notify affected consumers or external services only with maintainer
   authority and an evidence-backed scope statement.
7. Close with root cause, affected identities, corrective commits, regenerated
   artifact digests, validation receipts, residual limitations, and follow-up
   prevention work.

## Recovery and closure evidence

Use the [governed recovery runbook](governed-recovery-runbook.md) when a local
canonical artifact set must be restored. A closed incident must retain enough
evidence to reproduce the defect and verify the corrected state without
retaining prohibited or confidential payloads.
