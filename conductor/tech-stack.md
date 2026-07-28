# Technology Stack

## Architecture Baseline

This is a Mojo-first, Python-compatible, provenance-first data system. Performance-critical kernels should be implemented in Mojo where the toolchain is suitable, while Python 3.14 remains the complete reference implementation and operational fallback.

No required capability may exist only in Mojo until its Python parity contract, fixtures, and fallback behavior are verified.

## Dependency and Ecosystem Doctrine

The maintainer's repository ecosystem is the first reuse surface.

1. Search existing maintainer-owned repositories, packages, schemas, adapters, fixtures, workflows, and publication tooling before adding a new implementation.
2. Reuse or evolve existing maintainer-owned capabilities when their contracts fit the requirement.
3. Extract a shared package or contract when reuse across repositories is stable and evidence-backed.
4. Adopt current frontier dependencies through compatibility canaries, lockfiles, benchmarks, and rollback evidence.
5. Do not allow legacy dependencies to determine the target architecture.
6. Confine legacy behavior to explicit adapters, migration tools, and compatibility tests.
7. Use third-party foundational libraries where rebuilding them would not create distinctive maintainer-owned value.

Every dependency decision must classify the component as maintainer-owned reuse, a promoted shared package, a third-party frontier dependency, a temporary legacy compatibility dependency, or rejected/superseded.

## Languages and Runtimes

### Mojo

- Use Mojo for performance-critical parsing, normalization, matching, candidate generation, and large-scale transformation kernels.
- Develop on Windows through WSL; run authoritative Mojo CI on Linux.
- Maintain blocking tests against the selected stable Mojo toolchain.
- Maintain a scheduled or explicitly classified nightly-canary lane for early compatibility signals.
- Pin resolved toolchain versions in environment locks and record them in build evidence.

### Python

- Require CPython 3.14 for the primary Python package and CI.
- Use Python for source adapters, orchestration, schemas, validation, CLI/API surfaces, reporting, and the complete reference/fallback implementation.
- Define public Python interfaces with strict typing.
- Test every Mojo-accelerated behavior against shared Python golden fixtures and parity expectations.

## Python Packaging Standards

- Use `pyproject.toml` as the canonical project manifest.
- Use PEP 621 `[project]` metadata.
- Use PEP 735 dependency groups for development, test, quality, documentation, security, benchmark, and release tooling.
- Use PEP 508 dependency specifications and PEP 440 versions.
- Use `uv` for Python environment management, resolution, execution, building, and publishing.
- Commit `uv.lock` as the complete project lock.
- Export and validate a PEP 751 `pylock.toml` for tool-independent installation interoperability.
- Generate CycloneDX and SPDX software bills of materials from locked inputs.
- Prefer current compatible dependency releases, bounded by explicit compatibility evidence rather than unbounded upgrades.

## Cross-Language Environment Management

- Use Pixi for Mojo/MAX and cross-language toolchain environments.
- Keep Python-only workflows executable through `uv`.
- Keep Mojo and Python environment definitions synchronized through CI checks and generated toolchain reports.
- Record operating system, architecture, runtime, compiler, dependency locks, and relevant environment digests in reproducibility evidence.

## Data and Storage

### NZULM and NZMT

NZULM/NZMT is a first-class initial source family, not merely a project name.

- Inventory and preserve the existing NZULM/NZMT artifacts before transformation.
- Reuse validated structures from the `edithatogo/nzmedicines` repository where licensing, provenance, and source recency permit.
- Preserve NZMT identifiers and product hierarchy levels, including medicinal products, medicinal product units of use, medicinal product packs, trade products, trade product units of use, trade product packs, and containered trade product packs where present.
- Preserve SNOMED CT identifiers, ATC codes, GTINs, pharmacodes, sponsors, dosage forms, strengths, routes, and source-native relationships.
- Model Medsafe regulatory status and PHARMAC funding status as distinct assertions.
- Support FHIR Medication, MedicationKnowledge, Organization, Substance, and Provenance projections without making a projection the sole canonical representation.
- Validate NZ-specific FHIR extension URLs, definitions, versions, and registry status before public interoperability claims.
- Retain source-native bundles and generated indexes as reproducible inputs, with commit identity and content digests.

