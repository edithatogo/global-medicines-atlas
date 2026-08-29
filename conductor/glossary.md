# Global Medicines Atlas Glossary

## Evidence and medallion terms

Bronze comprises three internal Bronze strata, not additional medallion levels.

- **B0 Source Index** — the versioned index of agencies, datasets, APIs, and
  source surfaces; indexing does not imply acquisition, coverage,
  qualification, or currency.
- **B1 Acquisition Metadata** — append-only acquisition events, receipts,
  temporal identity, rights state, reuse decisions, HTTP or other retrieval
  evidence, admission state, and provenance relationships. These native
  records are authoritative; the deterministic acquisition manifest is a
  rebuildable query projection, while OpenLineage and table catalogues are
  interoperability projections.
- **B2 Raw Evidence** — immutable source-native bytes, or a rights-constrained
  immutable reference when bytes cannot lawfully be retained. Its machine
  states are `retained`, `external_reference_only`, and `blocked`; the latter
  two never fabricate payload bytes. Archive-member and document manifests are
  byte-level projections over B2, while text extraction and semantic
  interpretation are derived processing.

**Source-native record projection** is an optional Bronze product emitted by an
explicit parser that preserves source record granularity, native columns, and
identifiers. It is separate from the B1 acquisition manifest and must not
contain Silver harmonisation or lossy binary-to-text decoding.

Source-faithful Parquet, archive-member manifests, OpenLineage, Iceberg,
DuckDB, and other query/catalogue objects are rebuildable Bronze projections
over B1/B2, not a fourth evidentiary source of truth. Silver remains
source-faithful typed or harmonised structures; Gold remains
cross-jurisdiction matched evidence; Platinum remains products and
presentation.

**Acquisition** means a bounded retrieval attempt and its B1 evidence. It does
not by itself mean acceptance, source coverage, qualification, or publication.

**Coverage** is a measured statement over an explicit source, jurisdiction,
time, and evidence dimension. Missing coverage is not negative evidence.

**Projection** is a deterministically rebuildable representation over B1/B2.
It may improve portability, lineage, cataloguing, recovery, or query access,
but it does not supersede the acquisition history or raw-evidence identity.

**Health-service-benefit assertion** is an MBS-native statement about a
service item, group, fee, benefit, participant measure, restriction, or time.
It is independent of medicine regulatory, funding, formulary, terminology,
utilization, and clinical assertions.

**Public data plane** is the set of public Hugging Face dataset repositories
that durably hold publication-approved raw and derived objects at pinned
revisions. The content-addressed payload and receipt remain evidentiary truth;
the Hub catalogue and a local cache do not.

**Federation contract v4** is the additive distribution identity that binds a
repository authority and medallion object to its public dataset, immutable
revision, path, digest, visibility and anonymous verification, collection,
replica, schema era, comparison cohort, and cache lifecycle. It does not alter
the v1 layer/promotion, v2 field-lineage, or v3 backfill/replay vocabularies.
