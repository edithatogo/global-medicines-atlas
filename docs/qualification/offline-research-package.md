# Content-addressed local research packages

A research package can describe a local result with a `urn:sha256:` reference
instead of asserting that the result is publicly hosted. This form uses crate
schema version 2 and lineage schema version 3. Its lineage revision is the
assembly commit; inputs retain their own pinned source revisions and HTTPS
locations. The existing public form retains its HTTPS and revision requirements.

The metadata archive does not contain the result. Clean-room verification of a
local package requires the separately supplied canonical JSON result bytes and
checks their digest, row count, canonical ordering and query identity. The local
reference identifies bytes; it is not a downloadable URL or proof of publication.
The archive does not establish source availability, rights, admission or the
accuracy of source semantics. Those remain bound to their own receipts.

The initial implementation had focused synthetic validation. A later merged
real-source canary verified a saved archive in a separate process on the same
machine and environment; independent clean-room restoration remains open.

## Installed consumer verification

The clean-consumer harness accepts both metadata and its separate local result:

```sh
uv run --python 3.15.1 python scripts/qualify_clean_consumer.py \
  --research-export /absolute/path/metadata.zip \
  --research-result /absolute/path/query-result.json \
  --output build/quality-receipts/local-research-consumer.json
```

The metadata limit is 8 MiB and the canonical JSON result limit is 1 MiB.
Both must be regular files, not symlinks. A result requires a metadata archive.
The existing verifier rejects missing, altered, noncanonical or mismatched local
results and continues to reject a result sidecar for the public metadata form.
Public-form consumers can continue to omit `--research-result`.

Each built wheel and sdist is installed in a fresh environment. The research
probe runs with isolated Python import resolution (`-I`), verifies the archive
and result, and rebuilds identical metadata. Its receipt records hashes, lengths
and status without source/result values. The existing cross-platform synthetic
medallion canary supplies its exact query result to this local-format check;
the public metadata form is still rebuilt and verified in the pipeline.

This is installed-package verification using synthetic evidence. It establishes
neither an actual-source clean-room recovery nor independent storage/recovery
authority, source semantics, public availability or federation acceptance.
The earlier real-source canary is recorded separately in
`quality/qualifications/platinum-research-package-merged-canary-20261029.json`.