### Portable Source and Canonical Data

- Preserve source artifacts where lawful, with checksums, retrieval metadata, licensing state, and immutable manifests.
- Use Parquet as the primary portable tabular representation.
- Use Arrow-compatible schemas and explicit schema versions.
- Use JSON/JSONL for manifests, events, review queues, and compact interoperable records.
- Use CSV only for reviewed interchange, human inspection, or source-native compatibility.

### DuckDB

DuckDB is the primary embedded analytical engine.

- Query Parquet and canonical datasets without requiring a server.
- Materialize reviewed local analytical bundles where appropriate.
- Support deterministic comparisons, quality checks, and report generation.
- Keep DuckDB files reproducible from governed source and canonical artifacts.
- Do not treat an opaque DuckDB file as the sole authoritative copy of data.

### LanceDB

LanceDB is a derived semantic and vector index.

- Use it for candidate generation, semantic retrieval, terminology alignment, and assisted matching.
- Bind every vector/index entry to canonical identifiers, source evidence, model identity, embedding version, and index version.
- Treat similarity results as candidates requiring confidence, validation, and review—not authoritative equivalence.
- Ensure the index can be regenerated from canonical governed inputs.

### Legacy SQLite

- Treat existing SQLite databases as migration inputs or compatibility artifacts.
- Inventory schemas and provenance before migration.
- Preserve original files and checksums.
- Move canonical analytical workloads toward Parquet and DuckDB.

### Legacy Dependency Boundary

- Inventory current Node.js, Python, SQLite, and ad hoc script dependencies before changing them.
- Preserve required behavior through contracts and golden tests.
- Replace legacy libraries only after the frontier path reproduces required behavior and data outputs.
- Remove compatibility code only after downstream consumers and restoration paths are verified.
- Require a recorded exception for dependencies that are unmaintained, incompatible with Python 3.14, or redundant with the selected stack.

## Core Libraries

- Polars for lazy, parallel, streaming columnar transformation. Polars is already a Rust-native execution engine exposed through Python, so it is the default dataframe layer.
- PyArrow for Arrow and Parquet interoperability.
- DuckDB for embedded analytics.
- LanceDB for derived semantic/vector indexing.
- Pydantic and pydantic-settings for contracts and configuration.
- HTTPX and Tenacity for robust source acquisition.
- orjson for high-throughput JSON serialization where compatible with contracts.
- Structlog for structured operational logging.
- Typer and Rich for the command-line interface.
- NetworkX only where explicit graph algorithms are needed.

Dependencies must be introduced through a documented requirement, compatibility check, lock update, and harness evidence.

The first executable frontier cohort is locked and exercised: Pydantic v2 and
pydantic-settings for contracts, PyArrow schemas and Parquet interchange,
Polars transformations, DuckDB coverage queries, and LanceDB as a reserved
derived-index dependency. Pytest-gremlins and Edgetest provide mutation and
latest-dependency compatibility evidence. Pixi locks the Linux Mojo nightly
canary while `uv` remains the independent Python-only path.

## Internal Ecosystem Components

Initial reuse candidates include:

- `reimbursement-atlas` source contracts, terminology adapters, evidence readiness, publication gates, GitHub synchronization, Mojo/Python parity, and research-package outputs;
- `nzmedicines` NZULM/NZMT FHIR resources, relationship indexes, and projection rationale;
- `mchs` Rust-core promotion, PyO3 bindings, cross-engine parity, Renovate, release, and multi-surface harness patterns;
- `riopa-infrastructure` requirements, design, provenance, release-evidence, and Conductor conventions;
- `rareburden-commons` MoSCoW traceability, public-data governance, and release-gate conventions;
- `new-drug-reimbursement-game`, UOGTO, Kairos, and VOIAGE interfaces for reimbursement, uncertainty, and value-of-information analysis;
- existing Hugging Face and archive workflows for Parquet, Croissant, Xet, dataset cards, persistent identifiers, and publication verification.

Reuse requires contract and licence review. Repository existence alone is not evidence that a capability is current, complete, or suitable.

## Rust-Based Extension Policy

