# Stable-v1 evidence and post-release monitoring

This qualification is a deterministic **candidate monitoring plan**, not a
release record and not a set of post-release observations. The committed
receipt binds the current health, provenance, source-maturity, security,
performance and publication contracts by SHA-256. Its separate
`post_release_evidence` section remains `not_observed` with no observations.

Generate and verify it offline:

```shell
uv run --python 3.15.1 --group dev python scripts/build_stable_v1_monitoring_receipt.py
uv run --python 3.15.1 --group dev python scripts/build_stable_v1_monitoring_receipt.py --check
```

The script reads repository files and writes only the requested local receipt.
It does not probe sources, create alerts, sign artifacts, publish datasets,
create releases or contact external services.

## Monitoring contract

| Domain | Objective | Alert boundary | Governed rollback response |
| --- | --- | --- | --- |
| Source health | At least 95% available and fresh probeable-source observations over seven days | Two consecutive unavailable or stale observations | Quarantine the source and restore the last verified snapshot |
| Provenance | 100% digest-bound provenance on published assertions | Any absent source identity or digest | Withdraw affected claims and restore the verified predecessor |
| Source maturity | Zero unreviewed maturity regressions | Any maturity or documentation-readiness decrease | Withdraw affected claims pending requalification |
| Security | 100% of required protected checks successful | Missing, failing, pending or identity-mismatched evidence | Use the approved quarantine, revocation, withdrawal, replacement and notification process |
| Performance | Read-only p95 latency at or below 250 ms | Two consecutive 24-hour budget breaches | Restore the last qualified implementation and investigate |
| Publication | 100% verified identifiers, licences and checksums | Any durable identity, licence or checksum failure | Withdraw the publication and restore only an approved artifact |

Every rollback entry is a plan that requires approval. Nothing in the receipt
authorizes automatic external notification or rollback.

## Source-change monitoring

After an approved release, the monitor is intended to compare each observation
with the newest successful receipt on `main`, daily and at each source-declared
cadence. It watches access endpoints and modes, freshness, schema fingerprints,
adapter-output parity, catalogue readiness and licence state, and source or
documentation maturity. Schema changes quarantine the adapter for
requalification; maturity regressions withdraw only affected claims.

Candidate fixtures, local checks and plans never count toward SLO observation
windows. Real observations must carry an observation time, domain, durable
receipt path and receipt SHA-256. A future durable monitoring receipt must add
those observations without rewriting this candidate receipt.

## Missing baseline recovery

The [3 August successful run](https://github.com/edithatogo/global-medicines-atlas/actions/runs/30840275572)
was the only trusted predecessor found. Its artifact no longer appears in
GitHub's inventory. The repository and local build evidence did not contain
a verified copy. The first observed baseline retrieval failure was in the
[1 November run](https://github.com/edithatogo/global-medicines-atlas/actions/runs/41348780874)
(2 November AEST).

The [26 October drift run](https://github.com/edithatogo/global-medicines-atlas/actions/runs/40401370477/artifacts/12688343044)
reported one changed fingerprint (`ca-nova-scotia-pharmacare`), one unchanged,
one with no prior baseline, 160 unavailable and 13 blocked. GitHub concluded
the run failed. Its report remains drift evidence and its schema change
remains open for review. The original ZIP was retained byte-for-byte in
local Git-ignored evidence. Artifact SHA-256 is `d5c31c0b91c03a64aa94898f660a7515d73ebf1aeab8fda998fd97811cd9a1bf` and
report SHA-256 is `26486c94697597a8f5b3ecf55af00a3c805a7f9250dc4b70aee152b293860862`.

A missing predecessor with known history stops automatic runs. A maintainer
can dispatch **Source health and schema drift** on `main` with
`reset_missing_baseline=true` after confirming the predecessor is unavailable.
A retained artifact takes precedence and must pass exact provenance and
report-digest validation. API, download and format errors stop the run.

An explicit reset must observe at least one comparable fingerprint. Its
`source-health-baseline-reset.json` records the missing run and commit, the
new baseline run and commit, and the comparison gap. Drift between the
26 October comparison and the reset remains unassessed, and the October
change remains open. A successful reset provides a starting point for
later comparisons. The existing failure on detected drift stays in force.

## Authority boundary

`signing_approved`, `publication_approved` and `release_approved` are all
`false`; `external_actions_performed` and `release_eligible` are also `false`.
Changing any of those conclusions requires durable evidence and the explicit
maintainer authority defined by the stable-v1 qualification track. This
increment performs no signing, publication, release, alert-delivery or rollback
action.
