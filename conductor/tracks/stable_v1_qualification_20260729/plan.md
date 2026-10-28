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
    are complete. The task remains in progress because the Australian health
    federation gate is blocked and no stable release has been produced. The
    sole maintainer granted conditional software-only `v1.0.0` promotion
    approval on 2026-10-18; it applies only after all qualification gates pass
    and the exact candidate, hosted checks, and attestation verify. The approval
    and readiness records are
    `quality/qualifications/stable-v1-promotion-approval-20261018.json` and
    `quality/qualifications/stable-v1-release-readiness-reconciliation.json`.
  - 2026-10-27 reconciliation after the Phase 4 delivery and Platinum consumer
    receipts: the six exact July 2025 MBS Silver tables pass v4 remote read and
    bounded API, CLI, Atlas, and JSONL canaries. The Phase 4 reconciliation
    records no additional eligible output clearing all delivery gates, and the
    recovery readiness receipt still lacks an approved independent target.
    The authoritative contract remains blocked by the Australian federation
    gate; M-105 and M-107 remain blocked, M-106 and M-108 through M-112 remain
    unresolved, and M-113 remains verified. The refreshed receipt binds the
    new system receipts without upgrading their scope or statuses. The retained candidate
    is historical and unsigned, bound to `6be062860b70ce3ef28dec55adfc3a1995802947`;
    a fresh exact candidate and protected-check verification must wait until
    every qualification gate passes. The consumer guide now uses Python 3.15.1
    and identifies the historical candidate limit. No signing, tag, attestation,
    stable release, or external publication was performed.
  - GitHub attestation verification passed for the published `v1.0.0rc1`
    wheel; receipt: `quality/qualifications/stable-v1-release-provenance-receipt.json`.
    This remains prerelease evidence and does not constitute a public stable v1
    release or satisfy exact-candidate verification.
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
  - The stable approval handoff records the maintainer's conditional
    software-only `v1.0.0` authorization. The Australian federation gate remains
    blocked; signing, tagging, attestation, and publication are not authorized
    until all qualification conditions and exact-candidate verification pass.
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
    conditional stable-v1 promotion approval and production DR authority remain
    separately scoped. The conditional approval is now recorded; qualification
    and release remain blocked by Australian federation and exact-candidate
    requirements. OSF is deprecated. Public/no-credential catalogue archival is
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

- [x] Reconcile the approved Prompt 29 private historical acquisition receipt
  in the current-scope Bronze denominator. The value-free recognizer binds the
  source-specific internal-only acquisition authorization to all 15 admitted
  payloads, four expected releases, and clean-room digest restoration; it keeps
  source-record projection, public release, and external publication false.
  The current landing queue records `landed_and_evidenced`, and the exact-main
  Bronze report includes the receipt in its landing evidence while retaining
  the separate 116-source completeness blocker. This closes historical private
  receipt reconciliation only; no source-record projection, current utilisation
  coverage, public release, third-party separability, or independent archive
  durability is claimed.
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

## 2026-09-30 post-PR-672 exact-main qualification refresh

- [x] Regenerate the Bronze maturity receipt against exact merged `main`
  `74ba22a6fa6aa5ce3939201a6a87d867efc230ec` after PR #672 and bind the M5
  status page to that report. It remains blocked at 116 of 157 in-scope sources
  without qualifying landing evidence; completeness is the sole blocked Bronze
  maturity property, with 13 of 14 mandatory properties evidenced. Prompt 31
  was already included in this denominator; its closure adds no new landing
  increment. Australian federation, current-scope Bronze, M5 and stable-release
  approval remain open.

## 2026-09-30 post-PR-673 exact-main qualification refresh

- [x] Regenerate the Bronze maturity report against exact merged `main`
  `6fe5a8dfd02d9a72bcfe522e621cfbdb4c16ff89` after PR #673 and bind the M5
  status page to that commit. It remains blocked at 116 of 157 in-scope sources
  without qualifying landing evidence; completeness remains the sole blocked
  Bronze property, with 13 of 14 mandatory properties evidenced. The PR changed
  report provenance only; all four Stable v1 acceptance gates remain open.

## 2026-09-30 post-PR-674 exact-main qualification refresh

