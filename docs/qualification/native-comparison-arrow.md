# Native comparison Arrow candidate

`project_native_comparison` projects a revalidated native comparison into one
envelope table and an iterator of difference batches. It performs no file or
network access. Neither table grants source qualification, rights, admission,
publication authority, current-status claims or Gold promotion.

The envelope retains both complete input snapshots, including every native
occurrence on duplicate-identity abstention, all profiles, scope, source release
labels, B1/B2 digests, declared and actual row counts, completeness, outcome and
abstention reasons. Empty comparisons still have an envelope. Native timestamp
JSON strings retain precision and offsets. Nullable field structs distinguish
an absent field object from explicit missing, null and empty-string values.

The version-1 link digest hashes the domain prefix
`gma-native-comparison-arrow-v1` followed by a NUL and the validated comparison's
sorted-key, compact, UTF-8 JSON (non-ASCII characters are not escaped). It binds
declared input content, not independently verified source bytes. Ordinals retain
comparison order; no difference row duplicates the full snapshots.

Existing native row/field/text/difference limits are enforced before Arrow
allocation. Canonical JSON is incrementally hashed with a 128 MiB byte ceiling;
no complete serialized JSON byte string is accumulated. Difference batches
contain at most 1,024 rows. The envelope and validated inputs are bounded but
resident in memory; these are not total-RSS guarantees or streaming acquisition.

This projection does not extend federation v4 or map its unsupported historical
cohort to legacy/current. Qualified producers, federation admission, reviewed
Gold relationships and hosted publication remain separate work.