Rust components are appropriate where they provide a measured capability that Mojo, Python, Polars, DuckDB, or LanceDB do not already provide cleanly.

- Use PyO3 and Maturin for any promoted Rust-to-Python extension.
- Require shared fixtures, Python reference behavior, cross-engine parity, benchmarks, and explicit promotion evidence before a Rust implementation becomes authoritative.
- Do not duplicate the same performance kernel independently in Mojo and Rust without a documented boundary and benchmarked reason.
- Keep Arrow and Parquet as the interchange boundary for zero-copy or low-copy movement where practical.

### Candidate Rust Components

- Apache DataFusion is an evaluation candidate for embeddable Rust-native query plans, custom operators, streaming execution, or a future Rust service. DuckDB remains the primary local analytical engine until a benchmarked requirement demonstrates otherwise.
- Tantivy is an evaluation candidate for deterministic lexical retrieval across medicine names, brands, ingredients, identifiers, and source text. It complements rather than replaces LanceDB semantic retrieval.
- Qdrant Edge or Qdrant service is an evaluation candidate if LanceDB no longer satisfies embedded concurrency, filtering, service deployment, or scale requirements.
- `delta-rs` is a future candidate if transactional object-store tables and concurrent writers become approved requirements.
- Existing Rust-backed tools and libraries—including Polars, Pydantic Core, orjson, uv, Ruff, `ty`, and selected security/build tooling—should be preferred where they satisfy the required contract through stable Python or command-line interfaces.

### Selection Rule

Every candidate must pass an architecture decision record covering:

- The unmet requirement.
- Alternatives considered.
- Benchmark and profiling evidence.
- Operational and supply-chain cost.
- Python 3.14 and Mojo compatibility.
- Data portability and regeneration.
- Fallback and migration behavior.
- Harness and CI implications.

## Static Typing

- Use `ty` as the fast routine type-checking lane for local development and ordinary pull-request feedback.
- Use BasedPyright as the formal, stricter type-analysis lane for protected-branch and release readiness.
- Keep both configurations explicit and version-controlled.
- Treat disagreements between the two tools as visible compatibility findings; do not silently suppress them.
- Require public Python interfaces, canonical models, source contracts, and matching interfaces to satisfy the formal typing lane.

## Application Surfaces

- A typed CLI is the first operational interface.
- A read-only API may be added using FastAPI when required by an approved track.
- An MCP surface may be added as an optional adapter over reviewed read-only capabilities.
- A static or server-backed web atlas may be added as a separate application package.
- Public interfaces must expose provenance, dates, coverage, uncertainty, and evidence status.

## Repository Shape

- Maintain a single-developer monorepository.
- Use `src/` layout for the Python package.
- Keep Mojo kernels in a dedicated package/module tree with shared contract fixtures.
- Separate source acquisition, canonical models, matching, analytics, publication, and user interfaces.
- Keep generated artifacts distinguishable from authored source.
- Keep raw, local-only, licensed, sensitive, and public-release data in explicitly separated zones.

## Quality Harness

The harness should provide independently executable lanes for:

- Formatting and linting.
- Routine static typing with `ty`.
- Formal static typing with BasedPyright.
- Unit tests as the fastest behavioral layer.
- Integration tests across storage, source adapters, schemas, and language boundaries.
- End-to-end tests covering complete user-visible workflows.
- Smoke tests for installation, CLI, data access, and deployed surfaces.
- Property-based tests for parsers, normalization, matching, schemas, and round trips.
- Mutation testing with bounded timeouts and a recorded mutation score.
- Fuzz and malformed-input tests.
- Golden and negative-control fixtures.
- Mojo/Python parity tests.
- Deterministic regeneration checks.
- Schema and contract validation.
- Source content and schema-drift checks.
- Matching calibration and holdout evaluation.
- Performance benchmarks and regression budgets.
- Scalene profiling for Python CPU, memory, and allocation hotspots.
- Coverage reporting with a blocking threshold strictly greater than 90% for governed core code.
- Codecov uploads, pull-request annotations, flags by test lane, and protected-branch coverage gates.
- Documentation freshness and public-claim validation.
- Licence, provenance, privacy, and publication-boundary checks.
- Release reproducibility and consumer-side attestation verification.