- [x] Regenerate the Bronze maturity report against exact merged `main`
  `58408e87d1c35e1995d6bb789639089e4a2f0599` after PR #674 and bind the M5
  status page to that commit. It remains blocked at 116 of 157 in-scope sources
  without qualifying landing evidence, with completeness the sole blocked
  Bronze property and 13 of 14 mandatory properties evidenced. This is a
  provenance refresh only; the four Stable v1 acceptance gates remain open.


## 2026-10-03 post-PR-708 M5 source-coverage provenance

- [x] Refresh the Bronze maturity report from exact merged `main`
  `752908d174175f3307f34eecc677711fb189b745` after PRs #707 and #708, and bind
  this status page to that report. Reconcile the receipt count to 28 while
  preserving 42/157 landing evidence, 115 missing, and 13/14 dimensions;
  completeness, Australian federation, M5, and stable-release approval remain
  blocked.
- [x] Address the hosted unit findings by regenerating the queue and cohort
  from canonical sparse overrides, refreshing dependent qualification
  snapshots, and binding the status page to the recorded report provenance.
  The corrected affected contracts pass (254 tests; 2 provenance follow-up
  tests), with routine checks, context/ecosystem, and diff validation passing.
  PR #709 merged at `d573b997c10f3d5fd5fc00c838350c7cd452622c` after all
  required branch-protection checks passed; no acceptance gate was promoted.

## 2026-10-03 post-PR-713 exact-main M5 refresh

- [x] Regenerate `quality/qualifications/bronze-maturity.json` from exact
  merged `main` `9a2a7bfe9f02f3b04f792dc958d6773f5098128b` after PR #713 and
  rebind this status page to that report. It remains blocked at 115 of 157
  in-scope public/no-credential sources without qualifying landing evidence;
  completeness is the sole blocked Bronze property, with 13 of 14 mandatory
  properties evidenced. The archived P7 receipt reconciliation changes no
  source-origin acquisition, B1 admission, M-112, M5, or Stable v1 gate state.


## 2026-10-04 post-PR-733 M-112 acceptance reconciliation

- [x] Refresh the Australian federation acceptance page from the exact merged
  M-112 disposition. All 1,759 approved candidate paths now have explicit
  future-source dispositions; the denominator is unchanged, and no deferral is
  counted as rights approval, v4 admission, or federation acceptance. The page
  records the remaining per-object rights, B1/B2 lineage, digest-readback,
  admission, and consumer-canary requirements.
- [x] Re-run the stable-v1 contract reconciliation on exact merged `origin/main`
  `caf2684631742a732e783ff1124647c63f2ad1e5`. It is idempotent: 15 of 17
  release gates pass; Australian federation and explicit Stable v1 release
  approval remain blocked. Bounded Bronze and M5 pass with all 14 mandatory
  Bronze dimensions evidenced for the approved 42-source horizon.
- [x] Verify the acceptance-page and stable-contract tests (47 passed), routine
  Test-Goblin, context/ecosystem validation, and diff checks. No source payload
  values, rights conclusions, denominator decisions, v4 admissions, or release
  approvals changed.

## 2026-10-04 post-PR-755 M-112 identity reconciliation

- [x] Refresh the dependent Australian federation acceptance evidence from
  merged PR #755 (`8aa006d58a5f8809f0b0541a8ca921e84c96ec53`). The July 2025
  MBS v4 candidate's nine public object identities match its immutable
  publication receipt and current tree; only the identity blocker is resolved,
  and the product remains candidate-only. M-112 admission, rights, lineage,
  full-denominator digest readback, and consumer canaries remain open. The
  Stable v1 federation gate and separate maintainer release-approval gate
  therefore remain blocked; no release decision is inferred.

## 2026-10-04 post-PR-757 exact-scope MBS utilisation rights reconciliation

- [x] Update the dependent Australian federation acceptance page after PR #757
  approved reuse and external publication for the exact 14-object
  MBS-utilisation manifest under its official CC BY 3.0 Australia metadata.
  Keep the objects deferred because per-object B1 rights/reuse fields,
  complete B1/B2 lineage, v4 admission, and consumer canaries remain open.
  The third source ID in the broader authorization has no object in this
  cohort, and PBS-utilisation rights remain unresolved. Stable v1 federation
  acceptance and separate stable-release approval remain blocked.

