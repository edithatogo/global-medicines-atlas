# Offline MBS schema-profile consumer

`read_mbs_schema_profile` checks an already-decoded Arrow RecordBatch against
an explicit expected comparison profile, target table and caller-supplied B1
receipt. It reuses the producer's exact schema, metadata, receipt/revision and
per-row B1/B2 checks. It returns only an immutable declaration with status
`declared`; it does not return batch content or change native fields, metadata,
dates or existing release labels. Unknown declaration versions are rejected.

Declaration bytes are limited to 40 KiB before JSON parsing. A lexical preflight
rejects nested objects and arrays before parsing; duplicate keys, missing/extra
fields and non-integer version tags are rejected. Batch limits are 4,096 rows
and 16 MiB Arrow `nbytes`, with at most 64 metadata entries totalling 256 KiB.
These bounds precede lineage materialization; they are not process-memory or
Parquet-decoder limits. Callers must independently bound decoding and acquisition.

Empty batches still require the exact schema, metadata and receipt bindings;
there are no row lineage observations in an empty batch. Neither empty nor
nonempty results establish source completeness, native-value authenticity or
independent schema qualification. Matching self-supplied metadata and receipts
can satisfy these consistency checks. No date convention is inferred.

This helper performs no filesystem/network I/O or publication. Receipt-byte
closure does not make the declaration trusted. Federation v4 admission, rights,
trusted qualification, versioned profile export and historical-cohort support
remain separate; old v4 records and published Parquet are not rewritten.
