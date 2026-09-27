# Australian health federation acceptance, 2026-09-27

The stable-v1 federation gate remains blocked. Its nine requirements are
independent: completed donor archival does not qualify the public derived data
plane, Silver and Gold denominators, or Platinum results. This table records
the next acceptance evidence required by each requirement, using the current
track plans and observed archive receipts rather than implementation alone.

| Requirement | State | Acceptance evidence still needed |
| --- | --- | --- |
| M-105 donor consolidation | Blocked | Reconcile pinned and post-baseline behavior, data, and workflow dispositions against the complete donor inventory; distinguish successor roadmap work from proven parity. |
| M-106 independent MBS domain | Blocked | Qualify source-native service, benefit, participant, and temporal denominators without converting them to medicine or PBS assertions. |
| M-107 historical snapshots | Blocked | Verify the approved current and historical MBS/PBS inventory, schema-era labels, completeness, and recoverability, including unresolved source failures. |
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