## 2026-10-05 exact-main M5 maturity reconciliation

- [x] Reconcile the eight M5 dimensions and Stable v1 gates against exact
  current `main` `f160a0235c66c425150f90b4cdc6ea3d55365b5b`; refresh only
  provenance supported by current evidence, state the remaining external and
  human gates precisely, run affected checks, and complete Conductor review.
  The report remains qualified at 42/42 approved bounded sources; all eight
  M5 dimensions remain verified, with the Australian federation and final
  stable-release gates separate and blocked. Production disaster-recovery
  authority remains explicitly unclaimed and outside the acceptance gate set.
  Focused qualification tests (237), routine Test-Goblin, exact-main
  regeneration, and Conductor review passed; see the 2026-10-05 M5 evidence
  entries in `evidence.jsonl`.

## 2026-10-17 current-main M5 refresh

- [x] Re-run the Bronze maturity generator against exact `main`
  `7fe32a8830d9576ebcc4b431031d59e6809ef379` after PR #791. The report's
  substantive qualification is unchanged from the 2026-10-05 run: all eight
  M5 dimensions remain verified, the Bronze gate remains passed, and only the
  Australian federation and stable-release approval gates were blocked at the
  time of that refresh.
  Refresh the report's evaluated timestamp and exact source commit, verify
  the Stable v1 contract remains idempotent, and rerun the focused and routine
  affected checks before marking this refresh complete.

## 2026-10-18 M-105 narrow chronology waiver reconciliation

- [x] Record the maintainer-approved D-006-10 timing-only waiver and regenerate
  Stable v1 qualification from the complete M-105 disposition dossier. M-105
  is verified under the waiver; no pre-archive parity proof is claimed and the
  M-105 criterion itself is unchanged.
- [x] Keep M-106–M-112, Australian federation acceptance, and stable-release
  approval blocked; M-113 remains verified for donor archival. The separate production disaster-recovery authority gate
  remains outside the release contract. Focused tests (54), broader affected
  checks (65), Ruff, formatting, JSON/JSONL validation, and diff checks pass;
  hosted PR checks remain pending.

## 2026-10-18 M-105 waiver validator review correction

- [x] Make the waiver reconciliation fail closed on disposition/state mismatch,
  failed or unknown row states, missing behavior evidence, incomplete
  not-waived boundaries, and widened source-rights/publication/release flags.
  Eight adversarial cases refresh the matrix and dossier digests before checking
  rejection. Focused M-105/Stable tests (62) and broader affected tests (65),
  Ruff, formatting, BasedPyright, `ty`, and diff checks pass. Updated PR hosted
  checks remain pending; the independent Australian and release gates remain
  blocked.


## 2026-10-18 conditional Stable v1 promotion approval

- [x] Record the sole maintainer's conditional approval for software-only
  `v1.0.0` promotion in decision D-006-11 and its schema-validated receipt.
  The approval gate now passes. Stable v1 qualification remains blocked by
  Australian health federation; no signing, tag, release, attestation, dataset
  publication, production deployment, or production DR action was performed.
  The approval is usable only after every qualification gate passes and the
  exact candidate, protected checks, and attestation are verified.

## 2026-10-18 protected Stable v1 promotion workflow

- [x] Add an explicit release-type choice that defaults to the existing
  prerelease authority. The stable path accepts only the separately approved
  software-only `v1.0.0` scope after validating the qualification schema, all 17
  required gates, no unresolved blockers, and the digest-bound readiness and
  approval receipts. The publication workflow remains manual, protected, and
  draft-only; the Australian federation gate is still blocked, so it has not
  been dispatched and no release action has occurred.
- [x] Focused authority/workflow tests (26), Ruff, BasedPyright, and the pinned
  full Test-Goblin profile pass on macOS arm64 with Python 3.14.6 and uv
  0.11.29. Hosted checks for the rebased PR remain pending.


## 2026-10-18 protected-checkout identity review fix

- [x] Correct the stable publication identity guard for GitHub Actions exact-SHA
  checkout: require the protected `refs/heads/main` event and compare `HEAD`
  directly with `GITHUB_SHA`, without assuming a local main ref exists. Address
  automated review finding P1 on PR #1156. Focused tests (78), Ruff, formatting,
  `ty`, BasedPyright, actionlint, and diff checks pass. Hosted checks are pending
  for the corrected head. Federation remains blocked; no release action occurred.

