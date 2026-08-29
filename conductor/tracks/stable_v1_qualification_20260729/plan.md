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

- [~] Task: Reduce the protected CI critical path without weakening evidence
  - [x] Retain the existing isolated gremlin executor after batch size 10 and explicit four-worker modes both exceeded the existing hosted critical path
  - [x] Use the Python 3.14 sysmon coverage core; reject two-worker aggregate coverage after it ran slower and caused performance-budget contention
  - [x] Keep required check names stable while skipping mutation, gremlins, and consumer bodies only for provably documentation/Conductor-only pull requests; uncertain and non-PR events run the full suite
  - [x] Parallelize independent consumer-reproduction tests without changing required check names
  - [x] Measure hosted critical-path improvement and retain full exact-main verification
  - [~] Persist the content-validated gremlins cache across eligible hosted runs without sharing mutable execution state
  - [~] Add a non-blocking CPython 3.14 free-threaded canary for deterministic core contracts

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
  - Current-scope Bronze landing (M-095) and observable Renovate output (M-046)
    remain technical blockers; both dependent maturity dimensions stay M4.
  - `v1.0.0rc1` authority is explicitly prerelease-only. Final stable promotion
    remains blocked pending a distinct maintainer decision after the technical
    blockers pass.
  - Production DR and dataset publication remain separate boundaries and are
    not implied by software-only release qualification.
