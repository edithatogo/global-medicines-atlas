# PBS donor command compatibility

The canonical commands are `global-medicines-atlas source pbs parse` and
`global-medicines-atlas source pbs inspect`.
They reuse the existing PBS v3 adapter, archive and XML safety policies, and
Typer stack. No legacy requests/lxml dependency is introduced.

```sh
global-medicines-atlas source pbs parse --archive /temporary/schedule.zip --sha256 EXPECTED_SHA256 --max_items 5
global-medicines-atlas source pbs parse --archive /temporary/schedule.zip --sha256 EXPECTED_SHA256 --format json
global-medicines-atlas source pbs inspect --archive /temporary/schedule.zip --sha256 EXPECTED_SHA256 --max-tags 128
```

Use only public, publication-approved inputs and the digest from their pinned
archive manifest. These commands perform offline diagnostics, not acquisition,
admission, upload, or durable storage. A matching digest proves input fixity;
it does not independently prove rights or source authenticity. Public Hugging
Face revisions and hosted B1/B2 receipts remain the data-plane authority.

## Compatibility and deliberate changes

The donor `parse_pbs_xml.py` at commit
`64e764cebeb3826f98ce672cbb4affc65d06a92f` intended to print the first five
items, with item code, product description, AMT references and ATC codes.
The text command retains those labels, source order and default item count;
both `--max_items` and `--max-items` work. JSON additionally exposes nullable
AMT resource URIs, restrictions, source identities and explicit truncation.
No AMT code-type inference or clinical/regulatory equivalence is invented.

The donor `identify_pbs_tags.py` intended to display the first pharmaceutical
item's XML. `inspect` retains the full normalized first-item structure and a
bounded expanded-namespace tag sample. Serialization is explicitly labelled
`normalized_not_source_bytes`; exact bytes remain in the source archive.

The donor's `--url` and stale July 2025 default are intentionally replaced by
`--archive` plus required `--sha256`. Downloading and publication belong to
the governed GitHub Actions acquisition workflow. No hidden network fallback
is performed. The syntactically invalid trailing Markdown fence and failures
that previously returned success are not retained.

All input is validated before output: the entire archive and all item
identities must pass even when only one item is displayed. Output is bounded
to 1 MiB for parsing; inspection defaults to 64 KiB (configurable up to 1 MiB)
for the complete JSON document, including its newline. Oversized output fails
without partial stdout. Item count is 1–1000; sampled tags are 1–4096.

Synthetic compatibility and negative controls live in
`tests/test_pbs_source_cli.py`. Real raw payloads are not test fixtures in Git.
