# Specification: federated medallion frontier experiments

## Objective

Evaluate high-value preview and bleeding-edge capabilities made relevant by the
public Hugging Face data plane and Australian MBS/PBS graph scope. Experiments
produce reproducible decision evidence; none becomes a production dependency,
medallion authority, or completion gate without a separate promotion decision.

## Reuse baseline

Reuse the archived `datahouse_interoperability_experiments_20260820` and
`free_tier_datahouse_decision_evidence_20260821` fixtures, budgets, and findings.
Do not repeat bounded Iceberg, DuckLake, Delta, Hudi, or batch-attestation work
unless the public remote-data workload changes the decision input.

## Experiment families

### Remote query and streaming

- DuckDB HTTP/HF Parquet range scans with predicate/projection pushdown.
- Polars lazy/streaming scans over immutable HTTP or `hf://` objects.
- Arrow streaming and bounded local spill/cache behavior.
- DataFusion only where a Rust-native service/custom-operator need is measured.
- Cold, warm, concurrent, interrupted, offline, and high-latency profiles.

### Hugging Face object mechanics

- Xet-aware chunk reuse and content-defined deduplication across historical
  MBS/PBS releases without treating storage chunks as source identity.
- Resumable large-object restore, range behavior, cache validation, and
  anonymous access at pinned revisions.
- Immutable manifest resolution across collection and dataset moves.

### Catalogue interoperability

- Iceberg REST registration over public Hub Parquet and v4 identities.
- Iceberg v3 features only when the pinned Python 3.14-compatible stack supports
  them; degraded results remain explicit.
- Branch/tag/snapshot aliases bound to GMA acquisition IDs, never replacing
  payload/receipt provenance.

### Attestation and research packaging

- Merkle/batch manifests additive to per-object SHA-256.
- RO-Crate and Croissant packages spanning raw, Silver, Gold, and Platinum
  public datasets without duplicating restricted data.
- OpenLineage federation events across GMA, GitHub Actions, Hugging Face, and
  reimbursement-atlas with pinned schema URLs and v4 facets.
- Optional Sigstore/in-toto/SLSA attestations where free-tier identities and
  verification are durable and non-circular.

### Graph and semantic preview

- NetworkX reference graph plus Neo4j/Cypher, RDF-star/SPARQL, and compact
  property-graph exports from the same Gold node/edge tables.
- Lexical, ontology-assisted, and embedding/NLP candidate retrieval with
  calibration, negative controls, model cards, and review queues.
- LanceDB remains the default derived semantic index; Qdrant/Tantivy or another
  engine requires a measured gap.
- No restricted SNOMED CT-AU/AMT vocabulary bytes enter public experiments.

### Transactional and operational alternatives

- DuckLake, Delta Lake, and Hudi are revisited only with a measured
  multi-writer/high-update requirement.
- lakeFS or object-version workflows are evaluated only after an approved
  durable independent replica exists.
- No mandatory distributed service is introduced for workloads satisfied by
  embedded remote-query tools.

## Evaluation contract

Each experiment records:

- hypothesis and unmet requirement;
- exact public dataset/revision/path/digest and synthetic negative controls;
- baseline and candidate versions, environment, cold/warm state, and cache;
- correctness, parity, determinism, memory, latency, throughput, request/byte
  amplification, cost/free-tier consumption, security, and failure behavior;
- rights/sensitivity and data-exposure review;
- Python 3.14 fallback and rollback path;
- result: `promote-candidate | retain-preview | defer | reject` with thresholds;
  and
- non-promotion statement unless a separate ADR and production track accept it.

## Acceptance criteria

- **AC-01:** A versioned matrix maps every experiment to a measured requirement,
  reused prior evidence, dataset/revision, baseline, threshold, rollback, and
  final disposition; speculative rows without prerequisites fail closed.
- **AC-02:** Remote DuckDB/Polars/Arrow tests measure correctness, predicate and
  projection pushdown, request/byte amplification, bounded memory/cache, cold/
  warm/concurrent latency, interruption/resume, offline behavior, and parity.
- **AC-03:** Iceberg REST/v3 experiments register only rebuildable public
  Parquet metadata, preserve acquisition/payload identities, and document all
  compatibility degradation without changing core dependencies.
- **AC-04:** Merkle, RO-Crate, Croissant, OpenLineage, and optional attestation
  artifacts verify exact cross-dataset revisions and fail on mutation, missing
  object, reordered leaves, schema drift, or circular provenance.
- **AC-05:** Graph exports are deterministic projections of the same Gold
  tables; engine parity and query semantics pass, and no candidate or
  restricted terminology becomes authoritative/public by projection.
- **AC-06:** Xet/dedup experiments prove that optimization never changes source
  object identity, raw-byte restoration, or per-object digest evidence.
- **AC-07:** Security/threat, dependency/supply-chain, free-tier cost,
  operational burden, fallback, and deletion/withdrawal assessments accompany
  every promotion candidate.
- **AC-08:** No preview feature is promoted or made a required production
  dependency by this track; any promotion uses a separate accepted ADR, scoped
  implementation task, complete fallback, and required hosted checks.

## Dependencies and gates

- v4 identities and public datasets from
  `public_hf_federated_data_plane_20260829`.
- representative Silver/Gold/Platinum workloads from the corresponding tracks.
- Credentials, paid services, external catalogue deployment, public release,
  and technology promotion remain explicit gates.
