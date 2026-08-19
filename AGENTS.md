# Global Medicines Atlas agent contract

This is a single-maintainer, evidence-first repository. Automation may prepare,
test, document, commit, push, and open pull requests within an approved task.
It must not invent a second reviewer or silently cross the gates below.
Within those boundaries it continues autonomously; routine task, phase, review,
pull-request, merge, archive, and next-track transitions do not require a
separate “proceed”.

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
- Arrow/Parquet is portable truth; DuckDB and LanceDB are reproducible derivatives.
- Never inspect, commit, log, or publish credentials or restricted source bytes.
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

Use a scoped `codex/` branch and pull request. Run the focused tests followed by
`uv run python scripts/test_goblin.py full` where platform support permits.
Linux CI is authoritative for mutmut and Mojo. Record evidence in the active
track and reconcile plan markers only with observable results.
