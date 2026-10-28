
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
affected node and ty. Full-file BasedPyright retains 195 inherited diagnostics
versus 196 on the prior head, with zero new diagnostics. It is not a full-file
formal-typing pass. New hosted qualification remains pending.
# Review Report: exact PBS utilisation v1 conformance (2026-10-28)

## Summary

The six-object v1 candidate manifest is locally qualified and ready for a scoped
follow-up after PR #1361; durable readback and v4 admission remain pending.
Review was by the implementing agent and supplies no independent approval.

## Verification Checks

- [x] **Plan Compliance**: the shared v1 emitter accepts the exact six PBS
  identities validated by the existing metadata-only PBS evidence join.
- [x] **Style Compliance**: Ruff, formatting, ty and BasedPyright passed.
- [x] **New Tests**: five cases cover the exact PBS manifest, MBS rights
  isolation, unbound targets, unknown cohorts and partial denominators.
- [x] **Test Coverage**: 33 focused conformance/replay cases and 54 broader
  medallion, v4 role and context cases passed.
- [x] **Test Results**: six-object PBS and sixteen-object MBS CLI regeneration
  checks passed. The original MBS manifest is byte-identical.

## Findings and fixes

Review identified that the PBS manifest needed an explicit six-member count
check before construction. It was added with a partial-cohort regression.
The separate PBS rights mapping does not widen the default MBS policy. No
remaining scoped findings were identified. Every promotion remains blocked;
full-track acceptance and archival remain incomplete.

## PBS discovery-role readback review

The anonymous metadata route was qualified through installed CLI help and an
exact-target read. The pinned PBS dataset, public collection membership and
checksum-bound registry entry match the six retained identities. An initial
extractor used `entries`; the catalog's actual `datasets` key was then used and
the bounded read passed. The report hashes CLI JSON output rather than claiming
those hashes are raw HTTP response digests. The `not_assessed` registry state is
preserved and no rights or sensitivity conclusion is inferred. Native Gitleaks
8.30.1 checks passed for both new PBS conformance/discovery metadata artifacts.
This is a candidate role observation; complete-contract binding is still open.
