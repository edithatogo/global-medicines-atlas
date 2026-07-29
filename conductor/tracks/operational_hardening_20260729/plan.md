# Implementation Plan

## Phase 1: Observability contracts

- [ ] Task: Define source-health, freshness and schema-drift receipts ([#37](https://github.com/edithatogo/global-medicines-atlas/issues/37))
- [ ] Task: Write failure, retry, deduplication and escalation tests ([#37](https://github.com/edithatogo/global-medicines-atlas/issues/37))
- [ ] Task: Define security, privacy, performance and reliability budgets ([#37](https://github.com/edithatogo/global-medicines-atlas/issues/37))
- [ ] Task: Publish the international-resource information schema and validate all catalog entries against it ([#37](https://github.com/edithatogo/global-medicines-atlas/issues/37))
- [ ] Task: Unify catalog, adapter and ingestor capability declarations and prove one source-ID mapping per implementation ([#37](https://github.com/edithatogo/global-medicines-atlas/issues/37))
- [ ] Task: Make Test-Goblin collection declarative, marker-aware and complete, with exactly one primary lane per test ([#37](https://github.com/edithatogo/global-medicines-atlas/issues/37))
- [ ] Task: Define numeric mutation, coverage, latency, throughput, CPU, memory and allocation budgets ([#37](https://github.com/edithatogo/global-medicines-atlas/issues/37))
- [ ] Task: Standardize structured run/source/adapter/receipt logging and verify deterministic redaction ([#37](https://github.com/edithatogo/global-medicines-atlas/issues/37))
- [ ] Task: Define acquisition policy for schemes, redirects, DNS/IP resolution, private-network rejection, per-host budgets, retry jitter and cache integrity ([#37](https://github.com/edithatogo/global-medicines-atlas/issues/37))
- [ ] Task: Qualify every catalogued API/bulk surface and record unsupported portal-only sources ([#37](https://github.com/edithatogo/global-medicines-atlas/issues/37))
- [ ] Task: Phase Verification & Checkpoint

## Phase 2: Hardened operations

- [ ] Task: Implement scheduled monitors and bounded recovery behavior ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38))
- [ ] Task: Add dependency and cross-repository compatibility canaries ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38))
- [ ] Task: Make the full harness self-validating and include dependency, lane-separation and coverage-context checks ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38))
- [ ] Task: Emit durable mutation-score, survivor, timeout, source-health and schema-drift receipts ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38))
- [ ] Task: Add SQL keyset pagination, database schema identity, compatibility checks and measured indexes ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38))
- [ ] Task: Standardize bounded streaming parsers, archive/XML protections and hostile-input property tests ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38))
- [ ] Task: Add negative traversal, symlink, decompression-ratio, entry-count, nesting and schema-size tests for every extraction path ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38))
- [ ] Task: Add backup, restore and rollback automation ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38))
- [ ] Task: Prove locked offline fixture tests and safe network/rate-limit degradation ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38))
- [ ] Task: Validate Renovate, dependency review, CodeQL, secret scanning and action pinning ([#38](https://github.com/edithatogo/global-medicines-atlas/issues/38))
- [ ] Task: Phase Verification & Checkpoint

## Phase 3: Release-candidate evidence

- [ ] Task: Run threat model, load, soak, Scalene and fault-injection exercises ([#39](https://github.com/edithatogo/global-medicines-atlas/issues/39))
- [ ] Task: Qualify million-row cold/warm and concurrent-reader workloads against blocking latency, throughput and memory budgets ([#39](https://github.com/edithatogo/global-medicines-atlas/issues/39))
- [ ] Task: Review surviving mutants and benchmark regressions against immutable baselines ([#39](https://github.com/edithatogo/global-medicines-atlas/issues/39))
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
