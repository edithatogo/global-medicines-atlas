# Bronze: content-addressed receipts and partitioned Parquet landing

Conductor: `conductor/tracks/bronze_medallion_completion_20260819/`

GitHub: parent [#167](https://github.com/edithatogo/global-medicines-atlas/issues/167),
phase [#169](https://github.com/edithatogo/global-medicines-atlas/issues/169)

Requirements: M-002, M-030, M-094, M-097

Write failing tests, then implement bronze landing as partitioned Arrow/Parquet
with content-addressed receipts, source-native identifiers, provenance, dates,
rights, and uncertainty. DuckDB and LanceDB remain derivatives, not bronze.
