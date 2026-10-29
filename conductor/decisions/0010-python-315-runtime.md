# ADR 0010: Python 3.15 runtime

## Decision

Use CPython 3.15.1 as the only active Python runtime across development,
builds, tests, helper scripts, containers, and CI. Keep project metadata,
dependency locks, setup commands, consumer probes, and protected check names
aligned to that exact qualified patch. Do not retain Python 3.14 as an active
fallback or compatibility runner.

Historical receipts and release evidence remain immutable and may identify the
Python version under which they were produced. Synthetic tests may exercise
older-version parsing only when that behavior is the explicit subject of the
test. These records do not make Python 3.14 an active runtime.

## Rationale

The repository now has a user-directed runtime requirement for Python 3.15.1.
A single supported version avoids split local/CI behavior and ensures the
current end-to-end, full-coverage, and consumer lanes qualify the runtime that
maintainers actually use.

## Qualification

The migration is complete only after the selected 3.15.1 interpreter is
verified in a repo-local environment, current dependencies pass the focused
and coherent full checks, project and auxiliary locks validate, helper-created
consumer environments verify their actual interpreter, and hosted CI passes
without an active 3.14 job. Any unsupported dependency remains an explicit
blocker; Python must not be downgraded to bypass it.

## Supersession

This decision updates the active runtime baseline in `conductor/tech-stack.md`,
`conductor/design.md`, and `conductor/requirements.md`. Versioned v0.5/v0.8
decision records and immutable qualifications retain their original runtime
claims as historical evidence.
