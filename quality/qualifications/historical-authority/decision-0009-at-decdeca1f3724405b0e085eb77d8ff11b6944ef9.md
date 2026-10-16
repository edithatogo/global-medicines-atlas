# Decision 0009: consolidate Australian health authority and use a public data plane

**Status:** accepted for planning and implementation on 2026-08-29.

**Decision owner:** sole maintainer.

**Scope:** `edithatogo/aus_mbs_pbs_graph`,
`edithatogo/aus-health-data-scraper`, overlapping Australian MBS/PBS source
contracts, their raw and derived datasets, the Global Medicines Atlas
medallion, and the relevant Hugging Face datasets and collections.

## Decision

Adopt Global Medicines Atlas as the canonical code, schema, provenance, and
orchestration authority for the complete Australian MBS/PBS scope represented
by the two donor repositories. Incorporate all donor data, including legacy,
superseded, empty-placeholder, and failed-source artifacts where those bytes or
states are useful evidence. Incorporate all functionality by one of these
explicit mechanisms:

1. adopt or adapt working behavior into the governed GMA architecture;
2. replace broken, unsafe, or source-drifted behavior with a tested equivalent
   while retaining the exact legacy implementation as regression evidence;
3. retain exact data/code/history as a labelled compatibility artifact; or
4. convert a roadmap-only commitment into an explicitly unimplemented successor
   task rather than claiming it already exists.

For publication-approved Australian data, use public, source-specific Hugging
Face datasets as the mandatory durable data plane. GitHub Actions is the only
publication origin. Each object is pinned by repository, immutable revision,
path, byte count, and SHA-256 and is anonymously restored before transient
local materializations are removed. Public collection membership is discovery
metadata, not evidence of rights, contents, or coverage.

MBS is admitted as an independent health-service-benefit domain. It is in
product scope because service, diagnostic, and benefit policy can be usefully
analysed beside medicines; it is not a medicine dataset and is linked to PBS or
medicine entities only through typed, evidence-bearing Gold edges.

`reimbursement-atlas` remains a federated HEOR/reimbursement-analysis consumer
and transition compatibility surface. After cutover it must not remain a second
mutable authority for the same raw Australian objects. The two donor GitHub
repositories may be archived, never deleted, only after inventory, parity,
public-data, successor-link, restore, and compatibility gates pass.

## Rights and publication authority

In the 2026-08-29 task, the maintainer explicitly stated that the scoped raw
payloads may be redistributed and directed that they be public. This satisfies
the maintainer authorization gate for the exact donor MBS XML and P7 workbook
identified in the consolidation inventory and for the public end state of the
scoped MBS/PBS data plane. Implementation must still bind a non-secret
source/file/destination authorization receipt to each exact hosted publication;
it must not generalize the assertion to SNOMED CT-AU, AMT, UMLS, RxNorm
vocabulary bytes, unrelated private repositories, or unenumerated future
sources.

## Options considered

### A — Complete consolidation with semantic separation and public data plane (chosen)

All donor scope is incorporated, but production behavior, legacy evidence, and
future design commitments are labelled honestly. GMA becomes the single
control plane; public Hugging Face datasets hold the data; MBS remains
semantically independent; downstream repositories federate through pinned
contracts.

This maximizes preservation and analytical value while avoiding duplicate
mutable authorities and false equivalence between services and medicines.

### B — Keep the repositories independent

This would preserve current boundaries but continue duplicated source logic,
broken scheduled work, ungoverned local data, and ambiguous authority. It was
rejected because the donor scope fits the Atlas once MBS is modeled separately.

### C — Copy every file directly into the production package

This would appear maximally inclusive but would promote an invalid Python file,
dead URLs, unbounded requests, zero-byte notebooks, guessed XML tags, and
roadmap prose as if they were qualified functionality. It was rejected in
favor of exact preservation plus tested successors.

## Consequences

- Every donor file and behavior needs a machine-readable disposition and
  parity evidence.
- Historical/current comparison becomes a first-class product capability.
- B0/B1/B2 gain federation/distribution identities without adding a new
  medallion level; v4 remains additive to v1-v3.
- Silver and Gold must model MBS and PBS source structures independently before
  linking them.
- Local datasets become transient caches; durable approved data is public on
  Hugging Face and independently recoverable.
- The legacy composite Hugging Face dataset may be public only after an exact
  manifest comparison and hosted anonymous digest verification.
- Licensed or unresolved private archives outside the exact Australian scope
  remain private.
- Donor repository archival is a final human gate after parity, not a first
  migration step.

## Supersession and compatibility

This decision refines, but does not erase, Decision 0008. Source-specific
rights and exact publication receipts remain mandatory. It also refines the
earlier ecosystem statement that GMA should not duplicate a reimbursement
lake: GMA now absorbs this bounded donor source/medallion scope, while
non-duplicative HEOR, VOI, simulation, and licensed-client responsibilities
remain federated outside the repository.