## 2026-10-18 M5 Australian requirement status reconciliation

- [x] Reconcile the M5 maturity summary with merged PR #1155 and D-006-10:
  M-105 is verified under the narrow chronology waiver; M-106–M-112 remain
  blocked. State explicitly that no pre-archive parity proof is claimed and
  keep Australian federation as the remaining unresolved qualification gate.
  Reflect the verified contract totals (85 verified, 7 blocked; 16 of 17
  release gates passed) and D-006-11 as a passed conditional software-only
  release-approval gate, while making clear that promotion has not been
  executed and awaits completion of qualification and exact-candidate checks.
- [x] Leave qualification counts and gate results unchanged; this corrects
  stale prose only. Review correction updates counts and gate wording to the
  authoritative contract. Context/ecosystem validation and `git diff --check`
  pass.

## 2026-10-23 post-PR-1287 exact-main M5 refresh

- [x] Re-run the Bronze maturity generator and the Stable v1 projections against
  exact `main` `78e857839aad8298060c65eb5ef03a4e3114827a` after PR #1287, and
  rebind the M5 status page's current Bronze qualification source commit. The
  report's substantive qualification is unchanged: it remains qualified and
  mature at 42/42 approved bounded sources, with the 159-source
  public/no-credential universe, its 117 deferred entries and the separate
  29-source direct-receipt cohort unchanged. The bounded future-source ledger,
  the source-maturity catalogue projection and the Stable v1 contract
  reconciliation regenerated byte-identically, so this refresh changes report
  provenance only; the monitoring receipt check passed.
  The provenance acceptance test
  (`tests/test_stable_v1_qualification_contract.py::test_stable_v1_status_page_matches_current_bronze_report_provenance`)
  failed on the regenerated report before the status page was rebound and passed
  afterwards. All eight M5 dimensions remain M5/verified with no blocker IDs,
  85 requirements remain verified and 7 remain blocked, and 16 of 17 release
  gates pass. Australian health federation acceptance remains the single
  unresolved qualification gate; the conditional D-006-11 software-only
  `v1.0.0` approval is not exercised and no stable tag, signed asset,
  attestation or release was produced. Production disaster-recovery authority
  remains separately `not_claimed` and outside the acceptance-gate set.

## 2026-10-23 current M-105 disposition

- [x] Apply D-006-12 to the current Stable v1 contract while preserving the
  historical D-006-10 chronology-waiver receipt. The current M-105 requirement
  is blocked because pre-archive parity evidence cannot be established
  retroactively; contract totals are now 84 verified and 8 blocked. The
  Australian federation release gate remains blocked and the M5 Bronze
  qualification is unchanged.

## System completion execution focus (2026-10-25)

Select the next task through the [system completion charter](../../system-completion.md)
and [validated scheduling plan](../../system-completion.json). Name its shared
capability or gate, concrete failure, bounded frozen-inventory scope, expected
proof, and targeted validation. Advance the system lanes when prerequisites
permit; perform dataset semantics or coverage work only when needed for a
named gate. Preserve unresolved fields and all mandatory eligible-object
identity, lineage, rights, admission, recovery, and consumer evidence. Broader
coverage, new sources/terminology, and optional experiments remain deferred.
This scheduling direction changes no acceptance criterion, current M-105/M-107
disposition, or conditional release approval; current states come from the
authoritative contract, reconciliation, and bound receipts.

### October 28 PBS r17 contract reconciliation

- [x] Reconcile the new PBS r17 field-state receipt into M-109 evidence, the
  Stable v1 contract, and the readiness receipt. The M-109 and Australian
  federation gates remain blocked: the increment classifies only 10,368
  `rdf:about` syntax-role fields and does not resolve PBS relationships or
  source values. M-105/M-107, the remaining federation requirements, and
  conditional promotion prerequisites are unchanged. Targeted PBS and Stable
  contract checks, static analysis, and Conductor context validation pass;
  details are in `evidence.jsonl`; implementation commit `636c27bf` records the report, code, and contract bindings.

### October 28 M-107 exact endpoint metadata recheck

