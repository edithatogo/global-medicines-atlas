# Repository Improvement Audit — 2026-07-29

This audit reconciles repository findings into the active Conductor tracks.
It is planning evidence, not proof that the listed controls or features are
implemented.

## Must

| Area | Finding | Conductor target | GitHub target |
|---|---|---|---|
| International sources | The source catalog does not label the information each resource contains. | M-084; operational Phase 1 | #36, #37 |
| Product model | The canonical model cannot yet represent the full product, package, indication, price and structured-restriction contract. | M-085; stable Phases 1–2 | #40–#42 |
| Discovery | Users must already know a canonical concept ID. | M-086; stable Phases 1–2 | #40–#42 |
| Adapter architecture | Declarative adapters, parsers and census capabilities can diverge. | Operational Phases 1–2 | #37, #38 |
| Query scale | Pagination and filtering can materialize broad result sets in Python. | Operational Phases 1–3 | #37–#39 |
| Test completeness | Manually maintained Test-Goblin paths exclude four test files and duplicate others. | Operational Phases 1–2 | #37, #38 |
| Qualification evidence | Mutation and performance lanes lack blocking numeric budgets and durable receipts. | Operational Phases 1–3 | #37–#39 |
| Distribution | Built artifacts are not installed and exercised in a clean consumer environment. | M-087; stable Phases 1–2 | #41, #42 |
| Licensing | The repository has no selected software licence and package metadata is incomplete. | M-083, M-087; stable Phases 1 and 3 | #41, #43 |
| Documentation | Consumer installation, first query, API/CLI, schema, maturity and reproducibility guidance is incomplete. | M-081, M-087; stable Phases 1–2 | #41, #42 |
| Publication identity | Candidate datasets and the research protocol need separate lawful identities and persistent links. | M-088; stable Phases 1–3 | #41–#43 |
| Hosted governance | Committed declarations are not evidence of live rulesets or security settings. | M-079; operational Phase 3 and stable Phase 3 | #39, #43 |
| Acquisition security | Official downloads remain untrusted; destination, redirect, DNS/IP, decompression, extraction, parsing and compromise-recovery controls require explicit policy and negative evidence. | M-089; operational Phases 1–2 and stable Phase 2 | #37, #38, #42 |

## Should

- Standardize parser streaming and resource ceilings, archive/XML/CSV hostile
  input handling and acquisition trust boundaries.
- Use Codecov contexts or flags for unit, integration, end-to-end, property and
  edge evidence while retaining global and patch thresholds.
- Align `ty` and BasedPyright scope deliberately and narrow broad Ruff test
  exemptions over time.
- Maintain blocking stable dependency canaries and non-blocking prerelease or
  nightly canaries, including Mojo parity evidence.
- Add consistent CycloneDX and SPDX SBOM validation, source-health history,
  structured logging/redaction tests and scheduled dry-run release rehearsal.
- Publish only the lawful source catalog and synthetic matching benchmark after
  separate licence, data-card, Croissant and identifier review.

## Could

- Evaluate DataFusion and Tantivy only against representative measured
  workloads; retain DuckDB and the existing retrieval design unless evidence
  demonstrates a material benefit.
- Add bounded parser fuzzing, OpenSSF Scorecard, artifact attestations,
  multilingual discovery and a read-only MCP façade after the Must gates.

## Traceability

The authoritative task detail is in:

- `conductor/tracks/operational_hardening_20260729/plan.md`;
- `conductor/tracks/stable_v1_qualification_20260729/plan.md`;
- GitHub parents #36 and #40 and their native subissues #37–#39 and #41–#43.

GitHub issue-body synchronization was attempted on 2026-07-29 but the installed
integration returned `403 Resource not accessible by integration`; direct
GitHub access also timed out. Hosted issue updates therefore remain unverified
and must not be inferred from this local reconciliation.
