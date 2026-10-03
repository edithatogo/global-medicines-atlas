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
    - [ ] Complete source-specific rights receipts and live landing evidence for the remaining 119 in-scope public/no-credential sources; a catalogue or acquisition-audit status alone is not accepted Bronze landing evidence
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
            - The 2026-09-28 bounded refresh accepted the newly indexed August 2026 monthly release; 140/260 releases are accepted, 16 are quarantined, and 104 Archive-It URLs fail. Historical coverage remains incomplete and the refresh is internal-only; do not repeat until an official inventory or Archive-It availability change.
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
- [x] Task: Complete the FDA Orange Book versioned family (Prompt 16)
    - [x] Retry the exact FDA Archive-It releases under a respectful failure-receipt schedule; after six bounded passes, retain an explicit unavailable disposition rather than continuing unchanged retries
    - [x] Checksum-verify the fourth, fifth, and sixth private archives and clean-room reconstruction evidence without committing source bytes
    - [x] Retain an explicit unavailable disposition because the official surfaces still do not establish a complete inventory of prior structured ZIP releases and historical annual editions
    - [x] Keep historical completeness, coverage, public release, and external publication fail closed until separately evidenced and approved
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
- [x] Task: Acquire and archive the complete approved GSRS/UNII family (Prompt 18)
    - [x] Bind the maintainer's source-specific licensing decision to the exact authorization; private acquisition and retention approved 2026-08-22, public and external publication prohibited
    - [x] Acquire every authorized paired dated release without committing source bytes; all 68 releases and 136 paired payloads completed on 2026-08-26
    - [x] Add the private acquisition, receipt, Bronze landing, and checksum-bound archive runner; execution evidence remains pending successful transfer
    - [x] Preserve UNII, names, synonyms, substance types, and source relationships in immutable source-native payloads without treating terminology evidence as canonical medicine identity or regulatory approval
    - [x] Keep any public release and external publication separately gated
    - Receipt: `quality/qualifications/gsrs-unii-acquisition-success-20260826.json`; 1,297,588,027 source bytes, private archive `78ebcb813f1d4c9e3231c8dad68d73d863e896962c4bec353de1c52a4717b517`, and 136/136 digest-matching stream restores
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
- [x] Task: Complete FDA drug-shortage history with an explicit detail-archive disposition (Prompt 14)
    - [x] Acquire and archive 35,494 delegated CDX metadata records describing distinct historical detail-page payload captures; do not acquire the detail payloads
    - [x] Retain all 129 monthly source lists as the qualified temporal shortage-state corpus
    - [x] Recover three transient monthly replay failures in a bounded retry with two content-preserving replay overrides
    - [x] Record that no complete historical detail-page denominator was identified in the reviewed official surfaces; do not relabel an unbounded delegated crawl as complete source coverage
    - [x] Bind the maintainer's explicit 2026-08-26 approval to treat the monthly lists as the qualified temporal corpus and reconcile Prompt 14
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
- [x] Task: Acquire the Netherlands GIP medicine utilisation corpus (Prompt 32)
    - [x] Resolve the official corpus to 28 Farmacie and Add-on CSV releases through 2025
    - [x] Bind stable source titles while treating rotating service download keys as ephemeral transport metadata
    - [x] Preserve rolling-table, annual age/sex, ATC, version, population, source, and VAT-method boundaries
    - [x] Reconcile the existing source-specific approved-public decision bound to the exact 28-release title-set hash before payload acquisition
    - [x] Exercise immutable landing, receipts, 217,135-row source-faithful Bronze projection, clean-room recovery, and private archive verification across all 28 releases
    - [x] Publish the exact approved CC0 corpus at immutable Hugging Face revision `4e6395ee5217b0fb140dd7942f67b032039e7bbf` and anonymously restore all 28 source CSV digests
    - [x] Review fixes: make direct `GIPRelease` test construction satisfy the typed `date` contract (`945b12f`, `fc11f61`); focused tests, Ruff, and BasedPyright pass
- [~] Task: Acquire England OpenPrescribing utilisation views (Prompt 30)
    - [x] Resolve the six documented spending, medicine-reference, and organisation-reference API identities
    - [x] Bind the current official API documentation commit and its Open Government Licence source statement
    - [x] Select receipt-bound explicit date partitions instead of treating rolling five-year API views as static complete releases
    - [x] Bind the maintainer's 2026-08-26 approved-public Option B decision to successfully retrieved, receipt-bound API v1 partitions under the OGL
    - [x] Identify the provider's official contact route and prepare the supported machine-access request: `openprescribing-access-request.md`
    - [x] Send the request to `feedback@openprescribing.net` from the recommended maintainer account; the automatic acknowledgement and Sent readback are bound in `quality/qualifications/provider-outreach-receipts-20260929.json`. Substantive provider guidance remains pending and the existing source/rights scope is unchanged.
    - [x] Review fix: add a direct artifact contract for the request, plan, and evidence, assign it to Test-Goblin's unit lane, and supersede the unrelated operational-hardening test claim
    - [x] Reconcile PR #580 after merge `cdde51796355265eecdf25bf558f22dc1a6c5bee`; its exact head passed all 37 hosted checks, including Codecov patch coverage. The request is now sent, its automatic acknowledgement is recorded, and substantive provider guidance remains pending; this does not qualify new partitions or change rights.
    - [~] Obtain provider guidance for automated access; do not solve the Cloudflare challenge, widen rights scope, or substitute upstream NHSBSA files
    - [ ] Exercise immutable landing, receipts, source-faithful Bronze projection, clean-room recovery, and private archive verification
    - [x] Permit public release and external publication only for successfully retrieved partitions with OGL/OpenPrescribing attribution; the bounded six-endpoint attempt returned HTTP 403 and published nothing
    - [x] Review fixes: make Open Medic ZIP fixtures byte-deterministic and add opt-in hybrid xdist scheduling that keeps resource-sensitive tests serial (`4721359`, `59d77f4`); 137 affected tests, Ruff, ty, and BasedPyright pass