### Test-Goblin Profile

Reuse the maintainer-owned `test-goblin` compatibility profile established in
`reimbursement-atlas`:

- Hypothesis for generative and property-based testing.
- mutmut for bounded mutation testing and mutation-score evidence.
- pytest-randomly for order-sensitivity and hidden-state detection.

Expose this as a PEP 735 dependency group named `test-goblin`. It augments the
pytest foundation and does not replace unit, integration, end-to-end, smoke,
parity, or coverage lanes. If a maintained dedicated goblin package emerges,
evaluate it through the frontier dependency process before adding it to this
profile.

## CI/CD

GitHub Actions should include:

- Pull-request and protected-main validation.
- CPython 3.14 locked-environment validation.
- Mojo stable validation on Linux.
- Mojo nightly compatibility canary with clearly classified blocking semantics.
- Platform-appropriate smoke testing.
- Separate unit, integration, end-to-end, smoke, property, parity, benchmark, profiling, and mutation lanes.
- A dedicated test-goblin lane combining Hypothesis, mutmut, and pytest-randomly.
- A fast `ty` lane and a formal BasedPyright lane.
- Coverage generation above 90% and Codecov upload/status enforcement.
- CodeQL, secret scanning, dependency audit, and supply-chain checks.
- Actionlint and zizmor.
- Immutable commit-SHA pinning for GitHub Actions.
- Renovate dependency automation with policy-controlled grouping, lockfile maintenance, toolchain update rules, and scheduled compatibility branches.
- SBOM generation, provenance attestations, signed release inputs, and deterministic build verification.
- Dry-run-by-default external publication workflows.
- Explicit credential, licensing, human-review, and publication approval gates.

No green workflow may be treated as proof of an external publication unless the external artifact and durable receipt are independently observable.

## Conductor and GitHub Work Management

- Maintain `conductor/requirements.md` with uniquely identified MoSCoW requirements.
- Maintain `conductor/design.md` with Mermaid context, component, data-lineage, deployment, and work-lifecycle diagrams.
- Maintain a traceability map from requirements to designs, Conductor tracks, GitHub issues, tests, and release evidence.
- Give each track an index, specification, implementation plan, metadata, and evidence ledger.
- Create one GitHub parent issue per Conductor track.
- Create task subissues for actionable plan items.
- Maintain bidirectional references between issues and track files.
- Validate synchronization in the local harness and CI.
- Use structured issue forms and a project label taxonomy.
- Reuse the dry-run-by-default issue/project synchronization and generated-output validation patterns from `reimbursement-atlas`.

## Single-Developer Governance

- Optimize automation for one accountable maintainer.
- Do not invent independent reviewers or approvals that do not exist.
- Preserve explicit human gates for licensing, sensitive data, credentials, public release, and consequential interpretation.
- Record unresolved external dependencies as blockers rather than treating them as completed.
- Keep branches, commits, pull requests, issues, and Conductor evidence linked to observable outcomes.
- Use the Rust promotion and cross-engine parity pattern demonstrated in `mchs`: retain the reference implementation until fixtures, bindings, performance evidence, and release gates justify promotion.

## Hugging Face Outputs

- Plan a governed Hugging Face dataset for reviewed, redistributable NZULM and global medicines comparison outputs.
- Publish Parquet-based tables with explicit configs or splits for source registry, medicines, products, regulatory assertions, funding assertions, mappings, coverage, and provenance where licensing permits.
- Include a complete dataset card, Croissant metadata, schema and data dictionary, source and licence matrix, retrieval dates, checksums, coverage metrics, limitations, and citation metadata.
- Keep restricted or non-redistributable source bytes out of public artifacts while publishing lawful manifests and derived evidence where allowed.
- Validate the Dataset Viewer, Parquet exports, card metadata, licensing metadata, and destination identity before claiming publication.
- Treat the existing `edithatogo/reimbursement-atlas` Hugging Face dataset as a placeholder until it contains reviewed data and complete metadata; it currently must not be cited as a substantive dataset output.
- Mirror an approved read-only atlas to a Hugging Face Space only after data, provenance, accessibility, licensing, and release gates pass.
