# Australian donor parity review, updated 2026-10-23

M-105 remains **blocked**. The required pre-archive donor parity evidence
cannot be established retroactively. The 2026-10-18 narrow chronology waiver
([D-006-10](../../conductor/decisions/0006-external-gate-decision-register.md#d-006-10--m-105-narrow-chronology-waiver))
is preserved as a historical decision, but the maintainer's later
2026-10-23 instruction ([D-006-12](../../conductor/decisions/0006-external-gate-decision-register.md#d-006-12--m-105-blocked-status-reaffirmation))
keeps the current gate blocked. Post-archive evidence is not described as
pre-archive proof. M-106–M-113, source rights, and Stable v1 release approval
remain separate gates.

The pinned inventory covers 54 tracked blobs (16 graph, 38 scraper), including
every Python function and both workflows. The later delta review covers two
changed graph paths and eight changed scraper paths. The [M-105 disposition
matrix](../../quality/qualifications/australian-donor-m105-dispositions.json)
binds all 64 rows to final dispositions; no row remains pending behavioral
parity. The [waiver qualification](../../quality/qualifications/australian-donor-m105-chronology-waiver-20261018.json)
binds the exact matrix, archived heads, and public history receipts.

The two donor heads and complete histories were subsequently preserved and
anonymously restored at the exact public revision recorded by the archival
receipts. Those receipts close history preservation and the separately approved
archive actions; they do not prove behavioral parity for every donor artifact.

The [pinned inventory](../../quality/qualifications/australian-health-donor-inventory.json)
uses broad dispositions such as `adapt_or_replace_with_tests` and
`preserve_provenance`. The new [M-105 disposition matrix](../../quality/qualifications/australian-donor-m105-dispositions.json)
maps all 54 baseline blobs and ten later changed paths to M-105's final
six-value vocabulary, preserving exact Git identities and baseline payload
digests. Every matrix row now has a final disposition and evidence. Under the
approved chronology waiver, this post-archive dossier is used for M-105
reassessment without changing the historical sequence or asserting that the
evidence preceded archival. The donor monthly workflow is retained as exact legacy
history: its scheduled HTML scrape produced six 404s and no Git data commit.
GMA's separate scheduled workflow acquired and anonymously verified only the
approved August 2026 XML release on 2 September. Its verified
`c39dd99ab8a6fcf557aeec391e1891b5fa18754f` revision descends from the
earlier manual release revision `75f9f20a36ddb829dfe0ca88660664570782be02`;
the [scheduled receipt](https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-5515404352)
records both. This is not parity for item
or participant HTML coverage and does not authorize future releases. The pinned
scraper module has an explicit
legacy-only receipt: `month_range` is adopted with executable checks while
the async item and participant HTML callers remain in exact archived history.
Neither caller establishes current participant coverage. The donor's broken MBS parser
is now bound to the exact pre-archive 5,989-record/40-field qualification of
its replacement, including the rejected `MBSItem` shape. The donor's July XML
download is bound to exact public legacy bytes and the separately authorized,
hosted August acquisition. Both pinned revisions remain publicly addressable;
the dataset's later current head is not substituted for either receipt. The
existing [donor assessment](../../conductor/tracks/australian_health_source_consolidation_20260829/donor-assessment.md)
maps intended functions to successor behavior. The baseline and later
processor and processor-test rows now bind every donor function to executable
synthetic successor checks. P7 selection and separate typed HTML table
semantics replace the donor's mixed CSV, whose Path/string handling was broken.
This qualifies replacement behavior, not live participant acquisition or the
former mixed CSV artifact. Scraper async caller responsiveness is retained as
legacy behavior, not proven API parity. The
baseline and later scraper CI blobs now bind protected Test-Goblin test/lint
execution at exact PR head `0b006fe7a6fc1738867673ef4ee486668927ff77`.
This CI supersession does not qualify the donor scrape-and-commit schedule.
The donor entry point's hard-coded 2024 requests, async HTML calls and broken
mixed CSV orchestration are explicitly excluded as an obsolete demonstration,
with exact archived history retained. Fail-closed synthetic rehearsal and the
separately authorized hosted XML release remain independent capabilities, not
complete replacements for that HTML path. The exact donor scheduled run
reported six 404s and no data commit;
its green workflow result was not data success. The later entry-point edit
changes imports and formatting only. The later test for the retired async
scraper API is also excluded with reason; a separate regression now proves
synthetic item and participant bytes under bounded serial probes. This does
not preserve async API parity or establish live participant coverage. All
ten later changed paths now have dispositions with evidence. The earlier
delta receipt's
`current_head_history_preserved=false` was a pre-publication observation and
must not be read as current archival state.

The four donor functions across three graph PBS files are mapped separately: governed
ZIP/member handling replaces unbounded extraction and URL-derived filenames;
source-faithful v3 parsing replaces the syntactically invalid donor parser;
and the bounded local inspector retains the first-item XML view. Synthetic
behavior controls and the separately verified April 2026 public archive are
distinct evidence. No donor PBS payload existed in the pinned repositories,
and this does not claim all historical or future PBS releases.

The artifact denominator is reconciled, with exact history and the applicable
public payload receipts linked. On 2026-09-29 the maintainer recorded the
chronology disposition in [D-006-07](../../conductor/decisions/0006-external-gate-decision-register.md#d-006-07--m-105-donor-chronology-exception):
keep M-105 blocked and continue M-106–M-112 independently. That was the
operative disposition at the time; D-006-10 later supersedes it only for the
chronology condition. The archival chronology remains historical and later
proof cannot make parity precede the archives.

The archival chronology cannot be retroactively described as pre-archive M-105
parity. The separate maintainer approvals and observed archives are recorded in
the [scraper](../../quality/qualifications/scraper-archival-20260906.json) and
[graph](../../quality/qualifications/graph-archival-20260906.json) receipts.

## Bounded pre-archive record recheck, 2026-10-18

A second review queried merged GMA pull requests in the archive window and the
available #339/#340 issue comments, then inspected the most relevant earlier
consolidation and archival records. It found partial, source-specific evidence,
not a complete proof of parity for all 54 pinned blobs and ten later changed
paths before the first archive:

- [PR #349](https://github.com/edithatogo/global-medicines-atlas/pull/349)
  inventories both donor repositories and qualifies the exact 5,989-record MBS
  XML parser slice. Its scope does not establish parity for every scraper and
  graph artifact.
- [PR #364](https://github.com/edithatogo/global-medicines-atlas/pull/364)
  adds a synthetic MockTransport rehearsal. The historical scheduled URLs
  returned six 404s; this is not live participant coverage or full async API
  parity.
- [PR #476](https://github.com/edithatogo/global-medicines-atlas/pull/476),
  merged 2026-09-06T01:31:13Z before the scraper archive at 02:12:07Z, prepares
  preservation and archival readiness. It explicitly does not claim historical
  participant counts or literal async API parity.
- [PR #477](https://github.com/edithatogo/global-medicines-atlas/pull/477),
  merged 2026-09-06T02:08:30Z before the scraper archive, binds authorization
  for the exact history-preservation append. It proves the publication and
  restoration transaction, not behavioral parity for the complete donor
  inventory.

The searched pre-archive records therefore corroborate specific rows and
preservation steps but do not show that the full M-105 denominator passed before
either donor was archived. This remains the historical chronology finding.
D-006-10 subsequently waived only the sequence requirement, allowing the
post-archive evidence to be assessed without relabeling it as pre-archive proof.

## Donor-hosted PR record recheck, 2026-10-18

The archived donor repositories' available pull-request records were also
queried directly. The scraper's [PR #4](https://github.com/edithatogo/aus-health-data-scraper/pull/4),
merged 2026-08-30T06:00:29Z, adds a successor notice, repairs CI commands,
narrows parser exception handling, and adds synthetic checks for bounded async
requests and output bytes. These are useful pre-archive changes and evidence for
specific behaviors, but they do not disposition or qualify the full scraper
and graph donor denominator. The graph's [PR #5](https://github.com/edithatogo/aus_mbs_pbs_graph/pull/5),
merged 2026-08-30T05:56:15Z, is a successor notice with compatibility
boundaries; it explicitly does not claim complete current graph functionality.

Neither donor PR establishes full parity across all 54 baseline blobs and ten
later changed paths before either 2026-09-06 archive. The direct donor PR
records therefore add narrow contemporaneous evidence. D-006-10 later waives
only the chronology condition; it does not make these records proof of
pre-archive parity.

## Complete hosted donor-history recheck, 2026-10-18

A final metadata-only search covered the accessible pull-request histories and
Actions runs in both donor repositories up to their exact archive times. The
scraper history contains PR #4, which adds narrow successor and synthetic
request/output checks, and PR #5, an unmerged Renovate update. The graph history
contains the 2025 initial parsing setup, PR #5's successor notice, and PR #6,
an unmerged Renovate update. None establishes parity for the full 54-blob
baseline and ten later changed paths.

The scraper Actions history includes 14 scheduled monthly runs before archival;
their green workflow conclusions are not data-success evidence. The last
pre-archive run, [33461653233](https://github.com/edithatogo/aus-health-data-scraper/actions/runs/33461653233),
was already reconciled as six 404 responses and no data commit. The graph
history returned two Dependency Graph runs and no functional parity workflow.
These Actions records concern donor-side operation, not a complete comparison
against the GMA successors before archival.

This closes the bounded search of preserved GitHub PR and Actions records, not
unpreserved external or local evidence. No full pre-archive parity proof was
found. The exact archived histories and post-archive dispositions remain useful
preservation evidence. D-006-10 now waives only the chronology rule so that
this evidence can support M-105 qualification; no retroactive pre-archive
proof is claimed. M-106–M-113 and Stable v1 release approval remain separate.
