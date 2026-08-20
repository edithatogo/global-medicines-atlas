# Implementation Plan

Execution policy: [autonomous, decision-gated](../../autonomy.md).

This track completes bronze for current public/no-credential scope. It does not
implement silver, gold, or platinum. Hugging Face archival of public data is
owned by a sibling track; this plan consumes that archive boundary.

The immutable source payload and its content-addressed receipt are evidentiary
truth; source-faithful Parquet is the portable analytical representation;
table/catalogue layers are rebuildable metadata over those artefacts.

## Phase 1: Inventory, layer contract, and identity reconciliation

- [ ] Task: Write failing tests for bronze scope classification and catalog/fixture identity reconciliation ([#168](https://github.com/edithatogo/global-medicines-atlas/issues/168))
    - [ ] Assert in-scope first-cohort and global public/no-credential sources are enumerated from `medicine_source_catalog.json`
    - [ ] Assert credentialed and licensed-feed sources are excluded with reasons
    - [ ] Assert adapter and fixture identifiers map to catalog `source_id` values or an explicit alias
    - [ ] Assert RxNorm/UMLS live payloads are fixture-only
    - [ ] Confirm the intended failure before implementation
- [ ] Task: Implement the bronze inventory and layer contract
    - [ ] Record public ingest versus fixture-only versus excluded
    - [ ] Preserve independent regulatory, funding, formulary, and terminology dimensions
    - [ ] Cross-reference M-092 to M-100 and design section Medallion Datahouse
- [ ] Task: Phase Verification & Checkpoint
    - [ ] Run focused tests, affected harness, typing, and provenance checks
    - [ ] Record evidence; do not claim live bronze landing complete

## Phase 2: Pre-acquisition reuse gate

This phase is first-class. It exists to stop independent copies of the same
public data. It runs before any acquire/download, including Drugs@FDA.

- [ ] Task: Write failing tests for the reuse gate ([#167](https://github.com/edithatogo/global-medicines-atlas/issues/167) nested sub-issue)
    - [ ] Assert acquisition without the gate fails
    - [ ] Assert each disposition reuse | link | mirror | extend | fork | acquire-new is representable
    - [ ] Assert acquire-new is last resort when a payload copy already exists
    - [ ] Assert searches cover local clones, GitHub, Hugging Face, and the source registry
    - [ ] Confirm the intended failure before implementation
- [ ] Task: Implement the reuse gate against existing contracts
    - [ ] Reuse `docs/ECOSYSTEM_REUSE.md` and `.context/ecosystem.toml`
    - [ ] Search `medicine_source_catalog.json` and the Hugging Face catalogue
    - [ ] Bind the chosen disposition onto receipts and OpenLineage
    - [ ] Fail closed when Drugs@FDA or any acquire path skips the gate
- [ ] Task: Phase Verification & Checkpoint
    - [ ] Run focused tests, typing, and provenance checks
    - [ ] Record the disposition vocabulary in evidence

## Phase 3: Evidentiary payloads, temporal identity, and source-faithful Parquet

- [ ] Task: Write failing tests for bronze landing storage ([#169](https://github.com/edithatogo/global-medicines-atlas/issues/169))
    - [ ] Assert payload bytes are preserved and Parquet is not the payload
    - [ ] Assert receipts are content-addressed and bind payload digest, source identity, dates, and rights
    - [ ] Assert temporal fields are distinct; substituting retrieved_at for published time fails
    - [ ] Assert valid_* are absent when the source did not supply them
    - [ ] Assert acquisition ID is immutable across Parquet regeneration
    - [ ] Assert DuckDB and LanceDB are absent from bronze identity
    - [ ] Confirm the intended failure before implementation
- [ ] Task: Implement payload landing, temporal identity, and analytical Parquet
    - [ ] Reuse `receipts.py`; do not treat DuckDB or Parquet as evidentiary truth
    - [ ] Record source published/effective time, retrieved_at, valid_from/to, acquisition ID
    - [ ] Fail closed on missing rights, provenance, or receipt fields
- [ ] Task: Phase Verification & Checkpoint
    - [ ] Run focused tests, coverage, typing, and licensing checks
    - [x] Record payload digests, acquisition IDs, and Parquet identities in evidence

### Phase 3b: Append-only acquisition, admission, and HTTP receipts

- [x] Task: Harden append-only acquisition identity ([#169](https://github.com/edithatogo/global-medicines-atlas/issues/169), parent [#167](https://github.com/edithatogo/global-medicines-atlas/issues/167))
    - [x] Separate content_id / payload digest from acquisition_id
    - [x] Keep source/version, published/effective, retrieved_at, and source-supplied validity independent
    - [x] Physically deduplicate identical bytes without collapsing acquisition history
    - [x] Schema contract and migration-safe TemporalIdentity without content_id
- [x] Task: Bronze quarantine and admission lifecycle ([#169](https://github.com/edithatogo/global-medicines-atlas/issues/169))
    - [x] States landed → accepted | quarantined | rejected-from-processing
    - [x] Preserve malformed payloads; fail closed downstream unless authorised
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
- [ ] Task: Phase Verification & Checkpoint
    - [ ] Run focused tests and typing
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

- [~] Task: Write failing tests for in-scope bronze ingest ([#170](https://github.com/edithatogo/global-medicines-atlas/issues/170))
    - [ ] Assert each in-scope public/no-credential source can land raw bytes or has an explicit non-completion blocker
    - [ ] Assert already-governed fixtures land as bronze without becoming canonical silver
    - [ ] Assert credentialed sources cannot land through this path
    - [ ] Assert credentials and restricted bytes are never persisted
    - [ ] Assert Drugs@FDA ingest runs the reuse gate first
    - [ ] Confirm the intended failure before implementation
- [ ] Task: Implement public ingest and fixture landing for current scope
    - [ ] Use existing untrusted acquisition and first-cohort adapters
    - [x] Inspect truncated downloads, hostile ZIP/tar, decompression bombs, path traversal, MIME mismatch, malformed XML/JSON/CSV, schema poisoning, collisions, source mutation, replays, checksum mismatch, and hostile filenames; land bytes; quarantine processing; keep forensic receipts
    - [ ] Land Medsafe, PHARMAC, ARTG, PBS, DPD/NOC, MHRA/NICE, EMA/Union Register, PMDA/NHI, Drugs@FDA, and CMS Part D fixtures
    - [ ] Leave NZULM bulk, NZHTS, AMT, embargoed PBS, dm+d/TRUD, EMA PMS, SPOR, and live RxNorm payloads excluded
- [ ] Task: Phase Verification & Checkpoint
    - [ ] Run focused, integration, and source-boundary tests
    - [ ] Measure completeness with S-012 denominators; missing coverage is not negative evidence

## Phase 6: Hugging Face archive boundary, regeneration, and completion evidence

- [ ] Task: Write failing tests for archive boundary and regeneration ([#171](https://github.com/edithatogo/global-medicines-atlas/issues/171))
    - [ ] Assert Hugging Face is an output/archive boundary and not an ingest origin
    - [ ] Assert repository payloads and receipts remain evidentiary truth
    - [ ] Assert deterministic regeneration from receipts and fixtures
    - [ ] Assert restricted payloads cannot enter a public archive package
    - [ ] Confirm the intended failure before implementation
- [ ] Task: Bind the Hugging Face archive boundary without duplicating sibling archival work
    - [ ] Reuse the sibling Hugging Face public-data archival path when it has landed
    - [ ] Do not publish source-derived payloads without the rights gate
- [ ] Task: Record bronze-completion evidence for current scope
    - [ ] Update this track's evidence ledger with observable tests, coverage, and exclusions
    - [ ] Leave silver/gold/platinum unimplemented
- [ ] Task: Phase Verification & Checkpoint
    - [ ] Run focused tests then `uv run python scripts/test_goblin.py full` where the platform permits
    - [ ] Open a scoped `codex/` pull request, wait for required checks, repair, and merge
    - [ ] Classify unresolved Hugging Face publication as an external gate, never as bronze source-of-truth

## Source expansion program (WHO, Africa, FDA, EMA, utilisation)

Inventory for bronze prompts 1-36 shares one registry, one reuse-gate
contract, and one coverage-reconciliation finish. Live ingest is not claimed
for credentialed or rights-unresolved sources.

- [x] Task: Register tracks 1-36, extend `medicine_source_catalog.json`, and emit derived coverage matrices plus a versioned source index
    - [x] Reuse gate remains mandatory before acquire
    - [x] African source-coverage matrix is a derived catalogue artefact
    - [x] Hugging Face stays an archive boundary; new FDA/EMA rows are not auto-archived
    - [x] Record blockers honestly; missing coverage is not negative evidence
