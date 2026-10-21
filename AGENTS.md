# Global Medicines Atlas agent contract

This is a single-maintainer, evidence-first repository. Automation may prepare,
test, document, and commit local changes within an approved task. It must not
invent a second reviewer or silently cross the gates below. Within those
boundaries it continues autonomously; routine task, phase, review, and archive
transitions do not require a separate “proceed”.

## Absolute outbound-communication exclusion

- Never send, schedule, reply to, forward, post, comment, or otherwise transmit
  an email or message from the maintainer's account or any account connected to
  this session. This includes email, chat, direct messages, issue or pull-request
  comments, and other messaging channels.
- Never ask the maintainer to send a message or email, or ask for approval or an
  exception to send one.
- Do not use another account, service, tool, person, or workflow to bypass this
  exclusion. While it is in effect, do not push changes or open or update pull
  requests. Keep repository work local.
- This exclusion overrides any generic workflow instruction to contact someone,
  request send approval, push a branch, or open or update a pull request.

## Read first

1. `.context/project.toml`
2. `conductor/index.md`
3. `conductor/workflow.md`
4. `conductor/autonomy.md`
5. the active track `index.md`, `spec.md`, `plan.md`, and `evidence.jsonl`
6. the nearest code style guide and affected tests

Repository state, source receipts, tests, hosted checks, and external artifacts
take precedence over checklist summaries.

The pinned Conductor agent plugin is the Git submodule at
`.agents/plugins/conductor`. Cursor loads those protocols through
`.cursor/skills/`. After clone, run `git submodule update --init --recursive`.

## Invariants

- Regulatory, funding, formulary, and terminology assertions are independent.
- Missing coverage is not negative evidence.
- Preserve source-native identifiers, provenance, dates, rights, and uncertainty.
- Python 3.14 is the complete fallback; Mojo promotion requires parity evidence.
- The immutable source payload and its content-addressed receipt are
  evidentiary truth; source-faithful Parquet is the portable analytical
  representation; table/catalogue layers are rebuildable metadata over those
  artefacts. DuckDB and LanceDB are reproducible derivatives.
- Bronze has three internal Bronze strata, not additional medallion levels:
  **B0 Source Index** is the versioned index of agencies, datasets, APIs, and
  source surfaces, and indexing does not imply acquisition, coverage,
  qualification, or currency; **B1 Acquisition Metadata** is the append-only
  acquisition, receipt, temporal, rights, reuse, retrieval, admission, and
  provenance record; **B2 Raw Evidence** is immutable source-native bytes or a
  rights-constrained immutable reference when bytes cannot lawfully be
  retained. Source-faithful Parquet, archive-member manifests, OpenLineage,
  Iceberg, DuckDB, and other query/catalogue objects are rebuildable Bronze
  projections over B1/B2, not a fourth evidentiary source of truth. Silver
  remains source-faithful typed or harmonised structures; Gold remains
  cross-jurisdiction matched evidence; Platinum remains products and
  presentation.
- Never inspect, commit, log, or publish credentials or restricted source bytes.
- Publish dataset archives only from GitHub Actions directly to a public
  Hugging Face dataset. Local tooling may prepare and validate an archive, but
  it must fail closed on local upload attempts. Remove temporary local source
  bytes only after the hosted workflow records anonymous digest verification.
- Preserve dirty work and imported history; do not use destructive Git recovery.

## Human gates

The sole maintainer must explicitly approve credential creation/publication,
licensing conclusions, public releases, external dataset publication, archival
of compatibility repositories, and consequential clinical or policy claims.

When a decision is required, ask exactly one decision at a time, provide two
or three options, label the recommended option first, and explain the rationale
and material trade-offs. Apply the bounded self-correction and recovery rules
in `conductor/autonomy.md` before escalating a technical blocker.

## Completion

Use a scoped `codex/` branch and local commit while the outbound-communication
exclusion above is in effect; do not push or open a pull request. Run the
focused tests followed by one broader affected check. Run
`uv run python scripts/test_goblin.py full`
for production-behavior or release-gate changes where platform support permits.
For a test-only follow-up after current full-suite evidence, rerun the affected
tests and routine checks; do not repeat the local full profile solely because
the test changed. Complete protected CI lanes still run on every pull request.
Linux CI is authoritative for mutmut and Mojo. Record evidence in the active
track and reconcile plan markers only with observable results.

When a coordinator owns broad local validation, send that owner the frozen
commit/tree, worktree, required runtime, exact command, log path and terminal
exit-marker path. Wait for its launch handle; do not launch a competing full
profile. Focused checks and hosted CI remain independent. When no launch owner
is assigned, follow the normal local validation workflow and acquire any
existing host-level shared validation guard before a broad local run. Keep the
guard held until the command exits; do not add a repository-specific runner or
lock implementation solely for this purpose. Put the contract-pinned tool
directory first in `PATH` for the parent and child processes, especially for
clean-clone release reproduction that discovers tools from child `PATH`, and
record the resolved tool paths and versions. Host-level guards are local
coordination aids and do not change hosted CI requirements.

Before a broad run, record the tested commit and tree, any uncommitted input
changes, and the Python and uv versions. Use the runtime required by the
affected release/reproducibility contract, including child-process PATH, and
keep executable inputs fixed until the run exits. A remote `main` advance
does not invalidate evidence for that tested state. After integration, check
the actual delta: documentation, receipts, or test-only changes require affected
and routine checks; changed production behavior or release gates require the
applicable full profile. Preserve failed invocations separately from successful
recovery checks. Required hosted checks must pass on the final PR head.

Record the checked PR head, required CI results, merge commit and resulting
tree as observable completion evidence. GitHub provides the immediate merge
record; fold its final track receipt into the next substantive change rather
than opening a receipt-only successor PR or a receipt-of-receipt chain. Use a
literal body file or structured argument for multiline PR descriptions.
