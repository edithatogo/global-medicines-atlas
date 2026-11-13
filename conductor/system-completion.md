# System completion execution charter

## Accessibility testing excluded — 3 November 2026

The maintainer explicitly removed accessibility testing from project scope.
Manual and automated accessibility audits, screen-reader/assistive-technology
qualification, WCAG conformance testing and accessibility-specific acceptance
are excluded from every current Conductor track and from the roadmap. They
are not deferred work or a pending completion gate. Do not schedule further
accessibility testing without new explicit maintainer direction. Historical
results and unverified assessments remain evidence, not conformance claims.
Existing working UI features and tests are retained; this scope change does
not delete regressions, weaken protected CI, or mark unperformed tests passed.
All other source, temporal-data, rights, production and release gates remain.

## Execution objective and authority

On 29 October 2026 the maintainer selected **bounded software completion;
federation later**. Complete the existing software candidate using its current
qualified inputs and representative fixtures. Add no sources, object cohorts,
semantic interpretations or infrastructure merely to finish the software.

This supersedes the earlier scheduling requirement to work through all five
federation stages before stopping. It does not amend their acceptance contracts,
mark blocked requirements complete, or permit a Stable v1 release. The
Australian federation stages below remain the later milestone, with their
receipts and limitations intact. The bounded candidate is not a new release tag.

## Bounded software finish line

Use one coherent completion packet, with this finite checklist:

- The repo-local Python 3.15.1 environment installs from the existing lock.
- CLI, read-only API, Atlas and deterministic export behavior pass their existing
  representative tests. Retain their fixture and source-structure limits.
- The existing clean-consumer harness builds and installs the wheel and source
  distribution and verifies the installed CLI/API and package contracts.
- The contributor quick start uses supported commands and focused checks.
- The changed scope and deferred work are recorded here and on the roadmap;
  the scoped PR passes protected checks and is integrated by the repository's
  existing integrator. Reuse unchanged behavioral and hosted evidence.

Once this checklist passes, stop software-completion work. Do not fill every
remaining checkbox in historical plans. Report the tested candidate, commands,
artifact paths and limitations once. Stable v1 remains blocked by the existing
federation contract; dataset publication, deployment and expanded claims retain
their separate authority requirements.

## Later federation milestone

The [machine-readable scheduling plan](./system-completion.json), checked by
`scripts/validate_context.py`, records the lanes and their prerequisites. This
charter sets scheduling priority. It does not change acceptance criteria,
qualify data, waive requirements, or authorize publication or release.

Use the [Stable v1 contract](../quality/qualifications/stable-v1-contract.json),
its [readiness reconciliation](../quality/qualifications/stable-v1-release-readiness-reconciliation.json),
the owning track receipts, and `scripts/reconcile_stable_v1_contract.py` for
gate states. Read their bound evidence before choosing work; do not infer
current status from historical plan sections. Conditional maintainer approval
remains subject to its recorded conditions. The current M-105 and M-107
dispositions remain effective until supported by their required evidence and
any applicable decision.

### Acceptance lanes

| Order | Lane | Completion evidence and owning tracks |
| --- | --- | --- |
| 1 | Shared Silver/Gold contracts and uncertainty | Qualify source-faithful schemas, field-state accounting, supported meanings, and relationship promotion/rejection behavior. Preserve every field and reconcile it as interpreted, native unresolved, or unavailable. Unsupported meanings remain explicit; universal interpretation is not required. Silver/Gold and consolidation tracks own their existing criteria. |
| 2 | Qualified v4 delivery and admission | Bind eligible outputs to exact identities, lineage, rights, required contract roles, and admission receipts. Complete each mandatory eligible-object obligation. Data-plane and producer tracks own these receipts. |
| 3 | API, CLI, Atlas and export consumers | Traverse qualified admitted data through actual consumers and exports, retaining provenance, coverage, uncertainty, bounded behavior, and exact revision/digest evidence. Platinum owns these checkpoints with producer support. |
| 4 | Independent recovery and compatibility | Qualify the required independent recovery target, restoration, checksum inventory, RPO/RTO, and declared consumer/package compatibility. Data-plane, Platinum, and Stable tracks retain their respective acceptance boundaries. |
| 5 | Federation acceptance and Stable promotion | Reconcile authoritative requirement and gate evidence, complete federation acceptance, then reproduce and verify the exact candidate and protected checks before exercising conditional Stable approval. Use the existing release harness and authority. |

These are deferred dependency stages, not the bounded software checklist. After
explicit resumption, independent lanes may proceed when their prerequisites are
satisfied and file/object ownership is explicit. A fixture or representative
reference-class canary can establish shared behavior; it cannot substitute for
mandatory eligible-object identity, lineage, rights, admission, recovery, or
consumer evidence. Candidate publication, byte verification, reader canaries,
semantic qualification, product acceptance, and release remain distinct.

