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
- **M-033:** Keep LanceDB as an optional, regenerable derived semantic/vector
  index with explicit index/model identity, a core installation that does not
  require LanceDB, and deterministic fallback when the index is unavailable.
- **M-034:** Provide versioned source-adapter contracts and jurisdiction onboarding templates.
- **M-035:** Quantify country, source, medicine, assertion-type, and temporal coverage.

### Runtime and quality

- **M-040:** Evaluate performance-critical kernels Mojo-first with a complete
  Python 3.14 reference fallback; promote a Mojo kernel only after shared-fixture
  parity, representative performance and memory evidence, and fallback rehearsal.
- **M-041:** Require parity fixtures before Mojo or Rust implementations become authoritative.
- **M-042:** Run unit, integration, end-to-end, smoke, property-based,
  metamorphic, consumer/provider contract, deterministic-simulation, mutation,
  and parity testing.
- **M-043:** Maintain test coverage strictly above 90% for governed core code and enforce it through Codecov.
- **M-044:** Use `ty` for routine typing and BasedPyright for formal typing.
- **M-045:** Use workload-specific Scalene, cold/warm/concurrent benchmarks and
  immutable comparison receipts before promoting performance implementations.
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

- **M-060:** Use SHA-pinned GitHub Actions with actionlint, zizmor, CodeQL,
  repository/history secret scanning, dependency audit, SBOM, and provenance
  attestations; separately verify hosted secret scanning and push protection.
- **M-061:** Keep external publication workflows dry-run by default and
  explicitly gated; label qualification-only evidence so it cannot be mistaken
  for approved publication evidence.
- **M-062:** Generate reproducible release artifacts and consumer-verifiable
  attestations only for the exact governed bytes and approval state they claim.
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
- **M-068:** Maintain a machine-readable repository context manifest, root
  agent contract, context-drift validation, and durable CI receipt designed
  for one accountable maintainer without invented reviewer roles.
- **M-069:** Maintain a validated authority registry for relevant maintainer-owned
  GitHub and Hugging Face resources, requiring reuse-before-build dispositions,
  immutable GitHub snapshots, licensing gates, and non-overlapping capability
  ownership.
- **M-070:** Maintain an evidence-gated v0.1-to-v1.0 roadmap and machine-readable
  maturity model covering every blocking product dimension.
- **M-071:** Store regulatory and funding assertions bitemporally, preserving
  source-effective time, system-observation time, supersession and conflicts.
- **M-072:** Produce deterministic, confidence-scored cross-jurisdiction mapping
  candidates with explainable features, negative controls and adjudication state.
- **M-073:** Provide a versioned read-only API, CLI and accessible atlas that expose
  provenance, uncertainty, temporal scope and measured coverage.
- **M-074:** Generate governed Parquet, Croissant, data-card, citation, SBOM and
  provenance-attestation release artifacts without publishing by default.
- **M-075:** Monitor source availability, schema drift, data freshness and adapter
  health with bounded retries, provenance-bound monotonic baselines, durable
  receipts and actionable escalation.
- **M-076:** Enforce security, bounded-memory SQL keyset pagination, performance,
  compatibility, backup and recovery-point/recovery-time budgets before
  release-candidate promotion.
- **M-077:** Require clean-room reproduction, migration rehearsal, documentation,
  support and residual-risk evidence before stable v1.
- **M-078:** Maintain bidirectional traceability among releases, MoSCoW
  requirements, design components, Conductor tracks, GitHub parent/subissues,
  tests and evidence receipts.
- **M-079:** Keep repository governance as code and verify the hosted state:
  rulesets, least-privilege workflow permissions, merge policy, labels, project
  views, security features and maintainer bypasses must have dated evidence.
- **M-080:** Maintain a secure-development lifecycle covering threat modelling,
  dependency review, secret and code scanning, vulnerability reporting,
  incident handling, supply-chain attestations and time-bounded remediation.
- **M-081:** Maintain task-oriented contributor, operator, source-onboarding,
  architecture, data-rights, support, incident, recovery and research-
  reproduction documentation, with automated link, command, example and
  context-drift checks.
- **M-082:** Make the supported development and CI paths reproducible from
  locked dependencies, governed tool/runner versions and cached governed
  fixtures; network loss, rate limits and unavailable optional services must
  fail explicitly or degrade safely.
