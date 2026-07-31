# Global Medicines Atlas

[![Test-Goblin](https://github.com/edithatogo/global-medicines-atlas/actions/workflows/test-goblin.yml/badge.svg?branch=main)](https://github.com/edithatogo/global-medicines-atlas/actions/workflows/test-goblin.yml)
[![Codecov](https://codecov.io/gh/edithatogo/global-medicines-atlas/branch/main/graph/badge.svg)](https://app.codecov.io/gh/edithatogo/global-medicines-atlas)

Global Medicines Atlas is an evidence-first system for comparing medicine
regulatory approval, public funding, formulary status, and terminology across
jurisdictions.

The project keeps those dimensions independent. A terminology match, product
listing, price, or formulary entry is never treated as regulatory approval
without source-specific evidence.

## Current scope

- New Zealand NZULM/NZMT and FHIR adapter boundary.
- Tiered offline-first RxNorm/RxNav-compatible terminology resolution.
- Governed global API and downloadable-source catalog.
- Initial country contracts for New Zealand, Australia, the United States,
  United Kingdom, Canada, Japan, and the European Union.
- Fixture-driven Drugs@FDA bulk projection.

Detailed requirements, design, plans, and evidence are under
[`conductor/`](conductor/index.md). GitHub issues mirror each active Conductor
track in the
[Global Medicines Atlas Conductor Project](https://github.com/users/edithatogo/projects/35).

## Maintainer workflow

This is a single-accountable-maintainer repository with automated evidence
rather than invented reviewer roles. Start with [`AGENTS.md`](AGENTS.md) and
the machine-readable [context manifest](.context/project.toml). Pull requests
run the complete Python 3.14 harness, locked Mojo canary, context-drift checks,
CodeQL, Zizmor, dependency audit, and SBOM generation. Licensing, credentials,
public release, external publication, compatibility archival, and
consequential interpretation remain explicit human gates.

Codecov is active for this public repository. The project gate is 91%, the
patch gate is strictly above 90%, and each Test-Goblin lane uploads an
independently visible flag through GitHub OIDC. See the
[testing and Codecov contract](docs/testing/test-goblin.md#coverage-and-codecov)
for the fail-closed policy.

Relevant maintainer-owned GitHub and Hugging Face resources are governed by the
[ecosystem reuse registry](docs/ECOSYSTEM_REUSE.md), which runs in the routine
harness to prevent parallel implementations and untracked copying.

The evidence-gated [v0.1-to-v1.0 roadmap](conductor/roadmap.md) maps product
features and maturity levels to Conductor tracks and the native GitHub
[roadmap issue hierarchy](https://github.com/edithatogo/global-medicines-atlas/issues/44).

## Use the atlas

Start with the [task-oriented user guide](docs/user-guide.md) to:

- install the core package or opt into semantic retrieval;
- exercise the CLI, API contract, and server-rendered Atlas;
- interpret regulatory, funding, uncertainty, and comparison-validity results;
- reproduce the repository locally or rehearse recovery; and
- report support, security, or medicine-data integrity issues.

The repository currently provides source-checkout and built-artifact workflows,
not a published package, hosted API, or hosted Atlas service. Commands requiring
a canonical DuckDB database do not silently substitute the repository's
representative test fixtures for production medicine data.

## Data boundaries

The repository does not publish the local NZULM release, restricted
terminologies, credentials, or derived private research outputs. Source
catalog entries describe access surfaces; they do not claim complete ingestion
or global coverage. Read the [software and source-data rights](docs/data-sources/SOURCE_RIGHTS.md)
and [stable-v1 qualification limitations](docs/qualification/stable-v1-contract.md)
before reusing code, source material, or derived outputs.
