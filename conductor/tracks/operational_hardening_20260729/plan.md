# Implementation Plan

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

- [ ] Task: Implement scheduled monitors and bounded recovery behavior ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38))
- [ ] Task: Bind monitor baselines to trusted main-workflow provenance and verify receipt identity before comparison ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38))
- [ ] Task: Add dependency and cross-repository compatibility canaries ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38))
- [ ] Task: Govern runner and tool versions from one source and extend Renovate management to workflow literals and Mojo channels ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38))
- [ ] Task: Make the full harness self-validating and include dependency, lane-separation and coverage-context checks ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38))
- [ ] Task: Upload lane-specific Codecov contexts and document the intentional ty/BasedPyright/Ruff scope boundaries ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38))
- [ ] Task: Emit durable mutation-score, survivor, timeout, source-health and schema-drift receipts ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38))
- [ ] Task: Add SQL keyset predicates with `LIMIT n+1`, bounded Arrow export streaming, database schema identity, compatibility checks and measured query-plan/index receipts ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38))
- [ ] Task: Standardize bounded streaming parsers, archive/XML protections and hostile-input property tests ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38))
- [ ] Task: Add negative traversal, symlink, decompression-ratio, entry-count, nesting and schema-size tests for every extraction path ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38))
- [ ] Task: Add backup, restore and rollback automation ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38))
- [ ] Task: Separate dry-run qualification evidence from approved release attestations and bind attestations to exact governed bytes ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38))
- [ ] Task: Prove locked offline fixture tests and safe network/rate-limit degradation ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38))
- [ ] Task: Add repository/history leak detection and validate Renovate, dependency review, CodeQL, hosted secret scanning and action pinning ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38))
- [ ] Task: Add characterized typed boundaries before splitting policy, transport, persistence, serialization and orchestration responsibilities ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38))
- [ ] Task: Phase Verification & Checkpoint

## Phase 3: Release-candidate evidence

- [ ] Task: Run threat model, load, soak, Scalene and fault-injection exercises ([#39](https://github.com/edithatogo/global-medicines-atlas/issues/39))
- [ ] Task: Qualify million-row cold/warm and concurrent-reader workloads against blocking latency, throughput and memory budgets ([#39](https://github.com/edithatogo/global-medicines-atlas/issues/39))
- [ ] Task: Review surviving mutants and benchmark regressions against immutable baselines ([#39](https://github.com/edithatogo/global-medicines-atlas/issues/39))
- [ ] Task: Qualify one real Mojo kernel through Arrow-fixture parity, fallback and measured promotion, or record Python as authoritative with Mojo experimental ([#39](https://github.com/edithatogo/global-medicines-atlas/issues/39))
- [ ] Task: Run the medicine-data integrity threat model for poisoned downloads, stale snapshots, identifier collisions and false status inference ([#39](https://github.com/edithatogo/global-medicines-atlas/issues/39))
- [ ] Task: Rehearse clean recovery from governed artifacts ([#39](https://github.com/edithatogo/global-medicines-atlas/issues/39))
- [ ] Task: Verify hosted rulesets, security settings, labels and project views ([#39](https://github.com/edithatogo/global-medicines-atlas/issues/39))
- [ ] Task: Validate contributor, operator, source-onboarding and incident documentation ([#39](https://github.com/edithatogo/global-medicines-atlas/issues/39))
- [ ] Task: Record v0.8 qualification evidence ([#39](https://github.com/edithatogo/global-medicines-atlas/issues/39))
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
- [~] Task: Re-run complete Phase 1 verification after review fixes — local gate passed, but independent review found unresolved production host admission and DNS connection-binding defects; correction and re-review are in progress
