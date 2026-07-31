# Stable-v1 evidence and post-release monitoring

This qualification is a deterministic **candidate monitoring plan**, not a
release record and not a set of post-release observations. The committed
receipt binds the current health, provenance, source-maturity, security,
performance and publication contracts by SHA-256. Its separate
`post_release_evidence` section remains `not_observed` with no observations.

Generate and verify it offline:

```shell
uv run --python 3.14.6 --group dev python scripts/build_stable_v1_monitoring_receipt.py
uv run --python 3.14.6 --group dev python scripts/build_stable_v1_monitoring_receipt.py --check
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

## Authority boundary

`signing_approved`, `publication_approved` and `release_approved` are all
`false`; `external_actions_performed` and `release_eligible` are also `false`.
Changing any of those conclusions requires durable evidence and the explicit
maintainer authority defined by the stable-v1 qualification track. This
increment performs no signing, publication, release, alert-delivery or rollback
action.
