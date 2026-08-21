# Implementation Plan

Execution policy: [autonomous, decision-gated](../../autonomy.md).

This track completes bronze for current public/no-credential scope. It does not
implement silver, gold, or platinum. Hugging Face archival of public data is
owned by a sibling track; this plan consumes that archive boundary.

The immutable source payload and its content-addressed receipt are evidentiary
truth; source-faithful Parquet is the portable analytical representation;
table/catalogue layers are rebuildable metadata over those artefacts.

## Phase 1: Inventory, layer contract, and identity reconciliation

- [x] Task: Write failing tests for bronze scope classification and catalog/fixture identity reconciliation ([#168](https://github.com/edithatogo/global-medicines-atlas/issues/168))
    - [x] Assert in-scope first-cohort and global public/no-credential sources are enumerated from `medicine_source_catalog.json`
    - [x] Assert credentialed and licensed-feed sources are excluded with reasons
    - [x] Assert adapter and fixture identifiers map to catalog `source_id` values or an explicit alias
    - [x] Assert RxNorm/UMLS live payloads are fixture-only
    - [x] Confirm the intended failure before implementation
- [x] Task: Implement the bronze inventory and layer contract
    - [x] Record public ingest versus fixture-only versus excluded
    - [x] Preserve independent regulatory, funding, formulary, and terminology dimensions
    - [x] Cross-reference M-092 to M-100 and design section Medallion Datahouse
- [x] Task: Phase Verification & Checkpoint
    - [x] Run focused tests, affected harness, typing, and provenance checks
    - [x] Record evidence; do not claim live bronze landing complete

## Phase 2: Pre-acquisition reuse gate

This phase is first-class. It exists to stop independent copies of the same
public data. It runs before any acquire/download, including Drugs@FDA.

- [x] Task: Write failing tests for the reuse gate ([#176](https://github.com/edithatogo/global-medicines-atlas/issues/176))
    - [x] Assert acquisition without the gate fails
    - [x] Assert each disposition reuse | link | mirror | extend | fork | acquire-new is representable
    - [x] Assert acquire-new is last resort when a payload copy already exists
    - [x] Assert searches cover local clones, GitHub, Hugging Face, and the source registry
    - [x] Confirm the intended failure before implementation
- [x] Task: Implement the reuse gate against existing contracts
    - [x] Reuse `docs/ECOSYSTEM_REUSE.md` and `.context/ecosystem.toml`
    - [x] Search `medicine_source_catalog.json` and the Hugging Face catalogue
    - [x] Bind the chosen disposition onto receipts and OpenLineage
    - [x] Fail closed when Drugs@FDA or any acquire path skips the gate
- [x] Task: Phase Verification & Checkpoint
    - [x] Run focused tests, typing, and provenance checks
    - [x] Record the disposition vocabulary in evidence

## Phase 3: Evidentiary payloads, temporal identity, and source-faithful Parquet

- [x] Task: Write failing tests for bronze landing storage ([#169](https://github.com/edithatogo/global-medicines-atlas/issues/169))
    - [x] Assert payload bytes are preserved and Parquet is not the payload
    - [x] Assert receipts are content-addressed and bind payload digest, source identity, dates, and rights
    - [x] Assert temporal fields are distinct; substituting retrieved_at for published time fails
    - [x] Assert valid_* are absent when the source did not supply them
    - [x] Assert acquisition ID is immutable across Parquet regeneration
    - [x] Assert DuckDB and LanceDB are absent from bronze identity
    - [x] Confirm the intended failure before implementation
- [x] Task: Implement payload landing, temporal identity, and analytical Parquet
    - [x] Reuse `receipts.py`; do not treat DuckDB or Parquet as evidentiary truth
    - [x] Record source published/effective time, retrieved_at, valid_from/to, acquisition ID
    - [x] Fail closed on missing rights, provenance, or receipt fields
    - [x] Bind actual Parquet output bytes to a distinct append-only transformation-run receipt, OpenLineage run identity, code commit, environment digest, parser, and output schema
    - [x] Preserve acquisition, transformation, and admission as separate append-only event histories; admission reversals supersede rather than rewrite decisions
- [x] Task: Phase Verification & Checkpoint
    - [x] Run focused tests, coverage, typing, and licensing checks
    - [x] Record payload digests, acquisition IDs, and Parquet identities in evidence

### Phase 3b: Append-only acquisition, admission, and HTTP receipts

- [x] Task: Harden append-only acquisition identity ([#169](https://github.com/edithatogo/global-medicines-atlas/issues/169), parent [#167](https://github.com/edithatogo/global-medicines-atlas/issues/167))
    - [x] Separate content_id / payload digest from acquisition_id
    - [x] Keep source/version, published/effective, retrieved_at, and source-supplied validity independent
    - [x] Physically deduplicate identical bytes without collapsing acquisition history
    - [x] Schema contract and migration-safe TemporalIdentity without content_id
    - [x] Version acquisition events to bind source, retrieval, reuse, rights, and evidence context independently from transformation output
- [x] Task: Bronze quarantine and admission lifecycle ([#169](https://github.com/edithatogo/global-medicines-atlas/issues/169))
    - [x] States landed → accepted | quarantined | rejected-from-processing
    - [x] Preserve malformed payloads; fail closed downstream unless authorised
    - [x] Keep append-only admission decisions and transformation-run receipts distinct from acquisition events; bind actual Parquet bytes, code commit, lock environment, actor, clock, and supersession
- [x] Task: Evidence-grade HTTP retrieval receipts
    - [x] Capture original/final URI, redirects, method, status, ETag, Last-Modified, type, encoding, lengths, agent version
    - [x] Never persist credentials or authorization headers
- [x] Task: Phase Verification & Checkpoint
    - [x] Focused unit, property, edge, and acquisition tests passed locally
    - [x] Record evidence; do not claim silver or live ingest complete

### Phase 3c: Rights and retention engine

- [x] Task: Write failing tests for acquisition rights policy ([#167](https://github.com/edithatogo/global-medicines-atlas/issues/167))
    - [x] Assert every acquisition can record licence evidence, retention, redistribution, transformation, attribution, access restriction, review status, and review dates
    - [x] Assert retaining internal provenance is independent of publishing source bytes
    - [x] Assert unresolved, expired, credentialed, and conflicting rights fail closed for publication
    - [x] Assert later revisions can withdraw publication without rewriting earlier snapshots
    - [x] Confirm the intended ImportError / failing tests before implementation
- [x] Task: Implement the machine-readable policy layer
    - [x] Reuse `RightsState`, `publication_contracts`, `DATA_LICENSE.md`, and source-rights receipts; do not invent a parallel licence conclusion
    - [x] Bind optional `rights_policy` on `SourceReceipt` without changing unbound receipt digests
    - [x] Fail closed in `require_publishable_source_bytes` while allowing lawful internal provenance
    - [x] Leave maintainer licence and publication approval as explicit human gates
- [x] Task: Phase Verification & Checkpoint
    - [x] Run focused rights, receipt, and publication tests plus typing
    - [x] Record evidence; do not claim source licences concluded or bytes published

### Phase 3d: Admission-gated analytical projection

- [x] Task: Integrate admission into the Bronze landing lifecycle ([#169](https://github.com/edithatogo/global-medicines-atlas/issues/169))
    - [x] Stage verified bytes and acquisition evidence before admission
    - [x] Persist a landed event followed by an accepted or quarantined decision
    - [x] Permit Parquet, transformation receipts, and OpenLineage only after acceptance
    - [x] Preserve later automated and human decisions as superseding append-only events
    - [x] Gate deterministic regeneration and recovery projection on admission
- [x] Task: Phase Verification & Checkpoint
    - [x] Run focused lifecycle, integrity, recovery, archive, typing, and coverage checks
    - [x] Record evidence without claiming live-source or publication completion

### Phase 3e: Separate Bronze Parquet products

- [x] Task: Split the acquisition manifest from adapter-native source records ([#169](https://github.com/edithatogo/global-medicines-atlas/issues/169))
    - [x] Write failing tests for the mandatory one-row acquisition manifest and optional record-grain product
    - [x] Remove replacement-decoded payload content from generic Parquet projection
    - [x] Preserve adapter-native field names and types with record, acquisition, content, and schema-fingerprint linkage
    - [x] Give each emitted Parquet product its own actual-byte transformation receipt, Iceberg-ready identity, and OpenLineage event
    - [x] Rebuild the two-product layout deterministically while keeping canonical medicine/product normalization in Silver
- [x] Task: Phase Verification & Checkpoint
    - [x] Run focused landing, transformation, lineage, Iceberg, recovery, archive, typing, and coverage checks
    - [x] Record evidence without claiming binary parsing, live-source completion, or Silver implementation

## Phase 4: Iceberg-ready identities and OpenLineage projection

- [x] Task: Write failing tests for Iceberg-ready metadata and OpenLineage ([#169](https://github.com/edithatogo/global-medicines-atlas/issues/169))
    - [x] Assert stable table identities, partitioning, and schemas exist over Parquet
    - [x] Assert an Iceberg REST catalogue can register bronze metadata without pyiceberg in core
    - [x] Assert OpenLineage RunEvents use real field names and split payload vs parquet datasets
    - [x] Assert payload, Parquet, and catalogue datasets stay distinct identities
    - [x] Assert ColumnLineage and Symlinks do not collapse payload into Iceberg
    - [x] Assert temporal identity and reuse disposition appear as facets
    - [x] Confirm the intended failure before implementation
- [x] Task: Implement Iceberg-ready specs and OpenLineage projection
    - [x] Keep Iceberg optional; Python 3.14 core must not import it
    - [x] Do not add Marquez to the default install
- [x] Task: Phase Verification & Checkpoint
    - [x] Run focused tests and typing
    - [x] Record lineage event field names in evidence

## Phase 4b: Scale and performance engineering

Benchmark bronze primitives under a deterministic synthetic scale fixture
before any hot-path rewrite. Python remains orchestration.

- [x] Task: Write failing tests for bronze scale fixtures and budgets
    - [x] Assert CI fixture generation is deterministic and synthetic
    - [x] Assert published budgets validate against schema
    - [x] Assert a custom Rust crate is gated on a hot pure-Python path
    - [x] Confirm the intended failure before implementation
- [x] Task: Implement reproducible bronze scale benchmarks
    - [x] Measure ingestion, hashing, compression, Parquet, receipts, lineage, catalogue, archive inspection, and parsing
    - [x] Rank bottlenecks from measurements before optimizing
    - [x] Evaluate Rust for streaming hashing, archive inspection, parsing, compression, and high-volume validation
    - [x] Keep Python as orchestration; do not add a Rust crate without the wall-share and speedup gates
- [x] Task: Phase Verification & Checkpoint
    - [x] Run focused tests with `uv run --python 3.14.5 pytest tests/test_bronze_scale.py`
    - [x] Record bottleneck ranking and Rust disposition in evidence

### Phase 4d: Scale-aware Iceberg partition planning

- [x] Task: Replace constant and mutable Bronze partition keys with a
  scale-aware policy ([#169](https://github.com/edithatogo/global-medicines-atlas/issues/169))
    - [x] Write failing tests proving small tables are unpartitioned
    - [x] Partition large recurring products by source-release or acquisition month
    - [x] Optionally bucket high-volume source-record identifiers
    - [x] Reject jurisdiction, source, rights, admission, and review state as physical partition keys
    - [x] Preserve transforms through Iceberg REST create-body round trips
- [x] Task: Phase Verification & Checkpoint
    - [x] Run focused landing, Iceberg, lineage, recovery, typing, and coverage checks
    - [x] Record evidence without claiming production-scale tuning or Iceberg deployment

### Phase 4e: OpenLineage custom-facet conformance

- [x] Task: Tighten OpenLineage conformance (`9fde27a`; schemas `804f5ce`; [#169](https://github.com/edithatogo/global-medicines-atlas/issues/169))
    - [x] Commit a JSON Schema for every GMA custom facet before pinning immutable schema URLs
    - [x] Use correctly prefixed custom-facet keys and reject mutable branch schema references
    - [x] Model acquisition and transformation as separate OpenLineage runs
    - [x] Prefer standard Catalog, Dataset Type, and Data Quality Assertions facets
    - [x] Populate data-quality assertions from admission and integrity validation results
- [x] Task: Phase Verification & Checkpoint
    - [x] Run focused lineage, landing, recovery, scale, schema, typing, and coverage checks
    - [x] Record immutable schema revision and conformance evidence
- [x] Task: Review Fixes (`b3285c8`)
    - [x] Reject non-UUID OpenLineage run IDs and mismatched or non-accepted admissions
    - [x] Reconcile immutable schema URLs after rebasing onto merged PR #201
    - [x] Raise changed-line coverage for the OpenLineage projection to 100%
- [x] Task: Hosted CI Repair (`cc0dd18`)
    - [x] Assign the new conformance test module to the exhaustive Test-Goblin unit inventory
    - [x] Revalidate all 154 test modules and the focused harness/conformance tests

### Phase 4f: Durable payload storage and sensitivity contracts

- [x] Task: Add durable-storage and independent sensitivity contracts ([#169](https://github.com/edithatogo/global-medicines-atlas/issues/169))
    - [x] Write failing local/object-store, immutability, replication, inventory, restore, RPO/RTO, sensitivity, publication, schema, and landing tests
    - [x] Route authoritative payload persistence through a local-development or durable-object-storage abstraction
    - [x] Require versioning or Object Lock/WORM, independent replication, checksum inventory cadence, restore rehearsal cadence, and explicit RPO/RTO for durable operation
    - [x] Keep rights, personal-data sensitivity, and publication disposition independent and fail closed for publication
    - [x] Record Iceberg REST/v3, DuckLake, lakeFS, Merkle manifests, Delta/Hudi, graph, vector, OMOP, semantic normalization, and Rust terminology as non-blocking later experiments
- [x] Task: Phase Verification & Checkpoint
    - [x] Run focused storage, receipt, landing, recovery, schema, typing, and coverage checks
    - [x] Record repository evidence without claiming a deployed object store, production RPO/RTO qualification, external publication, or Bronze source completeness
- [x] Task: Review Fixes (`5d2ad1f`, `7012859`)
    - [x] Preserve legacy SourceReceipt and acquisition-event canonical identities while binding sensitivity on new landings
    - [x] Keep repeated and recovery landings append-only and deterministic
    - [x] Reject hostile payload suffixes, unverified object writes, and same-bucket replica claims
    - [x] Remove duplicate negative-test scaffolding introduced during concurrent branch reconciliation

### Phase 4c: Reproducibility and disaster recovery

- [x] Task: Write failing tests for bronze reconstruction ([#169](https://github.com/edithatogo/global-medicines-atlas/issues/169), parent [#167](https://github.com/edithatogo/global-medicines-atlas/issues/167))
    - [x] Assert clean-room rebuild from payloads and receipts only
    - [x] Assert DuckDB/LanceDB loss does not block reconstruction
    - [x] Assert catalogue and Parquet deletion regenerate without new acquisition IDs
    - [x] Assert interrupted acquisition fails closed then resumes
    - [x] Assert partial storage loss, duplicate retrieval, and code rollback keep payloads
    - [x] Confirm the intended failure before implementation
- [x] Task: Reconstruct metadata, Parquet, and catalogue from immutable truth
    - [x] Treat Hugging Face as non-authoritative; local payload plus receipt is truth
    - [x] Emit compact machine-verifiable recovery evidence
- [x] Task: Phase Verification & Checkpoint
    - [x] Run focused recovery tests and typing
    - [x] Record recovery evidence; do not claim production disaster recovery

## Phase 5: Public ingest and governed-fixture landing

- [x] Task: Write failing tests for in-scope bronze ingest (`53b2671`; [#170](https://github.com/edithatogo/global-medicines-atlas/issues/170))
    - [x] Assert each in-scope public/no-credential source can land raw bytes or has an explicit non-completion blocker
    - [x] Assert already-governed fixtures land as bronze without becoming canonical silver
    - [x] Assert credentialed sources cannot land through this path
    - [x] Assert credentials and restricted bytes are never persisted
    - [x] Assert Drugs@FDA ingest runs the reuse gate first
    - [x] Confirm the intended failure before implementation
- [x] Task: Make source-family landing the dominant generated workstream (`ddc1ecb`)
    - [x] Write failing factory, state-exhaustiveness, override-evidence, schema, and generated-queue contracts first
    - [x] Generate standardized configurations for static files, archives, paginated REST APIs, regulator search exports, document collections, and reproducible manual exports
    - [x] Resolve all 172 catalogue sources to exactly one state without persisting credentials or generating Silver transformations
    - [x] Generate the versioned JSON Schema, machine-readable queue, and Conductor Markdown projection from catalogue plus sparse overrides
    - [x] Preserve source-specific rights and credential gates; blockers are work items, not landing evidence
    - Current generated state is 16 landed-and-evidenced, 45 rights-blocked,
      18 credentialed-and-excluded, and 93 manual-only. Temporary failure,
      reused-source, and genuinely-not-yet-implemented states remain explicit
      zero-count categories until supported by evidence.
- [~] Task: Implement public ingest and fixture landing for current scope
    - [x] Use existing untrusted acquisition, admission, and first-cohort fixture contracts
    - [x] Inspect truncated downloads, hostile ZIP/tar, decompression bombs, path traversal, MIME mismatch, malformed XML/JSON/CSV, schema poisoning, collisions, source mutation, replays, checksum mismatch, and hostile filenames; land bytes; quarantine processing; keep forensic receipts
    - [x] Land Medsafe, PHARMAC, ARTG, PBS, DPD/NOC, MHRA/NICE, EMA/Union Register, PMDA/NHI, Drugs@FDA, and CMS Part D fixtures (`53b2671`)
    - [x] Leave NZULM bulk, NZHTS, AMT, embargoed PBS, dm+d/TRUD, EMA PMS, SPOR, and live RxNorm payloads excluded
    - [x] Remove the rights-unresolved `vendor/nzmedicines` snapshot from the current tree and replace its executable qualification dependency with a minimal first-party synthetic FHIR bundle; retain historical inventory metadata and keep NZULM/NZMT coverage unqualified
    - [ ] Complete source-specific rights receipts and live landing evidence for the remaining 136 public/no-credential sources; a catalogue blocker is not landing completion
        - [x] Implement and exercise the Union Register JSON acquisition, source-record projection, clean-room recovery, and private archive machinery against a representative corpus; keep live acquisition disabled pending the maintainer licence decision
        - [x] Record the maintainer's internal-only Union Register licence decision, acquire the official 2026-08-17 JSON snapshot, exercise Bronze and clean-room recovery over all 6,440 source-native records, and verify the private archive checksum; public release remains prohibited
        - [x] Review fixes: register the receipt-backed JSON parser and live-receipt capability in the source capability census (`d386a66`)
        - [x] Review fixes: bind the committed live qualification into stable-v1 measured coverage with fail-closed identity, recovery, archive-checksum, and Parquet-parity verification (`68c07c9`)
        - [x] Review fixes: reconcile the all-prompt audit assertion with the single receipt-backed live source and re-run the affected branch-coverage suite (`8a911f9`)
        - [x] Review fixes: cover catalog identity, source identity, and quantitative live-receipt failure edges required by the protected patch-coverage gate (`c64d3bf`)
        - [x] Generate a fail-closed review packet for all 20 U.S. sources from official FDA, openFDA, CMS, NLM, and NCATS policy surfaces; retain maintainer licensing, acquisition, and publication gates
        - [x] Record the maintainer's bounded internal-only U.S. licensing decision: five scoped openFDA candidates and eight FDA government-policy candidates may be acquired; seven CMS/NLM/NCATS terms gaps remain catalogue-only; public release remains prohibited
        - [x] Acquire all 13 authorized current-source payloads through the four-surface reuse gate and archive them locally without external publication
        - [x] Exercise immutable landing, rights-bound receipts, append-only admission, accepted-only Parquet/OpenLineage, and clean-room recovery against the live corpus; 8 acquisitions were accepted and rebuilt while 5 HTML/interactive payloads were preserved and quarantined
        - [x] Produce adapter-native Bronze records for the five bounded openFDA JSON canaries and the accepted Drugs@FDA, NSDE, and Orange Book archives; regenerate all eight record products byte-for-byte from immutable payloads and receipts
        - [x] Reconcile prompt 19 as the first live-complete acquisition prompt: the authoritative FDA NSDE comprehensive file and bounded openFDA NSDE projection are both live-qualified; keep Orange Book and other historical families incomplete
        - [x] Inventory the bounded official Orange Book history surfaces without payload retrieval and add a fail-closed maintainer authorization contract; do not equate current ZIP, current PDFs, monthly change pages, and the legacy FDA archive
        - [ ] Acquire complete historical releases for the applicable FDA source families; the bounded canaries and current snapshots do not complete prompt-level coverage
- [x] Task: Review Fixes for bounded U.S. live acquisition (`9a7dc7b`)
    - [x] Prevent bound GET/HEAD requests from gaining a chunked request body and skip compressed-wire Content-Length comparisons against decoded bytes
    - [x] Add authorization drift, fault isolation, excluded-content, private-archive, and transport regression tests; targeted branch coverage reached 93%
    - [x] Reconcile the completion audit to 5 live-qualified openFDA sources without claiming any completed acquisition prompt
- [x] Task: Review Fixes for U.S. source-record projection (`373f5e1`, `9749380`)
    - [x] Fault-isolate source-record parsing so one schema drift cannot stop the authorized acquisition batch or clean-room recovery
    - [x] Exercise malformed objects, technical-column collisions, alternate encoding, blank and short rows, header failures, fallback identities, and media mismatch
    - [x] Raise `us_source_records.py` changed-line coverage to 100% without weakening the Codecov patch gate
- [x] Task: CI repair for NSDE prompt qualification (`a575926`)
    - [x] Apply the repository-wide Ruff formatter to the new qualification assertion
    - [x] Re-run formatting, lint, `ty`, context, ecosystem, and JavaScript-style routine gates locally
- [x] Task: Review fixes for Orange Book historical planning (`87264e8`)
    - [x] Require both maintainer authorization and a complete exact-release inventory before any payload GET can be emitted
    - [x] Validate official documentation hosts independently from release-surface hosts
    - [x] Exercise authorization-only bypass, false completeness, and host-drift negative controls
- [x] Task: Phase Verification & Checkpoint
    - [x] Run focused, integration, and source-boundary tests
    - [x] Measure completeness with S-012 denominators; missing coverage is not negative evidence
    - PR #189 merged from exact head `8ced444` as `ffc5f60` after all 29
      protected checks, including Codecov patch coverage, passed. The
      checkpoint qualifies 17 fixture acquisitions across 16 source IDs and
      measures 136 remaining sources without observable landing evidence; it
      does not complete the partially implemented Phase 5 task.

## Phase 6: Hugging Face archive boundary, regeneration, and completion evidence

- [x] Task: Write failing tests for archive boundary and regeneration ([#171](https://github.com/edithatogo/global-medicines-atlas/issues/171))
    - [x] Assert Hugging Face is an output/archive boundary and not an ingest origin
    - [x] Assert repository payloads and receipts remain evidentiary truth
    - [x] Assert deterministic regeneration from receipts and fixtures
    - [x] Assert restricted payloads cannot enter a public archive package
    - [x] Confirm the intended failure before implementation
- [x] Task: Bind the Hugging Face archive boundary without duplicating sibling archival work
    - [x] Reuse the sibling Hugging Face public-data archival path when it has landed
    - [x] Do not publish source-derived payloads without the rights gate
- [x] Task: Exercise and archive the governed Bronze acquisition corpus (`bbfb76e`)
    - [x] Assess all 172 catalogue entries through the exhaustive landing queue
    - [x] Run reuse, immutable landing, admission, Parquet, OpenLineage, and clean-room recovery over all 17 governed acquisitions for 16 sources
    - [x] Emit a 419-entry tar archive, machine-readable manifest, and verified SHA-256 checksum without claiming live-source coverage
    - [x] Upload the exercised corpus as a GitHub Actions artifact; require an explicit `publish=true` dispatch for external Hugging Face publication
    - PR #191 merged as `d2b9237` after all 31 checks passed. Manual
      `publish=false` dispatch 32341782680 on merged `main` uploaded artifact
      9396593978; its 419-entry tar verified as
      `26ca3ee27ba645f2e3ce6b4fba6681709858203916fccc8366d4023e92c1b212`.
      The run exercised 17 fixture acquisitions across 16 source IDs and did
      not perform external publication or claim live-source coverage.
- [x] Task: Record bronze-completion evidence for current scope
    - [x] Update this track's evidence ledger with observable tests, coverage, and exclusions
    - [x] Leave silver/gold/platinum unimplemented
- [x] Task: Phase Verification & Checkpoint
    - [x] Run focused tests then `uv run python scripts/test_goblin.py full` where the platform permits
    - [x] Open a scoped `codex/` pull request, wait for required checks, repair, and merge
    - [x] Classify unresolved Hugging Face publication as an external gate, never as bronze source-of-truth
    - PR #189 preserved repository payloads and receipts as evidentiary truth,
      kept fixture evidence distinct from live source evidence, and left any
      source-derived external publication behind source-specific rights and
      maintainer approval gates.

## Source expansion program (WHO, Africa, FDA, EMA, utilisation)

Inventory for bronze prompts 1-36 shares one registry, one reuse-gate
contract, and one coverage-reconciliation finish. Live ingest is not claimed
for credentialed or rights-unresolved sources.

- [x] Task: Register tracks 1-36, extend `medicine_source_catalog.json`, and emit derived coverage matrices plus a versioned source index
    - [x] Reuse gate remains mandatory before acquire
    - [x] African source-coverage matrix is a derived catalogue artefact
    - [x] Hugging Face stays an archive boundary; new FDA/EMA rows are not auto-archived
    - [x] Record blockers honestly; missing coverage is not negative evidence
    - [x] Generate a schema-validated completion audit joining every numbered prompt to its exact queue and measured live-evidence state
    - [x] Keep fixture, catalogue, and archive evidence from satisfying any live-acquisition completion claim
- [x] Task: Exercise authorized FDA Orange Book historical acquisition and private archiving
    - [x] Bind the maintainer's Orange Book-only decision to an internal-retention authorization that prohibits public release and external publication
    - [x] Discover 259 exact current and historical release URLs from the approved FDA and FDA Archive-It surfaces
    - [x] Exercise reuse, immutable acquisition, receipts, rights binding, admission, source-faithful Parquet, clean-room recovery, private tar archiving, and SHA-256 verification
    - [x] Preserve 169 unique release payloads across three bounded passes; record 90 Archive-It HTTP 429 outcomes as temporary unavailability
    - [x] Project 73,239 current structured-ZIP rows without converting therapeutic-equivalence codes into clinical substitutability claims
    - [x] Reconcile the generated source queue and prompt audit from `rights_blocked` to `temporarily_unavailable` without marking Prompt 16 complete
- [ ] Task: Complete the FDA Orange Book versioned family (Prompt 16)
    - [x] Retry the exact FDA Archive-It releases under a respectful failure-receipt schedule; after six bounded passes, retain an explicit unavailable disposition rather than continuing unchanged retries
    - [x] Checksum-verify the fourth, fifth, and sixth private archives and clean-room reconstruction evidence without committing source bytes
    - [x] Retain an explicit unavailable disposition because the official surfaces still do not establish a complete inventory of prior structured ZIP releases and historical annual editions
    - [ ] Keep historical completeness, coverage, public release, and external publication fail closed until separately evidenced and approved
- [x] Task: Complete the current FDA NDC Directory family (Prompt 17)
    - [x] Resolve and acquire the finished, unfinished, compounder, excluded, and complete openFDA current bulk surfaces under the approved internal-only U.S. cohort
    - [x] Preserve immutable ZIP payloads, source-native TXT/XLS aliases, product/package grain, receipts, rights, admission, and temporal identity
    - [x] Project and clean-room reconstruct 1,122,796 source-native rows across five accepted release products
    - [x] Create and verify the 403,507,200-byte private TAR with SHA-256 `df73bb27c0e9f10881631a267f1b1a3be55bae0605431d80f168ba6ea0fa75f1`
    - [x] Reconcile Prompt 17 as live complete while preserving the invariant that NDC listing does not establish FDA approval
    - [x] Keep public release, external publication, and historical daily-snapshot coverage outside this qualification
- [x] Task: Prepare fail-closed GSRS/UNII rights and release preflight (Prompt 18)
    - [x] Refresh the official GSRS licensing, openFDA UNII, and precisionFDA archive evidence without acquiring dataset payloads
    - [x] Verify the public FDA archive exposes 68 paired UNII data and name releases from 2014-01-25 through 2026-08-04
    - [x] Add an executable inventory parser that rejects missing pairs, release-count drift, date drift, and non-official hosts
    - [x] Keep acquisition, retention, public release, and external publication fail closed until the maintainer records a source-specific decision
- [ ] Task: Acquire and archive the complete approved GSRS/UNII family (Prompt 18)
    - [ ] Bind the maintainer's source-specific licensing decision to the exact authorization
    - [ ] Acquire every authorized paired dated release without committing source bytes
    - [ ] Exercise immutable landing, rights receipts, Bronze admission, source-faithful Parquet, clean-room recovery, private archiving, and checksum verification
    - [ ] Preserve UNII, names, synonyms, substance types, and source relationships without treating terminology evidence as canonical medicine identity or regulatory approval
    - [ ] Keep any public release and external publication separately gated
- [x] Task: Implement complete FDA AERS/FAERS quarterly acquisition machinery (Prompt 12)
    - [x] Lock the official ASCII release inventory to 90 contiguous quarters from 2004-Q1 through 2026-Q2 under the approved internal-only U.S. cohort
    - [x] Acquire large immutable releases through atomic, bounded, retry-limited, content-range-verified downloads without following redirects
    - [x] Preserve demographic, drug, indication, outcome, reaction, reporter, therapy, statistics, size, and deleted-case tables without deduplication, identity collapse, medicine normalization, or causality inference
    - [x] Exercise immutable landing, rights-bound receipts, Bronze admission, source-faithful Parquet, clean-room reconstruction, byte-identical product checks, and private archive generation in repository tests
    - [x] Keep public release and external publication prohibited; commit no FAERS source bytes
- [x] Task: Qualify the complete live FDA AERS/FAERS quarterly corpus (Prompt 12)
    - [x] Acquire and admit every authorized quarter from the official release index
    - [x] Reconstruct every source-record product from immutable evidentiary truth and verify byte-identical Parquet pairs
    - [x] Create and checksum-verify the private archive, then reconcile Prompt 12 only from observed complete evidence
- [x] Task: Acquire current FDA enforcement and recall-notice surfaces (Prompt 13 partial)
    - [x] Resolve the official openFDA download inventory and acquire its complete current drug-enforcement bulk partition
    - [x] Acquire the distinct current FDA recall-notice XLSX and both official documentation surfaces under the approved internal-only U.S. cohort
    - [x] Preserve immutable payloads and receipts, project 17,876 source-native enforcement rows, and reconstruct the accepted Bronze products in a clean room
    - [x] Verify the source-record Parquet byte-for-byte and create the checksum-verified 23,582,720-byte private archive
    - [x] Record an explicit overlap contract that performs no automatic linkage or silent deduplication
    - [x] Keep Prompt 13, historical notice coverage, public release, and external publication fail closed
- [x] Task: Complete the FDA recall/enforcement family with an explicit historical-notice disposition (Prompt 13)
    - [x] Archive the FDA live archive-policy page and its immutable legacy recall-index snapshot alongside the current notice workbook
    - [x] Record that FDA delegates older pages across multiple archive services and publishes no single complete historical announcement inventory
    - [x] Preserve the complete openFDA enforcement export as the structured record corpus and keep announcements as a separate selected-publication provenance
    - [x] Exercise Bronze admission, clean-room recovery, private archive creation, and independent checksum verification without inferring notice-to-event equivalence
    - [x] Reconcile Prompt 13 from both source identities under the explicit disposition; retain historical-announcement completeness, public release, and external publication as unclaimed
- [x] Task: Acquire current FDA drug shortages and monthly list history (Prompt 14 partial)
    - [x] Acquire and project the complete current 1,628-record openFDA drug-shortages export at source-native grain
    - [x] Inventory one monthly official FDA shortage-list capture where available from June 2014 through August 2026
    - [x] Archive all 129 inventoried list snapshots across five bounded, checksum-verified private passes without treating transient archive failures as missing data
    - [x] Reconstruct the admitted current export and verify its source-record Parquet byte-for-byte
    - [x] Preserve current, resolved, discontinued, availability, reason, manufacturer, presentation, NDC, and source-native date fields without medicine normalization
    - [x] Keep Prompt 14, historical detail-page coverage, public release, and external publication fail closed
- [~] Task: Complete FDA drug-shortage history with an explicit detail-archive disposition (Prompt 14)
    - [x] Acquire and archive 35,494 delegated CDX metadata records describing distinct historical detail-page payload captures; do not acquire the detail payloads
    - [x] Retain all 129 monthly source lists as a candidate temporal shortage-state corpus
    - [x] Recover three transient monthly replay failures in a bounded retry with two content-preserving replay overrides
    - [x] Record that no complete historical detail-page denominator was identified in the reviewed official surfaces; do not relabel an unbounded delegated crawl as complete source coverage
    - [ ] Obtain the maintainer's explicit scope disposition before treating monthly lists as the qualified temporal corpus or reconciling Prompt 14
    - [x] Keep detail-page completeness, public release, and external publication unclaimed
- [x] Task: Acquire the complete public FDA REMS family (Prompt 15)
    - [x] Acquire all four official historical relational CSV surfaces and preserve 3,112 source-native program, version, product, application, status, requirement and date records
    - [x] Inventory and archive all 72 current REMS detail pages and 827 of 829 linked FDA-hosted PDF documents
    - [x] Retain explicit HTTP 404 failure receipts for the two broken official document links rather than inventing unavailable bytes
    - [x] Reconstruct all four admitted source-record products and verify their Parquet bytes exactly
    - [x] Create and checksum-verify the 3,927,029,760-byte private archive
    - [x] Keep REMS distinct from approval and pharmacovigilance, preserve the FDA historical-status warning, and keep public redistribution/release/publication fail closed
- [x] Task: Acquire the discontinued NHS NICE-appraised medicines utilisation series (Prompt 29)
    - [x] Resolve the official historic corpus to four releases covering 2008 through 2012
    - [x] Lock release-specific methodology, denominator, amendment, and correction boundaries
    - [x] Keep the successor Innovation Scorecard out of the historic corpus
    - [x] Obtain the maintainer's source-specific licensing decision before payload acquisition
    - [x] Exercise immutable landing, receipt, acquisition-manifest Bronze projection, clean-room recovery, and private archive verification
    - [x] Keep public release and external publication separately gated
- [~] Task: Acquire the Netherlands GIP medicine utilisation corpus (Prompt 32)
    - [x] Resolve the official corpus to 28 Farmacie and Add-on CSV releases through 2025
    - [x] Bind stable source titles while treating rotating service download keys as ephemeral transport metadata
    - [x] Preserve rolling-table, annual age/sex, ATC, version, population, source, and VAT-method boundaries
    - [ ] Obtain the maintainer's source-specific licensing decision before payload acquisition
    - [ ] Exercise immutable landing, receipts, source-faithful Bronze projection, clean-room recovery, and private archive verification
    - [ ] Keep public release and external publication separately gated
    - [x] Review fixes: make direct `GIPRelease` test construction satisfy the typed `date` contract (`945b12f`, `fc11f61`); focused tests, Ruff, and BasedPyright pass
- [~] Task: Acquire England OpenPrescribing utilisation views (Prompt 30)
    - [x] Resolve the six documented spending, medicine-reference, and organisation-reference API identities
    - [x] Bind the current official API documentation commit and its Open Government Licence source statement
    - [x] Select receipt-bound explicit date partitions instead of treating rolling five-year API views as static complete releases
    - [ ] Obtain the maintainer's source-specific licensing decision before payload acquisition
    - [ ] Exercise immutable landing, receipts, source-faithful Bronze projection, clean-room recovery, and private archive verification
    - [ ] Keep public release and external publication separately gated
- [~] Task: Acquire U.S. CMS Medicare Part D utilisation data (Prompt 31)
    - [x] Resolve the official corpus to 30 quarterly formulary ZIP releases through Q2 2026 and the three-resource 2024 annual spending surface
    - [x] Replace the generic CMS terms gap with the dataset-specific government-works licence record and formulary Agreement for Use
    - [x] Preserve plan/population exclusions, gross-versus-net spending, preliminary-versus-final, suppression, and source-native measure boundaries
    - [ ] Obtain the maintainer's source-specific acceptance before payload acquisition and retention
    - [ ] Exercise immutable landing, receipts, source-faithful Bronze projection, clean-room recovery, and private archive verification
    - [ ] Keep public release and external publication separately gated
- [~] Task: Acquire Nordic medicine utilisation aggregates (Prompt 33)
    - [x] Correct the three independent public access states without treating aggregate outputs as person-level registry access
    - [x] Lock Denmark's 1996–2025 metadata-only bulk inventory and distinguish it from interactive utilisation result exports
    - [x] Bound Norway's historic anonymous report surface to data through 2020 without claiming current successor coverage
    - [x] Lock Sweden's current annual and monthly aggregate query dimensions, years, measures, and cell/ATC limits
    - [x] Record the Denmark attribution terms, historic Norway attribution requirement, and Sweden CC0/API guidance
    - [ ] Obtain independent maintainer source-specific decisions before payload acquisition and retention
    - [ ] Exercise immutable landing, receipts, source-faithful Bronze projection, clean-room recovery, and private archive verification for each approved source
    - [ ] Keep public release and external publication separately gated
- [~] Task: Acquire additional public utilisation sources (Prompt 34)
    - [x] Correct Japan NDB aggregate and CIHI NHEX public access states without weakening microdata or broader licensed-source boundaries
    - [x] Lock the Open Medic 2014–2025 metadata inventory, Licence Ouverte identity, and repeated upstream payload-delivery failure
    - [x] Lock Japan's sixth NDB prefectural prescribing Tableau surface without claiming an official bulk download
    - [x] Lock CIHI's 2025 Series G drug-expenditure and open-data workbooks and HSE's 2024 PCRS claims-and-payments report
    - [x] Reconcile the generated Bronze queue and completion audit without treating source metadata as live utilisation coverage
    - [ ] Obtain independent source-specific decisions for Japan, Canada, and Ireland before payload acquisition and retention
    - [x] Retry the already-authorized Open Medic payload under its bounded failure-receipt schedule; all 12 annual archives were acquired, checksum verified, published under the approved Etalab-2.0 decision, and anonymously restored
    - [x] Implement the source-faithful Open Medic ZIP/CSV projection and exercise the oldest 2014 and newest 2025 schemas against the immutable public revision; retain all source values as strings and add only release-year and row-number linkage fields
    - [ ] Exercise immutable landing, receipts, source-faithful Bronze projection, clean-room recovery, and archive verification for each acquired source
    - [ ] Keep cross-country comparability and unapproved publication fail closed
- [~] Task: Expand authoritative global pharmacovigilance sources (Prompt 35)
    - [x] Preserve VigiBase as subscription-restricted and independently excluded from public-source Bronze claims
    - [x] Qualify the current MHRA Yellow Card, TGA DAEN, Canada Vigilance, and PMDA public surfaces from official metadata
    - [x] Preserve the Canada Vigilance documentation discrepancy: the page says 11 files while listing 13 named tables
    - [x] Correct stale endpoints and formats without treating metadata qualification as implemented ingestion or Bronze coverage
    - [ ] Obtain independent source-specific decisions before payload acquisition and retention
    - [ ] Exercise immutable landing, receipts, source-faithful Bronze projection, clean-room recovery, and archive verification for each acquired source
    - [ ] Keep causality, incidence, public release, and external publication claims fail closed
- [x] Task: Reconcile final measured source coverage (Prompt 36)
    - [x] Produce reproducible matrices by jurisdiction, authority, and ten independent evidence facets
    - [x] Report catalogued, fixture-qualified, and durable live-qualified counts independently
    - [x] Preserve incomplete coverage, missing-not-negative-evidence, and no-external-publication boundaries
    - [x] Carry forward only existing high-value gap candidates; do not invent a new track without new authority or materially new source evidence

## Phase 6: B0/B1/B2 Internal Bronze Strata Contract

- [x] Task: Formalize the three-strata Bronze authority boundary ([#275](https://github.com/edithatogo/global-medicines-atlas/issues/275))
    - [x] Inspect current `main`, active Bronze tracks and issues, and recently merged Bronze work without disturbing concurrent work
    - [x] Write failing executable contract tests for B0, B1, B2, projections, and later-medallion boundaries
    - [x] Confirm the intended failure before implementation (`AGENTS.md: missing B0 Source Index`)
    - [x] Define B0 Source Index, B1 Acquisition Metadata, and B2 Raw Evidence consistently in product, design, requirements, glossary, and track specification
    - [x] Add Mermaid diagrams that distinguish internal Bronze strata from Silver, Gold, and Platinum
    - [x] Run focused tests, context validation, formatting, linting, typing, and the full Test-Goblin profile; retain the exact-Python and local-load observations for hosted resolution
    - [x] Record PR [#276](https://github.com/edithatogo/global-medicines-atlas/pull/276) head `97b4ecc1d86d57abc9c48175b35a84fea4f49e36`, 37 passing hosted checks, and merged SHA `3d3f419baec4da32b3db6319f996b8853ca5ab8e` without changing acquisition IDs, digests, receipts, or evidence semantics

### Phase Verification & Checkpoint

- [x] Executable contract tests prove the normative phrases and authority boundaries across all required documents
- [x] Context validation recognizes the glossary as required project context
- [x] Required hosted checks pass at the exact pull-request head before merge
- [x] Review confirms documentation-and-contract-only scope and no source, receipt, digest, or acquisition-identity mutation

## Phase 7: Deterministic B0 Source Index Layer

- [x] Task: Implement the B0 Source Index projection ([#281](https://github.com/edithatogo/global-medicines-atlas/issues/281))
    - [x] Audit the canonical source catalogue, schema/model, census, coverage index, landing factory and queue, archival inventory, Hugging Face references, Conductor state, issues, and recent Bronze merges
    - [x] Reuse `medicine_source_catalog.json` and the landing queue as authorities; do not create a parallel source registry
    - [x] Write failing tests first and confirm the missing-module failure before implementation
    - [x] Implement schema-validated B0 rows with stable source IDs and independent discovery, acquisition-evidence, landing, rights, and qualification states
    - [x] Generate deterministic snapshot identity, JSON, Parquet, human-readable documentation, and citation/dataset metadata without external publication
    - [x] Run focused and affected tests, deterministic regeneration, context validation, formatting, linting, strict typing, and the full Test-Goblin profile
    - [x] Record PR [#283](https://github.com/edithatogo/global-medicines-atlas/pull/283) head `616f8b20287b58e61a50ac5537f431144960d375`, 37 passing hosted checks, and merged SHA `ccf3daf795898bea122f03a6eff90dd2e5cef1e9` without changing acquisition IDs, content digests, existing receipts, or evidence semantics
- [x] Task: Review Fixes
    - [x] Replace a vacuous qualification-reference assertion with field-for-field projection checks against the canonical catalogue and landing queue
    - [x] Re-run the 222-test affected source-index surface after review

### Phase Verification & Checkpoint

- [x] Every catalogue source occurs once with referential integrity to the landing queue
- [x] Committed JSON, Parquet, schema, documentation, and metadata regenerate deterministically
- [x] Tests enforce indexed, verified, fixture, live, acquired, qualified, coverage, and negative-evidence distinctions
- [x] Required hosted checks pass at the exact pull-request head before merge
- [x] Review confirms no parallel registry, external publication, or mutation of B1/B2 evidence identity

## Phase 8: Deterministic B1 Acquisition Metadata Layer

- [x] Task: Formalize the B1 acquisition metadata authority and query manifest ([#289](https://github.com/edithatogo/global-medicines-atlas/issues/289))
    - [x] Audit the existing `SourceReceipt`, `AcquisitionEvent`, temporal, HTTP, reuse, rights, storage, admission, recovery, Parquet and OpenLineage contracts
    - [x] Reuse the native append-only ledgers and existing acquisition-manifest product; do not create a second receipt system
    - [x] Write failing B1 reconstruction, redaction, identity, rights/admission, binary-reference and deterministic-manifest tests first
    - [x] Confirm the intended missing-module failure before implementation
    - [x] Implement the versioned B1 schema and deterministic one-row-per-event JSON/Parquet projection
    - [x] Reconstruct the query manifest from authoritative receipts, acquisition events, storage receipts and admission records with legacy compatibility
    - [x] Document B1 authority boundaries and update the existing acquisition-manifest implementation
    - [x] Run focused and affected recovery tests, deterministic regeneration, context validation, formatting, linting, strict typing and full Test-Goblin
    - [x] Record PR [#291](https://github.com/edithatogo/global-medicines-atlas/pull/291) head `c4c3ba555edc51802bff513523891e7e365fd7ca`, 37 passing hosted checks, and merged SHA `ce674425e24f5a694e3fb4e37a0664c7bc34131f` without changing existing receipt digests, acquisition IDs or content IDs
- [x] Task: Review Fixes
    - [x] Preserve idempotent admission history when the same acquisition is landed again instead of appending a redundant supersession chain
    - [x] Add a regression contract for stable admission history and byte-identical B1 Parquet on re-landing
    - [x] Record review-fix commit `89955f1a62339b8eca4b969cd27db5475ea4ee98`

### Phase Verification & Checkpoint

- [x] Native receipts and acquisition/admission events remain authoritative and append-only
- [x] Query manifest, OpenLineage and table catalogue objects remain deterministic rebuildable projections
- [x] Repeated identical content keeps distinct acquisition identities and one manifest row per event
- [x] Retrieval locations are redacted and the manifest never contains payload contents
- [x] Required hosted checks pass at the exact pull-request head before merge

## Phase 9: Explicit B2 Raw Evidence and Native Projection Boundary

- [~] Task: Formalize B2 raw evidence and split source-native projections ([#295](https://github.com/edithatogo/global-medicines-atlas/issues/295))
    - [x] Inspect existing content-addressed storage, landing, recovery, archive, receipt, fixture, and Parquet contracts
    - [x] Write failing B2 tests before implementation
    - [x] Add explicit retained, external-reference-only, and blocked B2 states without changing historical identities
    - [x] Generate deterministic archive-member and document manifests without decoding raw bytes
    - [x] Gate optional source-native records from Silver normalization and lossy binary decoding
    - [x] Rebuild B2 references and native projections after deleting Parquet/catalogue outputs
    - [x] Run focused, recovery, archive-safety, integrity, fixture, context, formatting, lint, and typing checks
    - [ ] Record exact pull-request head, hosted checks, and merged SHA without changing existing receipts, acquisition IDs, content IDs, or raw bytes

### Phase Verification & Checkpoint

- [x] B2 byte/reference state is explicit and content-addressed when retained
- [x] B1 contains references and metadata only; source-native records are separate rebuildable projections
- [x] ZIP/tar, document, opaque-binary, identity, and projection-boundary tests pass
- [ ] Required hosted checks pass at the exact pull-request head before merge
