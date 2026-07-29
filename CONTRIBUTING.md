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
