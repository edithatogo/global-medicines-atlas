
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

## Six hosted PBS replay receipt review

All six exact-main native runs and jobs passed once. Receipt scope, byte count,
SHA-256, producer identity, plan digest, snapshot/partition IDs, registration
hash and cleanup flags were checked against retained exact-source evidence.
Their artifact IDs and native verification-step times are bound in the final
manifest; transient dispatch journal fields are not used as completion proof.
No source payload values were retained or interpreted.

The follow-up reuses the shared v1 emitter with an isolated PBS rights basis.
All artifacts remain candidates and promotions remain blocked. Its integrated
source state passes 101 focused tests, Ruff, ty, BasedPyright for the v1 module
and its tests, and unchanged six-object PBS/sixteen-object MBS regeneration.
The harness test module retains 195 inherited formal-typing diagnostics against
195 on main, with zero new diagnostics; this is differential evidence only.
Nine new metadata artifacts pass native Gitleaks checks, and a synthetic
credential-field control remains detected under the exact digest exceptions.
Complete-history security and protected CI are tracked against the final PR.

Review was by the implementing agent. No remaining scoped findings were
identified; full federation acceptance and track archival remain incomplete.

# Review Report: PBS raw-B2 role readiness (2026-10-28)

## Summary

The metadata-only assessment resolves a superseded screening flag and identifies
actual remaining contract work; it supplies no admission or independent approval.

## Verification Checks

- [x] **Plan Compliance**: six exact frozen objects are joined across retained
  source-specific screening, identity, rights, v1, v3 and discovery evidence.
- [x] **Style Compliance**: additive JSON evidence and Markdown documentation.
- [x] **New Tests**: none; no production or test behavior changed.
- [x] **Test Coverage**: unchanged replay and conformance checks are reused;
  exact identities, input digests, native replay receipt digests and boundaries
  are independently checked for this metadata increment.
- [x] **Test Results**: 33 focused conformance/replay tests passed; context,
  ecosystem, exact-input digest/identity checks and native Gitleaks passed.

## Findings and fixes

Review found that a generic historical `review_required` screen was being
considered without its existing exact header-context successor. The report
binds both, preserving the old screen and documenting the aggregate-field
assessment. Current publisher descriptions provide family context only, because
current download sizes differ. Source-profile sensitivity is separate from
rights and does not claim exhaustive personal-data absence. All v4 contracts,
receipt closure, admission, consumer canaries and independent recovery remain
explicitly incomplete. Review was by the implementing agent.

# Review Report: PBS v4 contract instances and receipt closure (2026-10-28)

## Summary

Six exact configuration candidates pass schema, semantics and actual opaque
receipt closure; producer trust, admission and consumers remain incomplete.

## Verification Checks

- [x] **Plan Compliance**: existing raw-B2 roles are assembled without adding
  sources or implying domain semantics, independent recovery or admission.
- [x] **Style Compliance**: canonical JSON and scoped documentation.
- [x] **New Tests**: none; existing validators exercise these configurations.
- [x] **Test Coverage**: six canonical/identity/closure checks, six rights-subject
  negative controls, and native authority-schema readback match.
- [x] **Test Results**: 53 existing receipt-closure/admission tests passed;
  native Gitleaks passed. Context/ecosystem checks are run before commit.

## Findings and fixes

Initial schema validation rejected a collection slug where the schema requires
its full HTTPS URL. The configurations use the full observed collection URL.
Review also separated the newer object-verification timestamp and receipt from
the historical publication/primary-restore receipt. All six exact configurations
then validated and their real anonymous receipt reads passed. No opaque receipt
content was retained. Review was by the implementing agent; no independent
human or production approval is invented. Full-track archival remains unsafe.

# Review Report: exact PBS admission and reader runner (2026-10-28)

## Summary

The bounded runner prepares real exact-main admission and raw reader execution;
actual hosted qualification and whole-track acceptance remain incomplete.

## Verification Checks

- [x] **Plan Compliance**: six explicit existing objects only; independent trust
  derives from fixed source evidence rather than candidate claims.
- [x] **Style Compliance**: changed qualifier and tests pass Ruff and formatting.
- [x] **New Tests**: exact-six profiles, digest and scope rejection, independent
  trust mismatch, corrupted/oversized remote receipts, local refusal, missing
  attempt, actual CLI check and metadata-only CLI report behavior are covered.
- [x] **Test Coverage**: 167 focused/broader affected checks passed before three
  CLI/schema controls were added; the final qualifier selection has 27 passes.
- [~] **Test Results**: focused typing passed; one full Test-Goblin production
  milestone run is active. Its outcome and protected CI must be retained.

## Findings and fixes

Review required a valid positive workflow attempt before any network operation,
not merely before final receipt construction. The guard now runs immediately
after the existing exact-main guard. Typed mock callbacks replaced ambiguous
lambda parameters. The existing private receipt adapter is reused with narrow
explicit lint/type annotations rather than duplicating its URL handling.
No source bytes are read by local checks; real reader execution is hosted only.
The canary qualifies raw-byte delivery and is not described as Silver or
Platinum domain acceptance. Review was by the implementing agent.
