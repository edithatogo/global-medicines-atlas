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
  immutable reference when bytes cannot lawfully be retained.

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
