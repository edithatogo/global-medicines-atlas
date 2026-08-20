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
    - [ ] Complete source-specific rights receipts and live landing evidence for the remaining 136 public/no-credential sources; a catalogue blocker is not landing completion
        - [x] Generate a fail-closed review packet for all 20 U.S. sources from official FDA, openFDA, CMS, NLM, and NCATS policy surfaces; retain maintainer licensing, acquisition, and publication gates
        - [x] Record the maintainer's bounded internal-only U.S. licensing decision: five scoped openFDA candidates and eight FDA government-policy candidates may be acquired; seven CMS/NLM/NCATS terms gaps remain catalogue-only; public release remains prohibited
        - [x] Acquire all 13 authorized current-source payloads through the four-surface reuse gate and archive them locally without external publication
        - [x] Exercise immutable landing, rights-bound receipts, append-only admission, accepted-only Parquet/OpenLineage, and clean-room recovery against the live corpus; 8 acquisitions were accepted and rebuilt while 5 HTML/interactive payloads were preserved and quarantined
        - [ ] Acquire complete historical releases and adapter-native records for the applicable FDA source families; the bounded canaries and current snapshots do not complete prompt-level coverage
- [x] Task: Review Fixes for bounded U.S. live acquisition (`9a7dc7b`)
    - [x] Prevent bound GET/HEAD requests from gaining a chunked request body and skip compressed-wire Content-Length comparisons against decoded bytes
    - [x] Add authorization drift, fault isolation, excluded-content, private-archive, and transport regression tests; targeted branch coverage reached 93%
    - [x] Reconcile the completion audit to 5 live-qualified openFDA sources without claiming any completed acquisition prompt
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
