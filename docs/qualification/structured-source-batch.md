# Structured-source batch

Run the 42 finite source recipes with one command:

```sh
.venv/bin/python scripts/structured_source_batch.py \
  --manifest quality/source-batches/remaining-structured-42.json \
  --output build/structured-42-run --execute
```

Omit `--execute` to validate without network access. Four workers run each source
once. Supported responses are JSON, CSV, spreadsheets, XML/RSS and medicine
HTML tables; a page can lead to one explicit same-host structured export.
There are no automatic retries, recursive crawling or publication. Public-IP
binding, explicit host lists, HTTPS and a 64 MiB bound apply. Each source has a
result and file digests. An inaccessible source fails explicitly; a page without
an extractable table or export reports `needs_source_specific_adapter`.

The manifest configures all 42 sources. It does not assert that 42 working
exports exist, that a page is complete, or that the output is admitted Bronze
or approved for publication. Federation is excluded. Existing archive and
acceptance records remain separate from these local technical downloads.

HTML table acquisitions retain the original response as a SHA-256-named HTML
object, with a source receipt linking requested/final URLs and derived CSVs.
Relative export links resolve against the final response URL after redirects.

The 30 October one-time completion check found 2,392 of 2,396 OpenFDA bulk
partitions downloaded with matching recorded file sizes. Four timeout failures
were launched once into a separate retry directory, preserving original receipts
and partial files. No retry monitoring or publication was performed. The corrected
Ireland route failed its TLS handshake; Kenya and both Senegal recipes still
require source-specific adapters. These are unresolved, not successful datasets.
PR #1387 review fixes passed 74 focused tests, Ruff, ty and BasedPyright.
Federation remains deferred.
