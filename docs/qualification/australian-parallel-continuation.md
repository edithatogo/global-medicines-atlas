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

Difference kinds are `field_changed`, `unchanged`, `present_only_left` and
`present_only_right`, not source additions/cessations or clinical assertions.
Comparison outcomes are `compared` or `abstained`.
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

At frozen head `39eeebb`, the full suite recorded 3,515 passes, nine failures,
one optional Iceberg skip and 96.79% coverage. Both clean-clone release
reproduction tests passed on the corrected runtime. Eight failures passed on
one unchanged serial rerun; the product runner still exceeded its query budget
(577.556 ms p95 versus 250 ms). Local performance remains unqualified; later
full-suite lanes were not reached. All 38 hosted checks at that head passed.
Automated integration review found no blockers; final-head checks are required
after the documentation/evidence refinements.

## Follow-up: scoped comparisons and append-only history

The next implementation adds a pure MBS XML cohort producer. It parses the
whole receipt-matched source before selecting every occurrence of explicit
literal item/subitem keys. Full, selected and omitted counts remain separate;
a selection-manifest digest binds the comparison scope. This allows bounded
cohorts from the 5,989-row legacy source without truncating it or pretending a
single batch is complete. Duplicate identities cause comparison abstention.
LIVE receipts require an explicit historical/current/legacy label; this is not
independent source qualification. All test inputs are constructed synthetic
bytes; no real corpus was acquired or compared in this implementation.

The history append contract binds exactly the two later donor heads, existing
baseline bundles, new head-addressed bundles/manifests, a public destination,
CAS and unchanged prior objects. It checks supplied anonymous and Git-restore
observations and a durable-receipt digest before reporting cleanup consistency.
These are pure consistency checks, not authenticated evidence or permission.
The hosted append implementation and exact authorization extension remain
pending. The old initial publisher's replace-all and privacy rollback behavior
must not be used against this already-public archive.

PBS diagnostics now expose only fixed cause codes and separately retain first
retry and terminal details. Explicit cause traversal is bounded and cycle-safe;
exception messages, addresses and credential-bearing attributes are not read.
No requests, retries or timeout limits are added. The failed hosted connection
has not been diagnosed retrospectively or repaired by this observation code.

Coverage review found that the repository's unanchored ellipsis exclusion could
hide whole functions containing variadic tuple annotations. Removing that
redundant pattern retains the pinned library's exact stub exclusion and the
91% threshold. Three signature regressions failed before the fix. Reanalysis
of the prior full-run data gives 96.24% overall and still 100% for its three
target modules; the old recorded 96.79% is the historical configured result.
The follow-up focused suite passes 342 tests, with corrected coverage of 100%
for history append and native comparison, 97% for the MBS producer and 99% for
hosted PBS qualification (99.16% combined). Full and hosted checks follow.

The follow-up full run at `8b735b3` recorded 3,633 passes, one optional
Iceberg skip and one existing product performance failure (948.142 ms p95
versus 250 ms), with 96.42% coverage under the corrected exclusions. Routine,
strict typing, clean package consumers and both release-reproduction tests
passed. Later full-suite lanes were not reached; Linux CI remains authoritative
for those lanes. The unchanged performance failure was not repeatedly rerun.
The merged PR #401 base was joined without changing the frozen tree
(`56573a6d4ca381e77248ce376b077a79abe31979`). Final hosted checks follow.

### Review correction: release revision is not schema era

Automatic PR review identified that monthly effective dates in receipt
`catalog_version` were being used as comparison schema eras. That forced
otherwise comparable monthly releases to abstain. The producer now requires
two explicit inputs: `expected_source_revision`, matched exactly to the
receipt, and `schema_era`, an independent caller-declared comparison profile.
Same-era releases can compare across months; different eras still abstain.
No date stripping, schema inference or independent qualification is implied.

The original receipt, parser batch and existing public Bronze/Silver metadata
remain unchanged; B1/B2 digests still bind evidence. Broader versioned profile
separation is tracked separately, not applied retrospectively to public data.
The primary regression failed before correction; 168 integrated tests passed
afterward, with 98.45% combined coverage. The prior frozen full run is retained
as pre-correction evidence, not claimed as a final-head full pass. Exact final-
head hosted checks are required. The earlier 0% Codecov patch report arose
before the aggregate upload; all 38 checks on `faa02e8` subsequently passed
without a threshold change.

Independent automated review of `7fe0388` passed 14 selected regressions and
an additional unchanged-receipt/B1/B2 identity probe. No blocking findings
remained; this is technical review, not human publication approval.

### Evidence-closure delivery

PR #402 merged as `e75ef68` after all 38 final-head checks passed. The next
parallel batch, PR #403, merged as `44a603d`, with the same 38 successful checks
and exact reviewed/merged tree agreement. It adds a metadata-only PBS Actions
probe, an offline federation receipt-byte closure checker, and opt-in declared
MBS schema-profile metadata. None grants qualification or publication authority.

The combined focused suite passed 414 tests. Review then reproduced oversized
reference arrays reaching schema validation before their limit; the correction
adds rejection-only structural preflight. After correction, 210 integrated
federation/harness/context tests and 28 independent review tests passed, with
99.08% closure coverage. MBS and PBS independent reviews passed 19 and 27 tests.

The full run on frozen `39a61f192efe291e73951b5ec47c5164b5dbb4cd` recorded
3,733 passes, one optional `pyiceberg` skip and one existing local product
performance failure: 1,149.071 ms p95 versus the unchanged 250 ms budget.
Coverage was 96.47%; the coverage phase took 645.45 seconds. Strict checks,
clean wheel/sdist consumers and both release reproduction tests passed. Later
local full lanes were not reached; hosted checks passed. No repeated full or
product retry was used to replace the observed failure. The profiling follow-up
is recorded separately from dataset qualification and publication work.

Full evidence is retained in the [PR #403 validation comment](https://github.com/edithatogo/global-medicines-atlas/pull/403#issuecomment-5478397193).

The [single metadata-only Actions run](https://github.com/edithatogo/global-medicines-atlas/actions/runs/33392287024)
succeeded on merged `44a603d`, without a retry. Its [durable receipt](https://github.com/edithatogo/global-medicines-atlas/issues/341#issuecomment-5478488604)
was independently hash-checked and explicitly records `source_files_read=false`,
`publication_performed=false` and `corpus_qualified=false`. Current connectivity
is verified; the cause of the earlier failure is not retrospectively proven.
One [instrumented corpus qualification](https://github.com/edithatogo/global-medicines-atlas/actions/runs/33393205281)
was then dispatched against the same exact main commit. Its result is pending;
the existing 55-minute limit and no-publication boundary remain unchanged.
