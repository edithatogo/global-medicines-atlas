# Implementation Plan

Execution policy: [autonomous, decision-gated](../../autonomy.md).

## Phase 1: Qualification contract

- [x] Task: Build requirement, maturity and release-evidence matrices ([#41](https://github.com/edithatogo/global-medicines-atlas/issues/41))
  - Initial fail-closed projection: `quality/qualifications/stable-v1-contract.json`
    validated by `schemas/stable-v1-qualification-v1.json`; the complete matrix
    records verified, partial and blocked states without treating later
    implementation or external approvals as Phase 1 completion.
- [x] Task: Define clean-room reproduction and migration rehearsals ([#41](https://github.com/edithatogo/global-medicines-atlas/issues/41))
  - Four receipt-producing rehearsal definitions distinguish release clean-room
    reproduction, structural canonical migration, rollback, and governed
    recovery without implementing the runtime schema migration.
- [x] Task: Define support, limitation and residual-risk gates ([#41](https://github.com/edithatogo/global-medicines-atlas/issues/41))
  - The support-readiness register records candidate platforms, the optional
    semantic boundary, user-facing limitations, ownership, and fail-closed
    blocking risks.
- [x] Task: Define jurisdiction/source maturity and documentation-readiness matrices ([#41](https://github.com/edithatogo/global-medicines-atlas/issues/41))
  - A deterministic projection covers every canonical catalog `source_id` and
    jurisdiction while conservatively capping catalog-derived maturity at M2.
- [x] Task: Contract canonical medicine schema v2 and migration compatibility for substances, products, packages, indications, prices and restrictions ([#41](https://github.com/edithatogo/global-medicines-atlas/issues/41))
  - Structural contract added as `schemas/canonical-medicine-v2.json`; the
    runtime now requires an explicit adapter-owned structural projection,
    validates closed references and assertion dimensions, preserves the full
    digest-bound schema-v1 source-native record, and rolls it back without
    semantic loss. This is explicitly distinct from the temporal assertion
    `v1_to_v2` migration. The Phase 2 cohort qualified deterministic migration
    and rollback for structurally supported fixtures while blocking unsupported
    records rather than inferring complete source or jurisdiction coverage.
- [x] Task: Contract comparison-validity semantics for granularity, indication, population, mapping, normalization, material mismatches and inappropriate comparisons ([#41](https://github.com/edithatogo/global-medicines-atlas/issues/41))
  - The versioned vocabulary now has strict immutable runtime models and a
    deterministic evaluator. Any material mismatch is inappropriate; any
    unknown dimension abstains; compatible evidence is caveated; and every
    outcome explicitly denies medicine equivalence, substitutability,
    therapeutic interchangeability and equal benefit. API and CLI comparison
    responses expose fail-closed validity abstentions when source rows lack the
    required dimensional evidence. Phase 2 qualified aligned, caveated,
    inappropriate and abstaining controls through the public surfaces.
- [x] Task: Contract bounded concept discovery, catalog APIs, CLI commands, accessible autocomplete and match explanations ([#41](https://github.com/edithatogo/global-medicines-atlas/issues/41))
  - Deterministic core contracts and the read-only DuckDB query service now
    provide bounded exact-identifier and normalized lexical discovery, concept
    detail, jurisdiction/source catalogues, explicit non-equivalence match
    explanations, and signed keyset cursors. Versioned API routes and nested,
    scriptable JSON/JSONL CLI commands now expose those capabilities using the
    existing cache, request-ID, typed-error, HEAD and bounded-export
    conventions. The accessible Atlas now adds explicit-selection combobox and
    listbox discovery, keyboard and live-status behavior, visible canonical
    identity, hostile-label escaping, and a server-rendered no-JavaScript
    fallback. Governed semantic candidates may now augment exact and lexical
    results without replacing their authority or implying equivalence. Phase 2
    qualified the bounded fixture through API, CLI and rendered Atlas paths.
- [x] Task: Define clean-wheel consumer, supported-platform, package-metadata and public-API compatibility gates ([#41](https://github.com/edithatogo/global-medicines-atlas/issues/41))
  - The Test-Goblin package profile now installs wheel and source distribution
    into disposable core-only Python 3.14 environments and verifies metadata,
    dynamic version, reinstall, import, CLI, API, deterministic fallback and a
    fail-closed OpenAPI baseline. CI repeats the receipt-producing rehearsal on
    Windows, Linux and macOS; hosted all-platform qualification remains Phase 2.
- [x] Task: Define core and optional-semantic installation boundaries, LanceDB index/model identity and deterministic fallback gates ([#41](https://github.com/edithatogo/global-medicines-atlas/issues/41))
  - LanceDB is a `semantic` extra rather than a core dependency. Immutable,
    content-bound index/model identity must match exactly; absent dependencies,
    identities and indexes produce the deterministic unavailable fallback.
- [x] Task: Define non-overlapping GitHub, Hugging Face, Zenodo and OSF dataset/protocol identities and licence gates ([#41](https://github.com/edithatogo/global-medicines-atlas/issues/41))
  - Historical four-surface contract. Live identities are now GitHub, Hugging
    Face and Zenodo. OSF is deprecated and is rejected as a live publication
    identity. The public/no-credential Hugging Face catalogue archive is the
    completed publication path for that class.
- [x] Task: Phase Verification & Checkpoint
  - Independent review at `9332d27` found release-gate, canonical-schema,
    semantic-index, cross-page-validity, traceability, mutation and JavaScript
    style defects. The defects are remediated on the Phase 1 review-fix branch;
    checkpoint passed after PRs #98 and #99 completed 29 protected checks each
    and an independent post-merge re-review found no residual defects.

## Phase 2: v0.9 candidate

- [x] Task: Execute independent reproduction and disaster-recovery rehearsal ([#42](https://github.com/edithatogo/global-medicines-atlas/issues/42))
  - A fresh-clone reproduction of `v1.0.0rc1` passed deterministic migration,
    rollback, restore and fixture identity checks; receipt:
    `quality/qualifications/stable-v1-independent-reproduction-20260803.json`.
    That governed rehearsal meets the written software-reproduction bar.
  - Production disaster-recovery authority over live production systems remains
    an isolated external gate. It does not block academic or OSF work. OSF is
    deprecated.
- [x] Task: Rehearse compromised-source quarantine, signing/credential revocation, dataset withdrawal, corrected replacement and downstream notification ([#42](https://github.com/edithatogo/global-medicines-atlas/issues/42))
  - The offline hash-chained incident rehearsal verifies ordering, tamper
    rejection, idempotent retries and separate regulatory/funding evidence.
    Credential-authority, human-notification and publication actions remain
    explicit external gates and are not claimed as executed.
- [x] Task: Verify every protected CI, security and publication receipt ([#42](https://github.com/edithatogo/global-medicines-atlas/issues/42))
  - The offline verifier now pins the repository, pull request, exact commit,
    required CI/security check names and producer identities, then binds the
    observed check-run and workflow-run identifiers into a deterministic
    receipt. Pending, failing, missing, duplicate or mismatched evidence is
    rejected. Publication remains independently `blocked` or `not_attempted`
    without a durable commit-bound receipt; exact hosted verification for the
    PR #102 then passed all 29 exact protected checks. Publication is explicitly
    verified as `not_attempted`, rather than inferred from CI success.
- [x] Task: Audit task-oriented documentation, examples and support paths ([#42](https://github.com/edithatogo/global-medicines-atlas/issues/42))
  - Executable documentation contracts cover installation, API, CLI, Atlas,
    validity abstentions, recovery, support and publication/licence limits.
- [x] Task: Migrate canonical records to schema v2 and verify source-native round trips ([#42](https://github.com/edithatogo/global-medicines-atlas/issues/42))
  - A content-bound cohort receipt measures 42 preserved NZULM/NZMT FHIR
    fixtures plus PMDA, Drugs@FDA, PBS and EMA adapter fixtures. All structurally
    supported records migrate deterministically and roll back exactly; fixtures
    without source-native substance/product structure are explicitly blocked
    rather than inferred. Regulatory, funding and formulary counts remain
    separate throughout.
- [x] Task: Verify comparison-validity outcomes and negative controls never imply equivalence, substitutability or equal benefit ([#42](https://github.com/edithatogo/global-medicines-atlas/issues/42))
  - Deterministic aligned, compatible, material-mismatch and unknown controls
    cover valid, caveated, inappropriate and abstaining outcomes. Every control
    keeps equivalence, substitutability, therapeutic interchangeability and
    equal-benefit flags false across the public surfaces.
- [x] Task: Verify concept search, concept detail, jurisdictions and sources through API, CLI and atlas end to end ([#42](https://github.com/edithatogo/global-medicines-atlas/issues/42))
  - One governed read-only DuckDB fixture now produces a content-bound receipt
    for concept search/detail, jurisdiction/source catalogues and comparison
    validity through the API, CLI and rendered Atlas without external action.
- [x] Task: Install built wheel and sdist in clean environments and run import, CLI, API, version and reinstall checks ([#42](https://github.com/edithatogo/global-medicines-atlas/issues/42))
  - The clean-consumer harness already covers wheel and sdist installation,
    metadata, dynamic version, reinstall, import, CLI and API. The exact current
    PR #102 supplied same-commit Linux, macOS and Windows hosted receipts.
- [x] Task: Snapshot and semantically diff the public OpenAPI contract and smoke-test a generated client ([#42](https://github.com/edithatogo/global-medicines-atlas/issues/42))
  - The deterministic read-only snapshot is compared with an immutable ancestor
    baseline and rejects incompatible removals, security changes, request and
    response enum variance, mutations, request bodies and response changes.
    The generated typed client preserves repeated array parameters, URL-encodes
    path parameters, passes a real ASGI smoke test and regenerates exactly.
- [x] Task: Resolve or explicitly block every Must requirement ([#42](https://github.com/edithatogo/global-medicines-atlas/issues/42))
  - Every Must has an explicit verified, partial or blocked state with evidence
    and blocker identifiers in the qualification contract. External licence,
    publication, identifier, credential-authority and stable-release approvals
    remain blocked rather than being treated as implementation failures.
- [x] Task: Phase Verification & Checkpoint
  - Independent re-review after PRs #102 and #103 passed with no residual
    findings. Both pull requests completed 29 protected checks; merged main at
    `a8ee67c` completed all 26 applicable push checks. Published-artifact
    reproduction and external approvals remain explicitly deferred to Phase 3.

## Phase 3: v1.0 promotion

- [x] Task: Verify measured jurisdiction and source coverage ([#43](https://github.com/edithatogo/global-medicines-atlas/issues/43))
  - A deterministic receipt measures 96 catalogue sources, 34 jurisdiction
    denominator entries and 16 fixture-qualified sources. Zero sources are
    claimed live-qualified; regulatory, funding, formulary and terminology
    dimensions remain separately labelled.
- [x] Task: Verify hosted governance, security features and project views ([#43](https://github.com/edithatogo/global-medicines-atlas/issues/43))
  - Read-only acquisition verifies repository identity, default branch, branch
    protection, 24 required checks, security features, issue/subissue hierarchy,
    Project #35 fields, five views and six workflows. Phase 1/2 project states
    and the two risk/evidence views were reconciled and re-acquisition qualified
    every in-scope control.
- [~] Task: Produce signed release package and consumer verification guide ([#43](https://github.com/edithatogo/global-medicines-atlas/issues/43))
  - 2026-09-13 review fixes preserve failed/unverified qualification evidence,
    lower maturity and unresolved recovery risk; reject duplicate gate IDs;
    and reject inconsistent live-qualified payloads at runtime, portable schema
    and canonical serialization boundaries. Focused verification passes 136
    tests including monitoring. Full and hosted verification are recorded in the evidence ledger.
    The review does not complete dependent implementation or authorize release.
  - 2026-09-13 blocker audit: current repository evaluation finds 174 catalogue
    sources, 157 in-scope sources and 138 without landing evidence. The latest
    MBS utilisation hosted receipt verifies 28 files but retains three failed
    resources and explicitly partial coverage. Renovate-authored issues and
    pull requests remain unobserved. See
    `docs/qualification/stable-v1-blocker-audit-20260913.md`.
  - Repository-owned candidate packaging and the consumer verification guide
    are complete. The task deliberately remains in progress because a signed
    stable release has not been approved or produced, and the authoritative
    qualification contract still has four dependent/hosted gates plus the
    distinct stable-promotion human gate. The machine-readable reconciliation
    is `quality/qualifications/stable-v1-release-readiness-reconciliation.json`.
  - Isolated remaining human gate: stable-v1 promotion approval. GitHub
    attestation verification passed for the published `v1.0.0rc1` wheel;
    receipt: `quality/qualifications/stable-v1-release-provenance-receipt.json`.
    This does not constitute a public stable v1 release.
  - A deterministic wheel, sdist, normalized SBOM, manifest, checksum and
    consumer-verification candidate reproduces byte-for-byte across independent
    clean LF and CRLF checkouts. The approved `v1.0.0rc1` software-only
    prerelease is tagged and published on GitHub and archived at Zenodo DOI
    `10.5281/zenodo.21734811`. Production DR authority is a separate isolated
    external gate and is not required to complete academic publication work.
  - Independent post-merge review found that Hatch VCS could reuse an ignored
    generated `_version.py`, making the committed receipt dependent on prior
    checkout state. The build now removes that state before and after packaging,
    pins the byte-affecting Python, uv and PEP 517 toolchain, records those
    constraints in provenance, and verifies byte-identical independent clean
    clones before exercising both consumer paths.
  - PR #118 merged the final generated-text archive hardening after all 29
    protected checks passed. PR #119 then bound the candidate receipt to durable
    `main` commit `6be0628` and pinned uv `0.11.29`; all 29 protected checks
    passed again. A canonical-remote test checks out that exact commit, rebuilds
    the candidate byte-for-byte, and consumes both distributions on Linux,
    macOS and Windows. Independent Conductor review passed with no findings.
  - Review fix: recompute the reconciliation's referenced stable-v1 contract
    SHA-256 in tests so a stale content binding cannot pass after contract
    drift. The receipt path must resolve to the canonical contract.
- [x] Task: Verify dataset cards, Croissant records, checksums and GitHub/Hugging Face/Zenodo identifier links without publishing restricted data ([#43](https://github.com/edithatogo/global-medicines-atlas/issues/43))
  - The content-bound publication-metadata receipt verifies cards, Croissant,
    checksums, restricted-data boundaries and non-overlapping object roles.
    Live identities are GitHub, Hugging Face and Zenodo. OSF is deprecated.
    Public/no-credential catalogue archival is complete; credentialed sources
    remain out of scope.
- [x] Task: Obtain explicit maintainer licence and release approval ([#43](https://github.com/edithatogo/global-medicines-atlas/issues/43))
  - On 2026-08-01 the maintainer approved Apache-2.0 for repository software,
    bounded CC-BY-4.0 for expressly eligible maintainer-owned derived data, and
    an attested `v1.0.0rc1` software release. OSF is deprecated. The
    public/no-credential Hugging Face archive is the completed publication path
    for that class. Stable-v1 promotion remains a distinct human gate.
  - The stable approval handoff now specifies a candidate-bound decision only
    after Australian federation, Bronze current scope, and M5 pass. No stable
    approval has been requested or inferred from the prerelease authority.
- [x] Task: Record stable-v1 evidence and post-release monitoring plan ([#43](https://github.com/edithatogo/global-medicines-atlas/issues/43))
  - Six domain-specific SLO, alert and approval-gated rollback policies bind the
    candidate evidence while post-release observations remain `not_observed`.
    Signing, publication, release eligibility and external actions remain false.
- [x] Task: Phase Verification & Checkpoint
  - Independent Conductor review identified a normalization-collision ordering
    gap in the new metamorphic invariant. The implementation now uses explicit
    Unicode/source tie-breakers and includes the `("A", "a")` regression;
    PR #122 then passed all 29 hosted checks and merged to `main` as
    `ab608543e39aacd2bcab3dd19ac3103283256958`. The property, mutation,
    pytest-gremlin, Codecov patch, coverage and Scalene profile checks all
    passed. Independent Conductor review has no residual finding.
  - Repository-owned qualification is complete and independently reviewed.
    Exact `v1.0.0rc1` approval is now recorded in a machine-validated,
    software-only prerelease authority contract. GitHub attestation verification
    for the published wheel and fresh-clone reproduction are now recorded;
    stable-v1 promotion and production DR authority remain isolated remaining
    gates. OSF is deprecated. Public/no-credential catalogue archival is
    complete; credentialed sources remain out of scope.

## GitHub hierarchy

- Parent: [#40 Stable v1 qualification](https://github.com/edithatogo/global-medicines-atlas/issues/40)
- Qualification contract: [#41](https://github.com/edithatogo/global-medicines-atlas/issues/41)
- v0.9 clean-room candidate: [#42](https://github.com/edithatogo/global-medicines-atlas/issues/42)
- v1.0 promotion and external gates: [#43](https://github.com/edithatogo/global-medicines-atlas/issues/43)

## Phase 3A: Extended verification architecture

- [x] Task: Reduce the protected CI critical path without weakening evidence
  - [x] Retain the existing isolated gremlin executor after batch size 10 and explicit four-worker modes both exceeded the existing hosted critical path
  - [x] Use the Python 3.14 sysmon coverage core; reject two-worker aggregate coverage after it ran slower and caused performance-budget contention
  - [x] Keep required check names stable while skipping mutation, gremlins, and consumer bodies only for provably documentation/Conductor-only pull requests; uncertain and non-PR events run the full suite
  - [x] Parallelize independent consumer-reproduction tests without changing required check names
  - [x] Measure hosted critical-path improvement and retain full exact-main verification
  - [x] Persist the content-validated gremlins cache across eligible hosted runs without sharing mutable execution state
  - [x] Add a non-blocking CPython 3.14 free-threaded canary for deterministic core contracts

- [x] Task: Add optional local changed-test selection without weakening full CI
  - Pytest-testmon retains its serial dependency-history profile. Pytest-picked
    adds a stateless unstaged or explicit-parent Git-diff profile. Both remain
    local feedback tools and are excluded from authoritative hosted selection.

- [x] Task: Add independently executable metamorphic, consumer/provider
  contract and deterministic-simulation lanes to Test-Goblin ([#43](https://github.com/edithatogo/global-medicines-atlas/issues/43))
  - The specialized profiles pass independently and are assigned to the
    protected property, unit and integration lanes so hosted required-check
    names remain stable. Metamorphic normalization relations, read-only OpenAPI
    provider/consumer compatibility and replayable source-health transitions
    are executable without network or wall-clock state.
- [x] Task: Verify property, mutation, Codecov and Scalene enforcement remains
  executable and blocking or evidence-producing as designed ([#43](https://github.com/edithatogo/global-medicines-atlas/issues/43))
  - The harness contract collected 1,587 tests; routine Ruff/ty and strict
    BasedPyright pass. Aggregate branch coverage remains 95.19% against the 91%
    gate. Codecov project/patch and per-primary-lane flags remain fail-closed.
    Mutation/gremlin profiles remain required hosted checks, and an actual
    deterministic Scalene run produced its durable receipt and profile.
- [x] Task: Phase Verification & Checkpoint
  - Reconciled against implementation commit
    `ab608543e39aacd2bcab3dd19ac3103283256958` and current local reruns of the
    metamorphic, consumer/provider contract and deterministic-simulation
    profiles. Repository history records the protected-check and independent
    review outcome for PR #122; this checkpoint does not reverify hosted state
    and makes no publication, rights, or live-deployment claim. OSF is
    deprecated and is not a remaining gate for this checkpoint.

## Phase 3B: Hugging Face data-layer archival

- [x] Task: Archive public, no-credential data-layer artefacts to the existing
  Hugging Face catalogue identity ([#43](https://github.com/edithatogo/global-medicines-atlas/issues/43))
  - Inventory classified 96 catalog sources (85 public/no-credential, 11
    credential-restricted). Catalogue metadata, publication contracts, and
    governed representative fixtures were archived to
    `edithatogo/global-medicines-atlas-catalogue` revision
    `b25af36da32ffa3ddc5d525f1c568459d23f6e11`. Licensed `vendor/nzmedicines`
    bytes and credential-gated payloads were omitted. No live dump was
    downloaded. Receipt:
    `quality/qualifications/data-layer-archive-receipt.json`.

## Phase 3C: Authoritative contract reconciliation

- [x] Task: Reconcile the stable-v1 contract with current evidence (`776d52b`)
  - Canonical v2, comparison validity, bounded discovery, clean consumers,
    independent fixture reproduction, support documentation, hosted governance,
    and bounded software/publication controls are recorded as passed.
  - Current-scope Bronze landing (M-095) remains a technical blocker. Renovate
    output (M-046) was observed through the bot-authored Dependency Dashboard
    in issue #491 on 2026-09-13, restoring the security-and-supply-chain
    maturity dimension to M5.
- The 2026-09-28 Bronze refresh binds the approved CMS Part D receipt and
    four accepted U.S. source-record products to the maturity denominator,
    reducing uncovered in-scope sources from 124 to 120. A subsequent
    source-specific FDA drug-shortages receipt reconciliation reduced that
    denominator to 119. Seven dimensions remain M5/verified; source coverage
    remains M4/partial and the M5 release gate stays blocked. See
    `docs/qualification/stable-v1-m5-maturity-status.md`.
    The refreshed exact-merge report on `4667f144` accepts the scoped Prompt 14
    source-specific receipt for internal Bronze landing evidence. The older
    generic U.S. corpus row describes a separate quarantined acquisition.
    Delegated detail-page coverage remains incomplete and public release is
    unauthorized; this reconciliation does not promote broader source
    coverage, Australian federation, or Stable v1 approval.
  - The Australian MBS hosted HEAD-only diagnostic now classifies all three
    authorized Health.gov workbook requests as read timeouts after connection
    setup, with no headers or source bytes received (`36377888606`, exact main
    `58cb9e8c`). This narrows the observed failure phase but does not provide an
    authorized source delivery route or satisfy M-107/federation acceptance.
    A workstation-only repeat returned HTTP 200 and the expected XLSX metadata
    for each URL, without reading bodies. The authorization forbids workstation
    raw retention, so only a reachable authorized hosted route can advance
    workbook acquisition. The bounded local observation is retained at
    `quality/qualifications/australian-mbs-workstation-head-availability-20260928.json`.
  - The merged-main MBS workbook calendar-compatibility profile (`36381100367`,
    commit `bbae70a0`) counted 1,276 dates valid under both day/month orders
    and four valid only as DMY. This is value-free evidence and does not select
    a conversion convention, establish workbook-era semantics, or resolve the
    authorized hosted acquisition route; the Australian federation gate stays
    blocked. The durable aggregate is
    `quality/qualifications/mbs-workbook-date-order-compatibility-20260928.json`.
  - PR #607 added candidate-only field lineage over the pinned P7 workbook.
    Review of its prior hosted artifact found per-cell values in the storage
    summary; PR #608 now allowlists only sheet/cell denominators, aggregate
    storage/conversion counts, digests and value-free lineage. It merged as
    `8c830ebd` after every required check passed and automated review reported
    no inline findings. Exact-main run `36473432952` then verified four sheets,
    13,742 cells and 99 field mappings. The value-free receipt is
    `quality/qualifications/mbs-p7-workbook-field-lineage-20260929.json`;
    `date_profile` remains unset and the qualification remains candidate-only.
    Focused tests passed (81); the full local profile reported 5,212 passed,
    two clean-clone release reproducibility failures because local `uv`
    candidates are 0.11.8/0.12.19 rather than pinned 0.11.29, one optional
    Iceberg skip, and 96.71% coverage. The exact-main maturity refresh at
    `8c830ebd` still finds 118 of 157 in-scope sources without landing evidence;
    completeness remains blocked and 13 other dimensions remain evidenced.
    Focused qualification-contract/Bronze-maturity tests passed (102), and the
    routine harness passed.
    This does not close M-106, M-107, M-109, Australian federation, Bronze/M5,
    or Stable v1 approval.
  - The pinned PBS `pbs-iso-date-candidate-v1` profile completed exact-main
    (`36372245263`): 2,799 dates converted, one missing field, and 7,727,884
    rows unmapped; all five projections and 16 reference windows retained
    matching native digests and Parquet round-trips. This closes only the
    candidate-profile workflow. Source-era semantics, M-109 acceptance, current
    scope Bronze landing, M5 maturity, and Stable v1 approval remain open.
  - The narrower pinned-V3 ASCII grammar qualification completed on exact main
    (`36417477472`, commit `95d9583d`). The value-free aggregate records all
    five projections and 16 reference windows round-tripped across 7,730,684
    elements and 18,208,758 native fields, with 2,799 converted dates and one
    missing date field. It remains `structural_storage_candidate_only`:
    2,798 AMT references are unresolved, domain semantics are unqualified, and
    no publication was performed. The receipt is retained as
    `conductor/tracks/australian_benefits_silver_gold_20260829/pbs-qualification-receipt-20260928.json`;
    this does not close federation, M-109, Bronze, M5, or Stable v1.
  - `v1.0.0rc1` authority is explicitly prerelease-only. Final stable promotion
    remains blocked pending a distinct maintainer decision after the technical
    blockers pass.
  - Production DR and dataset publication remain separate boundaries and are
    not implied by software-only release qualification.

## Phase: Review Fixes

- [x] Task: Apply qualification integrity review fixes (04ac572, 425f01b, de176cd, aab814c).
  - All 38 hosted checks passed at aab814c; 4,901 local tests passed with one
    optional skip. Local mutation remains platform-limited as recorded in the
    evidence ledger. Acceptance gates and signed-release task remain open.

## 2026-09-28 M5 source-coverage update

- The authorized internal Orange Book refresh discovered and accepted the newly
  listed August 2026 FDA monthly release. One bounded pass retained 140 of 260
  releases; 104 Archive-It requests failed and 16 were quarantined. Historical
  coverage remains incomplete, public release is not authorized, and the
  Bronze/M5 gates remain blocked. Value-free receipt:
  `quality/qualifications/orange-book-historical-refresh-20260928.json`.

## 2026-09-29 NICE private Bronze receipt increment

- [~] Reconcile the approved Prompt 29 private historical acquisition receipt
  in the current-scope Bronze denominator. The value-free recognizer binds the
  source-specific internal-only acquisition authorization to all 15 admitted
  payloads, four expected releases, and clean-room digest restoration; it keeps
  source-record projection, public release, and external publication false.
- [x] Verify the 118-source denominator in the exact-main maturity report
  bound to `f6e7b9e27a642347ee63c5ef3ce391ed16bf212a`. The report remains blocked.
  Current-scope Bronze and M5 remain blocked; Australian federation and separate
  stable-release approval also remain open.

## 2026-09-29 exact-main qualification refresh

- The Bronze maturity report is refreshed against exact main `008d8317` after
  PR #606. It still records 118 of 157 in-scope public/no-credential sources
  without landing evidence; completeness is the only blocked Bronze dimension.
  The other 13 dimensions remain evidenced. Focused maturity/contract tests
  passed (102), and the routine Test-Goblin profile passed. The Australian
  federation, current-scope Bronze, M5 and stable-release approval gates remain
  open; no source or release authority is inferred.

## 2026-09-29 post-PR-609 qualification rebind

- [x] Regenerate the Bronze maturity report from the merged `main` tree at
  `7d8cfe4e1ead4b8693db80d38880982762f37365`. It still reports 174 catalog
  sources, 157 in-scope sources, 118 without qualifying landing evidence, and
  13 evidenced dimensions; completeness remains blocked. Focused Bronze and
  Stable v1 contract suites passed (102), and the routine harness passed.
  This refresh only rebinds the report timestamp and source commit; it adds no
  landing evidence and does not advance Bronze, M5, Australian federation, or
  stable-release approval.

- [x] Correct the status-page provenance identified in PR #610 review. It now
  cites the same exact-main commit as `quality/qualifications/bronze-maturity.json`;
  the direct contract test failed against the stale reference before the fix.
  Focused and routine validation passed; all 38 observed PR checks passed and
  PR #610 merged as `73c074c02950560696073ef77a479c7928f40b06`. This corrects
  documentation only and does not advance any gate.

## 2026-09-29 post-PR-613 qualification refresh

- [x] Regenerate the Bronze maturity receipt from exact merged `main`
  `b5e4302d9b23d3632900d955356fb7eaa7824b4c` after PR #613. It reports 174
  catalog sources, 157 in scope, 118 without qualifying landing evidence, and
  13 evidenced dimensions; completeness remains blocked. The status page now
  cites the refreshed report commit. This rebind adds no source landing and
  does not advance Bronze, M5, Australian federation, or stable-release
  approval.

## 2026-09-29 post-PR-623 qualification refresh

- [x] Regenerate the Bronze maturity receipt from exact merged `main`
  `214e7925735b8c9056806d4ef265976c594036ad` after PR #623. It reports 174
  catalog sources, 157 in scope, 118 without qualifying landing evidence, and
  13 evidenced dimensions; completeness remains blocked. The status page now
  cites the same report commit. Focused qualification tests passed (103), and
  the routine Test-Goblin harness passed. No new source receipt or acceptance
  evidence changes the four open gates: Australian federation, current-scope
  Bronze, M5 maturity, and stable-release approval.


## 2026-09-29 post-PR-626 qualification refresh

- [x] Regenerate the Bronze maturity receipt from exact merged `main`
  `2c70f59112280a0d9a137a3b25f5c870061e31e0` after PR #626. It still reports 174
  catalog sources, 157 in scope, 118 without qualifying landing evidence, and
  13 evidenced dimensions; completeness remains blocked. The M5 status page now
  cites the exact report commit. This provenance refresh adds no source landing
  and does not advance Bronze, M5, Australian federation, or stable-release
  approval.


## 2026-09-29 post-PR-628 qualification refresh

- [x] Regenerate the Bronze maturity receipt from exact merged `main`
  `a089cc15b7f9ab60f13232ca1f233bcc6df1f890` after PR #628. It reports 174
  catalog sources, 157 in scope, 118 without qualifying landing evidence, and
  13 evidenced dimensions; completeness remains blocked. The M5 status page cites
  the exact report commit. This provenance refresh adds no source landing and
  does not advance current-scope Bronze, M5, Australian federation, or
  stable-release approval. Focused qualification tests (103), the routine
  Test-Goblin profile, context/ecosystem validators, Ruff, `ty`, and diff checks
  passed.


## 2026-09-29 post-PR-630 qualification refresh

- [x] Regenerate the Bronze maturity receipt from exact merged `main`
  `f457dc0dd274ad26e0cedc313c64686d1d888064` after PR #630. It reports 174
  catalog sources, 157 in scope, 118 without qualifying landing evidence, and
  13 evidenced dimensions; completeness remains blocked. The M5 status page cites
  the exact report commit. This provenance refresh adds no source landing and
  does not advance current-scope Bronze, M5, Australian federation, or
  stable-release approval.


## 2026-09-29 post-PR-636 exact-main refresh

- [x] Merge PR #636 after all required hosted checks passed. The provider-thread
  correction reconciles OpenPrescribing's substantive reply and regenerates its
  queue and B0 projections without claiming a new landing.
- [x] Rebind the Bronze maturity report and this M5 status page to exact merged
  `main` `baec563d200ccb3dcdf1b5b5ada66dc7ba8c95bc`. It still reports 174
  catalogue sources, 157 in scope, 118 without qualifying landing evidence,
  two fixture-only, 15 excluded, and 13 evidenced maturity dimensions; source
  completeness remains blocked. The Australian federation, current-scope
  Bronze, M5, and separate stable-release approval gates remain open.


## 2026-09-30 post-PR-644 exact-main qualification refresh

- [x] Regenerate the Bronze maturity receipt against exact merged `main`
  `1f7e38f962a066d31bcd38e6885c39e1b4b92063` after PR #644. The report remains blocked at 117 of 157 in-scope
  public/no-credential sources without qualifying landing evidence; completeness
  remains the sole blocked Bronze maturity property, with 13 of 14 evidenced.
  Rebind the M5 status page to this exact report commit. The Australian
  federation, current-scope Bronze, M5, and separate stable-release approval
  gates remain open; this provenance refresh supplies no new source landing or
  release authority.


## 2026-09-30 post-PR-652 exact-main qualification refresh

- [x] Regenerate the Bronze maturity receipt against exact merged `main`
  `1b191a89b850f46432f91ba4aa0451357e747fe4` after PR #652 and rebind the M5
  status page to that report. It still finds 117 of 157 in-scope sources
  without qualifying landing evidence; completeness remains the sole blocked
  Bronze dimension, with 13 of 14 dimensions evidenced. This provenance refresh
  adds no landing and does not advance Australian federation, current-scope
  Bronze, M5, or stable-release approval. The focused Bronze/Stable-v1
  qualification tests passed (108).

## 2026-09-30 post-PR-655 Bronze landing reconciliation

- [x] Reconcile the approved Orange Book current-projection receipt as a
  source-specific landing and refresh Bronze evidence after PR #654. The
  current-scope denominator now records 116 of 157 in-scope public/no-credential
  sources without qualifying landing evidence; historical Orange Book coverage
  remains incomplete (140 of 260 releases accepted), and public release remains
  unauthorized. PR #655 refreshed the maturity report and status-page
  provenance against the exact main state at `2a240369d9016717d5d1798b26f5151866b61abc`.
  The landing reduces the uncovered count by one but leaves completeness and
  M5 blocked. Focused qualification tests and routine validation passed; this
  does not advance Australian federation or Stable v1 approval.

## 2026-09-30 post-PR-666 exact-main qualification refresh

- [x] Regenerate the Bronze maturity receipt against exact merged `main`
  `146a983f87263efd4c8bc19e6fb5b1cd7f6b9268` after PR #666 and rebind the M5
  status page. The report remains blocked at 116 of 157 in-scope public/no-
  credential sources without qualifying landing evidence, with completeness
  the sole blocked Bronze property and 13 of 14 mandatory properties
  evidenced. PR #666 confirms the exact historical PBS publication authority
  and previously verified raw archive digest, while general upstream reuse
  terms remain unknown; this does not qualify new acquisition or v4 admission
  and does not alter the denominator. Australian federation, current-scope
  Bronze, M5 and separate stable-release approval remain blocked.
