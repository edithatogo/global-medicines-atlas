# Australian health federation acceptance, 2026-09-27

The stable-v1 federation gate remains blocked. Its nine requirements are
independent: completed donor archival does not qualify the public derived data
plane, Silver and Gold denominators, or Platinum results. This table records
the next acceptance evidence required by each requirement, using the current
track plans and observed archive receipts rather than implementation alone.

| Requirement | State | Acceptance evidence still needed |
| --- | --- | --- |
| M-105 donor consolidation | Blocked | The [parity gap audit](australian-donor-parity-gap.md) and exact-identity disposition matrix now reconcile all 54 baseline blobs and ten later changed paths. The donor monthly workflow is retained as legacy-only; the separate scheduled GMA XML release has a verified public receipt. This post-archive evidence cannot satisfy M-105's requirement that parity be proved before either donor archive. Maintainer disposition of that historical exception remains separate from M-106–M-112. |
| M-106 independent MBS domain | Blocked | The [domain evidence matrix](australian-mbs-m106-domain.md) binds the approved 6,046-row XML service, group, fee, benefit, and temporal fields to their exact release. The separately authorized aggregate-patient workbook timed out in the hosted utilisation harvest; qualify its native denominator and establish item-level participation separately if required. |
| M-107 historical snapshots | Blocked | The [snapshot inventory](australian-mbs-pbs-m107-snapshots.md) distinguishes public MBS/PBS revisions, legacy and schema-era objects, partial utilisation coverage, and unresolved source failures. On 2026-09-28 the official annual-statistics page titled 2009-10 to 2025-26 linked a workbook named 2009-10 to 2024-25. The earlier discovery run [36327563968](https://github.com/edithatogo/global-medicines-atlas/actions/runs/36327563968) failed closed before staging. The corrected exact-main run [36330658537](https://github.com/edithatogo/global-medicines-atlas/actions/runs/36330658537) published revision `32ce8741be7f0508dca641a3e397759ec492da02`, anonymously verified all 28 objects, recorded `partial` latest-run coverage with all three Health.gov families unavailable, and removed hosted temporary bytes. The runner discovered zero workbook URLs because official publication-page requests timed out. This follow-up adds direct official workbook fallbacks for the known June-quarter and July-to-June 2025–26 resources plus the page-linked 2024–25 annual workbook; filename-period checks retain the annual gap. This does not establish a 2025–26 annual workbook, complete historical series, or M-107 acceptance. |
| M-108 public durable data plane | Blocked | Publish and anonymously restore each admitted Australian derived product with its exact v4 identity, rights, data card, collection and replica evidence. Raw archives alone do not satisfy this. |
| M-109 Silver | Blocked | Qualify real-corpus MBS and PBS source-field denominators, typed tables, historical schema mappings and lineage. Fixture tests do not establish full-field preservation. |
| M-110 Gold | Blocked | Qualify evidence-bearing typed graph nodes and edges, temporal validity, review decisions and negative controls over admitted real source tables. |
| M-111 Platinum | Blocked | Verify API, CLI, atlas and export products against pinned public Parquet and manifests, including provenance, freshness, coverage, cohort and confidence. |
| M-112 federation v4 | Blocked | Emit and independently verify live producer v4 contracts for the published derived corpus and downstream compatibility canaries. The schema and synthetic contracts are implementation evidence. |
| M-113 donor archival | Verified | Both separate maintainer approvals, exact public history preservation, anonymous clean restore and unchanged archived Git heads are recorded in the [scraper receipt](../../quality/qualifications/scraper-archival-20260906.json) and [graph receipt](../../quality/qualifications/graph-archival-20260906.json). |

The donor repositories were read back as archived on 2026-09-27. The scraper
receipt binds both exact donor heads to 30 anonymously verified public history
objects at revision `97038008d17a48f620302f04fe6a3156fb8d5d57`. The graph
receipt records its separate approval, retained heads, and unchanged public
revision. This is acceptance of the archival sequence, not of the entire
Australian health federation or a stable release.

The immediate executable path is to finish the exact producer denominator and
real-corpus Silver qualification, then publish and verify derived medallion
products and v4 identities. Restricted terminology and an administratively
independent replica retain their separate authority gates.
