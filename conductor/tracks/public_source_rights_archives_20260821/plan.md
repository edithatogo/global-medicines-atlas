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
  - [x] Build and publish the exact-manifest package from acquired and admitted FDA products
- [x] Checkpoint: Maintainer-authorized public revision restored; 13/13 payload digests verified

## Phase 3: International rights review

- [~] Task: Review all international sources against official terms (AC-02, AC-04)
  - [~] Capture bounded official landing-page observations for all sources; 18 unavailable endpoints and source-specific terms remain unresolved
  - [~] Record 13 additional policy-family assignments; 11 are publicly archived and two retain explicit acquisition failures
  - [x] Generate a fail-closed candidate acquisition and manifest-preparation queue with zero public-eligible sources
- [~] Checkpoint: Local focused validation passes; source-specific review and hosted review remain pending

## Phase 4: Public Hugging Face archives

- [~] Task: Publish and restore every acquired, admitted, public-eligible package (AC-05, AC-06)
  - [x] Generate source-specific cards, manifests, attribution, and withdrawal metadata for FDA and 11 international source IDs
  - [x] Exclude restricted fields and run sensitivity/publication gates for published packages
  - [~] Publish, resolve immutable revisions, restore, and verify all SHA-256 digests; two international acquisitions remain unresolved
- [~] Checkpoint: FDA 13/13 and international 23/23 restored digests pass; Open Medic and GIP remain pending

## Phase 5: Qualification and closeout

- [ ] Task: Produce the maintainer decision/evidence packet and reconcile Bronze work queues (AC-01–AC-07)
- [ ] Task: Run focused, routine, strict, and full supported validation (AC-07)
- [ ] Task: Complete Conductor review and apply all blockers (AC-07)
- [ ] Task: Open scoped PRs, obtain green hosted checks, merge, archive the track, and leave clean synchronized main (AC-07)
