# M-105 chronology review — 15 November 2026

The maintainer approved the narrow exception and conditional M-105 acceptance
after this review. [D-006-14](../../conductor/decisions/0006-external-gate-decision-register.md#d-006-14--m-105-acceptance)
records the decision and the existing dossier checks pass. D-006-12 remains a
historical blocked disposition; the earlier D-006-10 waiver is preserved as a
historical decision. Donor history, source rights, broader federation and
release authority are unchanged.

## Retained evidence

The [disposition matrix](../../quality/qualifications/australian-donor-m105-dispositions.json)
binds 54 baseline tracked blobs and 10 later changed paths to exact donor
identities and final dispositions. There are no rows marked pending behavioral
parity. Fifty rows retain legacy history or bytes, including two with explicit
legacy-only qualifications; the other fourteen record adaptations,
replacements, supersessions or exclusions with their own evidence. These are
not 64 claims of equivalent live behavior.

The existing chronology-waiver validator passes against the retained dossier;
before the new decision, the current-disposition validator correctly reported
M-105 blocked. The
focused donor and stable-contract suites passed 77 tests on Python 3.15.1.
Read-only GitHub metadata on 15 November confirmed both repositories remain
archived and their default-branch heads match the retained archive receipts:

| Donor | Archived head |
| --- | --- |
| `edithatogo/aus-health-data-scraper` | `009e80544588a956c8922aaab052ee08947e2b30` |
| `edithatogo/aus_mbs_pbs_graph` | `3993e5e331eb2d3d9e9d354d80e52c684ad26a1e` |

The [scraper](../../quality/qualifications/scraper-archival-20260906.json)
and [graph](../../quality/qualifications/graph-archival-20260906.json) receipts
bind the preserved histories. The donor scheduled HTML run's six 404s and its
lack of a data commit remain explicit limitations. Preserved legacy behavior is
not evidence of current participant coverage, an equivalent live scraper, or
permission to acquire or publish future data.

## Decision presented to the maintainer

**Selected: approve only the chronology exception and accept M-105 after
the exact retained dossier passes its existing checks.** The exception
waive only the requirement that complete parity evidence predate either donor
archive. It would permit the post-archive dossier to be assessed on its own
merits, while preserving the actual dates and the absence of a pre-archive
complete-parity receipt. The later decision-register entry and bound current
disposition record the maintainer's choice.

The reviewed decision text was: “Waive only the requirement that complete
donor-parity evidence predate either donor archive. Accept M-105 after the
existing exact-dossier and history checks pass. Preserve the actual archival
and evidence dates, all legacy-only dispositions, and the absence of a complete
pre-archive parity receipt.” Implementing that choice would add a later
decision and an exact evidence-bound disposition, run the existing Stable
contract reconciliation and negative controls, and update M-105 only. This
paragraph records the proposal that was subsequently approved.

The alternative was to keep D-006-12 unchanged and M-105 blocked. This preserves
the original chronology rule; further work on the same post-archive dossier
cannot change when the evidence was created. Either choice permits independent
work on M-106–M-112 without adding data.

Neither choice waives exact donor identities, file dispositions, applicable
behavioral or byte/history evidence, licence and history preservation, source
rights, M-106–M-113, independent recovery, federation acceptance or any release
gate. It does not authorize new data, dataset publication, live participant
collection or a consequential clinical claim. No participant or cohort-derived
data was accessed for this review.
