# Project Workflow

## Principles

1. Conductor requirements, designs, tracks, and plans are the planning source of truth.
2. Use existing executable acceptance tests where they cover the change; add a
   regression only for new behavior or an uncovered defect. Documentation and
   scheduling edits use their existing validators, without manufactured tests.
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

- Continue through tasks, phases, review fixes, permitted pull requests,
  green-check merges, reconciliation, and archival while work is safe and in
  scope. Authorized pushes, technical pull requests, CI/workflow execution, and
  merges are permitted under the `AGENTS.md` email and messaging exclusion.
  Outreach and standalone comments remain prohibited.
- Select the next unblocked system task using
  [the system completion plan](system-completion.md), across existing tracks.
  A dataset task must name the shared capability or existing gate it closes.
- Inform the maintainer of progress without converting updates into approval
  requests.
- Pause only at the decision boundary defined in `conductor/autonomy.md`.
- When a decision is required, present one decision with two or three options,
  put the recommendation first, and explain rationale and trade-offs.
- Apply up to three evidence-driven self-corrections before escalating a
  persistent blocker; continue independent unblocked work while doing so.

## Task Lifecycle

1. Select the next unblocked system task and record its existing gate, concrete
   failure, bounded scope, expected evidence and stop condition; mark it `[~]`.
2. Select the existing checks that exercise the affected behavior. For a new
   behavior or uncovered defect, add the smallest meaningful regression.
3. For a defect, reproduce its failure before the fix where practical. Do not
   manufacture failing tests for documentation or bookkeeping changes.
4. Implement the smallest coherent change.
5. Run exact affected test files/nodes and applicable static checks. Broaden
   only for demonstrated shared impact, new failures or unresolved risk; reuse
   unchanged evidence. Policy, report, receipt and test-only changes do not
   trigger a local full profile. Run required integration, package, coverage,
   security and release checks at coherent system milestones, including the
   full profile when the applicable contract and changed behavior require it.
   Do not repeat broad validation for each dataset or routine integration.
   Complete protected CI lanes remain required for every pull request.
6. For Python changes, run affected static checks; use routine `ty` and formal
   BasedPyright at the integration milestone. A prose edit does not require
   another repository-wide type check.
7. Retain the governed core coverage floor and Codecov checks in protected CI.
   Do not run full local coverage for every small edit.
8. Run security, provenance, licensing, regeneration and source-boundary checks
   when their inputs change and at required milestones; reuse unchanged results.
9. Record one concise terminal evidence entry per coherent batch, including any
   first failure and its recovery. Avoid separate reports for each unchanged gate.
10. Commit the bounded batch and update its plan together. A task-start marker,
    review acknowledgement or merge receipt does not need a separate commit/PR.

## Validation State and Merge Evidence

- If a coordinator owns broad local validation, hand over the frozen commit/tree,
  worktree, required runtime, exact command, log path and terminal exit-marker
  path. Wait for its launch handle instead of starting a competing full profile.
  Continue focused checks and hosted CI independently. Without an assigned
  launch owner, use the normal local workflow.
- Record the exact tested commit/tree, uncommitted input changes, Python and uv
  versions before broad validation. Use the runtime required by the affected
  release/reproducibility contract throughout child-process PATH. Keep executable
  inputs fixed while the run is live.
- Preserve a run's result for its tested state when remote `main` advances.
  After rebasing or otherwise integrating, inspect the actual delta and apply
  the proportional validation rules above. Full profiles remain required at
  applicable system milestones or when a demonstrated failure requires one.
  Complete protected CI still qualifies
  the final PR head.
- Retain original failed invocations and the exact recovery checks separately.
  A successful isolated rerun does not turn the original full run into a pass.
- Verify the checked head, required CI, merge commit and resulting tree. Use
  GitHub's observable merge record immediately and fold the final track receipt
  into the next substantive change. Do not create receipt-only successor PRs or
  chains that merely record the previous receipt's merge.
- Supply multiline PR descriptions through a literal body file or structured
  argument so shell interpolation cannot corrupt the review text.

## Required Test Lanes at Integration and Release

These lanes remain available and protected CI remains complete. This inventory
is not a demand to run every lane locally for every task or phase.

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

Each coherent implementation milestone records:

- affected automated tests;
- applicable coverage and typing verification, or an unchanged receipt;
- affected provenance and licensing checks, or an unchanged receipt;
- a manual verification procedure only where automation leaves a relevant gap;
- a durable evidence record;
- explicit classification of unresolved external gates.

Phase verification proceeds automatically. Manual verification is performed by
the agent where tools and fixtures make it reproducible. Maintainer
confirmation is requested only when verification itself crosses a human gate
or requires judgment that cannot be represented by automated evidence.

## Single-Developer Controls

- Do not invent independent approvals.
- Use technical pull requests and protected checks for change isolation and
  durable evidence. Preserve the `AGENTS.md` email and messaging exclusion;
  technical repository metadata does not authorize outreach or standalone
  comments.
- Keep credential, licensing, publication, and high-consequence interpretation gates explicit.
- Record unavailable external evidence as blocked or out of scope, never complete.

## Reuse and Dependency Review

Before introducing a new capability or dependency:

1. Search the maintainer's GitHub, package, dataset, schema, fixture, and workflow ecosystem.
2. Record relevant existing capabilities and source commits.
3. Decide whether to reuse, evolve, extract, replace, or reject each candidate.
4. Use the locked, qualified stack for completion. Defer optional frontier
   upgrades unless a demonstrated blocker requires them.
5. Add legacy adapters only where behavior or downstream compatibility requires them.
6. Record retirement conditions for every temporary compatibility dependency.
7. Add cross-repository canaries when a shared dependency or package could affect multiple projects.

The `test-goblin` profile is reused from `reimbursement-atlas`; it is a
maintainer-owned composition of established pytest ecosystem tools rather than
an unresolved package-name dependency.

## GitHub and Conductor Traceability

- One parent GitHub issue corresponds to each Conductor track.
- Existing plan tasks and parent issues provide sufficient traceability for a
  bounded batch. Do not create a subissue for every fix, receipt or review pass.
- Track files reference issue URLs and issues reference track paths and requirement identifiers.
- Synchronization is dry-run by default and validated in CI; do not refresh
  unchanged issue/project bookkeeping on each task.
- Renovate manages dependency updates through grouped, approval-controlled branches.

## Definition of Done

A task is complete only when its acceptance evidence is observable, all required tests pass, coverage remains above 90%, typing and security gates pass, documentation and provenance are current, and external gates are accurately classified.
