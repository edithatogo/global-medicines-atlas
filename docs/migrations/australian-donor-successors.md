# Australian donor compatibility and successor preparation

This is the canonical successor map, not a claim that consolidation, live
scheduling, or donor archival is complete. It adapts the existing nzmedicines
compatibility-notice pattern without inheriting that repository's approvals.

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

## Successor notice text for both donors

Active successor development is in
[Global Medicines Atlas](https://github.com/edithatogo/global-medicines-atlas).
This donor repository remains an unarchived compatibility and provenance
mirror. Its historical code, commit links and source identifiers are retained;
the old scraper's green runs must not be interpreted as successful acquisition.

GMA preserves independent MBS service-benefit, PBS funding/formulary, regulatory
and terminology evidence. It replaces defective donor parser/processor paths
with bounded typed implementations. The consolidation plan and explicit gaps
are tracked in [issue #339](https://github.com/edithatogo/global-medicines-atlas/issues/339).
Roadmap-only graph, ontology, NLP, Spark and Airflow plans are not delivered
features; see the canonical successor map above.

Exact donor data and complete Git-history preservation are available at
[MBS archive revision 4d1dae4](https://huggingface.co/datasets/edithatogo/australian-mbs-source-archive/tree/4d1dae488ac43522f20e8320a8b2a56bf9138341).
The independently acquired PBS schedule is at
[PBS archive revision 31ec854](https://huggingface.co/datasets/edithatogo/australian-pbs-source-archive/tree/31ec854ef9fc82f30a0dbe743fdf50a2e5bd24a7).
Neither is a promise of complete current coverage. Future dataset publication
runs from GitHub Actions to public Hugging Face, never from developer machines.

## Canary and archival checklist

Before claiming successor-notice completion, record both published notice
URLs/commits, verify their canonical and immutable archive links, and run:

```sh
uv run python -m pytest -q tests/test_donor_inventory.py tests/test_au_mbs_source.py tests/test_au_mbs_workbook.py tests/test_au_pbs_v3.py tests/test_mbs_compatibility.py tests/test_mbs_tables.py
```

This is fixture/contract compatibility evidence, not a live-source canary.
Phase 4 additionally needs a hosted current-release run, admitted nonempty
artifacts, persistent source-health receipts and anonymous digest verification.

Before any archival, re-query both default-branch heads, verify any changes
since the preserved commits have their own durable history receipt, check
open PRs/issues/workflows, complete successor notices and canaries, and obtain
the maintainer's exact two-repository archive approval. The original pinned
bundles do not preserve future notice commits or later donor work.

The following commands are documentation only; do not execute without that
approval and a recorded final preflight:

```sh
gh repo archive edithatogo/aus_mbs_pbs_graph --yes
gh repo archive edithatogo/aus-health-data-scraper --yes
```

Archival is reversible and must never delete branches, history, issues, source
archives or dirty local checkouts. Record before/after repository state and
approval in the evidence ledger. If rollback is approved, unarchive the exact
repository with `gh repo unarchive OWNER/REPOSITORY --yes`, then verify heads,
links, permissions and workflow settings against the preflight snapshot.
Do not automatically reactivate obsolete acquisition schedules. No archival
has been authorized or performed by this preparation document.
