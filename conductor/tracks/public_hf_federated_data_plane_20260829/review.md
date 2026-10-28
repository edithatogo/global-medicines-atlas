
# Review Report: exact PBS utilisation raw-B2 replay (2026-10-28)

## Summary

The scoped replay extension is ready for protected CI; hosted replay and the
whole federation track remain incomplete. Review was by the implementing agent.

## Verification Checks

- [x] **Plan Compliance**: the exact six frozen PBS objects can now produce
  metadata-only v3 registration plans using existing rights, publication,
  anonymous verification and B1/B2 evidence. No admission is inferred.
- [x] **Style Compliance**: Ruff, formatting, ty and BasedPyright passed.
- [x] **New Tests**: 22 PBS planning/executor cases cover exact scope, evidence
  and lifecycle tampering, forged plans, revision/path rejection, and cleanup.
- [x] **Test Coverage**: unchanged MBS planning/executor checks and 133 broader
  v4 publication/admission, harness and context checks passed. This is bounded
  automated qualification, not actual hosted download evidence.
- [x] **Test Results**: focused checks passed; existing MBS plan bytes and the
  retained PBS plan reproduce exactly. Context and ecosystem validation passed.

## Findings and fixes

The first PBS out-of-scope message broke the existing raw-B2 error contract;
its corrected message passed both existing and PBS checks. A synthetic I/O
callback lacked a typed Path parameter; it now passes formal typing. No
remaining findings were identified in this increment. Exact-target evidence
is reconstructed before download, and current rights attestation is kept
separate from the original acquisition's unknown rights state.

Full-track acceptance and archival remain pending the existing M-105–M-112
requirements; no scope or acceptance criterion was changed by this review.

Final lint found one intended regex alternation needing a raw string literal.
It was corrected before push; all affected-file lint/format checks, the two
locator tests, and context validation then passed.

## PR #1361 hosted leak-detection correction

The redacted hosted finding is the deterministic PBS replay identity. Its exact
field/value exception is independently recomputed by the harness; changed
values and API-key fields stay detected. Gitleaks 8.30.1 passed the complete
base/head history with the revised configuration and the native API-key
negative control remained detected. Three focused controls and 68 harness
tests passed. Formal typing exposed a pre-existing overly broad command-list
annotation in the affected test module; its minimal correction passed the
affected node, ty and BasedPyright. New hosted qualification remains pending.
