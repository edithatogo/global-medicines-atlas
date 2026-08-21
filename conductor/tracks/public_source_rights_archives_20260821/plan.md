# Plan

## Phase 1: Inventory and rights contracts

- [x] Task: Establish the 172-source rights ledger, schemas, validators, and tests (AC-01, AC-02)
  - [x] Capture the exact catalogue census and source-family groupings
  - [x] Add negative tests for missing, duplicate, stale, unsupported, and contradictory decisions
  - [x] Implement deterministic rights evidence and disposition generation
- [x] Checkpoint: Focused validation and the complete hosted matrix passed in PR #266

## Phase 2: FDA rights review and proposed public packages

- [x] Task: Prepare an exact-manifest FDA publication decision with third-party exclusions (AC-03)
  - [x] Enumerate every FDA source and bind official FDA/openFDA evidence
  - [x] Separate copyright permission from sensitivity and completeness
  - [x] Build and publish the exact-manifest package from acquired and admitted FDA products
- [x] Checkpoint: Maintainer-authorized public revision restored; 13/13 payload digests verified

## Phase 3: International rights review

- [x] Task: Review all international sources against official terms (AC-02, AC-04)
  - [x] Capture bounded official landing-page observations and retain unavailable endpoints as explicit unresolved states
  - [x] Record policy-family assignments; 12 affirmatively reusable sources are publicly archived and Open Medic retains an explicit acquisition-failure receipt
  - [x] Generate and reconcile the acquisition/publication queue: 25 published sources and one temporary acquisition failure
- [x] Checkpoint: Rights review is source-specific and fail-closed; unavailable bytes are not represented as archived

## Phase 4: Public Hugging Face archives

- [x] Task: Publish and restore every acquired, admitted, public-eligible package (AC-05, AC-06)
  - [x] Generate source-specific cards, manifests, attribution, and withdrawal metadata for FDA and 12 international source IDs
  - [x] Exclude restricted fields and run sensitivity/publication gates for published packages
  - [x] Publish, resolve immutable revisions, restore, and verify all SHA-256 digests; Open Medic remains temporarily unavailable
- [x] Checkpoint: FDA 13/13 and international 51/51 restored digests pass; Open Medic has an explicit failure receipt

## Phase 5: Qualification and closeout

- [x] Task: Produce the maintainer decision/evidence packet and reconcile Bronze work queues (AC-01–AC-07)
- [x] Task: Run focused, routine, strict, and full supported validation (AC-07)
- [x] Task: Complete Conductor review and apply all blockers (AC-07)
- [~] Task: Open scoped PRs, obtain green hosted checks, merge, archive the track, and leave clean synchronized main (AC-07)

## Review Fixes

- [x] Reconcile the generated publication queue with immutable FDA and international publication receipts (`dc4691c`)
- [x] Replace stale private-candidate wording in the reproducible FDA dataset card (`dc4691c`)
- [x] Bind both publication receipts to their exact source-ID sets (`dc4691c`)
