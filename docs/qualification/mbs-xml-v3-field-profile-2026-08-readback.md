# August 2026 MBS XML v3 profile readback and correction

This addendum records the hosted result for the exact August 2026 MBS source
era and corrects an overstatement in the original run interpretation. The
[source-era field crosswalk](./mbs-xml-v3-field-semantics-2026-08.md) is
preserved byte-for-byte at the digest bound by that historical report. Its
field-semantic acceptance claim is withdrawn; see the current
[semantics status](./mbs-xml-v3-field-semantics-status-2026-08.md).

## Exact hosted evidence

- Exact main commit: `a087acdfb935bb79f894ecd3f91530351f3faac8`
- Workflow: [39029209737](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39029209737)
- Aggregate artifact ID: `12100055332`
- Artifact digest: `sha256:982a5e5846a75dfd717a3ca7ad65f3a9906c96f2239944be06aafe270172fbb6`
- Report: [`mbs-source-era-candidate-2026-08-01-dmy-profile.json`](../../quality/qualifications/mbs-source-era-candidate-2026-08-01-dmy-profile.json)
- Report SHA-256: `8e8d14f88baabc10a172fd2ec3947f8a89947828d64fb0237398dc230896763e`
- Bound field crosswalk SHA-256: `8d942dfcf988b74abfca24d4c5883582c86478c4cc829a906b45239612676545`

## Result

The hosted run confirmed the pinned archive payload exactly matches the
official August release: `c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565`,
8,293,331 bytes. The candidate includes 6,046 source records, 40 native
fields, and 241,840 field occurrences. Each field has 6,046 rows, and all 40
per-field source-presence states match their projected native states.

The profile applies `mbs-dmy` only to this release, following the Department's
published `DD.MM.YYYY` XML field guide linked from the August release page.
Conversion statuses total 42,088 converted, 94,267 preserved, 24,837 missing
fields, and 80,648 explicit nulls. No invalid or unsupported-format values
remain. The report contains aggregate counts and no source values; source bytes
were not retained.

## Remaining qualification boundary

The hosted run proves byte identity, source/native presence alignment, and
observed date-conversion counts. The current guide supports the declared date
grammar for candidate profiling, but neither it nor the successful parse proves
that all field meanings are versioned for this exact release. Therefore
`field_semantics_accepted` is withdrawn and the field-semantics blocker remains
open. The historical report's original bytes and digest are retained; no raw
source rerun is needed to correct this interpretation. Public v4 admission was
not performed. Historical MBS/PBS eras, the complete approved M-109 denominator,
and full M-109 acceptance remain open. The candidate was not published or
promoted.