## Task selection and stop conditions

Before starting each task, record:

1. the owning system lane and existing capability or gate;
2. the concrete observed failure or missing acceptance proof;
3. the bounded object, code, and evidence scope within the frozen inventory;
4. the expected receipt or observable result that closes the gap; and
5. the smallest meaningful validation and the unchanged evidence to reuse.

While completing software, choose only a gap in the bounded checklist above.
After the federation milestone is explicitly resumed, choose its earliest
unblocked gap. A dataset task must explain why the shared gate requires that
work. Stop extending a
dataset when the required contract behavior and evidence are established;
retain unresolved values explicitly and proceed to the next system gap.

When a task cannot advance the selected milestone, return it to the backlog.
When a gate is blocked, record the exact missing evidence or authority and
continue independent eligible work under the existing bounded recovery policy.
Do not convert a blocked prerequisite into acceptance or declare federation or
Stable v1 complete while mandatory gates remain open. Software completion is
reported separately against the bounded checklist.

Broader Bronze coverage, new terminology, new sources, and optional frontier
experiments are deferred under the current instruction. Their existing
incomplete criteria and evidence remain visible. Reopen them only after the
maintainer resumes the relevant milestone or changes scope.
A later direct maintainer scope instruction supersedes this scheduling scope;
record the change explicitly in the versioned plan and its validator. A scope
change still supplies no rights, admission, publication, or release authority.

Use targeted checks for the changed behavior and reuse unchanged receipts.
Broaden testing only for an identified integration concern or a required
coherent milestone. Existing protected CI lanes and final release checks remain
in effect; policy, scheduling, and evidence edits do not by themselves require
a full local suite. All rights, release, privacy, source integrity, and absolute
outbound communications guardrails continue to apply.

## Authorized #61 follow-up — 2 November 2026

After the bounded checklist completed, the maintainer explicitly selected the
simplest remaining issue and authorized its unblocked implementation, review
and protected integration. #61 is selected for its finite external-product
criteria. Scope is a configured packaged ASGI service and actual wheel/sdist
startup verification using existing synthetic inputs. This does not reopen
Australian federation, acquire sources or authorize a public deployment.
Live deployment, canonical production-data and deployed-browser receipts remain
mandatory; see [the scoped plan](../docs/qualification/configured-service-61.md).

## Authorized #342 follow-up — 3 November 2026

After #1398 merged, the maintainer again requested the simplest remaining
unblocked work, review and protected integration. The selected finite gap is
installed verification of local research packages: the current clean-consumer
harness accepts metadata but cannot supply the result sidecar required by the
local format. Extend that existing harness and synthetic cross-platform canary.
Stop after protected integration and retain actual-source independent clean-room
restoration, public availability, all other federation and #61 deployment gates.
No source acquisition, publication, dependency upgrade or release is authorized
by this follow-up.

## Public presentation follow-up — 3 November 2026

The maintainer requested updated GitHub and Hugging Face pages with medallion
and roadmap visuals, completion proportions, badges, reciprocal links and
citation. Complete this finite documentation and catalogue-metadata update
through a protected PR and hosted-only exact-parent transaction. It does not
resume federation, acquire sources, change source rights or authorize a release
or live service. Track the measurements and limitations in
[the project overview](../docs/project-overview.md).

## Security and workflow tranche — 3 November 2026

The maintainer approved one bounded batch: complete native dependency-graph
submission, ledger-driven progress sections and closeout of merged #1399/#1400.
Use one scoped PR and the existing protected checks. Submit a full lock snapshot
only from audited exact main and verify the native result; do not dismiss alerts
or upgrade fixed packages to improve the count. Progress regeneration supplies
no Hub publication approval. Stop after integration/readback; deployment, new
data and broader federation remain deferred.

## Authorized #491 patch maintenance — 3 November 2026

After #1401 completed, the maintainer selected the narrow uv 0.13.6 maintenance
patch. Update existing active pins and generated locks, qualify on Python 3.15.1,
review and integrate after protected CI. Keep unrelated dependency versions,
historical receipts and all release/federation gates intact. Stop after merge
and the automatic dependency-submission readback; #491 remains open.

## Hosted #61 implementation — 3 November 2026

The maintainer requested the remaining hosted work in one CLI-driven batch.
Prepare/build/test on GitHub Actions, with runtime and disposable query caches
on the exact GMA Docker Space. Reuse only the existing accepted public FDA
snapshot; no new source or inventory expansion. Apply a main-only, parent-bound
code transaction using the existing workflow credential, retaining anonymous
digest and endpoint checks. No purchase, organization transfer, other Space
mutation or credential creation. Preserve #61 production-data and accessibility
gates: an historical catalogue without reviewed temporal assertions is a
candidate and does not close the issue. Stop after protected integration and
one native execution, recording any exact-target permission/entitlement denial.

