# Australian historical archive coverage, 16 November 2026

This reconciliation uses existing repository evidence and public Hub manifest
and tree metadata at the revisions recorded in the [machine-readable
report](../../quality/qualifications/australian-historical-coverage-reconciliation-20261116.json).
It does not read source or projection payloads, participant or cohort-derived
data, acquire or publish datasets, or change a rights, privacy, admission or
recovery decision. Previously recorded anonymous payload-digest verification
is distinct from the present metadata checks.

## Historical observations

| Existing archive material | Reconciled period and limitation |
| --- | --- |
| MBS historical utilisation ZIPs | Five demographics ZIPs are labelled 1993–1997, 1998–2002, 2003–2007, 2008–2012 and 2013–2015; a separate group ZIP is labelled 1993–2015. Their LFS digests and sizes agree with retained source identities. A prior, specific December 1993 item/month comparison confirms an observation in that period. Labels do not prove every quarter is present. |
| Annual Medicare workbook | The existing workbook's previously qualified native financial-year labels run from 2009–10 through 2025–26, despite its filename ending in 2024–25. Its source-native structure was qualified; this is not a completeness or admission conclusion. |
| PBS legacy reports | The retained discovery list includes item, patient-category and ATC archives labelled 1992–2014, plus separate 2015 and 2016 year-to-date reports. Their paths are included in the crosswalk below. Labels do not establish every period or the contents of each member. |
| Historical PBS ATC2 teaching CSV | Month labels run from July 1991 through June 2008. This is a transformed teaching dataset, not an untouched official export. Preserve the CC-BY-4.0 and upstream GPL-3 notices and attribution; upstream gap-filled zeroes are not independent evidence of zero utilisation. It does not replace AIHW age/LGA series. |
| AIHW historical ATC2 workbook | The previously documented supplementary workbook is labelled May 2002 to January 2015. Its current archive LFS digest and size match its retained identity. |
| Later AIHW monthly ATC2 ZIP | The archived edition is labelled January 2015 to September 2026. It is not the unidentified September 2025 edition. Its LFS digest and size match the retained publication identity. |
| September 2025 PBS API ZIP | The existing 33-member snapshot is a PBS **schedule reference**, not proof of medicines utilisation. Its LFS digest and size match the retained identity. |

These are source labels or specific prior observations, not a continuous,
interchangeable or complete series. In particular, a narrow comparison of three
December 1993 cells did not establish whether the workbook's `>85` label
includes people aged 85. The cutoff remains unconfirmed.

## Existing-object reconciliation

All **505** distinct resources in the retained PBS utilisation discovery list
match their archive-manifest source ID and expected path or content-versioned
path. They correspond to **508** stored payload paths with **508** paired
receipt paths present in the checked Hub tree. Three resources have two paths:
one pair has the same recorded digest and two pairs have different recorded
digests. The 120 previously authorized additional resources are a subset of the
505, not an extra 120. This is a bounded discovery-to-manifest and tree join;
receipt contents and publisher URLs were not re-read here.

For those 508 payload paths, 121 current LFS SHA-256 identities and sizes
match the manifest. The other 387 have Git blob identity and size checks, not a
fresh SHA-256 read of payload bytes. The root manifest's raw and canonical
hashes match the retained publication receipt. Its last-run status covers an
ATC2 append, not the completeness of the whole archive.

The previous MBS official index matched **82 XML links across 41 pages** to
source receipts. At the previously checked and current MBS source-archive
revisions, all 82 payload paths and all 82 receipt paths have the same Git
object identities and sizes. The prior source-URL matching is retained; this
comparison does not independently re-read receipt contents or hash payloads.

The prior search of seven public dataset trees found no matches for the **91**
derived historical workbook outputs by output ID or digest, with a size
fallback for Git-only Parquet. Five heads are unchanged; the only changes in
the other two trees are the documented ATC2 append, its manifest and receipt,
and a catalogue README. None matches the earlier screening rules. This carries
the seven-tree result to the observed revisions; it is not proof of absence
outside those trees or permission to publish the outputs.

## Remaining limits

The PBS schedule crosswalk has 312 matched of 316 official link occurrences.
Four remain unresolved: August 2022 XML V3 and V2 down-converted, and the
August and September 2026 API CSV ZIPs. A separate MBS historical PDF index
contains 224 link occurrences, representing 218 distinct URLs; those are index
observations, not a retrieval or rights determination. The expected historical
period and source denominator has not been established. The September 2025
AIHW ATC2 edition remains unidentified.

M-107 remains **blocked**. Source-era semantics, rights, privacy, admission and
independent recovery remain separate requirements and are not inferred from
archive presence or from this crosswalk.

## Reproduction boundary

The [offline generator](../../scripts/reconcile_australian_historical_coverage.py)
checks hash-bound repository receipts and consumes a caller-supplied metadata
snapshot: the PBS manifest; selected current PBS tree entries; current and
earlier MBS tree entries; selected archive-object metadata; and the seven-tree
revision/delta observations. The report retains the exact revisions, paths,
object identities, sizes and limitations. To rerun `--check`, provide these
metadata snapshots for the pinned revisions with `--metadata-dir`; the
generator performs no network requests and does not need payload bytes.