- [x] Task: Acquire U.S. CMS Medicare Part D utilisation data (Prompt 31)
    - [x] Resolve the official corpus to 30 quarterly formulary ZIP releases through Q2 2026 and the three-resource 2024 annual spending surface
    - [x] Replace the generic CMS terms gap with the dataset-specific government-works licence record and formulary Agreement for Use
    - [x] Preserve plan/population exclusions, gross-versus-net spending, preliminary-versus-final, suppression, and source-native measure boundaries
    - [x] Obtain the maintainer's source-specific acceptance before payload acquisition and retention; approved public for the exact inventory-bound corpus on 2026-08-27
    - [x] Exercise immutable landing, receipts, source-faithful Bronze record projection, clean-room recovery, and anonymous public archive verification
        - [x] Publish and anonymously verify all 33 exact payloads, receipts, and consolidated payload/archive-member manifest Parquet through GitHub Actions at revision `abcff8ebd1f624c4bbb0a87d903b184388c98254`
        - [x] Implement a resumable GitHub Actions projection path over that immutable public revision, with streaming source-string preservation, independent table Parquet, anonymous digest verification, and runner-byte removal
        - [x] Bind all 33 projection shards to the exact raw manifest with a deterministic fail-closed qualifier before the hosted workflow may publish the canonical qualification
        - [x] Review fix: name the raw-field invalidity predicate explicitly and cover every new qualifier statement plus branch without weakening fail-closed validation
        - [x] Deliver the exact-inventory qualifier through PR #415; updated head `ecc3763` passed all 38 protected checks and auto-merged as `26c68f6`
        - [x] Produce and verify source-native formulary and spending record Parquet, then reconcile the receipt-backed landing overrides and canonical completion audit
          - As of 2026-09-01T19:37:26Z, the hosted projection workflow has no
            observed runs. Configuration and a merged qualifier are readiness
            evidence, not execution or publication evidence.
          - The 2026-09-13 hosted attempt ran all 33 shards: three spending
            projections succeeded, but 30 formulary projections failed on
            undecodable high bytes under the assumed UTF-8 codec; final
            qualification was skipped. The corrective projection uses a
            reversible Latin-1 byte mapping for unmarked legacy text and
            UTF-8 only when an explicit BOM is present, records the mapping
            per projection, and adds a one-shard hosted canary before another
            full dispatch. This is a projection choice, not a claim that CMS
            declared the source's character set or that any failed shard is
            qualified.
          - On 2026-09-25, PR #527 passed protected CI and merged; hosted
            canary run `36117860522` projected the selected formulary payload
            into 22 Parquet files covering 433,095,732 source records. Their
            public digest and size metadata matched the receipt anonymously
            at revision `ef0bbb53bb2c88685cddac8830ab7e602fdad664`.
            Full run `36122136607` subsequently published all 33 shards, but
            its finalizer failed before qualification because the job lacked
            checkout and `uv` setup. The 33 retained JSON receipts pass the
            exact-inventory qualifier locally (631 projections,
            11,643,919,491 reported records). A pinned hosted receipt-only
            recovery is required to publish and anonymously verify the full
            qualification; the canary and local check alone do not satisfy
            that gate or the landing audit.
          - Hosted recovery run `36302250649` succeeded on merged PR #528.
            The qualification is anonymously visible at public revision
            `aa176310b5748d471cec2c36955cac36eacb4ba2`: all 33 shards,
            631 Parquet projections, and 11,643,919,491 reported source
            records. Independent readback matched every public Parquet digest
            to the qualification receipt. The source-record projection
            subgate is passed; the committed exact qualification receipt now
            binds both CMS source IDs to approved rights and the immutable raw
            revision. The generated landing queue and Prompt 31 audit report
            both as live-qualified while preserving the formulary fixture
            history and the incomplete broader Bronze program. PR #599
            subsequently reconciled the receipt-bound landing overrides and
            canonical Prompt 31 audit: both exact source IDs are
            `landed_and_evidenced`, `live_acquisition_complete` is true, and
            there are no sources without live evidence or pending Prompt 31
            actions. This closes Prompt 31 only. Part D is not total U.S.
            utilisation, and broader Bronze completeness remains blocked.
    - [x] Keep public release and external publication separately gated; the maintainer approved attributed public release and external publication on 2026-08-27 subject to the CMS Agreement for Use and fail-closed interpretation boundaries
- [x] Task: Review Fixes for CMS Part D public qualification
    - [x] Reconcile the preflight recommendation with the maintainer's exact approved-public decision
    - [x] Require an explicit qualification timestamp so report regeneration is deterministic
    - [x] Stream the deterministic temporary runner archive and reject unexpected clean-room members without loading multi-gigabyte payloads into memory; retain no runner bytes after publication
    - [x] Re-run qualification, clean-room recovery, anonymous public archive verification, and affected validation after all 33 exact payloads completed in hosted run `33233368217`
- [~] Task: Acquire Nordic medicine utilisation aggregates (Prompt 33)
    - [x] Correct the three independent public access states without treating aggregate outputs as person-level registry access
    - [x] Lock Denmark's 1996–2025 metadata-only bulk inventory and distinguish it from interactive utilisation result exports
    - [x] Bound Norway's historic anonymous report surface to data through 2020 without claiming current successor coverage
    - [x] Lock Sweden's current annual and monthly aggregate query dimensions, years, measures, and cell/ATC limits
    - [x] Record the Denmark attribution terms, historic Norway attribution requirement, and Sweden CC0/API guidance
    - [x] Re-verify Sweden's current medicines-statistics scope, CC0 declaration and API attribution guidance against official pages; prepare a bounded decision packet without retrieving result payloads
    - [x] Reconcile Medstat's live query criteria: turnover is supported for primary and hospital sectors, not the Total sector; bind one export to both source-defined strata without deriving a sum
    - [x] Obtain independent maintainer source-specific decisions before payload acquisition and retention (Denmark approved 2026-09-13; Norway approved 2026-10-01; Sweden approved 2026-09-29; all internal-only)
    - [~] Exercise immutable landing, receipts, clean-room recovery, and private archive verification for approved Nordic sources (Norway's bounded 2014–2018 NIPH report is reconciled; Sweden's 2025 aggregate run is reconciled; Denmark remains blocked on its ambiguous export format and provider clarification)
    - [x] Keep public release and external publication separately gated for every Nordic source; the model rejects either authorization flag
