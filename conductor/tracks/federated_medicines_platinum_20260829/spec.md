# Specification: federated medicines Platinum products

## Objective

Deliver useful Platinum products over governed Gold evidence without requiring
users or maintainers to operate a durable local data lake. GMA remains the
canonical product/control plane; public Hugging Face datasets provide immutable
raw and derived data identities; reimbursement-atlas and other repositories
consume stable contracts as federated clients.

## Product surfaces

### CLI

Extend the typed CLI to:

- list public datasets, exact revisions, schema eras, and coverage;
- query MBS service items, fees/benefits, PBS medicines/items/restrictions, and
  reviewed relationship edges;
- compare legacy/current snapshots and two arbitrary effective cohorts;
- explain provenance, field lineage, confidence, review, rights, and cache
  state for any row or edge;
- download/stream a bounded selected partition with digest verification; and
- export reproducible Parquet/CSV/JSON/graph packages with manifest and citation.

### Read-only API

Expose versioned endpoints for source, service, medicine, evidence edge,
historical change, coverage, provenance, dataset identity, and health/freshness.
Pagination is bounded and deterministic. Every response declares entity
granularity, dimension, jurisdiction, source/effective time, retrieval time,
Hub revision, coverage state, and comparison validity.

### Atlas

Provide accessible, keyboard-operable views for:

- side-by-side MBS and PBS evidence without semantic collapse;
- item/service/medicine timelines and schema-era changes;
- evidence graph exploration with method/confidence/review filters;
- source availability, freshness, coverage, and missing-period warnings;
- provenance drill-down to the exact public raw object and receipt; and
- legacy-versus-current comparisons that label stale/superseded evidence.

### Research and compatibility exports

Publish content-addressed query snapshots, notebooks/examples that contain no
durable raw corpus, Croissant/RO-Crate/citations, and optional graph exports.
Provide compatibility contracts and canaries for reimbursement-atlas and the
archived donor repository successor links.

## Remote-first query architecture

The product resolves a v4 identity, verifies the manifest and revision, and
queries public Parquet through DuckDB/Polars with projection and predicate
pushdown where compatible. A bounded content-addressed cache records origin,
digest, created/last-verified time, expiry, maximum bytes, eviction, and offline
behavior. Cache misses or unavailable Hub objects produce explicit unavailable
states; they do not silently fall back to stale data.

Full downloads remain possible for reproducibility, but are optional and
verified. DuckDB files, web indexes, and graph stores are regenerable product
caches, not unique data authorities.

## Federation model

Federation means one declared authority per contract and dataset, not multiple
mutable copies:

- GMA owns the Australian source/medallion/product contracts.
- Public Hub repositories own immutable distribution identities for exact data
  objects.
- reimbursement-atlas consumes pinned data contracts for HEOR analysis and may
  expose compatibility views without republishing a divergent raw corpus.
- other repositories consume source/Gold/Platinum contracts through canaries.
- the public estate registry and collections provide discovery, not authority.

## Acceptance criteria

- **AC-01:** CLI, API, and atlas query pinned public Hugging Face revisions with
  no pre-existing local dataset and return deterministic results for MBS, PBS,
  edges, history, coverage, and provenance.
- **AC-02:** Every result exposes source/revision/path, entity granularity,
  semantic dimension, time, schema era, legacy/current state, coverage,
  uncertainty/confidence, review, and comparison-validity metadata.
- **AC-03:** Remote query uses projection/predicate pushdown and bounded caches;
  tests cover corrupt/changed manifests, partial reads, HTTP range failure,
  offline mode, stale cache, eviction, retry/rate limits, and oversized results.
- **AC-04:** Historical comparisons correctly distinguish additions,
  cessations, changes, missing snapshots, source outages, and schema drift and
  never infer a negative current status from absence.
- **AC-05:** The atlas is WCAG-conscious, keyboard-operable, non-color-only,
  responsive, and tested with representative assistive/accessibility tooling.
- **AC-06:** Reimbursement-atlas and donor-successor compatibility canaries use
  the v4 contract and detect revision/schema/semantic drift; no downstream
  consumer requires an unpinned mutable source.
- **AC-07:** Research/export packages are deterministic, content-addressed,
  cited, publicly available, and reproducible from the exact data-plane
  revisions without committing the data corpus to Git.
- **AC-08:** Load, concurrency, pagination, security, privacy, accessibility,
  OpenAPI, CLI, end-to-end, package, full harness where supported, hosted review,
  and evidence gates pass.

## Non-goals and human gates

- No clinical decision support, individual eligibility decision, therapeutic
  equivalence, or automated policy recommendation.
- No silent promotion of preview storage/query/graph technology.
- Public release/version promotion and consequential policy interpretation
  remain explicit maintainer gates even when implementation checks are green.

## Dependencies

- `public_hf_federated_data_plane_20260829`
- `australian_benefits_silver_gold_20260829`
- existing API/CLI/atlas, canonical model, comparison-validity, publication,
  source-health, and stable-v1 qualification contracts.
