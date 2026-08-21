# Plan

## Phase 1: Inventory and rights contracts

- [x] Task: Establish the 172-source rights ledger, schemas, validators, and tests (AC-01, AC-02)
  - [x] Capture the exact catalogue census and source-family groupings
  - [x] Add negative tests for missing, duplicate, stale, unsupported, and contradictory decisions
  - [x] Implement deterministic rights evidence and disposition generation
- [~] Checkpoint: Local focused validation passes; hosted review remains pending

## Phase 2: FDA rights review and proposed public packages

- [x] Task: Prepare an exact-manifest FDA publication decision with third-party exclusions (AC-03)
  - [x] Enumerate every FDA source and bind official FDA/openFDA evidence
  - [x] Separate copyright permission from sensitivity and completeness
  - [x] Build public packages from acquired and admitted FDA products
- [x] Checkpoint: Published the exact 13-source package and verified all payload digests after clean restore

## Phase 3: International rights review

- [~] Task: Review all international sources against official terms (AC-02, AC-04)
  - [~] Capture bounded official landing-page observations for all sources; 18 unavailable endpoints and source-specific terms remain unresolved
  - [~] Record 13 additional candidate policy-family assignments; every licensing conclusion and publication disposition remains pending maintainer approval
  - [x] Generate a fail-closed candidate acquisition and manifest-preparation queue with zero public-eligible sources
- [~] Checkpoint: Local focused validation passes; source-specific review and hosted review remain pending

## Phase 4: Public Hugging Face archives

- [ ] Task: After exact-manifest approval, publish and restore every acquired, admitted, public-eligible package (AC-05, AC-06)
  - [ ] Generate source-specific cards, manifests, attribution, and withdrawal metadata
  - [ ] Exclude restricted fields and run sensitivity/publication gates
  - [ ] Publish, resolve immutable revisions, restore, and verify all SHA-256 digests
- [ ] Checkpoint: Review and validate Phase 4

## Phase 5: Qualification and closeout

- [ ] Task: Produce the maintainer decision/evidence packet and reconcile Bronze work queues (AC-01–AC-07)
- [ ] Task: Run focused, routine, strict, and full supported validation (AC-07)
- [ ] Task: Complete Conductor review and apply all blockers (AC-07)
- [ ] Task: Open scoped PRs, obtain green hosted checks, merge, archive the track, and leave clean synchronized main (AC-07)