- [~] Task: Acquire additional public utilisation sources (Prompt 34)
    - [x] Correct Japan NDB aggregate and CIHI NHEX public access states without weakening microdata or broader licensed-source boundaries
    - [x] Lock the Open Medic 2014–2025 metadata inventory, Licence Ouverte identity, and repeated upstream payload-delivery failure
    - [x] Lock Japan's sixth NDB prefectural prescribing Tableau surface without claiming an official bulk download
    - [x] Lock CIHI's 2025 Series G drug-expenditure and open-data workbooks and HSE's 2024 PCRS claims-and-payments report
    - [x] Reconcile the generated Bronze queue and completion audit without treating source metadata as live utilisation coverage
    - [ ] Obtain independent source-specific decisions for Japan, Canada, and Ireland before payload acquisition and retention
    - [x] Retry the already-authorized Open Medic payload under its bounded failure-receipt schedule; all 12 annual archives were acquired, checksum verified, published under the approved Etalab-2.0 decision, and anonymously restored
    - [x] Implement the source-faithful Open Medic ZIP/CSV projection and exercise the oldest 2014 and newest 2025 schemas against the immutable public revision; retain all source values as strings and add only release-year and row-number linkage fields
    - [x] Exercise immutable landing, receipts, source-faithful Bronze projection, clean-room recovery, and archive verification for each acquired source
    - [ ] Keep cross-country comparability and unapproved publication fail closed
- [x] Task: Review Fixes for all-release Open Medic qualification (`14be890`)
    - [x] Bind the Hugging Face reuse candidate itself to immutable revision `d19f7a66e35c58c557615bffa456856b485b7edc`
    - [x] Use acquisition month for large-table Iceberg partition planning rather than applying a temporal transform to integer `source_release_year`
    - [x] Re-run focused provenance and acquisition tests, strict typing, Conductor integrity, and the accelerated broad suite
    - [x] Confirm all 37 exact-head hosted checks and squash-merge PR #324 as `823262f`
- [x] Task: Reconcile and qualify the split international permissive archive (`1acc10d`)
    - [x] Restore the exact ten-source international archive contract after Open Medic moved to its separate approved repository
    - [x] Verify the immutable public revision and land only source-native or document-safe products supported by the exact manifest
    - [x] Exercise clean-room recovery without treating derived RxNorm identifiers as live source payloads
    - [x] Record fail-closed qualification evidence without claiming complete international coverage or new publication
