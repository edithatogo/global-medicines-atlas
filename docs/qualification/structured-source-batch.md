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