- [x] Recheck the three already-authorized Health.gov workbook URLs using one
  metadata-only `HEAD` per endpoint. All returned HTTP 200, the expected XLSX
  content type, and the same byte lengths and Last-Modified dates as the prior
  workstation preflight. No body was read. Because the prior exact-main hosted
  probe timed out and transport metadata has not changed, do not repeat the
  harvest; M-107 remains blocked pending a changed hosted route or an
  agency-supported delivery route. The [snapshot record](../../../docs/qualification/australian-mbs-pbs-m107-snapshots.md)
  and readiness digest now bind this observation.

### October 28 PBS r18 review correction

- [x] Review the r17 field-role evidence and fix the missing digest binding to
  its exact schema-path inventory. The r18 successor enforces the inventory
  SHA-256 and records it in the report; a negative control rejects changed
  inventory identity. M-109, the Australian federation gate, and conditional
  promotion remain blocked. The affected PBS and Stable contract suites, static
  checks, and context validation pass. Review was performed by the implementing
  agent, not an independent reviewer. Commit `2f2d61f0` contains the report,
  input digest binding, readiness reconciliation, and review correction.

- [x] Implement the shared execution charter and machine-validated scheduling
  plan; require named existing gates, bounded failures, proof and stop conditions.
  Extend the existing CI context validator to reject source/inventory expansion,
  acceptance waivers, unknown gate/track references, and planning acceptance
  claims. Retained archived tracks remain valid owners. Thirty focused context
  tests pass on repo-local CPython 3.15.1; Ruff, formatting, BasedPyright, `ty`,
  context validation and diff checks pass. No local full profile was run.
  Existing qualification/release artifacts and protected hosted checks retain
  their authority; hosted results for this change remain pending.
- [~] Advance the selected `admitted-delivery` system lane: trace an existing
  eligible Silver producer output through v4 admission and the actual consumer
  boundary, resolve the first shared failure, and retain all mandatory object
  evidence and source-specific blockers under the existing contracts.

### Stable support runtime reconciliation (2026-10-27)

The Stable v1 support register carried a stale CPython 3.14 claim after the
repository runtime and CI had moved to CPython 3.15.1. Reconcile the support
register to the current project contract and the exact-main Test-Goblin
cross-platform consumer evidence. The support aggregate is verified only when
every support boundary passes and there is no blocking unresolved residual
risk. This does not change or waive the independent Australian federation
release gate.

- [x] Record the exact-main Python 3.15.1 runtime and Linux/macOS/Windows
  consumer evidence in
  `quality/qualifications/stable-v1-python-runtime-validation-20261027.md`.
- [x] Correct the support report and Stable v1 contract runtime claims; derive
  support aggregate readiness from its boundary and residual-risk states.
  Preserve the accepted production DR limit as a separate non-acceptance gate.
- [x] Verify the focused contract suite (57 passed), Ruff, formatting, `ty`,
  BasedPyright, context validation, and diff checks. The conditional stable
  authority validator remains blocked by the unresolved Australian federation
  gate; the historical release candidate remains unverified and unsigned.

### Australian federation evidence pointer reconciliation (2026-10-28)

- [x] Preserve the 2026-10-27 Phase 4 report and add a 2026-10-28 successor
  binding the verified 91-workbook header meanings and zero formula/source-error
  observations to the unresolved value states. Reconcile the successor into the
  Stable v1 gate and M-108/M-109/M-112 requirement evidence. Focused
  evidence-binding and fail-closed tests pass (implementation 4387181c).
  The Australian federation gate remains blocked; this does not make the stable
  candidate promotable or the track archivable.

## Phase: Review Fixes
- [x] Task: Review the evidence reconciliation; no corrective findings. Focused
  tests, context validation, lint, formatting, and type checks pass
  (4387181c).


## Phase: M-110 bounded edge-review pointer reconciliation (2026-10-28)

- [x] Task: Reconcile the existing maintainer disposition for the exact 5,989 July
  2025 MBS v3 same-record candidate edges into M-110 and the Australian
  federation contract evidence. Correct the acceptance table: the bounded
  candidate edge set was reviewed, while broader M-110 calibration and
  federation acceptance remain open. Reconciliation does not alter M-110's
  blocked state or the overall federation gate. Implementation `333f00f0`;
  focused qualification checks passed.

