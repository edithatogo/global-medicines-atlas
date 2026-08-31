# Australian consolidation: parallel implementation checkpoint

This work extends three existing Conductor tracks without a new data authority
or dependency stack. It is not completion of Australian Silver, Gold or the
public derived dataset.

## Donor completeness

The frozen donor inventory remains unchanged. The additive
`quality/qualifications/australian-donor-delta.json` records two graph and eight
scraper changed paths at the observed later heads. `donor_delta.reconcile_delta`
requires an independently supplied complete observation and rejects substituted
identities, omitted paths, duplicate dispositions and executable changes labelled
documentation-only. It does not authenticate GitHub metadata itself.

The no-data flag classifies path roles, not embedded content. Complete review
does not prove behavioral parity, current-head history preservation, permission
or archive readiness. GMA already retains bounded timeout and fail-closed parsing
intent; the donor's async wrapper remains a labelled legacy API difference.
Both newer donor commits still require hosted history-preservation receipts.

## Transport

The generic federated reader now accepts the exact observed
`us.aws.cdn.hf.co` delivery host, without wildcards or relaxed digest, visibility,
admission, credential, cookie, cache, deadline or Actions-only raw-read guards.
Synthetic canaries cover approved signed redirects and hostile lookalikes.

The shared system resolver now preserves the OS `getaddrinfo` preference while
deduplicating addresses. All distinct answers still undergo private-network
checks before a single IP-bound request. This repairs nondeterministic address
selection; it is not proven to explain the PBS metadata connection failure in
run `33379551308`. The original timeout and subsequent connection failure remain
separate failed observations; neither establishes corpus qualification.

## Native historical comparison

The new comparator works only on bounded, caller-supplied source observations.
It preserves exact literal strings, missing/null/empty states and occurrence
lineage. Matching source, table, semantic dimension, schema era and identity
profile are prerequisites; incomplete or duplicate-identity snapshots abstain.
The result retains both inputs and is revalidated against recomputed differences.
No copied mutable input may invalidate a previously accepted result.

Outcomes are `field_changed`, `unchanged`, `present_only_left` and
`present_only_right`, not source additions/cessations or clinical assertions.
Declared completeness and digests are not independent source verification.
Bounds are 4,096 rows, 256 fields per row, 65,536 fields per snapshot, 8 MiB
native text and 65,536 differences checked before result allocation. These are
finite candidate-cohort limits, not a whole-corpus or resident-memory guarantee.
Real producer integration, Parquet products, Gold edges and v4 publication remain
separate work; no raw data or derived corpus is stored by this pure comparator.

## Validation environment

An isolated Python 3.14.6 environment uses the unchanged `uv.lock`. The old
installed uv download catalogue lacked that interpreter; the official updated
catalogue supplied it. The exact release builder additionally requires
uv 0.11.29, available through an isolated tool environment. The installer updated
its managed 3.14 alias despite `--no-bin`; the prior 3.14.5 alias was restored and
both default 3.14.5 and isolated 3.14.6 were verified. No repository pin or
lockfile changed. Local performance and hosted execution remain separate.

The integrated focused suite recorded 437 passes and one Hypothesis timing-only
failure (256.22 ms against 200 ms; internal replay 0.53 ms). Its single isolated
rerun passed unchanged. All three comparison/delta/reader modules have 100%
statement and branch coverage. Ruff, ty and BasedPyright passed. The frozen
full suite and exact-head hosted checks remain the delivery gates.
