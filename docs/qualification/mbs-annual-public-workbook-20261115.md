# Existing public Medicare annual workbook — 15 November 2026

The exact public workbook previously described as unavailable is already in the
[MBS utilisation archive](https://huggingface.co/datasets/edithatogo/australian-mbs-utilisation-archive/tree/05342df7dd2f92fe6e85e28e8add9bf3f43d0389).
Its 1,058,479 source bytes match SHA-256
`ace9d6e72dcfca3c9fd779b4c476788ea1d465ceaafd465f97cea712dad44598`.
The bound B1 receipt has SHA-256
`4328cf80841e3f766041efc0537ecfd31ef1bfab1e728a629081995cf24f066c`.
The receipt identifies the original publisher URL and the later hosted
public-copy materialization separately; this readback did not contact the
publisher or add a source.

The exact ZIP container passed the existing bounded member checks and CRC
verification. It has 29 members and five named sheets: `Contents`, `All
Services`, `Out of Hospital Services`, `Patients` and `Broad Type of Service`.
The `Patients` sheet has 2,202 classified aggregate rows, 17 native financial
year labels from 2009–10 to 2025–26, ten state/territory-or-total labels and
13 broad service-type labels. One additional formatted row after the table is
empty. No unclassified nonempty rows or duplicate financial-year/state/broad-
service-type keys were observed. All 2,202 patient cells have nonnegative
integer-shaped numeric values; the qualification emits their **shapes and row
counts only**, not their source values, geography labels or service-group labels.
Those shape results do not establish suppression, deduplication or completeness.

The native title describes financial-year patient statistics by broad service
type and state. The workbook says, “A patient is defined as a person who claimed
at least one MBS service.” Its native columns distinguish `Patients`,
`Services`, `Benefits`, per-patient and per-capita measures, and estimated
resident population. `Column1` remains uninterpreted. Although the original
filename ends in `2024-25.xlsx`, the sheet itself includes `2025-26` rows;
both identities are preserved rather than rewriting the source filename.

[Machine-readable qualification](../../quality/qualifications/mbs-annual-public-workbook-qualification-20261115.json)
records the exact revision, source and B1 identities, native headers, period
labels, bounded shape counts, and limitations. The reproducible local profiler
reads the exact existing source stream and receipt and emits no patient
observation values. Its identity, ZIP, XML, header, definition and privacy
controls are exercised with synthetic test workbooks.

M-106 remains **blocked**. The source note does not establish whether patient
counts are deduplicated across broad service groups or supply item-level
distinct-patient counts. The profile does not qualify the claim-processing
time basis, suppression rules, a patient denominator for admission, or any
cross-source linkage. No v4 admission, source-rights conclusion, dataset
publication or participant/cohort-derived data access was performed.