- **M-083:** Govern versions and releases with dynamic versioning, SemVer,
  changelog and citation metadata, an explicit software-licence decision,
  immutable release assets and a pre-publication qualification gate.
- **M-084:** Publish and validate a versioned international-source information
  schema that labels each resource's entities, information domains, status
  semantics, geographic and population scope, languages, available fields and
  change semantics without conflating regulatory and funding evidence.
- **M-085:** Evolve the canonical medicine model to represent substances,
  ingredients, medicinal products, packaged products, organisations,
  indications, populations, routes, strengths, quantities, prices, currencies
  and structured eligibility or restriction rules through typed relationships
  while retaining every source-native identifier and record.
- **M-086:** Provide bounded concept discovery by name, ingredient and
  jurisdiction-native identifier through the API, CLI and accessible atlas,
  with explicit canonical/native match explanations and stable pagination.
- **M-087:** Test core and optional-semantic variants of every distributable
  wheel and source archive from clean consumer environments and require package
  metadata, supported-platform policy, installation, reinstall, import, CLI,
  API, fallback and dynamic-version checks.
- **M-088:** Give each lawful public dataset a non-overlapping identity across
  GitHub, Hugging Face and Zenodo, including schema, licence, checksums,
  version, data card or protocol, persistent identifiers and provenance links;
  restricted medicine payloads must never be implied to be redistributable.
  OSF is deprecated and is not a live publication identity.
- **M-089:** Treat all acquired content as untrusted: enforce source-derived
  approved schemes and destinations, redirect-hop validation, connection binding
  or peer enforcement to a prevalidated public address, private-network rejection,
  bounded retries and concurrency, compressed and expanded size limits,
  archive/path safety, fail-closed parsing, quarantine, redacted security
  events and rehearsed compromise recovery.
- **M-090:** Make every cross-jurisdiction comparison declare entity granularity,
  indication and population scope, mapping relationship, source-native legal or
  funding status, normalization method, material mismatches and a validity state
  of `valid`, `valid_with_caveats`, `insufficient_evidence` or
  `inappropriate_comparison`; terminology similarity must never imply
  therapeutic equivalence, substitutability or equal benefit. These versioned
  runtime terms supersede the earlier draft labels partial, unavailable and
  inappropriate.