## Phase: Review Fixes (continued)

- [x] Task: Review the bounded-review pointer and acceptance-table correction;
  no corrective findings. The focused fail-closed qualification checks pass
  (333f00f0).

## Australian August projection current-tree reconciliation and review (2026-10-28)

- [x] Perform a bounded anonymous metadata read of the four exact attested
  August 2026 MBS Bronze Parquet objects at public revision
  `b925a8a80b0f90db09513e7ce1378045461b05c0`. Their four LFS SHA-256 values
  and byte counts still match the existing rights/scope receipt. The `d781`
  prefix has only an accepted, unreviewed Bronze admission; the `f9f9` prefix
  has no admission sidecar. No source or Parquet payload bytes were downloaded.
- [x] Bind the readback to M-108 and the federation gate without changing any
  qualification, rights, admission, publication, or frozen-inventory state.
  Refresh readiness hashes and correct M-108/M-109/M-111/M-112 acceptance
  summaries to reflect the latest Phase 4, v4 remote-reader, consumer, and
  recovery evidence.
- [x] Review the scoped federation changes and fix the stale acceptance summary.
  The affected receipt, qualification, guardrail, and reconciliation tests pass
  (523); context, Ruff, formatting, ty, BasedPyright, and diff checks pass.
  Stable promotion authority validation correctly remains blocked on unresolved
  Australian federation gates. No local full profile was run.
- [ ] Keep M-108 blocked pending exact product-specific v4 cards/admission,
  independent-replica evidence, and the `f9f9` prefix disposition. Continue
  independent semantics and required source-evidence work where current
  authority and source contracts support it; do not archive this track until
  the gate is actually accepted.

### Formal Conductor review correction (2026-10-28)

- [x] Review commit `0bc2513b` against the Stable v1 plan, qualification
  contract, product guidance, and affected tests. The review found the M-109
  acceptance row did not reflect current 91-workbook header evidence or
  distinguish the internal P7 DMY consistency inference from an unqualified
  workbook-era date convention. Correct the row and bind its new digest in the
  readiness reconciliation. The P7 date convention and domain meaning remain
  unqualified; no acceptance gate changes. The Stable contract and context
  test files pass (89 total); context validation, Ruff, formatting, `ty`,
  BasedPyright, and diff checks pass.
- [ ] Reconcile PR #1354 protected checks and merge only after they pass; keep
  Stable v1 and the federation track blocked until all contract gates pass.

### PR #1354 hosted-check inventory and workflow-permission correction (2026-10-28)

- [x] Diagnose the exact-head CI failures. Test-Goblin rejected the existing
  Phase 4 workbook reconciliation test as unassigned, causing all Python lanes
  to fail before execution. `zizmor --pedantic` also flagged two documented
  recovery workflows' `actions: read` permission because its purpose was not
  annotated at the permission declaration.
- [x] Assign the reconciliation test to the unit lane and annotate the minimum
  `actions: read` permission in the two workflows that download previous-run
  recovery artifacts. Focused tests: 99 passed; Test-Goblin contract inventory,
  Ruff, formatting, `zizmor --pedantic .github`, and diff checks passed.
- [x] Push correction `38a3b713`. The exact-head unit lane then exposed four
  additional stale assertions; their diagnosis and repair are recorded below.

### PR #1354 exact-head unit failure correction (2026-10-28)

- [x] Diagnose the four exact unit failures on head `38a3b713`: two assertions
  referred to superseded PR-number prose and an obsolete unadmitted-candidate
  state; two expected a generic `durable` error while the current receipt
  validator correctly reports stage-specific invalid-URL errors.
- [x] Reconcile the acceptance summary with the exact 14-object MBS-utilisation
  rights scope and the separately attested six-object PBS-utilisation rights
  scope, preserving the pending B1/B2 lineage, admission, canary, and broader
  rights limits. Refresh the acceptance-summary digest in Stable readiness.
  Update regression assertions to the current evidence and validate the
  stage-specific error behavior without changing runtime code.
- [x] Focused affected tests: 139 passed across the M-112 state, donor-history,
  Stable contract, and Phase 4 reconciliation modules. Ruff, formatting,
  context validation, and diff checks pass.