## Free-only #61 hosting — 3 November 2026

The maintainer requires free options. Retire the paid-plan Docker Space create
path after its observed HTTP 402. HF ZeroGPU currently lists Python 3.10/3.12,
which does not qualify the required 3.15.1 runtime. Prepare one Render Free
Python service for the existing API/Atlas and retain HF dataset authority.
Require native owner/workspace and no-payment-method readback before activation;
no purchase, credits, billing change, paid resources or automatic upgrade.
Provider sign-in/new consent remain human. Preserve existing qualification,
source, rights and production-data boundaries; free service sleep/quota limits
are not a production-availability claim. Stop at protected integration and the
observed native activation boundary.

## Requested PBS historical backfill — 5 November 2026

The maintainer requested assessment of DataPlace PBS results and the longest
available file history. Resume bounded discovery and backfill preparation for
these utilisation families. The exact candidate cohort and gaps are in
[the backfill proposal](../docs/qualification/pbs-historical-backfill-20261105.md).
This exception does not resume broader federation, alter its frozen denominator,
resolve source rights or authorize additional external dataset publication.
Retain the explicit additional-cohort publication gate and workbook-size blocker.

The maintainer subsequently explicitly approved publication of the additional
legacy PBS files and relevant Medicare Statistics data into the existing HF
archive and requested completion of this backfill. This supersedes the pending
additional-cohort gate above for these sources; retain rights metadata, scoped
archive-only validation, protected integration and hosted anonymous digest checks.
No general federation, restricted-claims acquisition or release is implied.

## Custodial public PBS exports — 5 November 2026

The maintainer explicitly requested remaining OneDrive checks, comparison with
archived public tables and publication of missing public evidence. Scope is four
exact digest-approved Services Australia aggregate query exports, preserving
explicit-zero/query-layout evidence. No participant artifacts or general source
expansion are authorized. Use the existing Actions-only append and verification
path; stop after readback. See the scoped comparison report.

## Requested MBS custodial backfill — 6 November 2026

The maintainer explicitly requested the analogous MBS OneDrive comparison,
including the 1993 tranche, and publication of missing public data to the existing
HF archive. Execute only the digest-frozen public cohort in
[the comparison](../docs/qualification/mbs-flinders-public-backfill-20261106.md).
The shared capability is Actions-only, immutable, verified custodial-public report
preservation. Participant/linkage, study-derived, login/error and metadata-only
responses remain excluded. Stop after protected integration, hosted append,
full anonymous restore, and restoration of the disabled workflow state. General
federation and every existing acceptance gate remain unchanged.

### Requested original-report age-band follow-up

On 6 November 2026 the maintainer requested resolution of the three MBS age-band
comparison cells and an HF update if needed. This permits the scoped public
comparison annotation in the existing MBS archive, preserving native labels,
source bytes, semantic uncertainty and participant privacy. Reuse the verified
30-object archive receipt and verify only the new metadata object plus manifest
preservation. All broader federation and release gates remain unchanged.

## Remaining public archive authorisation — 6 November 2026

The maintainer explicitly requested remaining OneDrive checks, public MBS,
Medicare and AIHW acquisition/comparison, resolution of the AIHW download blocker
and publication of missing public evidence. This supersedes the prior AIHW
discovery-only boundary for this finite cohort. Retain participant/cohort-derived
exclusions, existing upstream terms, exact public-source identities, Actions-only
publication and anonymous verification. Stop at the scoped archive readback;
no federation, semantic admission or release gate changes. See the
[bounded packet](../docs/qualification/remaining-public-archives-20261106.md).

## Historical ATC2 teaching archive — 6 November 2026

The maintainer explicitly approved archiving the 1991–2008 workshop PBS CSV
with CC BY 4.0 and upstream GPL-3 notices, attribution and the gap-filled-zero
caveat, publication to the existing HF archive and verified temporary cleanup.
Execute only the four-object digest-frozen historical ATC2 contract through
Actions. Continue bounded public ATC2 discovery; participant/cohort-derived
sources, general federation, semantic admission and public releases remain
excluded. Stop this publication at anonymous readback and workflow restoration.

## Recovered AIHW ATC2 monthly file — 13 November 2026

The maintainer requested recovery, comparison and publication of missing public
ATC2 data. The previously unavailable publisher ZIP is now available and the
exact 88,904,070-byte object is absent from the verified PBS archive manifest.
Prepare one source-faithful append under the existing hosted publication and
anonymous-verification boundary. Keep the publisher attribution and licence
notice with the object, preserve the prior manifest, and retain the local copy
until verification succeeds. Participant and cohort-derived data remain private.
