# PBS privacy and provenance: the 19 unmatched paths

The earlier [acquisition privacy coverage](../../quality/qualifications/australian-pbs-acquisition-privacy-coverage-20261115.json)
matched 1,703 paths to the `au-pbs` event directory and left 19 unmatched in
that particular directory. The new [metadata-only crosswalk](../../quality/qualifications/australian-pbs-unmatched-provenance-20261116.json)
binds all 19 to other retained evidence by dataset, revision, path, SHA-256 and
byte count. It adds no privacy clearance. All 1,722 paths in the existing
PBS-related and reimbursement privacy cohort remain unassessed and blocked
from payload reads and consumer use. Eighteen of these 19 paths belong to the
frozen M-112 inventory; the reproduced Silver output is outside it.

- Five are archived PBS PDFs. Each has a separately retained acquisition event
  in `au-pbs-archive`, with the same payload digest and observed byte count.
  Each event records sensitivity and personal-data status as unknown; its
  landed reviewer state remains unreviewed.
- Twelve are reimbursement projections. Earlier metadata binds nine to
  byte-identical producer files and three to layer partitions of a separate
  producer file. The partition source is not claimed to be byte-identical to
  its outputs. These are historical lineage and readback receipts, not new
  examinations of the projection contents.
- One is the April 2026 PBS Bronze projection. A historical source-terms
  readback and a later readiness summary record unknown redistribution terms.
  A separate 20 October maintainer attestation covers this exact projection;
  its permission instrument was not independently located or reviewed. Neither
  record assesses privacy or authorizes a new publication or v4 admission.
- One is the reproduced April 2026 PBS Silver output. Its historical publication
  receipt records an anonymous digest verification, while its candidate
  readiness evidence records no v4 admission. Two prior builds matched using
  the same algorithm; the earlier field-state receipt names a different output.
  Its exact-output rights attestation does not establish privacy or semantics.

The Bronze and Silver outputs bind to the same recorded source archive digest,
but have different output identities and transformations. This observation
does not transfer privacy or rights decisions between them. The September 2025
API ZIP and its 33 named members also retain their existing unknown privacy
dispositions; filenames and one XML member's schema labels do not screen their
contents.

The report reads only fixed, hash-bound repository metadata and five bound
acquisition-event JSON records. It does not read source or projection payloads,
participant or cohort-derived material, or change the frozen inventory,
publication, rights, admission, recovery or federation gates. The original
19-path report remains unchanged; this crosswalk explains the scope of its
unmatched result rather than rewriting history.

Reproduce using the repository-local Python 3.15.1 interpreter:

```sh
build/issue-env/bin/python -m scripts.reconcile_pbs_privacy_provenance --check
```
