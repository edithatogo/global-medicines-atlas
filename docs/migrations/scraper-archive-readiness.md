# Scraper archival readiness

Scope: `edithatogo/aus-health-data-scraper`, observed on 2026-09-06 at
`009e80544588a956c8922aaab052ee08947e2b30`. This is preparation, not an
archive approval or a claim of complete historical source coverage.

## Local work reconciled

The donor checkout remains at `931da0b9b6ae3e3cec0743568abb71a50d62b7cf`
with local edits. The [inventory](scraper-local-20260906/inventory.json)
records exact file hashes and preserves the two-file
[group-filter patch](scraper-local-20260906/group-filter.patch).
It applies to that baseline, not directly to the newer hosted head.

GMA adapts the useful change as `mbs_compatibility.select_group_records`:
`None` returns all admitted records; a group such as `T8` selects exact native
values without changing record identity, ordering, fields or provenance.
`select_p7_records` remains compatible. Blank and padded filters fail rather
than silently broadening the selection. Tests cover both official `MBS_XML/Data`
and donor `mbs/item` profiles, missing groups, unknown groups and P7 parity.

The untracked [PBS JSON example](scraper-local-20260906/sample_pbs.json)
contains two synthetic Medicine A/B entries. It is retained as a legacy fixture,
not an acquired PBS schedule, a supported production input or funding evidence.
The local deletions concern seven zero-byte notebook placeholders already in
the preserved baseline history. Their names and deletion state are recorded;
no analysis content was found in those baseline objects. Finder `.DS_Store`
metadata is excluded. The donor checkout has not been edited or cleaned.

## Explicit compatibility dispositions

| Behavior | Decision before archival | Evidence / follow-up |
| --- | --- | --- |
| Inclusive months, item/participant URLs and filenames | Retained behind bounded compatibility contracts | `tests/test_mbs_compatibility.py` |
| XML group filtering | Adapted, including local general-group work | `tests/test_au_mbs_source.py` |
| Async `scrape_items` / `scrape_participants` signatures | Retain in donor history; no drop-in GMA API promise | GMA uses its governed acquisition interface; no demonstrated consumer requires these exact functions |
| HTML `rowspan` / `colspan` | Explicitly unsupported when spans exceed one | `tests/test_mbs_tables.py`; add a source-specific profile if a real supported source requires it |
| One heterogeneous `dataset.csv` | Superseded by separate typed tables | Source/table identity and native columns remain distinguishable |
| Historical participant counts | Acquisition remains unqualified | Continue in GMA under consolidation issue #339; discover a supported source and require nonempty admitted artifacts and receipts |
| Future monthly source updates | Separate source-specific operational scope | August 2026 exact release evidence is not blanket authorization or proof of future coverage |

Literal API parity and unrestricted generic HTML parsing are therefore not
archive acceptance claims. Preserving useful behavior does not require copying
these legacy interfaces. No roadmap-only graph, terminology or NLP feature
needs to be implemented merely to archive this scraper.

## Open donor work disposition

Live inventory found only `main` and `renovate/configure` branches, PR #5 and
issues #1–#3. No additional hosted feature branch was found.

| Donor item | Successor disposition |
| --- | --- |
| [Issue #1](https://github.com/edithatogo/aus-health-data-scraper/issues/1), testing and CI | GMA owns bounded tests, mutation/property lanes, workflow validation, action pinning and protected checks. Run the donor canaries and the existing GMA harness for this change; no duplicate donor CI modernization is needed for a frozen repository. |
| [Issue #2](https://github.com/edithatogo/aus-health-data-scraper/issues/2), security/context/settings | GMA owns its own context, contribution/security policy, dependency and coverage workflows. Donor hosted settings and bot activation are excluded from this archival migration, not claimed fixed. Preserve the issue and its recorded 422 failure. |
| [Issue #3](https://github.com/edithatogo/aus-health-data-scraper/issues/3), parent hardening | Resolve through the evidence-backed dispositions of #1/#2 at final archive closeout. |
| [PR #5](https://github.com/edithatogo/aus-health-data-scraper/pull/5), Renovate onboarding | Do not merge onboarding into a repository intended for archival. Close as superseded during final archive closeout; retain the PR history. |

These dispositions transfer the useful requirements into this GMA record.
Donor issues/PR remain open until final archive closeout; no comments, bot
configuration, branch deletion or hosted-setting changes were made.

## Exact history publication package

The existing public baseline bundle does not contain `009e805`. The checked-in
history contract also covers graph donor `3993e5e`, so its atomic preservation
transaction appends both existing pinned extensions. This does not authorize
archival of the graph repository.

- Contract: `quality/qualifications/australian-donor-history-publication-contract.json`.
- Entrypoint: `scripts/publish_donor_history.py`.
- Workflow: `.github/workflows/australian-donor-history.yml`.
- Destination: `edithatogo/australian-mbs-source-archive` (existing public dataset).
- Additions: two head-addressed incremental `.bundle` objects and two JSON
  sidecars under `provenance/donor-deltas/`.
- Execution: explicitly approved exact merged main commit, hosted environment,
  independent GitHub/Git delta checks, anonymous baseline snapshot, absent-only
  object additions, server-enforced parent CAS, durable intent and acknowledgement,
  anonymous all-object digest comparison, and clean bare Git restoration.
  Restoration uses strict unpacking to loose objects rather than depending on
  generated pack-index sidecars; exact refs, ancestry and full strict fsck
  remain mandatory. Corrupt PACK streams are rejected.
- Cleanup: only after durable verified receipt readback. No deletion or visibility
  rollback of the public dataset; failures retain the hosted temporary workspace
  for the remainder of the runner lifetime and do not claim cleanup.
- Recovery: supply the authenticated bot CAS acknowledgement comment ID. The
  publisher verifies its prior intent, rechecks exact scope and restores without
  uploading again, even if another writer has advanced the dataset head.
  A later reviewed execution commit may verify the same exact contract; the
  receipt retains the original publishing commit and records the verifier.
  This proves the pinned publication revision, not preservation by subsequent
  writers; final archival still needs a current-state preflight.
  A write with no durable acknowledgement remains unresolved;
  it never creates an empty new commit to conceal that ambiguity.

Publication is deliberately disabled. The exact contract still has
`publication_authorized=false` and no approval reference. An approved reference
on GMA issue #339 must be bound in a reviewed contract before workflow dispatch.
The current preparation has not cloned donor source data, uploaded archives,
dispatched a publication workflow or archived a repository.

## Final closeout sequence

1. Complete this change's local and protected hosted checks and merge its PR.
2. Obtain exact approval for the four-object history append; review the bound
   contract, dispatch on its exact main commit, and record verified restoration.
3. Re-query donor heads, branches, open work and successor links. If a donor
   notice changes, preserve its new commit too; never silently reuse an older
   history receipt. Keep the dirty local donor checkout intact.
4. Obtain exact approval to archive `edithatogo/aus-health-data-scraper`.
   Resolve its open hardening issues and onboarding PR using the dispositions
   above, archive without deleting history, and record before/after state.

The consolidated track remains in progress until its required external
preservation and archival evidence exists.

## Approved execution (2026-09-06)

The maintainer approved the four-object history publication and subsequent scraper-only archival in [issue #339](https://github.com/edithatogo/global-medicines-atlas/issues/339#issuecomment-5556212193). The exact contract is now enabled for reviewed hosted execution. Earlier disabled/pending statements above describe preparation. Publication, restoration and archival results remain pending; the graph repository remains unapproved for archival.
