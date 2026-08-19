# Bronze: evidentiary payloads, temporal identity, and source-faithful Parquet

Conductor: `conductor/tracks/bronze_medallion_completion_20260819/`

GitHub: parent [#167](https://github.com/edithatogo/global-medicines-atlas/issues/167),
phase [#169](https://github.com/edithatogo/global-medicines-atlas/issues/169)

Requirements: M-002, M-030, M-094, M-097, M-099, M-100, S-013

The immutable source payload and its content-addressed receipt are evidentiary
truth; source-faithful Parquet is the portable analytical representation;
table/catalogue layers are rebuildable metadata over those artefacts.

Write failing tests, then preserve payload bytes, content-addressed receipts,
independent temporal identity, Iceberg-ready table identities, and OpenLineage
projection. DuckDB, LanceDB, and Iceberg remain derivatives, not bronze
evidentiary truth.
