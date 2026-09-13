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
- [ ] **Test Coverage**: Full harness and hosted results are recorded in the
  append-only track evidence ledger; focused checks alone do not qualify release.
- [x] **Test Results**: 112 focused release, authority, workflow and Stable v1
  contract tests passed before full validation.

## Findings

### [High] Reconciliation promoted adverse observations without fresh evidence — fixed

- **Files**: `scripts/reconcile_stable_v1_contract.py` and
  `tests/test_stable_v1_qualification_contract.py`.
- **Context**: Regeneration replaced unverified requirements and support with
  verified states, raised lower maturity, replaced failed technical gates with
  passed states and accepted a newly unresolved production-recovery risk.
  Duplicate gate identifiers also let the last entry erase an earlier failure.
- **Fix**: Preserve supplied non-passing states, blockers, recovery disposition
  and technical evidence. Known maturity ceilings can lower readiness but
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
