# Test-Goblin Compatibility Profile

This repository reuses the maintainer-owned test-goblin profile established in
`edithatogo/reimbursement-atlas`.

The profile now includes pytest-gremlins as a fast pytest-native mutation lane,
alongside the independent mutmut lane. Edgetest separately validates the newest
resolvable Pydantic and columnar dependency cohorts in isolated environments.

## Profile

The executable profile is declared as a PEP 735 dependency group in
`pyproject.toml`. Resolved versions are committed in `uv.lock`; the
tool-independent environment is exported to PEP 751 `pylock.toml`.

The harness exposes explicit `unit`, `integration`, `e2e`, `smoke`,
`property`, `metamorphic`, `contract`, `simulation`, and `edge` test lanes.
Metamorphic tests check relations between transformed inputs when a complete
oracle is impractical. Contract tests qualify versioned consumer/provider
boundaries. Deterministic simulation testing (DST) replays explicit event
schedules and clocks through operational state transitions. The `routine`
quality lane consolidates
formatting, linting, import ordering, modernization, security-style checks,
pytest conventions, and fast typing into Ruff plus `ty`. The final `strict`
lane runs `basedpyright` strict mode. Full-project branch `coverage`, Linux
`mutation`, dynamic wheel/sdist `package`, and deterministic network-free
Scalene `profile` remain separate.

Every collected test item receives exactly one generated primary marker from
the manifest in `scripts/test_goblin.py`. The `contracts` profile performs a
real `pytest --collect-only` pass and fails if an explicit primary marker
disagrees with the module's manifest lane. Other markers may describe secondary
traits but cannot create a second primary execution assignment.

The same `contracts` profile validates that the six primary CI lanes match the
harness,
that every lane uploads a distinct Codecov flag, that all external Actions use
full commit SHAs, and that workflow setup literals agree with
`quality/tool-versions.json`. These checks make CI topology part of the
executable harness rather than relying on workflow review alone.

Numeric promotion thresholds are machine-readable in `quality/budgets.json`
and constrained by `quality/budgets.schema.json`. Phase 1 deliberately labels
them `contract_only`: they define thresholds but do not claim that mutation or
representative-scale performance evidence has been collected. Later phases
must produce durable observations before using these contracts as promotion
evidence. Mutation and performance receipts are validated against
`quality/evidence-receipt.schema.json`. A `contract_only` receipt is forbidden
from carrying observations and cannot satisfy enforcement; a `measured`
receipt requires a commit, timestamp, and numeric observations. The mutation
and profiling lanes enforce supplied receipts through
`TEST_GOBLIN_MUTATION_RECEIPT` and `TEST_GOBLIN_PERFORMANCE_RECEIPT`
respectively, without manufacturing a receipt when none is supplied. Coverage
is already blocking and reads its threshold directly from the validated budget.
Measured receipts also bind the producing commit, command and SHA-256 identity
of every retained artifact. The Scalene lane writes its receipt automatically.
The Linux mutation lane invokes Mutmut's own `export-cicd-stats` command after
the run. It retains `mutants/mutmut-cicd-stats.json` as the authoritative raw
artifact and derives the measured receipt only from those numeric counts.
Missing, malformed, empty or non-numeric exports fail the lane; no environment
variable can substitute invented observations. The mutation budget remains
`contract_only` until calibration is formally promoted.

## Local Commands

```powershell
uv sync --python 3.14.6 --group test-goblin --locked
uv run --python 3.14.6 --group test-goblin python scripts/test_goblin.py quick
uv run --python 3.14.6 --group test-goblin python scripts/test_goblin.py contracts
uv run --python 3.14.6 --group test-goblin python scripts/test_goblin.py metamorphic
uv run --python 3.14.6 --group test-goblin python scripts/test_goblin.py contract
uv run --python 3.14.6 --group test-goblin python scripts/test_goblin.py simulation
uv run --python 3.14.6 --group test-goblin python scripts/test_goblin.py coverage
uv run --python 3.14.6 --group dev python scripts/test_goblin.py routine
uv run --python 3.14.6 --group dev python scripts/test_goblin.py strict
uv run --python 3.14.6 --group dev python scripts/test_goblin.py package
uv run --python 3.14.6 --group dev python scripts/test_goblin.py profile
```

The `package` profile builds both wheel and source distribution, installs each
into a disposable core-only Python 3.14 environment, verifies metadata and
dynamic version identity, exercises import/CLI/API/OpenAPI behavior, reinstalls
the artifact, and writes `build/quality-receipts/consumer.json`. CI repeats the
same rehearsal on Windows, Linux, and macOS with platform-specific receipts.

Run the mutation profile on Linux CI or in WSL:

```bash
uv run --python 3.14.6 --group test-goblin python scripts/test_goblin.py mutation
```

