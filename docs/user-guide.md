# User guide

This guide routes supported local tasks without implying that the project has
published a package, service, complete global dataset, or stable-v1 release.
The Atlas is research infrastructure, not medical advice or clinical decision
support. Verify any medicine status against the cited authority and effective
date.

## Install core or semantic retrieval

The authoritative runtime is Python 3.14. From a source checkout, install the
locked core environment without development groups:

```console
uv sync --python 3.14.6 --locked --no-dev
```

LanceDB-backed semantic retrieval is optional. Install it explicitly when that
capability is required:

```console
uv sync --python 3.14.6 --locked --no-dev --extra semantic
```

Core operation must remain usable without LanceDB. Mojo is an experimental
acceleration canary and is not a substitute for the Python path. The repository
is not currently distributed from PyPI; do not treat these source-checkout
commands as evidence of a published package.

## Run the CLI

Inspect the read-only command surface first:

```console
uv run global-medicines-atlas --help
uv run global-medicines-atlas comparison --help
```

Queries require an explicit canonical DuckDB database and a cursor-signing
secret of at least 16 bytes. Supply the database only from a trusted, governed
build; no production database is bundled with the repository.

```console
GMA_CURSOR_SECRET="replace-with-a-local-secret" uv run global-medicines-atlas comparison --database /absolute/path/atlas.duckdb --concept-id rx:example --jurisdiction NZ --jurisdiction AU --valid-at 2026-07-31T00:00:00Z --observed-at 2026-07-31T00:00:00Z
```

On PowerShell, set the variable for the current process with
`$env:GMA_CURSOR_SECRET = "replace-with-a-local-secret"` and run the command
without its leading POSIX assignment. Do not commit or paste a real secret into
an issue.

## Exercise the API and Atlas

The API and server-rendered Atlas are application factories that require an
explicitly injected read-only query service. This repository does not yet
provide a supported production launcher or hosted endpoint. Exercise their
current user contracts against deterministic fixtures with:

```console
uv run pytest tests/test_product_api.py tests/test_concept_api.py
uv run pytest tests/test_atlas_e2e.py tests/test_atlas_discovery_e2e.py
```

Embedding code should construct `ReadOnlyQueryService` with a governed DuckDB
path, a deployment-owned cursor secret, and an allowed root, then pass it to
`create_app` or `create_atlas_app`. The factories are intentionally read-only;
deployment authentication, TLS, rate limiting, monitoring, and recovery remain
operator responsibilities rather than claims made by this repository.

## Interpret comparisons and abstentions

Regulatory approval and public funding are separate evidence dimensions. A
funded or formulary-listed medicine is not thereby approved, and approval does
not establish funding, availability, price, equivalence, substitutability,
therapeutic interchangeability, or equal benefit.

Read `valid_at` as the time the assertion applies and `observed_at` as the time
the atlas knew it. Inspect source provenance, uncertainty, and evidence
availability before interpreting a conclusion. Unknown coverage is not a
negative finding.

Comparison validity evaluates granularity, indication, population, mapping,
normalization, and material mismatch evidence. A material mismatch produces an
inappropriate-comparison result. Missing or unknown evidence produces an
abstention: it means the repository cannot support that comparison, not that
the medicines are equal or unequal. See the
[stable-v1 qualification contract](qualification/stable-v1-contract.md) for the
complete fail-closed boundary.

## Reproduce locally

Install the complete locked development environment and run the routine local
harness:

```console
uv sync --python 3.14.6 --locked --all-groups
uv run python scripts/test_goblin.py quick
uv run ruff check .
uv run ruff format --check .
```

The aggregate [stable-v1 rehearsal](qualification/stable-v1-rehearsal.md)
produces deterministic representative-fixture evidence. It is not proof of a
clean-room public release, complete source coverage, or production recovery.
Contributor typing and full-lane commands are documented in
[CONTRIBUTING.md](../CONTRIBUTING.md).

## Recover or report a problem

For local governed artifacts, use the [operations index](operations/README.md)
and [governed recovery runbook](operations/governed-recovery-runbook.md).
Recovery exercises use synthetic local artifacts and do not establish an RPO,
RTO, immutable backup, or production disaster-recovery capability.

- Ask non-sensitive usage questions through the path in
  [SUPPORT.md](../SUPPORT.md).
- Submit reproducible, non-sensitive data issues with the repository's data
  incident issue form and follow the
  [data incident response procedure](operations/data-incident-response.md).
- Report vulnerabilities, credentials, personal information, and exploitable
  medicine-data integrity defects privately as described in
  [SECURITY.md](../SECURITY.md).

## Publication and licence limitations

Repository software is licensed under Apache-2.0. Eligible maintainer-owned
derived datasets may be licensed under CC-BY-4.0 only when an approved public
artifact manifest expressly places them in scope. Third-party medicine sources
retain their own terms, access controls, attribution duties, and redistribution
restrictions. Review
[software and source-data rights](data-sources/SOURCE_RIGHTS.md) before reuse.

GitHub, Hugging Face, Zenodo, and OSF have distinct intended publication roles,
but a configured identity or URL is not evidence that an object was published,
licensed, approved, or verified. External identifiers, credentials, rights
review, release execution, and publication remain explicit evidence gates.
