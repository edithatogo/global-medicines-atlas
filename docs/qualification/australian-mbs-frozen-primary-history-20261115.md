# Existing MBS primary restore evidence

This qualification uses existing public inventory and workflow metadata. It
adds no dataset, reads no participant or cohort-derived data, and makes no new
rights or admission decision. The [machine-readable reconciliation](../../quality/qualifications/australian-mbs-primary-history-20261115/reconciliation.json)
records the exact eleven scoped identities.

## Earlier full primary restore

During [run 36532129354](https://github.com/edithatogo/global-medicines-atlas/actions/runs/36532129354),
the historical source-metadata workflow created a new metadata-only archive
revision and anonymously restored and hashed every object in its resulting
inventory. Its public [verification receipt](https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-5885067299)
names the exact revision `243f9ff5498816af6e4d9ae4db60528728f01834` and the
same path, byte count and SHA-256 for all seven frozen MBS objects: three raw
XML paths and four Parquet projections. Each was already present in the
parent inventory. The successful job and its exact historical code show that
its temporary download cache was removed after the durable verification.

The receipt was created before the later August B1 acquisition on 4 October
2026; the same-content join does not reverse that chronology. The four
out-of-inventory projections have different revision and path identities and
are not covered by this receipt. An earlier readiness report examined only a
subset of available restore receipts; this reconciliation supplements that
review and does not change the historical report's original observation.

## New bounded in-memory check

[Run 43697888963](https://github.com/edithatogo/global-medicines-atlas/actions/runs/43697888963)
reconstructed the three assessed raw objects from the same exact primary
revision in memory. Each buffer's digest and byte count matched, and each
buffer was closed. The hosted artifact's native SHA-256, ZIP integrity, exact
member set, object identities and privacy boundaries were independently
checked before retaining its value-free receipt. No payload file or value was
retained or emitted by this run.

Both observations concern the existing primary copy. They do not establish an
independent replica, a disaster-recovery target or an RPO/RTO. The newer check
is an in-memory reconstruction rather than a disk restore. Neither observation
establishes v4 admission or a reader canary.

## Reproduction

```sh
build/federation-env/bin/python -m scripts.qualify_mbs_frozen_primary_history --check
```

The retained source receipt is a public inventory of object names, sizes and
digests. It contains no source payload values. The recorded historical code
hashes are bound to the run's immutable commit; the current reconciliation is
metadata-only and does not repeat the historical publication or restore.
