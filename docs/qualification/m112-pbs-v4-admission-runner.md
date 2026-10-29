# Exact PBS raw-B2 admission and reader qualification

The runner `scripts/qualify_m112_pbs_v4_admission.py` accepts only the six
existing exact PBS contract candidates. It reconstructs the caller-governed
trust profile from separately pinned source identities, B1/B2 lifecycle,
retrieval time, exact rights attestation, source-specific sensitivity assessment
and v1/v3 receipts. It does not derive authority or subject expectations from
the candidate contract. Changed manifest, contract, schema or evidence bytes
fail closed.

The implementation reuses the existing schema/semantic validator, guarded
read-only receipt adapter, receipt closure, independent admission engine,
consumer contract binding and `FederatedReader` canary. It adds no new reader,
source parser, dataset destination or domain interpretation.

## Local policy check

Use repo-local Python 3.15.1:

```sh
uv run --locked --python 3.15.1 python scripts/qualify_m112_pbs_v4_admission.py \
  --target-path 'raw/pbs/utilisation/reference/pbs-item-drug-map.csv' --check
```

This checks the exact configuration and independent profile without network
reads or admission. It reports `candidate_policy_checked_not_admitted`.

## Exact-main hosted execution

The dispatch-only workflow is
`.github/workflows/australian-m112-pbs-v4-admission-qualification.yml`. After
its code and exact candidate configuration pass protected checks and merge,
select one of its six explicit paths and pass the exact merged main commit.
Both workflow and Python entrypoint enforce main, repository, dispatch event
and exact commit. Python also requires run and positive attempt identities
before receipt or source reads. Workflow permissions are `contents: read`;
no secrets, dataset writes or communications are used.

For each selected object the runner:

1. validates fixed configuration and source evidence;
2. downloads each unique metadata receipt once through the existing bounded,
   anonymous guarded transport and verifies complete receipt closure;
3. admits the exact contract against its independent source-derived profile;
4. exercises the production reader, verifying the remote digest, streamed
   digest and byte count, consumer binding and cleanup after close; and
5. retains a metadata-only admission/closure/reader report as a run artifact.

Use one recorded dispatch per object and retain native run/job/artifact
readback. Do not count local policy checks, synthetic test admissions or
workflow existence as hosted completion. A failed observation does not justify
redispatching an operation whose native run remains active.

The reader consumes raw bytes without interpreting source rows or values.
This is raw-B2 delivery qualification; it does not qualify Silver domain
semantics, Platinum API/CLI/Atlas table behavior, an independent recovery
replica, broader source coverage, production promotion or Stable v1. Existing
raw admission counts remain unchanged until successful hosted receipts are
retained and reconciled. The separately qualified six-table MBS Silver cohort
retains its own distinct consumer scope.
