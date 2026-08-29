# Maintainer-Owned Ecosystem Reuse

The machine-readable authority map is [`.context/ecosystem.toml`](../.context/ecosystem.toml).
Before adding a dependency, dataset, adapter, publication workflow, or domain
contract, check that registry and the maintainer's GitHub and Hugging Face
resources.

The rule is:

1. reuse or extend the declared maintainer-owned authority when its contract fits;
2. extract a shared package only after two repositories need a stable contract;
3. preserve repository, immutable snapshot, licence, and transformation provenance;
4. contribute improvements to the authoritative repository rather than maintaining
   divergent copies;
5. keep licensing, credentials, publication, and consequential claims as human gates.

`global-medicines-atlas` owns medicine identity and separate regulatory,
funding, formulary, terminology, and Australian health-service-benefit source
contracts. Under Decision 0009 it becomes the canonical code and governance
authority for the MBS/PBS functionality and data previously split across
`aus_mbs_pbs_graph` and `aus-health-data-scraper`. It absorbs that whole donor
scope through explicit dispositions: working behavior is adopted or adapted,
broken behavior is replaced by a tested equivalent, exact legacy artifacts are
retained for comparison, and roadmap-only capabilities become honest successor
tasks.

This is not a rejection of consolidation. It is the mechanism by which all of
the donor scope is incorporated without pretending that syntactically invalid
scripts, dead URLs, empty notebooks, or unimplemented Neo4j/NLP plans were
production capabilities. The donor repositories become read-only compatibility
and provenance surfaces and may be archived only after parity and public-data
receipts pass.

`reimbursement-atlas` remains a federated HEOR and reimbursement-analysis
consumer during the transition. GMA is the source/medallion control plane for
the Australian MBS/PBS corpus; reimbursement-atlas consumes pinned public data
contracts and may retain non-duplicative analysis, policy, and compatibility
surfaces. It does not remain a second mutable authority for the same raw
objects after cutover. GMA continues to interoperate with decision-analysis
repositories and does not absorb a VOI engine, simulation runtime, or licensed
FHIR client merely because those systems consume medicine evidence.

Hugging Face publication is an output boundary and the mandatory durable public
data plane for publication-approved objects, not an unreviewed source of truth.
The bytes and content-addressed receipt remain authoritative. Existing datasets
are reused only when exact revisions, manifests, source rights, provenance,
coverage, visibility, and anonymous restoration pass. No approved dataset may
remain durable only on a developer machine.

## Australian consolidation authorities

| Surface | Transition authority | Disposition |
|---|---|---|
| `edithatogo/aus_mbs_pbs_graph@64e764c` | Donor code, one July 2025 MBS XML payload, PBS v3 parser experiment, graph design intent | Migrate all behavior/data or preserve exact legacy evidence; archive after parity |
| `edithatogo/aus-health-data-scraper@931da0b` | Donor MBS HTML/XML workflow, P7 workbook, fixtures and legacy notebooks | Migrate all behavior/data or preserve exact legacy evidence; archive after parity |
| `edithatogo/global-medicines-atlas` | Canonical Australian acquisition, medallion contracts, evidence graph and products | Authoritative after cutover receipts pass |
| public Hugging Face Australian datasets | Raw and derived public data plane | Immutable revision/path/digest identities; never inferred from collection membership |
| `edithatogo/reimbursement-atlas` | Federated HEOR analysis and transition compatibility | Consume GMA contracts; retire duplicate mutable source authority after canaries pass |

## Pre-acquisition reuse gate

Before any acquire or download (including Drugs@FDA), search:

1. local clones and declared `local_boundary` paths;
2. maintainer GitHub repositories in this registry;
3. Hugging Face datasets, including
   `edithatogo/global-medicines-atlas-catalogue`;
4. the medicine source catalog (`medicine_source_catalog.json`).

Then choose exactly one of **reuse | link | mirror | extend | fork |
acquire-new**. acquire-new is last resort. Acquisition without this gate
fails. Each search is pinned in a versioned discovery snapshot (schema
`global-medicines-atlas.reuse-discovery`; see
[`schemas/reuse-discovery-snapshot-v1.json`](../schemas/reuse-discovery-snapshot-v1.json)).
The snapshot records query, revision, candidate digest, tool version,
generation time, expiry, and per-surface success/unavailable/incomplete state.
Success with no candidates means no candidate was found; unavailable or
incomplete means the search cannot support that conclusion. A stale snapshot
or skipped surface fails closed for `acquire-new`.

Refresh with `scripts/refresh_reuse_discovery.py`, consuming JSON indexes from
the existing authenticated `gh` or Hugging Face CLI context without writing
credentials. The pinned JSON supports offline reconstruction and is not a copy
of source payload bytes. The choice and snapshot ID are recorded on the
acquisition receipt, B1 manifest, and OpenLineage projection.
