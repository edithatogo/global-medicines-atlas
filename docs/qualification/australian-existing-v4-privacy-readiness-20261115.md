# Existing MBS v4 and PBS privacy readiness

This packet checks retained metadata and exact public Hub tree observations.
It does not add or publish a dataset, read unassessed PBS payloads, access
participant or cohort-derived data, change rights, perform an admission, or
claim independent recovery. The [machine-readable report](../../quality/qualifications/australian-existing-v4-privacy-readiness-20261115.json)
retains the exact inputs and the eleven individual MBS identities.

## MBS exact-revision identity and recovery

Hosted run [43687742836](https://github.com/edithatogo/global-medicines-atlas/actions/runs/43687742836)
subsequently streamed and verified the SHA-256 and byte count of all eleven
objects at their exact revisions. Its metadata-only artifact passed native
artifact-digest and ZIP-CRC verification; the [per-object binding](../../quality/qualifications/australian-existing-mbs-digest-binding-20261115.json)
records the resulting verification evidence. It remains unbound to a v4
contract and creates no admission, reader canary or independent recovery.

Anonymous tree metadata confirms all eleven paths and byte counts at their
respective frozen or previously scoped revisions. Eight Parquet objects expose
matching LFS SHA-256 values. The three non-LFS XML paths expose matching Git
blob IDs and sizes; the SHA-256 values in the observation are expected values
from prior receipts, not fresh digest observations. These earlier metadata
checks were distinct from the later streamed digest and do not establish v4
admission or a consumer canary.

The existing primary restore for the raw utilisation archive concerns a
different dataset. The other selected primary-restore receipt covers six
July 2025 Silver paths, none of the eleven paths in this cohort. Neither
receipt establishes independent recovery. A subsequent search found an earlier
exact-revision primary restore covering the seven frozen objects; see the
[primary restore reconciliation](australian-mbs-frozen-primary-history-20261115.md).
That later finding does not change the four outside projections or establish
an independent replica. The previously recorded source
privacy, rights and lineage evidence remains separate; the four outside
projections retain their footer-adjusted replay limitation.

The dispatch-only [hosted digest workflow](../../.github/workflows/australian-existing-mbs-exact-digest.yml)
reads only the eleven already source-profiled MBS objects at their exact
revisions. It retains a value-free metadata receipt only. It does not write
source bytes or dataset objects, create a v4 contract, admit data, exercise
the production reader, or establish an independent restore. The successful
hosted receipt is a verification input, not proof that the other contract
roles are complete. The first dispatch failed before a source read because of
its module entry point; the corrected exact-main dispatch passed.

## PBS privacy evidence

Of the 1,707 unassessed schedule objects, 311 match retained official schedule
links by exact identity and digest-bound acquisition metadata. A link label or
public location alone is not a privacy classification.

Two existing archive identities have the same April 2026 ZIP digest. A retained
profile of one exact XML member records 5,163 schema paths. Among those paths,
224 contain patient- or person-related tokens and 32 contain contact-related
tokens. These are **schema-label counts**, not counts of people or proof that
the files contain participant records. The labels include prescribing text,
patient charges and organisation contact fields. The profile does not screen
all values or prove the scope of every ZIP member, so neither archive nor any
derived output receives a new privacy clearance from this comparison.

The September 2025 PBS API ZIP previously identified by the maintainer is one
of the unassessed schedule objects. The retained [archive reconciliation](../../quality/qualifications/australian-public-archive-reconciliation-20261113.json)
records an anonymous digest check and 33 CSV member names for that exact ZIP;
its path, SHA-256, byte count and acquisition receipt also match the frozen
object's later revision. Member names establish neither the fields nor the
values inside them, so this source-specific evidence does not clear the ZIP.

All 1,722 previously unassessed PBS-related or reimbursement objects retain
their existing privacy dispositions. An appropriate source-specific method and
evidence are still needed before the remaining payloads can be admitted or
used as consumers. Existing six-object utilisation assessments remain scoped
to their own source identities.

## Reproduction

Use the qualified repository-local Python 3.15.1 interpreter:

```sh
build/federation-env/bin/python -m scripts.qualify_australian_v4_privacy_readiness --check quality/qualifications/australian-existing-v4-privacy-readiness-20261115.json
```

The hosted digest operation is available only by workflow dispatch on the
exact merged main commit and is guarded again in Python before network access.
Its receipt contains paths, revisions, byte counts and SHA-256 values, never
payload values. It does not read the unassessed PBS objects.
