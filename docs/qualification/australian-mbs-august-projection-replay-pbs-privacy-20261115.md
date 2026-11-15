# August MBS projection metadata replay and PBS privacy coverage

The existing eight August MBS projection identities have separate v3
metadata-registration plans. The [replay report](../../quality/qualifications/australian-mbs-august-projection-v3-20261115/metadata-replay.json)
binds each path, revision, digest, source receipt and B1/B2 references to its
v2 field lineage and the relevant earlier reproduction evidence. It replays
each registration twice in memory. It does not recreate or inspect Parquet,
prove an independent replica, perform a v4 admission, or run a live consumer.

The four frozen outputs have prior exact-byte in-memory reproduction. For the
four later outputs, the retained reproduction matched after an equal-length
writer-version footer substitution; it did not run the historical writer.
The two `f9f9` outputs retain the separately recorded independent-replica
prerequisite before admission or consumer checks. None of these checks accepts
the clinical meaning of the source fields.

The [source metadata reconstruction](../../quality/qualifications/australian-mbs-august-source-reconstruction-20261115/reconstruction.json)
rebuilds acquisition-event and external-reference metadata for two original
source receipts. Their original retrieval dates remain unchanged. The B2
references use an already verified, byte-identical later archive object; the
new metadata does not claim those files or references existed on the original
retrieval dates. It creates no processing-admission decision.

The [PBS privacy coverage report](../../quality/qualifications/australian-pbs-acquisition-privacy-coverage-20261115.json)
matches the 1,722 existing unassessed PBS/reimbursement paths against the
1,702 retained PBS acquisition-event files. The match uses SHA-256 only: the
events do not supply a byte count. It finds 1,703 paths matching all 1,702
distinct event digests; the extra path is the already recorded duplicate
archive identity. Each matched event records sensitivity and personal-data
status as `unknown`, with publication `review_required`. Nineteen paths have
no matching digest in this particular event directory. That does not prove no
other evidence exists for them.

All 1,722 paths remain unassessed and blocked from payload reads and consumer
use. Neither matching digests nor an unknown classification establishes the
presence or absence of personal data, transfers rights, or clears a ZIP's
members. No unassessed PBS, participant or cohort-derived payload was read;
no dataset was acquired or published.

Reproduce with the repository-local Python 3.15.1 interpreter:

```sh
build/federation-env/bin/python -m scripts.reconcile_mbs_august_projection_sources --check
build/federation-env/bin/python -m scripts.qualify_mbs_august_projection_replay --check
build/federation-env/bin/python -m scripts.qualify_pbs_acquisition_privacy_coverage --check
```