- [x] Push the correction, reconcile all protected checks at that exact PR
  head, and merge only after they pass. PR #1354 merged at
  `67278c534438a15bfb529f6ab10e815f6bde1b9a` after every required protected
  check passed. All Australian federation dispositions remain as evidenced;
  this correction does not satisfy the gate.

### PR #1354 transaction-intent retention review repair (2026-10-28)

- [x] Formal review found that three metadata append workflows wrote the
  transaction intent locally but uploaded it only after the mutation script
  completed. Split normal runs into a preflight phase, 90-day Actions artifact
  upload, hosted artifact download/readback, and an append phase that requires
  exact equality with the recomputed intent. Recovery runs retain their
  existing authenticated acknowledgement path. This creates a retained
  precondition before mutation without outbound comments or messages.
- [x] Add negative-control coverage for mismatched prepublished intent and
  workflow-order assertions. The combined affected suite passes (895 tests);
  Ruff, formatting, Actionlint, and diff checks pass.
- [x] Repeat the combined focused checks (895 passed), push the repair, and
  inspect the exact-head protected runs. Every required PR check passed at
  `7a61ecd019fe264fd03c3ac0b601841eaf4e9a8e`; PR #1354 merged as
  `67278c534438a15bfb529f6ab10e815f6bde1b9a`. Action artifacts have 90-day
  retention and do not count as permanent Conductor evidence; no hosted
  transaction was executed. Federation gate and stable promotion remain
  blocked.

### August `f9f9` projection disposition (2026-10-28)

- [x] Bind the exact two-object `f9f9` prefix to the current anonymous tree
  readback and rights-only attestation. Record `deferred_not_admitted` because
  the product has no Bronze admission sidecar, product-specific federation-v4
  card, typed admission, or independent-replica evidence, and the attestation
  does not authorize admission or canaries. Add the disposition to generated
  Stable M-108 and federation-gate evidence and refresh the readiness receipt.
  No source, inventory membership, rights conclusion, publication, admission,
  or canary changed. The M-108 and federation gates remain blocked.
- [x] Review repair: bind the Phase 4 reconciliation digest used to support the
  missing product-card and independent-replica findings. Focused tests,
  `ty`, BasedPyright, Ruff, formatting, context validation, and diff checks
  pass. Review was performed by the implementing agent; no independent review
  or gate acceptance is claimed.
- [x] Re-run both affected qualification modules after the review repair:
  66 passed; context validation and diff checks pass. No full local profile was
  run because this evidence-bound disposition does not change runtime behavior.
- [ ] Continue M-108 only when each remaining exact output has complete
  product-specific qualification, independent-replica evidence, and separate
  admission authority; retain the present no-admission boundary.

### Formal Conductor review of the 2026-10-28 disposition update

- [x] Review the scoped change from `origin/main` through the f9f9 disposition
  and review-fix commit. The first focused type-check pass found that the
  affected M-112 test helper exposed decoded JSON as `dict[str, object]`,
  producing eight indexing/iteration diagnostics. Correct it to
  `dict[str, Any]` in `30d4fd85`; the changed range then passes the 66 focused
  qualification tests, Ruff, Ruff formatting, `ty`, BasedPyright, and diff
  checks. Review was performed by the implementing agent; no independent
  reviewer or gate acceptance is claimed. M-108 and the Australian federation
  gate remain blocked, so the Stable v1 track remains open and is not archived.

### M-112 current receipt reconciliation and review (2026-10-28)

- [x] Bind the current M-112 role receipt and exact 14-object MBS-utilisation
  B1/B2 lineage overlay into the Stable M-112 requirement, federation gate,
  acceptance summary, and release-readiness receipt. Record 8 exact v4
  admissions and 8 canaries against the frozen 1,759-object denominator, with
  1,751 still deferred; distinguish the 14 lineage joins from v4 admission.
  Preserve the reviewer-unreviewed landed-admission status and blocked gate.
  Implementation `bdeb6dc1`.
- [x] Review the scoped contract and acceptance update. Correct the acceptance
  page's stale reconciliation date and refresh its digest binding. The 67
  focused M-112/Stable tests, Ruff, Ruff formatting, `ty`, BasedPyright,
  context validation, and diff checks pass. Review was performed by the
  implementing agent; no independent reviewer, new admission, canary, source,
  publication, or federation acceptance is claimed.

