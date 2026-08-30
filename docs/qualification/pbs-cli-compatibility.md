# PBS donor CLI compatibility

The donor `aus_mbs_pbs_graph` at
`64e764cebeb3826f98ce672cbb4affc65d06a92f` exposed `--max_items` (default
five) in `scripts/parsing/parse_pbs_xml.py` and a first-item XML view in
`scripts/utils/identify_pbs_tags.py`. The parser's trailing Markdown fence
prevented execution; its intended inspection behaviour is preserved, not
its syntax error or error-swallowing exit status.

Use the existing governed inspector over a prepared archive:

```sh
uv run python scripts/inspect_pbs_v3.py fixture.zip --max_items 5 --first-item-xml
```

`--max-items` is the preferred spelling; both spellings accept 1–1000 items.
`--max-tags` accepts 1–4096. Input reads stop at the archive byte limit plus
one byte, and complete JSON output is capped at 4 MiB before anything is
printed. Exceeding a bound exits unsuccessfully without partial stdout.
JSON retains the full archive record count and digests, with a bounded `items`
sample containing item code, product name, AMT references, ATC codes and
restrictions. `first_item_xml_projection` is optional normalized XML (at most
1 MiB), not an exact slice of original bytes. Missing optional fields remain
empty/null rather than fabricated `N/A` source values.

The donor `--url` acquisition interface is deliberately not retained. Source
acquisition and public archival run only through the reviewed GitHub Actions
workflow; this inspector neither downloads nor publishes. It validates the
whole archive before sampling, so malformed unsampled items still fail.
Archive ZIP/member bytes and B1 receipts remain evidentiary truth.
