# Quality frontier and hardening closure

This document reconciles issues [#80](https://github.com/edithatogo/global-medicines-atlas/issues/80), [#81](https://github.com/edithatogo/global-medicines-atlas/issues/81), and [#82](https://github.com/edithatogo/global-medicines-atlas/issues/82) against the current repository and hosted evidence.

## Repository-owned controls

The following controls are implemented and exercised:

| Control | Evidence | State |
|---|---|---|
| Property-based testing | `tests/test_metamorphic_testing.py`, Test-Goblin `property` lane | Qualified |
| Metamorphic testing | `tests/test_metamorphic_testing.py`, Test-Goblin `property` lane | Qualified |
| Contract testing | `tests/test_contract_testing.py`, OpenAPI semantic baseline | Qualified |
| Deterministic simulation testing | `tests/test_deterministic_simulation.py`, Test-Goblin `e2e`/unit coverage | Qualified |
| Mutation testing | Test-Goblin `mutation` profile and durable receipt artifact | Qualified |
| Code coverage | Test-Goblin coverage profile and Codecov OIDC upload | Qualified |
| Scalene profiling | Test-Goblin `profile` profile and durable receipt artifact | Qualified |
| Security and supply chain | CodeQL, Gitleaks, dependency audit/SBOM, dependency review, actionlint, zizmor | Qualified |
| Immutable workflow actions | Full commit-SHA pins in `.github/workflows/` | Qualified |
| Solo-maintainer operation | No mandatory human approval or CODEOWNERS review gate | Qualified |
| Main branch protection | Active ruleset `Protect main from destructive updates`, id `20156276` | Hosted setting observed |
| Context engineering | `AGENTS.md`, `SECURITY.md`, `CONTRIBUTING.md`, `scripts/validate_context.py`, Conductor autonomy policy | Qualified |

The techniques previously marked absent in the issue audit are therefore no
longer gaps. Their tests are deliberately bounded and do not claim live-source
or production qualification.

## Renovate boundary

The repository contains a Renovate configuration inheriting
`github>edithatogo/renovate-config`, with a Dependency Dashboard requested,
approval-gated updates, immutable GitHub Action pins, and no competing
Dependabot configuration.

Hosted Renovate installation, repository access, and a visible Dependency
Dashboard or first Renovate pull request are not verifiable from the current
repository checkout. That remains an external hosted-setting gate for #81,
not a reason to add a second update bot or weaken the dependency policy.

## Closure interpretation

- #80 repository-owned testing and CI/CD gaps: implemented and evidenced.
- #81 repository-owned security, context, solo-maintainer, and ruleset work:
  implemented and evidenced; Renovate hosted onboarding remains pending.
- #82 parent hardening work: repository controls are reconciled; the parent
  remains open until the Renovate hosted gate is independently evidenced.

No mandatory human approval gate, CODEOWNERS requirement, force-push bypass, or
competing dependency bot is introduced by this closure.
