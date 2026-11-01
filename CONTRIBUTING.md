# Contributing

This is a single-maintainer, evidence-first repository. Contributions use a
short-lived branch and pull request; successful required checks and resolved
conversations are the merge gate. A second-person approval is not required.

## Development

The Conductor agent plugin is pinned as a Git submodule at
`.agents/plugins/conductor`. After clone, initialize it with:

```shell
git submodule update --init --recursive
```

Bootstrap once in your own checkout with Python 3.15.1 and the locked test
environment. Do not replace another operation's environment:

```shell
uv sync --python 3.15.1 --locked
uv run --no-sync python --version
uv run --no-sync pytest -q tests/test_smoke.py
```

During edits, select exact affected test files or nodes. Preserve the worktree's
pytest cache; use `--lf --last-failed-no-failures=none` for failure-only recovery.
An empty failure cache is not verification. Use zero automatic retries.
The default locked `test-goblin` group supplies the required pytest plugins,
including the configured timeout plugin; the `test` group alone is insufficient.

For a coherent integration milestone, install only the additional locked
groups needed by its checks, then use the existing runner:

```shell
uv sync --python 3.15.1 --locked --group typing
uv run --no-sync python scripts/test_goblin.py routine
uv run --no-sync python scripts/test_goblin.py strict
uv run --no-sync python scripts/test_goblin.py package
```

The full profile is `full`, not `all`. Run it when required by the changed
production behavior or release contract, with the applicable dev/security
groups installed; it is not the bootstrap or per-edit command. Existing
protected hosted lanes still qualify every PR head. Policy-only changes use
`uv run --no-sync python scripts/validate_context.py` and affected context tests.

Use `uv run --no-sync python scripts/test_goblin.py <lane>` for one primary lane:
`unit`, `integration`, `e2e`, `smoke`, `property`, or `edge`. Adapter and
storage-boundary changes normally use `integration`; complete user workflows
use `e2e`; malformed or adversarial inputs use `edge`. The harness rejects
unassigned or multiply assigned test files.

On Windows, prefer the `uv`-managed Python runtime rather than a Store Python
shim. Pixi and Mojo are Linux/WSL or hosted-CI paths; Python-only development
must remain independently executable. If OneDrive has left a dirty checkout,
preserve it and use an isolated branch or worktree rather than resetting it.

## Hosted-governance drift

The committed hosted-governance receipt is the auditable point-in-time record
of rulesets, classic branch protection, security features, CodeQL, dependency
review, and alert endpoint access. Verify the committed receipt offline with:

```shell
uv run --python 3.15.1 --group dev python scripts/qualify_stable_v1_hosted_governance.py
```

An operator with authenticated read-only GitHub CLI access can refresh that
receipt with the same command plus `--acquire`. Acquisition makes no hosted
write, but it intentionally updates the committed snapshot and receipt; review
the resulting diff before accepting a changed control state. This project uses
zero required human approvals: protected automated checks and resolved
conversations are the merge gate.

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
3. run affected checks, reusing unchanged evidence; use broader checks at a
   coherent milestone under [the workflow](conductor/workflow.md);
4. state fixture, live-network, rights, and publication limitations;
5. wait for all required hosted checks, including Codecov patch coverage;
6. link the pull request to its existing Conductor task and parent issue;
   no new issue or separate receipt-only PR is needed for routine work.

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