- [x] Task: Review Fixes for split international archive qualification (`1acc10d`)
    - [x] Make live-receipt evidence scope explicit for receipt-backed landing overrides and reject scope on non-landed states
    - [x] Generate the committed aggregate qualification from the live runner instead of manually transcribing results
    - [x] Preserve eight Latin-1 French delimiter payloads as quarantined B2 evidence rather than weakening UTF-8 inspection
    - [x] Record PR [#326](https://github.com/edithatogo/global-medicines-atlas/pull/326) head `6201559019c0d3d2611cc08987210672f854323a`, 37 passing hosted checks, and merged SHA `19d71f1573b1699101b54494fec2c681e0eec923`
- [x] Task: Qualify the French public archive with an encoding-explicit source parser (`8c3abd3`)
    - [x] Keep generic UTF-8 inspection fail closed and require an explicit source profile before admitting CP1252 tabular text
    - [x] Preserve every unlabeled source field, row order, raw payload byte and acquisition identity in the source-native projection
    - [x] Re-run clean-room recovery and advance only the two receipt-backed French source identities
- [x] Task: Review Fixes for French public Bronze tables (`8c3abd3`)
    - [x] Preserve physical source line numbers when blank tabular rows are skipped
    - [x] Reject unknown codec names before admission and treat lookup failures as fail-closed parse findings
    - [x] Assign the French parser tests to the exhaustive Test-Goblin inventory
    - [x] Record PR [#328](https://github.com/edithatogo/global-medicines-atlas/pull/328) head `ab7682cb1262321df7e277147b4a1ce732b5f595`, 37 passing hosted checks, and merged SHA `10daa783c6acf462059c35c6e2a409f1f990ef7f`
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

## Phase 7: B0/B1/B2 Internal Bronze Strata Contract

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

## Phase 8: Reproducible Manual Acquisition Recipes and Receipts

- [x] Task: Add deterministic, rights- and reuse-gated manual acquisition contracts ([#308](https://github.com/edithatogo/global-medicines-atlas/issues/308))
    - [x] Generate one versioned recipe per current manual-only queue item without duplicating the queue
    - [x] Add receipt schema, redaction, deterministic identity, file hashing, and explicit blocked/unavailable states
    - [x] Provide offline list, bounded-session initialization, and receipt-validation CLI workflow
    - [x] Require pinned discovery snapshots and permitted rights before completion
    - [x] Validate handoff through the ordinary B1/B2 landing adapter contract and record hosted merge evidence
    - [x] Record PR [#309](https://github.com/edithatogo/global-medicines-atlas/pull/309) head `587d253fb6d04cb8d3e64078e1c9eefe919da309`, all required hosted checks green, and merged SHA `a45cb7a2ac6080789c59dd1bc1f75f46096f8191`

## Phase 9: Pinned Reuse Discovery Snapshot

- [x] Task: Bind pre-acquisition reuse decisions to deterministic discovery snapshots ([#302](https://github.com/edithatogo/global-medicines-atlas/issues/302), parent #167)
    - [x] Record required surfaces, queries, revisions, candidate digests, availability, freshness, and snapshot ID
    - [x] Fail closed for stale, skipped, unavailable, or incomplete discovery when choosing `acquire-new`
    - [x] Provide offline refresh/reconstruction, schema, documentation, and contract tests without copying source bytes
    - [x] Record PR [#303](https://github.com/edithatogo/global-medicines-atlas/pull/303) head `bd221add29e89731de48dd63db0f6f9c7c6da10c` and merged SHA `00bc45e7d977b56fd01276dd18e3a6b4d92c9281`, with all 37 required hosted checks and Codecov patch coverage passing

### Phase Verification & Checkpoint

- [x] Snapshot IDs are deterministic and bind query, candidates, tool version, freshness, and all four required surfaces
- [x] Offline refresh and reconstruction distinguish no candidate from unavailable/incomplete or stale discovery
- [x] Existing reuse dispositions and evidence identities remain unchanged; no source bytes were copied
- [x] Required hosted checks pass at the exact pull-request head before merge

## Phase 10: Source-profile-aware Bronze admission

- [x] Task: Add a versioned source-profile admission stage after generic integrity ([#299](https://github.com/edithatogo/global-medicines-atlas/issues/299))
    - [x] Inspect admission, integrity, parser/archive safety, catalogue, adapters, and governed fixtures
    - [x] Write failing object/array/JSONL/CSV/XML/archive/document and profile-mismatch tests first
    - [x] Add bounded profile schema and catalogue/adapter contract
    - [x] Apply generic integrity first, then profile validation without rewriting landed bytes
    - [x] Run focused and affected admission, parser, archive, fixture, context, formatting, lint, and typing checks
    - [x] Record PR [#300](https://github.com/edithatogo/global-medicines-atlas/pull/300) head `6e9752ee8dad0652b90cd40cab058ed9ab84a10b`, 37 passing hosted checks, and merged SHA `8f9cd56b0b155e29ea5ac1d66c10e3099767700d` without changing source bytes, existing receipts, acquisition IDs, or content IDs

### Phase Verification & Checkpoint

- [x] Generic integrity remains authoritative for hostile input and corruption
- [x] Unprofiled JSON arrays are accepted; explicit profile mismatches quarantine or warn
- [x] Profile limits and source-native structure do not convert index or landing into coverage
- [x] Required hosted checks pass at the exact pull-request head before merge
- [x] Review confirms documentation-and-contract-only scope and no source, receipt, digest, or acquisition-identity mutation

## Phase 11: Deterministic B0 Source Index Layer

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

## Phase 12: Deterministic B1 Acquisition Metadata Layer

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

## Phase 13: Explicit B2 Raw Evidence and Native Projection Boundary

- [x] Task: Formalize B2 raw evidence and split source-native projections ([#295](https://github.com/edithatogo/global-medicines-atlas/issues/295))
    - [x] Inspect existing content-addressed storage, landing, recovery, archive, receipt, fixture, and Parquet contracts
    - [x] Write failing B2 tests before implementation
    - [x] Add explicit retained, external-reference-only, and blocked B2 states without changing historical identities
    - [x] Generate deterministic archive-member and document manifests without decoding raw bytes
    - [x] Gate optional source-native records from Silver normalization and lossy binary decoding
    - [x] Rebuild B2 references and native projections after deleting Parquet/catalogue outputs
    - [x] Run focused, recovery, archive-safety, integrity, fixture, context, formatting, lint, and typing checks
    - [x] Record PR [#296](https://github.com/edithatogo/global-medicines-atlas/pull/296) head `dddbbd1f8dd837a32ea83a810a06bca344a6c9a1`, 37 passing hosted checks, and merged SHA `13d2698675eb35a195a7d5fcb54f2355a5b54d6c` without changing existing receipts, acquisition IDs, content IDs, or raw bytes

### Phase Verification & Checkpoint

- [x] B2 byte/reference state is explicit and content-addressed when retained
- [x] B1 contains references and metadata only; source-native records are separate rebuildable projections
- [x] ZIP/tar, document, opaque-binary, identity, and projection-boundary tests pass
- [x] Required hosted checks pass at the exact pull-request head before merge

## Phase 14: End-to-End Three-Strata Qualification

- [x] Task: Qualify the B0/B1/B2 substrate over the complete governed corpus ([#315](https://github.com/edithatogo/global-medicines-atlas/issues/315), parent #170)
    - [x] Inspect source index, acquisition metadata, raw-evidence storage, projections, admission profiles, reuse snapshots, manual recipes, and recovery code
    - [x] Write qualification tests first covering all thirteen required properties
    - [x] Compose existing governed primitives: catalogue indexing, governed fixture landing, B1 reconstruction, B2 record building, delete-and-rebuild recovery
    - [x] Add schema-validated report with exact commit, per-stratum property states, evidence-class counts, migration compatibility, deterministic rebuild, residual risks, blockers, `three_strata_qualified`, and separate `bronze_mature`
    - [x] Keep fixture evidence distinct from live evidence; no new rights conclusions; no identity rewrites
    - [x] Update architecture diagram, maturity model documentation, queue projection verification, and hosted merge evidence
    - [x] Record PR [#316](https://github.com/edithatogo/global-medicines-atlas/pull/316) head `9887d51f55a9f83fee9a70d7370ad05125b2324a`, 37 passing hosted checks, and merged SHA `2341475cb0ee75c3ae78a72c9beb94fcdbe0851a`; issue #315 closed, parent #170 remains open


## Orange Book official-index refresh (2026-09-28)

- [x] Reopen one bounded internal acquisition after the official FDA
  additions/deletions index exposed the August 2026 monthly list, a new release
  beyond the 2026-08-21 inventory. Existing source-specific authorization
  permits internal acquisition and retention only, up to 320 releases and
  2 GiB.
- [x] Acquire the current 260-URL inventory once. The new August 2026 FDA PDF
  was accepted (276,627 bytes; SHA-256
  `3a80ae5a22c4a1522e9d1db5159a8fcb69c93b9c14492424e1b6e788509408ea`). The
  current pass recorded 140 accepted, 16 quarantined, and 104 failed URLs; all
  104 failures were `http_status` from `wayback.archive-it.org`. The private
  archive digest is
  `250613299c6e8038ba00b451cd2980afe97c944a125a472d6245c515261d29d3`
  (191,621,120 bytes), verified at the retained local evidence path in the
  qualification receipt.
- [x] Reconcile the source queue and regenerate all B0 projections from the
  canonical catalogue and overrides. The Orange Book next action now requires a
  material official inventory or Archive-It availability change, matching the
  bounded retry decision. B0 snapshot `1198635440e3dbd67103b55324870dd089fdff14257d377781ea3c2d9e111024`;
  23 focused tests and 49 broader source-index, acquisition, and Bronze maturity
  tests pass. Context validation, Ruff, formatting, JSONL, and diff checks pass.
- [ ] Historical inventory and coverage remain incomplete. The same 104 archive
  failures and 16 quarantined responses persist; no public release or external
  publication is authorized. Do not repeat this full acquisition unless the
  official inventory or source availability changes again.

## FDA drug-shortages maturity receipt reconciliation (2026-09-28)

- [x] Reconcile the Codex review finding against both source receipts. The
  source-specific Prompt 14 qualification records internal retention, the
  complete current export and 129 monthly-list temporal corpus, recovered
  source-record projection, byte-identical Parquet, and verified archive
  checksums. The older generic U.S. Bronze corpus row describes a separate
  quarantined acquisition and does not supersede the designated receipt.
- [x] Add a fail-closed maturity recognizer for that exact receipt contract and
  negative controls for source identity, schema version, authorization,
  projection/recovery/parity counts, temporal scope, checksum verification, and
  publication boundaries. The refreshed exact-merge report now counts 119 of
  157 in-scope sources as lacking accepted landings; overall Bronze maturity
  remains blocked.
- [x] Record PR [#586](https://github.com/edithatogo/global-medicines-atlas/pull/586),
  exact head `91d30793f8f923ab21a506b2dc786ae119157d90`, all required checks
  passed, and merged SHA `4667f14403ea4f394b17ce3e1a5e221c7095e394`.
  Focused source/maturity tests passed (127); routine and context checks passed.
- [ ] Remaining 119 source-specific landings, rights, and receipt evidence;
  do not infer coverage from indexing, acquisition intent, or unrelated audit
  completions. FDA shortages delegated detail-page coverage remains incomplete
  and publication remains unauthorized.

## Medstat HTML export format diagnosis (2026-09-28)

- [x] Merge the redacted HTML-shape diagnostic in PR [#591](https://github.com/edithatogo/global-medicines-atlas/pull/591), exact head `7415e63d`, merged SHA `76b311d704db443d0f4de11f53d925bec528d641`; all protected checks passed.
- [x] Run the authorized internal-only acquisition workflow once on exact `main`. It returned HTTP 200, `.xls`, 4,446 bytes, `text/html;charset=UTF-8`, a source-titled HTML document, and one table with three rows and six cells. The page had no forms, controls, frames, scripts, links, or buttons.
- [x] Review the official landing, data-description, and metadata-download pages. They establish the 1996–2025 sales period and source-defined sector limitations; the metadata-download page lists supporting CSVs, but none documents the interactive export endpoint's response media type. Receipt: `quality/qualifications/nordic-medstat-export-format-doc-review-20260929.json`.
- [x] Prepare and send the narrowly scoped source-owner clarification request at `medstat-export-format-request.md`. Sent receipt `1a0e9ad775ff9a95` and a separately recorded, unbound automatic reply `1a0e9b780c580bd2` are in `quality/qualifications/provider-outreach-receipts-20260929.json`; the reply's RFC `In-Reply-To` does not match the request and substantive format guidance remains pending.
- [~] Keep the download rejected while awaiting provider guidance. The diagnostic transiently read and decoded the 4,446-byte response to calculate bounded HTML-shape counters, but did not retain the response bytes or emit its text. The bounded shape and official documentation do not establish whether this is a valid HTML-formatted spreadsheet or an error response. Do not implement an HTML parser or treat this response as source evidence before provider confirmation; internal landing, private retention, Bronze acceptance, public release, and external publication remain unclaimed.

## NICE private Bronze receipt reconciliation (2026-09-29)

- [x] Reconcile the approved Prompt 29 historical acquisition with the current
  source-landing queue. A receipt-bound recognizer now requires the exact NICE
  source ID, all 15 accepted admissions and acquisition manifests, four
  expected releases, complete digest metadata, a successful clean-room restore,
  and the separate maintainer approval for internal acquisition and retention.
  Public release and external publication must remain false.
- [x] Regenerate the source-landing queue and B0 projections. NICE is now
  `landed_and_evidenced` for its bounded historical private B1/B2 corpus; the
  current Bronze candidate count moves from 119 to 118 unlanded sources. No
  restricted payload bytes were read during this reconciliation, and no source
  records, current utilisation coverage, third-party separability, or
  independent archive durability are claimed.
- [x] Re-run the qualification against exact merged `main` and record its
  commit-bound maturity receipt. Commit `f6e7b9e27a642347ee63c5ef3ce391ed16bf212a`
  reports 118 in-scope sources without qualifying landings. Bronze completeness
  and M5 remain blocked by those 118 sources.
- [x] Review follow-up binds the NICE receipt to exactly 15 independently
  expected payloads and corrects Prompt 29 to request source-record qualification
  without reacquisition. Focused tests pass (116); the full local profile reports
  5,207 passed, 2 environment-only uv-version failures, 1 skipped, and 96.71%
  coverage; both failures pass with isolated uv 0.11.29. Protected CI and Codecov
  patch coverage pass on PR #595.

## 2026-09-29 exact-main Bronze/M5 reconciliation

- [x] Refresh `quality/qualifications/bronze-maturity.json` against exact merged `main` `4dc23b296656895b6d6fc882e007bcbd43e3f9eb` after PR #599. The report still finds 118 of 157 in-scope public/no-credential sources without qualifying landing evidence. All other mandatory Bronze dimensions remain evidenced; current-scope completeness and M5 remain blocked.
- [x] Verify the previously raised Prompt 31 discrepancy is resolved: the formulary and spending sources are both `landed_and_evidenced`, and the Prompt 31 audit reports `live_acquisition_complete`. This does not change the overall Bronze denominator or Australian federation gates.

## 2026-09-29 post-PR-613 exact-main refresh

- [x] Re-evaluate the maturity report against exact merged `main`
  `b5e4302d9b23d3632900d955356fb7eaa7824b4c` after PR #613. The report still
  finds 118 of 157 in-scope sources without qualifying landing evidence; the
  other 13 mandatory dimensions remain evidenced. This refresh corrects report
  provenance only and does not claim new acquisition, Bronze completeness, or
  M5 maturity.

## 2026-09-29 Medstat request and acknowledgement merge reconciliation

- [x] PR #611 recorded the sent format inquiry, restored prior evidence rows
  byte-for-byte, and bound the sent RFC Message-ID. All 37 observed PR checks
  passed; merged as `e3ba5b76db6cd02cf593e6c23598cdea45983b02`.
- [x] PR #612 recorded the automatic reply as unbound after its raw
  `In-Reply-To` failed to match the inquiry RFC Message-ID. The correction
  supersedes the earlier correlation claim without rewriting the append-only
  ledger. All 37 observed PR checks passed; merged as
  `0e69588fd9c8e00fa1eb4201fe2c4a981ef194d0`.
- [~] Substantive source-owner format guidance remains pending. The returned
  automatic message does not resolve the export format; continue rejecting the
  response and make no acquisition, rights, Bronze, or publication claim.

## 2026-09-29 post-PR-622 exact-main Bronze/M5 reconciliation

- [x] Re-evaluate `quality/qualifications/bronze-maturity.json` against exact
  merged `main` `588efbb99956a09c9678bb21b8550c32905009fe` after PR #622. The
  report still finds 118 of 157 in-scope sources without qualifying landing
  evidence; 13 of 14 mandatory dimensions are evidenced and completeness is
  blocked. This corrects report provenance only; Bronze completeness and M5
  remain blocked.
- [x] Run focused qualification tests, routine checks, context and ecosystem
  validation, then bind their results in append-only evidence.
- [x] Refresh the stable-v1 M5 status page to bind exact-main Bronze report
  commit `4cca88d3e13be535643e2408d627837802b82c6c`. The report still finds 118 of 157 in-scope sources
  without landing evidence, so completeness and M5 remain blocked.
  Focused status/provenance tests and context validation passed.

## Sweden Socialstyrelsen bounded aggregate acquisition (2026-09-30)

- [x] Record the maintainer's 2026-09-29 source-specific approval for source-
  generated aggregate API results retained internally only. The cap is 70,000
  cells and 100 ATC codes per query; person-level data, bulk downloads, public
  release, and external publication remain excluded.
- [x] Implement and merge the bounded acquisition workflow in PR #638
  (`09d3c837`), then run the maintainer-authorized hosted acquisition once on
  exact main `09d3c8370b04c4b92439b2587e683e92276f3d6b`. Run
  [36611480442](https://github.com/edithatogo/global-medicines-atlas/actions/runs/36611480442)
  completed successfully and verified five aggregate response digests in the
  private pinned archive; no source payload bytes were downloaded locally.
- [x] Reconcile the exact workflow, five payload digests, private archive
  digest/revision, query limits, and retention-only authorization into the
  Prompt 33 audit and M5 completeness recognizer. Regenerated queue, Prompt 33,
  B0, and maturity outputs now count Sweden as one bounded private landing and
  leave 117 of 157 in-scope sources without qualifying landings. Focused
  Prompt 33 and maturity tests pass (126); Ruff, formatting, `ty`, and diff
  checks pass. PR #639 merged at `fb7947d840835f44316bca54adf4cb48210032c7`
  after all 39 hosted checks passed, including Codecov and full coverage.
- [x] Refresh the M5 status page and qualification against exact merged main
  `fb7947d840835f44316bca54adf4cb48210032c7`. The regenerated report still
  finds 117 of 157 in-scope sources without qualifying landings; this provenance
  refresh does not resolve source licensing, publication rights, complete
  Swedish coverage, Australian federation, M5 source-coverage maturity, or
  Stable v1 approval. PR #640 merged at
  `0bc072cd543924deea8658f9400a37b5b94185d4` after all 37 hosted checks passed.

## 2026-09-30 Japan NDB current-edition metadata refresh

- [x] Reconcile the official MHLW catalogue and current edition page. The 11th
  NDB Open Data was published 2026-06-16 for FY2024 claims and FY2023 health
  checkups; prescription tables expose aggregate pharmacological-class
  quantities across sex/age, prefecture, and service-month strata. Only public
  page metadata was read; no data links, rows, or bytes were accessed. Receipt:
  `quality/qualifications/japan-ndb-current-release-metadata-20260930.json`.
- [x] Reconcile MHLW's sitewide PDL 1.0 default against the open edition page.
  The page does not say whether separate dataset rules or third-party rights
  apply. No project rights conclusion is made.
- [~] Keep payload acquisition and retention unauthorized until the
  source-specific maintainer decision is recorded. Correct the catalogue's
  funding/product-identity taxonomy before promoting these aggregate
  utilisation semantics.

## 2026-09-30 Japan NDB merge and taxonomy boundary

- [x] Merge the metadata-only current-edition receipt and contract test in PR
  [#643](https://github.com/edithatogo/global-medicines-atlas/pull/643),
  commit `1fc84791d1f51ab5fdc72004e420f247eaedbd8a`; all 37 hosted checks
  passed. The value-free receipt is bound to the 11th NDB Open Data edition;
  no source data rows or payload bytes were accessed.
- [x] Trace the NDB taxonomy correction through the source-catalog v5 schema
  and Stable-v1 measured-coverage contract. The current source model has one
  required dimension and the Stable-v1 report fixes four counted dimensions;
  adding utilisation as an independent catalog dimension therefore requires
  coordinated schema/version compatibility work. Do not relabel utilisation
  as funding or silently alter the Stable-v1 denominator.
- [~] Keep NDB acquisition and retention blocked pending the source-specific
  maintainer rights decision. Track the utilisation taxonomy migration as a
  separate versioned-contract task before promoting NDB utilisation semantics.

## 2026-09-30 post-PR-647 exact-main Bronze/M5 reconciliation

- [x] Regenerate the Bronze maturity report against merged `main`
  `522f4ff9783cd45ca814e5ccf400e88377ebaaa2`. It reports 174 catalog sources,
  157 in-scope sources, 117 without qualifying landing evidence, and 13 of 14
  dimensions evidenced; completeness remains blocked. The NICE private
  historical corpus is receipt-qualified only for bounded internal B1/B2
  landing, with no source-record projection or publication claim.
- [x] Rebind the Stable-v1 M5 status page to the report's exact evaluated
  commit. Focused maturity and Stable-v1 provenance tests, routine validation,
  context and ecosystem checks pass. No Bronze, M5, federation, or stable
  release gate is promoted.

## Orange Book current projection reconciliation (2026-09-30)

- [x] Reconcile the bounded current Orange Book source-record projection in
  `quality/qualifications/us-live-bronze-records-20260820.json` with the source
  landing queue. Record the source as `landed_and_evidenced` only for its
  receipt-backed current projection; retain Prompt 16's historical-family
  blocker and the 2026-09-28 104 Archive-It failures and 16 quarantined
  responses. Do not infer historical completeness or public-release rights.
- [x] Regenerate the landing queue, B0 source index, maturity report, and prompt
  audit. The accepted landing count increases from 40 to 41 and the completeness
  deficit falls from 117 to 116; Bronze maturity remains blocked.
- [x] Validate focused maturity, queue, source-index, and prompt-audit tests,
  routine quality checks, context validation, and generated artifact consistency.

## 2026-10-02 post-PR-700 Bronze dimension reassessment

- [x] Regenerate the Bronze maturity report against exact current `main`
  `3cd30375aae578c4abd99a72f4048c39deed1596`. The report evaluates all 14
  mandatory dimensions: 13 are evidenced and only completeness is blocked.
  The inventory remains 174 catalogue sources, 157 in-scope, 42 receipt-backed
  landings, 115 without qualifying landing evidence, 2 fixture-only, and 15
  excluded. The queue has 91 manual-only, 25 rights-blocked, and one temporarily
  unavailable in-scope source. Approved rights dispositions alone do not
  establish acquisition or B1/B2 landing evidence.
- [x] Rebind the Stable-v1 M5 status page to this exact report commit. M5
  source coverage, Australian federation acceptance, and final Stable-v1
  release approval remain separate blocked gates; production DR authority is
  a separate non-acceptance gate.
- [x] Record the reassessment without promoting Bronze maturity or changing
  source rights, acquisition, coverage, publication, or any acceptance gate.

## 2026-10-02 post-PR-702 exact-main report refresh

- [x] Rebind the qualification and M5 status page to exact merged `main`
  `9f32b2a798745dd6db88f56a2833753830fe3bca`. The 174/157/42/115 source counts
  and the 13-evidenced, one-blocked dimension result are unchanged. This
  corrects report provenance only.

## 2026-10-03 versioned receipt cohort and future-source ledger

- [x] Add a supplemental, versioned receipt-backed source cohort without
  changing the current-scope Bronze or Stable v1 M5 acceptance gates.
  - [x] Write failing tests proving direct receipts, rather than queue labels,
    determine cohort membership and current-scope sources partition cleanly.
  - [x] Bind each selected source ID to its validated receipt reference and
    digest; preserve the source catalogue and queue input digests.
  - [x] List every other current-scope source with its queue state, reason,
    next action, and explicit re-entry trigger. Keep fixture-only and excluded
    source classes separate.
  - [x] Regenerate the full-scope maturity report against exact merged `main`
    `12e5ca4678e077f8e6bf954aaa780aac83040994`; preserve the 174/157/42/115
    source counts, 13 evidenced dimensions, and blocked completeness state.
  - [x] Run focused and affected checks, record evidence, and reconcile this
    task marker.
  - The supplemental cohort contains 27 direct receipt-qualified source IDs.
    Its future list contains the remaining 130 current-scope IDs: 115 that the
    full-scope evaluator still reports without landing evidence, plus 15 with
    other/queue-level landing evidence that does not satisfy direct-receipt
    cohort membership. No M-095 denominator change or M5 promotion is claimed.


## 2026-10-03 rights reconciliation and post-merge qualification

- [x] Merge the accepted-source rights projection reconciliation after
  resolving the evidence-log conflict with exact merged `main`; preserve both
  histories and verify the resulting JSONL. The catalogue `rights_status`
  guard and independent source-rights approvals are both required.
- [x] Regenerate the receipt cohort after the rights catalogue projection
  changed its hashed input, then rebind current-scope Bronze and Stable v1 M5
  status to exact merged `main` `93aab4e4e553e1957f743eacc27f8b7537cbf29a`.
  Cohort remains 27 direct-receipt sources and 130 deferred current-scope IDs;
  the full-scope inventory remains 157 in scope, 42 with landing evidence,
  115 without qualifying landing evidence, 13 of 14 dimensions evidenced, and
  Bronze completeness and Stable v1 M5 blocked.
- [x] Validate the changed rights/cohort/maturity contracts (140 passed),
  Ruff, `ty`, BasedPyright, routine Goblin, context/ecosystem validators, and
  exact-head protected CI before merge.

## 2026-10-03 Open Medic receipt reconciliation

- [x] Recognize the existing all-release Open Medic Bronze receipt only under
  its source-specific acquisition authorization, approved exact public
  revision, source-rights disposition, and maintainer-reviewed rights ledger.
  The validator checks all 12 accepted annual releases, distinct acquisition,
  payload and source-record digests, archive totals, source-record projection
  parity, and explicit non-claims. No acquisition, rights decision, or
  publication was performed.
- [x] Regenerate the supplemental direct-receipt cohort and future-source
  ledger. The qualified receipt cohort moves from 27 to 28 and deferred current
  scope from 130 to 129. The full-scope evaluator remains at 42/157 landing
  evidence, with 115 missing; 13/14 dimensions are evidenced and completeness
  and M5 remain blocked. Phase 5 remains incomplete.
- [x] Review hardening rejects non-integer summary counts and duplicate annual
  source-record digests. A negative test confirmed numeric type drift is
  rejected.
- [x] Address the hosted Codecov patch result by adding malformed-ledger,
  missing/duplicate identity, and invalid release-shape negative controls.
  That test-only follow-up measured 97.94% combined coverage locally; hosted
  patch coverage passed on the corresponding PR head before the subsequent
  manifest-binding fix.
- [x] Resolve the Codex review finding that release-row digests were syntax-
  checked but not bound to the pinned public archive. Verify the exact public
  manifest digest and its 12 receipt/payload entries without fetching archive
  payload bytes; commit a separately content-addressed expected Bronze release
  manifest and require an exact per-row match for payload, acquisition,
  admission, count, and source-record identities.
- [x] Run focused qualification tests and the full local Test-Goblin profile.
  The full profile reports 5,417 passed, 2 uv-version failures, 1 optional
  skip, and 96.74% coverage; both failures pass under the required uv 0.11.29.
- [x] Merge PR [#707](https://github.com/edithatogo/global-medicines-atlas/pull/707)
  at exact head `4e7ccceb2e8bbde639b86ad596aaded0281a4a38`, squash merge
  `bf7fde1f1907d055dc784cb29822677cb3adeb6b`. All required hosted checks,
  including Codecov patch coverage and protected CI, passed; the review thread
  was resolved after the content-binding fix.
- [x] Re-evaluate the cohort on exact merged `main`; deterministic regeneration
  produced no diff. The 28/129 cohort split, 42/157 landing evidence, 115
  missing, and 13/14 dimension result remain unchanged.


## 2026-10-03 exact-main reconciliation and safe deferral

- [x] Reconcile the post-PR-707/708 direct-receipt cohort and current-scope
  maturity snapshot against exact merged `main`
  `752908d174175f3307f34eecc677711fb189b745`; refresh stale status summaries
  without changing the 157-source denominator or the 42/115 landing counts.
- [x] Keep the July 2025 MBS XML and July 2024 P7 workbook in the future-source
  list. Their immutable public B2 payload receipts are not typed direct B1
  qualification receipts. State the missing B1 receipt evidence and preserve
  M-112 federation acceptance as a separate gate; do not acquire or publish
  source bytes.
- [x] Address the hosted unit findings by storing source-specific next
  actions in canonical sparse overrides and regenerating the queue, cohort,
  and qualification snapshots. The corrected affected contracts pass (254
  tests); the follow-up status-page provenance contract passes (2 tests), and
  routine Test-Goblin, context/ecosystem, JSONL, and diff checks pass. PR #709
  merged at `d573b997c10f3d5fd5fc00c838350c7cd452622c` after every required
  branch-protection check passed. The 157-source denominator and blocked
  completeness/M5 findings remain unchanged.

## 2026-10-03 Australian MBS raw Bronze receipt candidate

- [x] Reconcile the August 2026 MBS typed SourceReceipt, AcquisitionEvent,
  accepted admission record, and B2 external-reference manifest to their
  exact local content hashes and pinned public archive manifest. No source
  payload bytes were fetched or retained locally. The record is only a
  qualification candidate because it lacks the required preceding durable
  `landed` event; it is not counted in the direct-receipt cohort.
- [x] Correct the receipt/run pairing additively against the exact nested
  source-receipt hashes and acquisition/admission identities. Historical M112
  audits remain intact and their projection-lineage, root-manifest, and
  differing-Parquet-digest findings remain open.
- [x] Defer `au-mbs` after review confirmed no durable `landed` event precedes
  the accepted decision, and that decision has no `supersedes_decision_id`.
  Preserve the acquisition and B2 metadata without fabricating lifecycle
  history; the final cohort is 28 qualified / 129 deferred. Full-scope unique
  landing accounting remains 42/157 with 115 missing and 13/14 dimensions
  evidenced. The denominator is unchanged; Bronze completeness and M5 remain
  blocked.
- [x] Bind every MBS B1/B2 receipt, admission, archive manifest, and source
  admission-history file consumed by the validator into the cohort dependency
  manifest. Regenerate the B0 index, source queue, future-source ledger, and
  maturity projection.
- [ ] Re-evaluate direct Bronze qualification only after the actual durable
  landed event and its exact accepted-event supersession link are evidenced.
- [ ] Complete source-record projection lineage reconciliation and M-112
  Australian federation acceptance as separate downstream gates.

## 2026-10-03 MBS P7 archived receipt reconciliation

- [x] Reconstruct the July 2024 P7 hosted storage SourceReceipt from its
  committed payload identity, retrieval timestamp, workflow commit, and pinned
  transformation identity. Its canonical digest matches the digest recorded
  in the hosted qualification (`ba18c367...fdf0d52`) without reading workbook
  bytes locally.
- [x] Keep that receipt explicitly limited to archive-storage verification:
  it records a Hugging Face archive retrieval, not a source-origin acquisition,
  and the workflow emitted no B1 admission lifecycle. Leave P7 deferred from
  direct receipt qualification, preserve the unresolved legacy date profile,
  and keep M-112 separate.
- [x] Regenerate the landing queue, B0 index, direct-receipt cohort, and future
  source list. Cohort remains 28 qualified / 129 deferred; full current scope
  remains 42 of 157 with landing evidence, 115 without, and 13 of 14 maturity
  dimensions evidenced.
- [x] Run 212 affected tests, routine Test-Goblin, context/ecosystem
  validation, formatting, lint, typing, and diff checks.
- [x] Re-run the affected suite and routine profile after binding the new
  reconciliation producer into the cohort dependency manifest; refresh the
  generated cohort and confirm exact reproducibility.
- [ ] Re-evaluate direct Bronze qualification only after a source-origin
  retrieval and chronological B1 admission history are evidenced.
