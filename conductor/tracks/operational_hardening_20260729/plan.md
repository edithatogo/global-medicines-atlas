# Implementation Plan

Execution policy: [autonomous, decision-gated](../../autonomy.md).

## Phase 1: Observability contracts

- [x] Task: Define source-health, freshness and schema-drift receipts ([#37](https://github.com/edithatogo/global-medicines-atlas/issues/37)) `903dee3`
- [x] Task: Write failure, retry, deduplication and escalation tests ([#37](https://github.com/edithatogo/global-medicines-atlas/issues/37)) `903dee3`
- [x] Task: Define security, privacy, performance and reliability budgets ([#37](https://github.com/edithatogo/global-medicines-atlas/issues/37)) `aabba52`
- [x] Task: Publish the international-resource information schema and validate all catalog entries against it ([#37](https://github.com/edithatogo/global-medicines-atlas/issues/37)) `e8f588e`
- [x] Task: Unify catalog, adapter and ingestor capability declarations and prove one source-ID mapping per implementation ([#37](https://github.com/edithatogo/global-medicines-atlas/issues/37)) `e8f588e`
- [x] Task: Make Test-Goblin collection declarative, marker-aware and complete, with exactly one primary lane per test ([#37](https://github.com/edithatogo/global-medicines-atlas/issues/37)) `aabba52`
- [x] Task: Define numeric mutation, coverage, latency, throughput, CPU, memory and allocation budgets ([#37](https://github.com/edithatogo/global-medicines-atlas/issues/37)) `aabba52`
- [x] Task: Standardize structured run/source/adapter/receipt logging and verify deterministic redaction ([#37](https://github.com/edithatogo/global-medicines-atlas/issues/37)) `9a64332`
- [x] Task: Define acquisition-policy contracts for schemes, redirects, DNS/IP resolution, private-network rejection, per-host budgets, retry jitter and cache integrity; operational enforcement continues in Phase 2 ([#37](https://github.com/edithatogo/global-medicines-atlas/issues/37)) `9a64332`
- [x] Task: Classify every catalogued API/bulk surface by declared, documentation, fixture or live qualification and record unsupported portal-only sources ([#37](https://github.com/edithatogo/global-medicines-atlas/issues/37)) `0cebcdf`
- [x] Task: Phase Verification & Checkpoint — 845 passed, 7 expected Windows symlink skips; 93.95% branch coverage; Ruff, ty and BasedPyright strict passed

## Phase 2: Hardened operations

- [x] Task: Implement scheduled monitors and bounded recovery behavior ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38)) `4a410a7` `734e959` `4f5a8b3` `608c680`
- [x] Task: Bind monitor baselines to trusted main-workflow provenance and verify receipt identity before comparison ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38)) `608c680`
- [x] Task: Add dependency and cross-repository compatibility canaries ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38)) `15354b4` `6a76b59`
- [x] Task: Govern runner and tool versions from one source and extend Renovate management to workflow literals and Mojo channels ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38)) `6a76b59` `53e60ed` `70d4721` `730502e`
- [x] Task: Make the full harness self-validating and include dependency, lane-separation and coverage-context checks ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38)) `15354b4` `6a76b59`
- [x] Task: Upload lane-specific Codecov contexts and document the intentional ty/BasedPyright/Ruff scope boundaries ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38)) `15354b4`
- [x] Task: Emit durable mutation-score, survivor, timeout, source-health and schema-drift receipts ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38)) `15354b4` `6a76b59` `608c680`
- [x] Task: Add SQL keyset predicates with `LIMIT n+1`, database schema identity, compatibility checks and measured query-plan receipts; bounded Arrow export remains deferred because no Arrow export interface exists ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38)) `298a985` `0d5dca0`
- [x] Task: Standardize bounded streaming parsers, archive/XML protections and hostile-input property tests ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38)) `4a410a7` `734e959`
- [x] Task: Add negative traversal, symlink, decompression-ratio, entry-count, nesting and schema-size tests for supported extraction paths ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38)) `4a410a7` `734e959`
- [x] Task: Add backup, restore and rollback automation ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38)) `4a410a7` `734e959` `4f5a8b3`
- [x] Task: Separate dry-run qualification evidence from approved release attestations and bind attestations to exact governed bytes ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38)) `608c680`
- [x] Task: Prove locked offline fixture tests and safe network/rate-limit degradation ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38)) `608c680`
- [x] Task: Add repository/history leak detection and validate Renovate, dependency review, CodeQL, hosted secret scanning and action pinning — all pinned-action, configuration and hosted workflow gates pass at `8e0b898`; secret scanning, push protection and Dependabot security updates are enabled, while Renovate app execution and repository-wide action-policy enforcement remain explicit Phase 3 hosted-governance work ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38)) `15354b4` `6a76b59` `53e60ed` `70d4721` `730502e` `af0c4f7` `30c594f` `8e0b898`
- [x] Task: Add characterized typed boundaries before splitting policy, transport, persistence, serialization and orchestration responsibilities ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38)) `298a985` `4a410a7` `15354b4`
- [x] Task: Phase Verification & Checkpoint — [PR #71](https://github.com/edithatogo/global-medicines-atlas/pull/71) merged as `49991b8`; 23 required checks passed; Codecov reported 92.43% project coverage with project and patch gates passing

## Phase 3: Release-candidate evidence

- [x] Task: Run threat model, load, soak, Scalene and fault-injection exercises — the bounded synthetic receipt passed all declared budgets, 25 warm/soak iterations, four concurrent readers, four medicine-data integrity threats and tampered-backup rejection; it binds exact hosted Scalene artifact identities while explicitly denying production qualification ([#39](https://github.com/edithatogo/global-medicines-atlas/issues/39)) `6830b6d`
- [x] Task: Qualify million-row cold/warm and concurrent-reader workloads against blocking latency, throughput and memory budgets ([#39](https://github.com/edithatogo/global-medicines-atlas/issues/39)) `aaf5bd0` `995d0be`; [PR #72 run](https://github.com/edithatogo/global-medicines-atlas/actions/runs/30602190188) passed the GitHub-hosted Linux gate
- [x] Task: Review surviving mutants and benchmark regressions against immutable baselines — immutable performance and mutation regression gates pass; focused test remediation reduced survivor debt from 523 to 317 and raised the hosted score from 72.56% to 83.70%, clearing the independent 80% v0.8 threshold without waivers or scope reduction ([#39](https://github.com/edithatogo/global-medicines-atlas/issues/39)) `7853f78` `b1fa968`
- [x] Task: Record Python 3.14 as authoritative and Mojo as experimental: the pinned hosted smoke canary proves toolchain availability, while the machine-validated receipt denies promotion because no real kernel, Arrow parity, runtime fallback path or representative benchmark exists ([#39](https://github.com/edithatogo/global-medicines-atlas/issues/39)) `9d0d04b`
- [x] Task: Run the medicine-data integrity threat model for poisoned downloads, stale snapshots, identifier collisions and false status inference ([#39](https://github.com/edithatogo/global-medicines-atlas/issues/39)) `8df1793`
- [x] Task: Rehearse clean recovery from governed artifacts — deterministic backup, replacement, restore, rollback and quarantine identities passed locally and in the hosted dedicated recovery job; production independent-storage, RPO/RTO and crash-consistency claims remain authority-gated ([#39](https://github.com/edithatogo/global-medicines-atlas/issues/39)) `50aa28e`
- [x] Task: Verify hosted rulesets, security settings, labels and project views — strict main protection, security features and all 20 additive manifest labels were verified live; Project 35 has the same five-view pattern as the other active projects and issues #36–#43 now use all shared custom fields consistently. The absent repository ruleset is dispositioned in favour of the equivalent existing branch protection; Renovate App activation remains an explicit maintainer-authority gate ([#39](https://github.com/edithatogo/global-medicines-atlas/issues/39))
- [x] Task: Validate contributor, operator, source-onboarding and incident documentation — required sections, local links and issue-form contracts pass locally and in all 25 hosted checks ([#39](https://github.com/edithatogo/global-medicines-atlas/issues/39)) `6160ad1`
- [x] Task: Record v0.8 qualification evidence — the machine-readable receipt qualifies the bounded release while retaining explicit publication, production disaster recovery, Renovate activation and Mojo-promotion limits ([#39](https://github.com/edithatogo/global-medicines-atlas/issues/39))
- [ ] Task: Phase Verification & Checkpoint

## GitHub hierarchy

- Parent: [#36 Operational hardening](https://github.com/edithatogo/global-medicines-atlas/issues/36)
- Observability and source qualification: [#37](https://github.com/edithatogo/global-medicines-atlas/issues/37)
- Hardened operations and supply chain: [#38](https://github.com/edithatogo/global-medicines-atlas/issues/38)
- Independent release-candidate evidence: [#39](https://github.com/edithatogo/global-medicines-atlas/issues/39)

## Phase 1 Review Fixes

- [x] Task: Share fail-closed destination validation between acquisition and source-health probes, reject non-public networks and require explicit live-host admission `c2dcbbd`
- [x] Task: Align source capability claims with catalog integration maturity and add semantic qualification states without inventing live evidence `0cebcdf`
- [x] Task: Validate marker-aware pytest collection and wire machine-readable coverage and evidence-budget boundaries into Test-Goblin `30763b1`
- [x] Task: Preserve legacy dimension-aware source declarations and archived publication qualification tests `0cebcdf`
- [x] Task: Re-run complete Phase 1 verification after review fixes — governed host admission, validated-IP binding, redirect revalidation, TLS authority isolation and policy-driven redirect limits passed independent review; 875 passed, 7 expected Windows symlink skips; 93.89% branch coverage; Test-Goblin collected 881 tests; Ruff, ty, BasedPyright strict and context validation passed `1ebdc4d` `57e8e36` `2f414e8`
