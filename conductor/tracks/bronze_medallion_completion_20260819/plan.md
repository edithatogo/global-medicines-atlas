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
    - [ ] Record payload digests, acquisition IDs, and Parquet identities in evidence

## Phase 4: Iceberg-ready identities and OpenLineage projection

- [ ] Task: Write failing tests for Iceberg-ready metadata and OpenLineage ([#169](https://github.com/edithatogo/global-medicines-atlas/issues/169))
    - [ ] Assert stable table identities, partitioning, and schemas exist over Parquet
    - [ ] Assert an Iceberg REST catalogue can register bronze metadata without pyiceberg in core
    - [ ] Assert OpenLineage RunEvents use real field names and split payload vs parquet datasets
    - [ ] Assert temporal identity and reuse disposition appear as facets
    - [ ] Confirm the intended failure before implementation
- [ ] Task: Implement Iceberg-ready specs and OpenLineage projection
    - [ ] Keep Iceberg optional; Python 3.14 core must not import it
    - [ ] Do not add Marquez to the default install
- [ ] Task: Phase Verification & Checkpoint
    - [ ] Run focused tests and typing
    - [ ] Record lineage event field names in evidence

## Phase 5: Public ingest and governed-fixture landing

- [ ] Task: Write failing tests for in-scope bronze ingest ([#170](https://github.com/edithatogo/global-medicines-atlas/issues/170))
    - [ ] Assert each in-scope public/no-credential source can land raw bytes or has an explicit non-completion blocker
    - [ ] Assert already-governed fixtures land as bronze without becoming canonical silver
    - [ ] Assert credentialed sources cannot land through this path
    - [ ] Assert credentials and restricted bytes are never persisted
    - [ ] Assert Drugs@FDA ingest runs the reuse gate first
    - [ ] Confirm the intended failure before implementation
- [ ] Task: Implement public ingest and fixture landing for current scope
    - [ ] Use existing untrusted acquisition and first-cohort adapters
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
