# Graph repository archival readiness

Prepared on 2026-09-06 for `edithatogo/aus_mbs_pbs_graph` at
`3993e5e331eb2d3d9e9d354d80e52c684ad26a1e`. The repository is unarchived;
archival approval is the remaining human gate. See the
[machine-readable preflight](../../quality/qualifications/graph-archive-readiness-20260906.json).

## Preservation and implementation

The existing [hosted preservation receipt](https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-5556271994)
proves clean restoration of this exact graph head from its baseline and
incremental bundles. Public revision `97038008d17a48f620302f04fe6a3156fb8d5d57`
still matches the verified revision and all 30 sibling paths. Its receipt
model and digest were revalidated; no source payload was downloaded locally
and no additional publication is required.

The substantive July 2025 MBS XML is already preserved with its exact digest,
5,989 records and 40 native fields. There is no donor PBS dataset to migrate.
GMA replaces the donor download/parser/tag-inspection experiments with governed
MBS/PBS implementations. The latest donor delta is only README/SUCCESSOR text.
The [successor map](australian-donor-successors.md) retains the unimplemented
terminology, graph and NLP roadmap with explicit maturity boundaries. Completing
those future capabilities is not a prerequisite to archiving legacy code.

## Final hosted inventory and open-work dispositions

- `main` remains at the preserved head. `renovate/configure` remains at
  `d05f2475c211f42f1ae135dac9528139bcb02c38`; its sole PR addition is
  `renovate.json`, with no unique data or implemented feature. This branch and
  its PR remain on GitHub; the main-head bundle claim does not include it.
- No tags, releases or workflow artifacts were found. The native Dependency
  Graph workflow is active; it is not an acquisition pipeline or evidence of
  acquired coverage. No hosted settings were changed.
- [Issue #2](https://github.com/edithatogo/aus_mbs_pbs_graph/issues/2) is closed
  as superseded: GMA owns parser regressions, bounded tests and governed CI;
  duplicate donor modernization is excluded.
- [Issue #3](https://github.com/edithatogo/aus_mbs_pbs_graph/issues/3) is closed
  as superseded: GMA owns security/context controls. Donor bot activation,
  new rulesets and the recorded GitHub 422 are excluded, not claimed fixed.
- [Issue #4](https://github.com/edithatogo/aus_mbs_pbs_graph/issues/4) is closed
  with the evidence-backed child dispositions above.
- [PR #6](https://github.com/edithatogo/aus_mbs_pbs_graph/pull/6) is closed
  unmerged as superseded. Its branch and discussion are retained.
- A fresh query found zero open issues and PRs. The successor notice's two
  immutable archive links returned HTTP 200. No donor commit was introduced.
- No graph checkout was found among immediate entries of
  `/Volumes/PortableSSD/GitHub`; this is a bounded search, not a claim about
  other disks. No local donor files were modified.

## Validation and final action

174 focused inventory, MBS/PBS and history canaries passed in 9.31 seconds.
The recorded same-code full local suite passed 4,819 tests with one optional
skip and 96.65% coverage, then stopped at the macOS mutation gate; Linux CI is
authoritative. This metadata-only preparation uses fresh context validation
and its own protected hosted checks.

After this readiness PR merges, obtain explicit approval for
`edithatogo/aus_mbs_pbs_graph` only. Immediately before archival, re-query the
head, both branches, open work and public archive revision. If a new donor
commit appears, preserve its exact history before proceeding. If Renovate
creates new work, disposition it before archival. Archive without deleting
branches or history, then record the observed before/after state in this track.
The previous scraper approval does not authorize graph archival.
