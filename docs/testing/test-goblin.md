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
`property`, and `edge` test lanes. Its `routine` quality lane consolidates
formatting, linting, import ordering, modernization, security-style checks,
pytest conventions, and fast typing into Ruff plus `ty`. The final `strict`
lane runs `basedpyright` strict mode. Full-project branch `coverage`, Linux
`mutation`, dynamic wheel/sdist `package`, and deterministic network-free
Scalene `profile` remain separate.

## Local Commands

```powershell
uv sync --python 3.14.6 --group test-goblin --locked
uv run --python 3.14.6 --group test-goblin python scripts/test_goblin.py quick
uv run --python 3.14.6 --group test-goblin python scripts/test_goblin.py coverage
uv run --python 3.14.6 --group dev python scripts/test_goblin.py routine
uv run --python 3.14.6 --group dev python scripts/test_goblin.py strict
uv run --python 3.14.6 --group dev python scripts/test_goblin.py package
uv run --python 3.14.6 --group dev python scripts/test_goblin.py profile
```

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

- Python 3.14.6 is selected by `.python-version` and enforced by the project
  metadata and CI commands.
- Property and randomized-order tests are blocking on pull requests.
- Bounded mutation tests run as a dedicated lane with explicit timeout and
  cancellation behavior.
- Mutation-score thresholds begin as measured evidence and become blocking once
  calibrated against the governed core.
- Coverage is independently blocking above 90% (currently 91%) for both project and patch
  coverage. Codecov uploads authenticate with GitHub OIDC.
- Scalene profiles are retained as CI artifacts for 14 days.
- Renovate groups frontier dependency updates, rate-limits pull requests,
  requires Dependency Dashboard approval for majors, and never automerges.

The initial governed NZ FHIR adapter suite is the first operational slice.
Additional source adapters enter the profile as their contracts are migrated.
