# Project Workflow

## Principles

1. Conductor requirements, designs, tracks, and plans are the planning source of truth.
2. Every implementation task begins with executable acceptance tests.
3. Regulatory approval and funding assertions remain separate.
4. Primary-source provenance, licensing, uncertainty, and coverage are required data.
5. External publication, credentials, licensing decisions, and consequential releases remain explicit human gates.
6. A green local or hosted check is not proof of an external outcome without an independently observable artifact and receipt.
7. Search the maintainer-owned ecosystem before creating a new capability.
8. Frontier dependency adoption requires compatibility evidence; legacy compatibility must remain isolated and temporary.

## Task Lifecycle

1. Select the next unblocked task and mark it `[~]`.
2. Write or identify failing unit, integration, end-to-end, smoke, property, mutation, or parity tests appropriate to the change.
3. Confirm the intended failure.
4. Implement the smallest coherent change.
5. Run the focused tests, then the broader affected harness.
6. Run routine typing with `ty` and formal typing with BasedPyright.
7. Verify coverage remains strictly above 90% for governed core code and upload CI coverage to Codecov.
8. Run security, provenance, licensing, deterministic-regeneration, and source-boundary gates.
9. Record evidence and deviations in the active track.
10. Commit only scoped work, record the commit identifier, and update the plan.

## Required Test Lanes

- Unit tests.
- Integration tests.
- End-to-end tests.
- Smoke tests.
- Property-based tests.
- Mutation testing with bounded timeouts.
- Test-goblin runs combining Hypothesis, mutmut, and pytest-randomly.
- Mojo/Python and Rust/Python parity tests where applicable.
- Golden fixtures and negative controls.
- Source-contract, schema-drift, malformed-input, and deterministic-regeneration tests.
- Scalene profiling and benchmark regression checks for promoted performance work.

## Phase Verification

Every phase ends with:

- affected automated tests;
- coverage and typing verification;
- provenance and licensing checks;
- a concise manual verification procedure;
- a durable evidence record;
- explicit classification of unresolved external gates.

## Single-Developer Controls

- Do not invent independent approvals.
- Use pull requests and protected checks for change isolation and durable evidence.
- Keep credential, licensing, publication, and high-consequence interpretation gates explicit.
- Record unavailable external evidence as blocked or out of scope, never complete.

## Reuse and Dependency Review

Before implementation:

1. Search the maintainer's GitHub, package, dataset, schema, fixture, and workflow ecosystem.
2. Record relevant existing capabilities and source commits.
3. Decide whether to reuse, evolve, extract, replace, or reject each candidate.
4. Prefer the current standardized frontier stack when compatibility evidence passes.
5. Add legacy adapters only where behavior or downstream compatibility requires them.
6. Record retirement conditions for every temporary compatibility dependency.
7. Add cross-repository canaries when a shared dependency or package could affect multiple projects.

The `test-goblin` profile is reused from `reimbursement-atlas`; it is a
maintainer-owned composition of established pytest ecosystem tools rather than
an unresolved package-name dependency.

## GitHub and Conductor Traceability

- One parent GitHub issue corresponds to each Conductor track.
- Actionable plan tasks become linked subissues.
- Track files reference issue URLs and issues reference track paths and requirement identifiers.
- Synchronization is dry-run by default and validated in CI.
- Renovate manages dependency updates through grouped, approval-controlled branches.

## Definition of Done

A task is complete only when its acceptance evidence is observable, all required tests pass, coverage remains above 90%, typing and security gates pass, documentation and provenance are current, and external gates are accurately classified.
