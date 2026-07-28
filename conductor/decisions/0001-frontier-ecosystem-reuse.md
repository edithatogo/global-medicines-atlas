# ADR 0001: Frontier Ecosystem Reuse

**Status:** Accepted  
**Date:** 2026-07-27

## Context

The maintainer operates related repositories, datasets, publication systems, schemas, adapters, and analytical tools. References to those repositories are intended to align this project with that ecosystem, not merely imitate their directory structures.

The project must avoid rebuilding capabilities the maintainer already owns and allowing historical dependencies to prevent adoption of the current supported frontier.

## Decision

The project will:

- search the maintainer-owned ecosystem before designing new components;
- reuse, evolve, and package maintainer-owned work where contracts fit;
- standardize shared libraries and workflows at the current evidence-backed frontier;
- use compatibility canaries, locks, benchmarks, parity fixtures, and rollback plans for rapidly evolving dependencies;
- isolate legacy dependencies behind explicit adapters;
- document retirement conditions for temporary compatibility code;
- use third-party foundational libraries when recreating them would not add distinctive value.

## Consequences

- Cross-repository discovery and compatibility become normal planning tasks.
- Reused components retain repository, commit, version, licence, and provenance.
- Stable shared capabilities may move into maintainer-owned packages.
- Legacy behavior remains testable without dictating the canonical architecture.
- Frontier updates can be adopted quickly when automated evidence and recoverable locks exist.

## Decision Test

1. Does the maintainer already own a suitable implementation or contract?
2. Can it be reused or evolved without inappropriate coupling?
3. Is the selected third-party dependency the current supported frontier?
4. What compatibility, benchmark, and rollback evidence exists?
5. Which legacy consumers require an adapter, and when can it be retired?
