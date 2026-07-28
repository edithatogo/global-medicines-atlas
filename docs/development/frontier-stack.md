# Frontier data and runtime stack

The executable baseline is deliberately polyglot but layered:

- Pydantic v2 owns strict domain and settings validation.
- PyArrow owns versioned in-memory and Parquet interchange schemas.
- Polars is the default Rust-native dataframe engine.
- DuckDB is the embedded SQL and coverage-analysis engine.
- LanceDB is installed for regenerable semantic candidate indexes; it must not
  become an authoritative medicine-equivalence store.
- Mojo is locked through Pixi for future measured kernels. Python 3.14 remains
  the complete reference and fallback.

`pixi.lock` currently resolves the Linux Mojo nightly and Python toolchains.
The Mojo CI canary is intentionally non-blocking until a kernel has shared
golden fixtures and Python parity. Python-only development remains available
through `uv`.

## Frontier validation

```console
uv run python scripts/test_goblin.py routine
uv run python scripts/test_goblin.py strict
uv run python scripts/test_goblin.py gremlins
uv run python scripts/test_goblin.py dependencies
pixi run mojo-check
```

Pytest-gremlins is a second mutation engine, not an alias for the repository's
Test-Goblin profile. Edgetest creates isolated environments and upgrades the
Pydantic contract pair and Arrow/Polars/DuckDB data stack independently.

Nightly and experimental dependencies remain subject to lockfile review,
Renovate, compatibility evidence, and rollback. A dependency is not promoted
merely because it resolves.