### PBS schema-version field evidence (2026-10-28)

- [x] Bind PBS r19 into the Australian acceptance summary, Stable contract,
  and release-readiness receipt. The exact root `@version` field is interpreted
  as source schema version 3.1 from the existing metadata-only receipt; the
  schema patch and all PBS medicine values and relationships remain unresolved.
  The machine contract remains blocked only on the Australian federation gate.
  No source, rights, admission, canary, publication, or stable-release state
  changed. After review hardening the receipt path before file access, focused
  PBS and Stable contract tests pass (60 and 64); total focused coverage is
  94.60% and PBS module branch-inclusive coverage is 95%. Source/runner static
  checks, context validation, and diff checks pass. Review is by the
  implementing agent only. Commit `5f64d335` records the r19 increment.

### PBS `rdf:resource` generic syntax-role qualification (2026-10-28)

- [x] Add the exact QName-bound RDF/XML syntax role to PBS field-state
  successor r16, preserving r15 and all source values. Implementation
  `c8ea243b`. The W3C RDF/XML
  Recommendation supports the generic object-node IRI-reference role for
  1,159,282 additional fields. The complete PBS partition is now 3,086,366
  interpreted, 15,122,392 `native_unresolved`, and zero unavailable. The
  exact URI screen remains lexical evidence; target resolution, predicate
  meaning, relationship edges, and complete M-109 acceptance remain open.
- [x] Bind r16 and its limitations into the Australian acceptance summary,
  Stable contract evidence, and readiness receipt. Stable v1 remains blocked
  on `stable-v1-australian-health-federation`; M-105, M-107, M-108 and other
  acceptance conditions were not waived or reclassified.
- [x] The affected PBS field-state module passes (50 tests); the new runner
  reproduces the retained r16 report byte-for-byte; Ruff, formatting, `ty`,
  and BasedPyright pass for changed implementation and runner files. Focused
  three focused Stable qualification tests and context validation pass and are
  recorded in the evidence ledger. Review remains an implementing-agent review, not an
  independent approval.
- [ ] Continue federation work through its remaining evidence gates. Do not
  close or archive the Stable v1 track while its authoritative contract has
  unresolved gates.

### M-111 browser canary for the admitted July MBS cohort (2026-10-28)

- [x] Extend the existing bounded delivery qualification to optionally render
  the same Atlas responses through Chromium, compare rendered cells to the
  API result in memory, enforce a same-host request boundary, and retain only
  hashes, counts and HTTP status. Enable it in the existing exact-six MBS v4
  admission workflow. Synthetic fixture browser test, affected delivery tests,
  Ruff, formatting, `ty`, configured BasedPyright targets, Actionlint and diff
  checks pass. No source payload, rights, admission, or publication state was
  changed locally.
- [x] Merge the scoped change after protected checks pass, dispatch the
  existing exact-main admission workflow, then validate and reconcile the
  resulting six-object browser receipt into M-111 and Stable readiness. PR
  #1357 merged as `29afcd342507f6110c557a0ddb0a9346d903bac4`; exact-main run
  `40653807510` passed the six-object browser and consumer canaries. The
  Australian federation and Stable v1 gates remain blocked until all their
  independent requirements pass.

## Phase: M-112 exact PBS-utilisation rights and lineage reconciliation (2026-10-28)

- [~] Bind the existing six-object PBS-utilisation rights attestation to the
  exact six frozen object identities and the landed B1/B2 lineage receipt.
  Reconcile only the stale per-object rights state; preserve each Bronze
  admission as unreviewed and keep v4 admission and consumer canary false.
  Expected evidence: a digest-bound six-object reconciliation and tests proving
  exact path/digest/byte binding and unchanged M-112 deferral/admission counts.

## Phase: Review Fixes — M-111 receipt binding (2026-10-28)

- [x] Rebind all six consumer contract, semantic-profile, and canary identity
  digests to exact-main receipt `40653807510`; add a regression that verifies
  the consumer and readiness records against the hosted evidence. Commit
  `5a3879b7`; 67 focused tests, static checks, and Conductor validators pass.
