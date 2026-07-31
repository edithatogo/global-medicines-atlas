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
- [~] Task: Contract canonical medicine schema v2 and migration compatibility for substances, products, packages, indications, prices and restrictions ([#41](https://github.com/edithatogo/global-medicines-atlas/issues/41))
  - Structural contract added as `schemas/canonical-medicine-v2.json`; the
    runtime now requires an explicit adapter-owned structural projection,
    validates closed references and assertion dimensions, preserves the full
    digest-bound schema-v1 source-native record, and rolls it back without
    semantic loss. This is explicitly distinct from the temporal assertion
    `v1_to_v2` migration. Representative contracts do not establish complete
    source or jurisdiction coverage; Phase 2 rehearsal remains open.
- [~] Task: Contract comparison-validity semantics for granularity, indication, population, mapping, normalization, material mismatches and inappropriate comparisons ([#41](https://github.com/edithatogo/global-medicines-atlas/issues/41))
  - The versioned vocabulary now has strict immutable runtime models and a
    deterministic evaluator. Any material mismatch is inappropriate; any
    unknown dimension abstains; compatible evidence is caveated; and every
    outcome explicitly denies medicine equivalence, substitutability,
    therapeutic interchangeability and equal benefit. API and CLI comparison
    responses expose fail-closed validity abstentions when source rows lack the
    required dimensional evidence. Phase 2 representative-cohort and full
    end-to-end qualification remain open.
- [~] Task: Contract bounded concept discovery, catalog APIs, CLI commands, accessible autocomplete and match explanations ([#41](https://github.com/edithatogo/global-medicines-atlas/issues/41))
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
    results without replacing their authority or implying equivalence.
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
  - The authoritative publication-identity registry assigns one non-overlapping
    intellectual-object role to each surface, validates cross-object links, and
    fails closed unless identifiers and licence decisions have durable evidence.
    Current external identifiers and all licence decisions remain unresolved or
    merely configured; no publication or approval is inferred.
- [x] Task: Phase Verification & Checkpoint
  - Independent review at `9332d27` found release-gate, canonical-schema,
    semantic-index, cross-page-validity, traceability, mutation and JavaScript
    style defects. The defects are remediated on the Phase 1 review-fix branch;
    checkpoint passed after PRs #98 and #99 completed 29 protected checks each
    and an independent post-merge re-review found no residual defects.

## Phase 2: v0.9 candidate

- [x] Task: Execute independent reproduction and disaster-recovery rehearsal ([#42](https://github.com/edithatogo/global-medicines-atlas/issues/42))
  - A deterministic aggregate receipt exercises independent child-process
    reproduction, governed backup/restoration/rollback and fail-closed receipt
    identity. It explicitly does not claim production disaster recovery,
    network isolation, artifact-only release reproduction or publication.
- [x] Task: Rehearse compromised-source quarantine, signing/credential revocation, dataset withdrawal, corrected replacement and downstream notification ([#42](https://github.com/edithatogo/global-medicines-atlas/issues/42))
  - The offline hash-chained incident rehearsal verifies ordering, tamper
    rejection, idempotent retries and separate regulatory/funding evidence.
    Credential-authority, human-notification and publication actions remain
    explicit external gates and are not claimed as executed.
- [~] Task: Verify every protected CI, security and publication receipt ([#42](https://github.com/edithatogo/global-medicines-atlas/issues/42))
  - The offline verifier now pins the repository, pull request, exact commit,
    required CI/security check names and producer identities, then binds the
    observed check-run and workflow-run identifiers into a deterministic
    receipt. Pending, failing, missing, duplicate or mismatched evidence is
    rejected. Publication remains independently `blocked` or `not_attempted`
    without a durable commit-bound receipt; exact hosted verification for the
    candidate pull request remains pending.
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
- [~] Task: Install built wheel and sdist in clean environments and run import, CLI, API, version and reinstall checks ([#42](https://github.com/edithatogo/global-medicines-atlas/issues/42))
  - The clean-consumer harness already covers wheel and sdist installation,
    metadata, dynamic version, reinstall, import, CLI and API. The exact current
    candidate still requires all-platform hosted receipts before completion.
- [x] Task: Snapshot and semantically diff the public OpenAPI contract and smoke-test a generated client ([#42](https://github.com/edithatogo/global-medicines-atlas/issues/42))
  - The deterministic read-only snapshot rejects incompatible removals,
    mutations, request bodies and response changes while permitting compatible
    additions; a generated typed Python client passes an offline transport
    smoke test and deterministic regeneration.
- [ ] Task: Resolve or explicitly block every Must requirement ([#42](https://github.com/edithatogo/global-medicines-atlas/issues/42))
- [ ] Task: Phase Verification & Checkpoint

## Phase 3: v1.0 promotion

- [ ] Task: Verify measured jurisdiction and source coverage ([#43](https://github.com/edithatogo/global-medicines-atlas/issues/43))
- [ ] Task: Verify hosted governance, security features and project views ([#43](https://github.com/edithatogo/global-medicines-atlas/issues/43))
- [ ] Task: Produce signed release package and consumer verification guide ([#43](https://github.com/edithatogo/global-medicines-atlas/issues/43))
- [ ] Task: Verify dataset cards, Croissant records, checksums and GitHub/Hugging Face/Zenodo/OSF identifier links without publishing restricted data ([#43](https://github.com/edithatogo/global-medicines-atlas/issues/43))
- [ ] Task: Obtain explicit maintainer licence and release approval ([#43](https://github.com/edithatogo/global-medicines-atlas/issues/43))
- [ ] Task: Record stable-v1 evidence and post-release monitoring plan ([#43](https://github.com/edithatogo/global-medicines-atlas/issues/43))
- [ ] Task: Phase Verification & Checkpoint

## GitHub hierarchy

- Parent: [#40 Stable v1 qualification](https://github.com/edithatogo/global-medicines-atlas/issues/40)
- Qualification contract: [#41](https://github.com/edithatogo/global-medicines-atlas/issues/41)
- v0.9 clean-room candidate: [#42](https://github.com/edithatogo/global-medicines-atlas/issues/42)
- v1.0 promotion and external gates: [#43](https://github.com/edithatogo/global-medicines-atlas/issues/43)
