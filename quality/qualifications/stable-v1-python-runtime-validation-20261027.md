# Stable v1 Python runtime validation

The active project contract requires CPython 3.15.1 as the complete reference
runtime (`AGENTS.md`, `.context/project.toml`, and `conductor/tech-stack.md`).
The prior Stable v1 support register incorrectly retained a CPython 3.14
reference claim from older qualification evidence.

Exact-main Test-Goblin run
[`40495426213`](https://github.com/edithatogo/global-medicines-atlas/actions/runs/40495426213)
completed successfully on commit
`2851255c3bb6e3a4f9b7fc2cd7907cdf01a14bcd`. It ran on Python 3.15.1 and
qualified wheel and sdist consumer paths on Linux, macOS, and Windows. The
three platform consumer jobs passed, as did the routine, strict, integration,
end-to-end, unit, smoke, regeneration, coverage, mutation, property, edge,
package, and other applicable Test-Goblin jobs. The manual Apache Hudi preview
was skipped by design and is not part of the support contract.

Hosted job logs explicitly report `Using CPython 3.15.1` on Linux and macOS
and the CPython 3.15.1 interpreter path on Windows. The historical candidate
reproduction test was skipped because its retained receipt is pinned to
CPython 3.14.6. That is why this run verifies the active runtime and current
consumer paths but does not verify the historical candidate.

The run verifies the supported runtime and consumer matrix at this exact main
commit. It does not verify a Stable v1 release candidate, clear the Australian
federation gate, or authorize release.
