# Contributing

This is a single-maintainer, evidence-first repository. Contributions use a
short-lived branch and pull request; successful required checks and resolved
conversations are the merge gate. A second-person approval is not required.

## Development

Use Python 3.14 and the locked environment:

```shell
uv sync --python 3.14.6 --locked --all-groups
uv run python scripts/test_goblin.py all
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run basedpyright
```

Use `python scripts/test_goblin.py <lane>` for exactly one primary test lane:
`unit`, `integration`, `e2e`, `smoke`, `property`, or `edge`. Adapter and
storage-boundary changes normally use `integration`; complete user workflows
use `e2e`; malformed or adversarial inputs use `edge`. The harness rejects
unassigned or multiply assigned test files.

On Windows, prefer the `uv`-managed Python runtime rather than a Store Python
shim. Pixi and Mojo are Linux/WSL or hosted-CI paths; Python-only development
must remain independently executable. If OneDrive has left a dirty checkout,
preserve it and use an isolated branch or worktree rather than resetting it.

## Medicine source and adapter changes

Follow [source onboarding](docs/data-sources/source-onboarding.md). A change is
not complete until it records authority, rights state, access mode, temporal
semantics, source-native identifiers, evidence limits, fixtures, adapter
capabilities, tests, and monitoring disposition. Never add live credentials or
restricted source bytes to fixtures.

## Pull-request evidence

Before merge:

1. update the applicable Conductor plan and evidence ledger;
2. add every new test file to one Test-Goblin lane;
3. run routine typing and the relevant behavioral lanes locally;
4. state fixture, live-network, rights, and publication limitations;
5. wait for all required hosted checks, including Codecov patch coverage;
6. link the pull request to its GitHub issue and Conductor task.

Mojo is an experimental acceleration path and must retain a Python fallback.
Conductor requirements, plan, metadata, and evidence are canonical. Update them
when a tracked requirement changes.

For medicine data, preserve the official authority, native identifiers and
labels, source URL, licence, digest, valid time, observed time, uncertainty, and
coverage limitations. Regulatory approval, funding, formulary inclusion, price,
procurement, terminology, and availability must remain distinct.

Do not cross credential, licence, publication, release, or human-review gates
without explicit authority. Hosted rulesets and GitHub Project views are
external settings and must be verified separately from committed configuration.