Mutmut 3 requires operating-system `fork` support and therefore cannot execute
on native Windows. The harness reports that boundary explicitly.

## Capability Mapping

| Capability | Tool |
|---|---|
| Test runner and fixtures | pytest |
| Generative/property tests | Hypothesis |
| Metamorphic testing | Hypothesis and explicit transformation relations |
| Consumer/provider contract testing | Versioned OpenAPI semantic snapshots |
| Deterministic simulation testing | Explicit clocks and replayable event schedules |
| Mutation testing | mutmut |
| Order-sensitivity detection | pytest-randomly |
| Parallel execution | pytest-xdist |
| Coverage and Codecov input | pytest-cov |
| Fast typing | ty |
| Formatting, linting, imports, modernization, and consolidated static checks | Ruff |
| Formal strict typing | basedpyright |
| CPU profiling | Scalene |
| Dependency maintenance | Renovate |

## Required Targets

- Source parsers and malformed-input handling.
- Medicine and product normalization.
- NZMT, RxNorm, ATC, SNOMED CT, identifier, and cross-jurisdiction mappings.
- Regulatory and funding assertion separation.
- Provenance, source-rights, and publication gates.
- Deterministic artifact and index generation.
- Mojo/Python and Rust/Python parity boundaries.

## CI Semantics

### Coverage and Codecov

- Python 3.14.6 is selected by `.python-version` and enforced by the project
  metadata and CI commands.
- Property, metamorphic, contract, deterministic-simulation and randomized-order
  tests are blocking on pull requests. The three specialized profiles are also
  independently executable; their modules run inside the primary property,
  unit and integration lanes respectively so existing protected-check names
  remain stable.
- Bounded mutation tests run as a dedicated lane with explicit timeout and
  cancellation behavior.
- Mutation-score thresholds begin as measured evidence and become blocking once
  calibrated against the governed core.
- Coverage is independently blocking above 90% (currently 91%) for both project and patch
  coverage. Every primary lane uploads an independently named, non-carryforward
  Codecov flag through GitHub OIDC, while the complete suite retains the `full`
  context.
- Scalene profiles are retained as CI artifacts for 14 days.
- Renovate groups frontier dependency updates, rate-limits pull requests,
  requires Dependency Dashboard approval for majors, coordinates governed
  Python, uv, Pixi, actionlint and Gitleaks literals, and manages the exact
  Mojo dependency through Pixi. Mojo updates run
  `scripts/update_mojo_contract.py VERSION`, which prepares a fresh Pixi lock
  and transactionally publishes the manifest, exact requirement, channel and
  lock. The Renovate bot must explicitly allow this post-upgrade command;
  otherwise the update fails closed for maintainer review. Gitleaks updates
  remain fail-closed until `scripts/update_gitleaks_contract.py VERSION`
  verifies the selected Linux x64 asset against the checksum manifest attached
  to the same official GitHub release and transactionally updates its
  digest-bound manifest/workflow contract.
  Governed multi-file updaters create and verify a predecessor safeguard for
  every target before publication. If publication and canonical rollback both
  fail, restoration is attempted for every replaced target and the raised
  `ContractUpdateError` exposes the retained, digest-verified recovery
  locations. Missing, unreadable, or digest-mismatched canonical files make
  the complete contract set incoherent; every verified predecessor safeguard
  is then retained. Safeguards are removed only after every canonical target
  is positively read and verified. Operators must restore those predecessors
  before accepting any partially published dependency contract.
  Renovate never automerges.
- A checksum-verified Gitleaks binary scans the complete Git history. Hosted
  checksum retrieval authenticates transport and the GitHub release location,
  but the upstream checksum manifest is not independently signed by this
  workflow; it is not equivalent to signature or attestation verification.
  Hosted
  GitHub secret scanning and push protection remain external controls requiring
  dated verification; workflow presence does not prove that they are enabled.

## Static-analysis scope

Ruff is the consolidated formatting and routine lint gate over the repository.
Its test exemptions are deliberate: pytest assertions, literal expectations,
and inferred fixture annotations remain executable specification rather than
production API documentation. Script `print` calls are allowed only where a
command-line script intentionally reports an artifact or status.

`ty` is the fast routine type gate for `src/` and `sources/`. BasedPyright is
the strict formal gate and additionally includes `scripts/`, where subprocess,
CLI and optional-tool boundaries require the more mature checker. This
asymmetry is intentional and executable in `pyproject.toml`; new production
packages must enter both scopes, while script inclusion in `ty` will be
promoted only after its Python 3.14 subprocess and dynamic-import behavior is
compatible.

The initial governed NZ FHIR adapter suite is the first operational slice.
Additional source adapters enter the profile as their contracts are migrated.