- **M-091:** Maintain a versioned research protocol and preregistration
  covering research questions, jurisdiction and source selection, inclusion and
  exclusion rules, outcomes, matching and adjudication, missingness and
  conflicts, planned and sensitivity analyses, amendments, deviations,
  software/data identities and reproducible execution.
  Phase 1 is governed by `schemas/academic-protocol-v1.json`, projected from
  `research/protocol/academic-protocol-v1.json`, and traced to GitHub [#67](https://github.com/edithatogo/global-medicines-atlas/issues/67).
  The persistent public identity is the in-repo protocol artefacts plus Zenodo
  DOI `10.5281/zenodo.21734811`. OSF is deprecated; historical OSF rehearsal
  packages remain in-repo as superseded artefacts and are not a live
  submission path.

### Medallion bronze (current horizon)

- **M-092:** Maintain an explicit medallion architecture (bronze, silver, gold,
  platinum) in which bronze evidentiary truth is the immutable source payload
  plus its content-addressed receipt: source-native identifiers, provenance,
  dates, rights, uncertainty, and independent temporal identity. Missing
  coverage is not negative evidence.
- **M-093:** Keep regulatory, funding, formulary, and terminology assertions
  independent in bronze; do not collapse those dimensions during landing.
- **M-094:** The immutable source payload and its content-addressed receipt are
  evidentiary truth; source-faithful Parquet is the portable analytical
  representation; table/catalogue layers are rebuildable metadata over those
  artefacts. DuckDB and LanceDB remain regenerable derivatives and are not
  bronze. Parquet is not raw-as-landed and is not bronze evidentiary truth.
- **M-095:** Complete bronze for current-scope public/no-credential catalog
  sources and already-governed fixtures. Credentialed, licensed-feed, and
  restricted-payload sources remain catalogued with explicit exclusion from this
  completion horizon. Python 3.14 remains the complete fallback. Credentials and
  restricted source bytes must never be inspected, committed, logged, or
  published.
- **M-096:** Treat Hugging Face as a bronze archive and output boundary, never
  as the source of truth or as an ingest origin for medicine payloads.
- **M-097:** Provide bleeding-edge bronze mechanics for in-scope public sources
  and governed fixtures: modern public ingest, content-addressed receipts,
  payload preservation, source-faithful Parquet, explicit licence and rights,
  deterministic regeneration, and schema-on-read where source schemas vary. This
  is a completed landing layer for current scope, not a prototype.
- **M-098:** Before any acquire or download, including Drugs@FDA, run a
  pre-acquisition reuse gate that searches local clones, maintainer GitHub
  repositories, Hugging Face (including
  `edithatogo/global-medicines-atlas-catalogue`), and the source registry
  (`medicine_source_catalog.json` / `.context/ecosystem.toml`), then explicitly
  choose one of reuse | link | mirror | extend | fork | acquire-new. Record the
  choice in receipts, OpenLineage, and track evidence. acquire-new is last
  resort. Acquisition without the gate fails.
- **M-099:** Distinguish source published/effective time, retrieved_at,
  valid_from/valid_to only where the source supplied them, and an immutable
  acquisition/version ID on every acquisition receipt. Missing published time
  stays missing and must not be filled from retrieved_at. The acquisition ID
  does not change when Parquet is regenerated.
- **M-100:** Project OpenLineage-compatible Datasets, Jobs, and Runs from
  native receipts using real OpenLineage field names. Payload datasets are not
  Parquet datasets. Receipts remain richer native provenance. Marquez is not
  part of the default install.
- **M-101:** Represent the source payload, source-faithful Parquet, and
  optional table/catalogue representation as distinct OpenLineage datasets
  linked by derivation (ColumnLineage) and alternative identity (Symlinks).
  Project acquisition identity, temporal identity, reuse disposition, rights
  state, and content digests into facets. Do not collapse payload identity
  into Parquet, Iceberg, or storage-table identity. Native receipts remain
  authoritative. Events must conform to the current OpenLineage RunEvent
  shape.

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
- **S-010:** Separate domain contracts, policy evaluation, storage/query
  adapters, transport, serialization and orchestration behind characterized,
  strictly typed boundaries without speculative micro-packages.
- **S-011:** Publish or refresh the lawful public bronze archive through the
  Hugging Face boundary once that archival path is available, without treating
  the remote dataset as authoritative.
- **S-012:** Measure bronze completeness by source identifier, jurisdiction,
  dimension, rights state, receipt class, and Parquet partition identity.
- **S-013:** Keep bronze Parquet Iceberg-ready with stable table identities,
  namespaces, schemas, partition specifications, append-only evolution rules,
  and snapshot-to-acquisition bindings so files can be registered in an Iceberg
  REST catalogue behind an optional extra. Iceberg is not mandatory. Parquet
  remains valid without Iceberg. Iceberg row lineage, branches, and tags are
  optional aliases; Atlas acquisition provenance remains authoritative. Do not
  migrate bronze evidentiary truth into Iceberg metadata. Python 3.14 core
  must not require Iceberg.

## Could Have

- **C-001:** Use `delta-rs` if approved requirements introduce concurrent transactional object-store tables.
- **C-002:** Provide an optional MCP read-only adapter.
- **C-003:** Provide multilingual labels and jurisdiction-specific policy briefs.
- **C-004:** Add scheduled source-health and schema-drift monitors with issue escalation.
- **C-005:** Add a Qdrant service deployment after benchmarked need is demonstrated.
- **C-006:** Record machine-readable contracts for silver, gold, and platinum
  layers without implementing those layers.

## Won't Have in the Initial Increment

- **W-001:** Individual clinical advice or prescribing recommendations.
- **W-002:** Claims of therapeutic equivalence based only on cross-jurisdictional matching.
- **W-003:** Redistribution of restricted source data without a recorded lawful basis.
- **W-004:** Claims of global coverage without measured jurisdiction and source coverage.
- **W-005:** A mandatory distributed database or service when embedded portable tools satisfy the requirement.
- **W-006:** Removal or archival of `nzmedicines` before migration verification and compatibility notice review.
- **W-007:** Implement silver, gold, or platinum transformation, matching, or
  serving layers in this bronze-completion horizon.
- **W-008:** Expand bronze-completion work to credentialed, licensed-feed, or
  restricted-payload sources in this horizon.
