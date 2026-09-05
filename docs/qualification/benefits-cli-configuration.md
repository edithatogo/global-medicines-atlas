# Australian benefits CLI configuration

`gma benefits RESOURCE --trust-file TRUST.json --metadata-root METADATA
--schema-file contracts/medallion/v4/federation.schema.json --column item_code
--limit 100` reads one bounded page through the shared benefits service.
Set `GMA_CURSOR_SECRET` to an operator-managed value of at least 32 UTF-8
bytes. Keep it stable when following `next_cursor` with `--cursor`. Never put
the secret in the trust file or command arguments.

The operator provisions the trust file independently from candidate metadata.
It has `version: "1.0"` and a nonempty `resources` array (maximum 32). Each
entry supplies `resource_id`, `semantic_dimension`, `entity_granularity`, a
serialized `DistributionBinding` under `binding`, the independently expected
`semantic_sha256`, and relative `contract_path` and `semantic_path` values.
The binding includes the independently expected `contract_sha256`, destination
dataset/revision and complete produced-object identity. Candidate files are
bounded regular files below `--metadata-root`; path traversal and symlink
escapes are rejected. Schema bytes must satisfy the existing pinned resolver
contract. There is deliberately no command that derives trust from candidate
files. Provisioning a file does not prove who approved it or establish rights.

Output is one JSON `BenefitsPage`, including immutable provenance, semantic
dimension, page/window digests and a signed next cursor. `--column` is
repeatable. A page contains at most 100 rows from a declared 1,000-row window;
this is not complete-corpus enumeration. `--offline` performs no retrieval;
each CLI process starts with an empty transient cache, so it normally emits
typed `offline_cache_unavailable` and exits 3. Available pages exit 0; invalid
queries/configuration or missing resources emit the CLI error envelope and
exit 2. Neither configuration loading nor successful queries publish data,
admit new resources or promote graph/clinical assertions.
