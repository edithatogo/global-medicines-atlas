# Australian donor compatibility and successor status

Final archival status (2026-09-06): both Australian donor repositories are
archived. Graph archival was separately approved and verified at
2026-09-06T03:02:52Z; see the
[graph archival receipt](../../quality/qualifications/graph-archival-20260906.json).
Both graph branch refs are retained; earlier pending statements below describe
the preparation chronology, not the current archive state.

## Historical preparation snapshot (before archival)

Pre-graph-archive snapshot (2026-09-06): the four-object history append passed anonymous
verification in [run 34005721959](https://github.com/edithatogo/global-medicines-atlas/actions/runs/34005721959).
`aus-health-data-scraper` is archived; its issues #1–#3 and PR #5 are closed as
superseded, with branches/history and local edits retained. The graph repository
is unarchived and requires separate approval. See the
[closeout receipt](../../quality/qualifications/scraper-archival-20260906.json).
Earlier pending/disabled statements below describe the preparation chronology.

The capability dispositions below remain the canonical successor map.
Historical preparation details are labelled as such; current archival status
is recorded above and in the final receipts. The compatibility pattern does
not inherit another repository's approvals.

## Exact baseline and capability disposition

The [machine-readable map](../../quality/qualifications/australian-donor-successors.json)
binds both commits to the [complete donor inventory](../../quality/qualifications/australian-health-donor-inventory.json).
Tests require all eight roadmap commitments and an existing successor task.

| Donor commitment | Disposition | Completion boundary |
| --- | --- | --- |
| Neo4j/Cypher | Design preview | Frontier graph parity over portable Gold tables |
| SNOMED CT-AU RF2 and official mappings | Separately gated | Exact rights/access approval; no restricted bytes by implication |
| Complete AMT hierarchy/mappings | Separately gated | PBS reference extraction is implemented, full terminology ingestion is not |
| Complete ATC hierarchy | Separately gated | PBS codes are implemented, hierarchy acquisition needs its own denominator/rights |
| NLP/NER | Design preview | Candidate extraction, calibration and adjudication; no automatic promotion |
| Temporal MBS/PBS graph | Design preview | Gold evidence edges and historical comparison, not clinical equivalence |
| Spark | Rejected for current adoption | Reconsider only after a measured unmet workload and separate ADR |
| Airflow | Rejected for current adoption | Reuse hosted Actions/catalogue controls; no second orchestration service |

None of these eight capabilities was implemented by the pinned donors.
The frozen donor assessment describes the pre-consolidation baseline; it is
not a current status report. MBS XML/workbook and PBS v3 parsers, bounded CLI
inspection, historical mock probes and typed HTML/P7 compatibility are now
repository implementations. Live scheduling is a separate Phase 4 gate.

## Proposed successor notice refresh (authorization pending)

The text below is a draft for the default-branch `README.md` and
`SUCCESSOR.md` in each archived donor repository. It corrects the stale archive
status and identifies the exact public successor dataset revisions observed
on 2026-10-04. This proposal does not authorize unarchiving either repository,
committing the text externally, creating a tag or release, or publishing a
dataset. The existing `v0.1` scraper tag predates successor documentation and
should remain historical; do not move or replace it.

> This repository is an archived compatibility and provenance mirror. Its
> history and source identifiers are retained. Active successor development
> is in [Global Medicines Atlas](https://github.com/edithatogo/global-medicines-atlas);
> see its [Australian donor capability map](https://github.com/edithatogo/global-medicines-atlas/blob/main/docs/migrations/australian-donor-successors.md).
>
> Public successor dataset identities observed 2026-10-04:
>
> - MBS source archive: [`edithatogo/australian-mbs-source-archive` at
>   `40891976f77ee5e7688edceed25c9ac98a77547e`](https://huggingface.co/datasets/edithatogo/australian-mbs-source-archive/tree/40891976f77ee5e7688edceed25c9ac98a77547e).
> - PBS source archive: [`edithatogo/australian-pbs-source-archive` at
>   `48fd7345fb09277bb5b85644dba72804633a2abb`](https://huggingface.co/datasets/edithatogo/australian-pbs-source-archive/tree/48fd7345fb09277bb5b85644dba72804633a2abb).
>
> Frozen historical donor evidence remains directly available at the
> [MBS archive revision `4d1dae488ac43522f20e8320a8b2a56bf9138341`](https://huggingface.co/datasets/edithatogo/australian-mbs-source-archive/tree/4d1dae488ac43522f20e8320a8b2a56bf9138341)
> and the [PBS archive revision `31ec854ef9fc82f30a0dbe743fdf50a2e5bd24a7`](https://huggingface.co/datasets/edithatogo/australian-pbs-source-archive/tree/31ec854ef9fc82f30a0dbe743fdf50a2e5bd24a7).
> These immutable baseline revisions preserve historical donor material;
> they do not identify the current successor dataset heads.
>
> The current successor revisions above are immutable dataset revisions, not
> a promise of complete or continuously current coverage, and this notice does
> not state a source licence or expand reuse rights. MBS service-benefit
> evidence remains distinct from PBS funding/formulary, regulatory, and
> terminology evidence.
> Historical donor archives remain available at the separately documented
> baseline revisions; later successor dataset revisions do not rewrite that
> history. Dataset publication is performed only by the governed GitHub
> Actions workflow with anonymous digest verification.

Before using this draft, re-read both repository heads and the two dataset
revisions. For any future compatibility release, use a new versioned release
that links to the approved notice; keep existing tags and history unchanged.

## Successor-link readback (2026-10-04)

The anonymous GitHub readback confirmed both repositories are archived at
their expected preserved heads. Their current `README.md` files link to
`SUCCESSOR.md`, and both notices link to the GMA repository and this canonical
successor map. However, both README files and notices still say the donor
repository is unarchived. The notices link to the historical HF revisions
above rather than identifying current successor dataset heads. The GMA-side
canonical copy is corrected here; the archived external notices have not been
changed.

| Donor repository | Archived head | README blob | `SUCCESSOR.md` blob | GitHub Releases | Tags |
| --- | --- | --- | --- | ---: | --- |
| `edithatogo/aus-health-data-scraper` | `009e80544588a956c8922aaab052ee08947e2b30` | `0abbc7ca2e8b3fff572e43e60f57631348e33a47` | `7836ca20ec41e835d52118e1ecbca8ed463ff4fc` | 0 | `v0.1` |
| `edithatogo/aus_mbs_pbs_graph` | `3993e5e331eb2d3d9e9d354d80e52c684ad26a1e` | `9d9fd230fb9eb3d178f56d86cb0fd55259322b80` | `7836ca20ec41e835d52118e1ecbca8ed463ff4fc` | 0 | none |

The scraper's `v0.1` tag points to commit `25bc585647d1f16b4f45c8b648212ab81e157b60`;
its tagged README blob `31adba7b45e228e21f4f19049eb280accf83952f` predates the
successor notice and has no successor link. No GitHub Release objects or
release assets were observed for either donor. The detailed readback is
`quality/qualifications/australian-donor-successor-link-readback-20261004.json`.

The current public successor dataset metadata identifies MBS revision
`40891976f77ee5e7688edceed25c9ac98a77547e` and PBS revision
`48fd7345fb09277bb5b85644dba72804633a2abb`; both were public and ungated at
readback. These metadata observations do not verify every object digest or
establish source rights. The donor-link acceptance task remains open until the
stale archived notices and the scraper tag's absent successor path are
resolved through an approved route. Updating content in an archived public
repository requires explicit maintainer authorization; no repository was
unarchived or mutated for this readback.

## Historical canary and archival checklist

The metadata-only refresh on 2026-08-31 observed graph head `3993e5e` and
scraper head `009e805`. The graph delta is two documentation paths; the scraper
delta is eight paths including code, workflow and tests. Its commit message is
not an executable-change denominator. GMA already bounds requests and rejects
unsupported parsing; the donor's new `asyncio.to_thread` calling behavior is
legacy compatibility, not demonstrated GMA async API parity. No raw-data paths
changed, but neither later commit is covered by the original history bundles.
Both need exact hosted preservation receipts before the final archive gate.

Before claiming successor-notice completion, record both published notice
URLs/commits, verify their canonical and immutable archive links, and run:

```sh
uv run python -m pytest -q tests/test_donor_inventory.py tests/test_au_mbs_source.py tests/test_au_mbs_workbook.py tests/test_au_pbs_v3.py tests/test_mbs_compatibility.py tests/test_mbs_tables.py
```

This is fixture/contract compatibility evidence, not a live-source canary.
Phase 4 additionally needs a hosted current-release run, admitted nonempty
artifacts, persistent source-health receipts and anonymous digest verification.

Before the 2026-09-06 archival, the maintainer required re-querying both
default-branch heads, verifying any changes
since the preserved commits have their own durable history receipt, check
open PRs/issues/workflows, complete successor notices and canaries, and obtain
the maintainer's exact two-repository archive approval. The original pinned
bundles do not preserve future notice commits or later donor work.

Archival is reversible and must never delete branches, history, issues, source
archives or dirty local checkouts. Record before/after repository state and
approval in the evidence ledger. If rollback is approved, unarchive the exact
repository with `gh repo unarchive OWNER/REPOSITORY --yes`, then verify heads,
links, permissions and workflow settings against the preflight snapshot.
Do not automatically reactivate obsolete acquisition schedules. Both
archivals are complete as recorded above. This document does not authorize a
future unarchive, public mutation, or dataset publication.
