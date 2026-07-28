# Requirements Baseline

**Prioritisation:** MoSCoW  
**Scope:** Global medicines regulatory approval and public funding comparison system

## Must Have

### Canonical scope and evidence

- **M-001:** Represent regulatory approval and funding/reimbursement as distinct, independently sourced assertions.
- **M-002:** Preserve jurisdiction, authority, medicine/product granularity, indication or restriction scope, valid time, retrieval time, and source evidence.
- **M-003:** Represent missing, unknown, conflicting, not covered, and not applicable states distinctly.
- **M-004:** Maintain machine-readable source, licence, provenance, coverage, and transformation registers.
- **M-005:** Prevent publication when required provenance, licensing, coverage, or uncertainty fields are absent.

### NZULM/NZMT foundation

- **M-010:** Treat NZULM/NZMT as a first-class source family.
- **M-011:** Preserve NZMT hierarchy levels, native identifiers, relationships, labels, dosage forms, strengths, routes, GTINs, pharmacodes, ATC and SNOMED CT mappings where present.
- **M-012:** Preserve Medsafe regulatory assertions separately from PHARMAC funding assertions.
- **M-013:** Support validated FHIR projections using Medication, MedicationKnowledge, Organization, Substance, and Provenance resources.
- **M-014:** Validate all NZ-specific FHIR extensions and avoid unsupported registry or standards claims.

### nzmedicines consolidation

- **M-020:** Import every relevant `edithatogo/nzmedicines` artifact into a non-overlapping NZ adapter and fixture boundary.
- **M-021:** Preserve the complete upstream Git history and source commit identifiers.
- **M-022:** Reconcile upstream artifacts against richer local NZULM files without overwriting local changes.
- **M-023:** Record a file-level disposition: adopted, adapted, superseded, retained as fixture, or excluded with reason.
- **M-024:** Maintain migration notices and a compatibility-mirror plan.
- **M-025:** Link migration requirements, design decisions, Conductor tasks, GitHub issues, tests, and evidence.

### Global data platform

- **M-030:** Use Parquet and Arrow-compatible schemas as portable canonical tabular representations.
- **M-031:** Use DuckDB as the primary embedded analytical engine while retaining reproducibility from portable artifacts.
- **M-032:** Use Polars as the default lazy, streaming dataframe layer.
- **M-033:** Use LanceDB only as a regenerable derived semantic/vector index.
- **M-034:** Provide versioned source-adapter contracts and jurisdiction onboarding templates.
- **M-035:** Quantify country, source, medicine, assertion-type, and temporal coverage.

### Runtime and quality

- **M-040:** Implement performance-critical kernels Mojo-first with a complete Python 3.14 reference fallback.
- **M-041:** Require parity fixtures before Mojo or Rust implementations become authoritative.
- **M-042:** Run unit, integration, end-to-end, smoke, property-based, mutation, and parity testing.
- **M-043:** Maintain test coverage strictly above 90% for governed core code and enforce it through Codecov.
- **M-044:** Use `ty` for routine typing and BasedPyright for formal typing.
- **M-045:** Use Scalene and benchmark evidence before promoting performance implementations.
- **M-046:** Use Renovate for grouped dependency and toolchain updates.
- **M-047:** Maintain a machine-readable internal ecosystem registry covering reusable maintainer-owned packages, schemas, adapters, fixtures, workflows, publication tools, and compatibility contracts.
- **M-048:** Search and assess the internal ecosystem before approving a new implementation or third-party abstraction.
- **M-049:** Isolate legacy dependencies behind explicit compatibility adapters with evidence-backed retirement plans.
- **M-054:** Provide a `test-goblin` dependency and CI profile using Hypothesis, mutmut, and pytest-randomly.
- **M-055:** Apply test-goblin to high-risk parsers, normalizers, mapping logic, provenance/licence gates, and deterministic generators.

### RxNav/RxNorm

- **M-050:** Provide an operational tiered RxNorm resolver with an offline local
  fixture or extract and an optional RxNav-compatible HTTP adapter; a complete
  RxNav-in-a-Box deployment is not mandatory.
- **M-051:** Provide fixture lifecycle, read-only client contracts, timeout and
  availability behavior, offline tests, and optional health checks for a
  configured local service.
- **M-052:** Preserve RxNorm licensing and local-only boundaries and never publish restricted source payloads by implication.
- **M-053:** Provide deterministic fallback behavior when the local RxNav service is unavailable.

### CI/CD and release

- **M-060:** Use SHA-pinned GitHub Actions with actionlint, zizmor, CodeQL, secret scanning, dependency audit, SBOM, and provenance attestations.
- **M-061:** Keep external publication workflows dry-run by default and explicitly gated.
- **M-062:** Generate reproducible release artifacts and consumer-verifiable attestations.
- **M-063:** Maintain one GitHub parent issue per Conductor track and linked subissues for actionable tasks.
- **M-064:** Register jurisdiction adapters independently from their ingestors,
  require a regulatory source contract, and model funding and formulary sources
  as separate dimensions.
- **M-065:** Begin global onboarding with NZ, Australia, the United States,
  United Kingdom, Canada, Japan, and the European Union while reporting source
  and ingestion coverage honestly.
- **M-066:** Maintain a machine-readable, date-reviewed catalog of authoritative
  APIs, bulk downloads, searchable registers, and licensed feeds, including
  access mode, cadence, rights status, readiness, and evidentiary limits.
- **M-067:** Use a repeatable jurisdiction-census process based on WHO
  regulatory-authority coverage and national health-technology assessment or
  reimbursement authorities; never claim the catalog is globally complete
  without a measured denominator and review date.

## Should Have

- **S-001:** Evaluate Apache DataFusion for measured Rust-native query or streaming requirements without displacing DuckDB prematurely.
- **S-002:** Evaluate Tantivy for deterministic lexical medicine retrieval alongside LanceDB semantic retrieval.
- **S-003:** Evaluate Qdrant when embedded concurrency, filtering, or service scale exceeds LanceDB requirements.
- **S-004:** Publish lawful reviewed datasets to Hugging Face with Parquet, Croissant, data cards, coverage, licence, provenance, and citation metadata.
- **S-005:** Provide a read-only global comparison API and accessible atlas.
- **S-006:** Support historical snapshots and bitemporal regulatory/funding assertions.
- **S-007:** Map jurisdiction-native concepts to canonical identifiers while retaining original terminology.
- **S-008:** Promote reusable capabilities into maintainer-owned packages when at least two repositories need the same stable contract.
- **S-009:** Maintain cross-repository compatibility canaries for shared frontier libraries and toolchains.

## Could Have

- **C-001:** Use `delta-rs` if approved requirements introduce concurrent transactional object-store tables.
- **C-002:** Provide an optional MCP read-only adapter.
- **C-003:** Provide multilingual labels and jurisdiction-specific policy briefs.
- **C-004:** Add scheduled source-health and schema-drift monitors with issue escalation.
- **C-005:** Add a Qdrant service deployment after benchmarked need is demonstrated.

## Won't Have in the Initial Increment

- **W-001:** Individual clinical advice or prescribing recommendations.
- **W-002:** Claims of therapeutic equivalence based only on cross-jurisdictional matching.
- **W-003:** Redistribution of restricted source data without a recorded lawful basis.
- **W-004:** Claims of global coverage without measured jurisdiction and source coverage.
- **W-005:** A mandatory distributed database or service when embedded portable tools satisfy the requirement.
- **W-006:** Removal or archival of `nzmedicines` before migration verification and compatibility notice review.
