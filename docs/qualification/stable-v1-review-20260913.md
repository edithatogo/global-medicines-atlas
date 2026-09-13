# Review Report: Stable v1 qualification

## Summary

Two high-priority qualification-integrity defects were reproduced and repaired;
Stable v1 still requires its existing implementation, evidence and human gates.

## Verification Checks

- [x] **Plan Compliance**: Partial — fixes strengthen release evidence; Bronze,
  Australian federation, Renovate, M5 and stable approval remain open.
- [x] **Style Compliance**: Pass — Ruff and production BasedPyright pass.
- [x] **New Tests**: Yes — failed-first controls cover runtime/schema parity,
  copied-model serialization, readiness, duplicate gates, state preservation,
  lower maturity and unaccepted recovery risk.
- [x] **Test Coverage**: Local suite reports 97% rounded coverage. All 38 hosted
  checks pass at `de176cd7297a4d5f68c71387cbd22c0e7b38329b`, including
  Linux mutation, Mojo and Codecov. Local full harness stops at the mutation
  survivor baseline after macOS native fork failures; no threshold was changed.
- [x] **Test Results**: 127 focused tests pass including monitoring. The final
  full-suite run passes 4,892 tests with one optional PyIceberg skip. The first
  run detected a stale schema-bound monitoring receipt; regeneration corrected
  its bindings before the passing run.

## Findings

### [High] Reconciliation promoted adverse observations without fresh evidence — fixed

- **Files**: `scripts/reconcile_stable_v1_contract.py` and
  `tests/test_stable_v1_qualification_contract.py`.
- **Context**: Regeneration replaced unverified requirements and support with
  verified states, raised lower maturity, replaced failed technical gates with
  passed states and accepted a newly unresolved production-recovery risk.
  Duplicate gate identifiers also let the last entry erase an earlier failure.
- **Fix**: Preserve non-passing technical states, requirement blockers, unaccepted
  recovery disposition and technical evidence. Known maturity ceilings can lower readiness but
  cannot raise it. Reject duplicate gate IDs before constructing the map.
- **Boundary**: This remains a reconciliation tool, not an independent evidence
  verifier. Existing blocked gates still require observable acceptance evidence.

### [High] Live-qualified labels were accepted despite contradictory evidence — fixed

- **Files**: `src/global_medicines_atlas/release_evidence.py`,
  `schemas/release-evidence-v1.json` and `tests/test_release_evidence.py`.
- **Context**: A serialized blocked result could be relabelled live-qualified
  while retaining unresolved gates. Dirty Git state, unknown denominators,
  missing versions/digests, restricted rights and hidden fixture snapshot
  digests were also accepted. The portable schema lacked conditional readiness
  checks. A copied model could bypass construction checks during serialization.
- **Fix**: Enforce live readiness at model validation, require positive and
  consistent live/permitted receipt counts, reject unresolved gates and fixture
  snapshots, add portable schema conditions and required gate outcomes, and
  revalidate before canonical serialization.
- **Boundary**: Structural consistency cannot establish source authenticity or
  confer release approval. The generator still cannot produce approved evidence.

## Completion disposition

Reviewed from `ee90c933965278e4fa673fb26801788b5270ec64` using repository
source, tests, schemas and track evidence. This is a same-agent review; no
independent human reviewer is claimed. The track remains in progress and must
not be archived until its full acceptance criteria are evidenced. The existing
Denmark Medstat source decision remains pending and is not resolved by this
review or by the instruction to complete the track.
