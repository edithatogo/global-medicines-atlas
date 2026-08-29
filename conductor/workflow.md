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
9. Tracks execute autonomously under `conductor/autonomy.md`; routine work and evidence-backed checkpoints do not require maintainer confirmation.
10. Dataset archive publication runs in GitHub Actions and targets a public
    Hugging Face dataset directly. Developer machines may prepare and validate
    inputs but are not publication origins; hosted anonymous digest
    verification precedes removal of temporary local bytes.
11. Publication-approved datasets are durable on the public Hugging Face data
    plane at pinned revisions. Repository and workstation data directories are
    transient build/cache surfaces; they may not become the only durable copy.

## Autonomous Execution

- Continue through tasks, phases, review fixes, pull requests, green-check
  merges, reconciliation, and archival while work is safe and in scope.
- Select the next unblocked track automatically when the current track is
  complete.
- Inform the maintainer of progress without converting updates into approval
  requests.
- Pause only at the decision boundary defined in `conductor/autonomy.md`.
- When a decision is required, present one decision with two or three options,
  put the recommendation first, and explain rationale and trade-offs.
- Apply up to three evidence-driven self-corrections before escalating a
  persistent blocker; continue independent unblocked work while doing so.

## Task Lifecycle

1. Select the next unblocked task and mark it `[~]`.
2. Write or identify failing unit, integration, end-to-end, smoke, property,
   metamorphic, contract, deterministic-simulation, mutation, or parity tests
   appropriate to the change.
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

Phase verification proceeds automatically. Manual verification is performed by
the agent where tools and fixtures make it reproducible. Maintainer
confirmation is requested only when verification itself crosses a human gate
or requires judgment that cannot be represented by automated evidence.

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
