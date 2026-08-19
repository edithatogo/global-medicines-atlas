# Implementation Plan

Execution policy: [autonomous, decision-gated](../../autonomy.md).

This track completes bronze for current public/no-credential scope. It does not
implement silver, gold, or platinum. Hugging Face archival of public data is
owned by a sibling track; this plan consumes that archive boundary.

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
    - [ ] Cross-reference M-092 to M-097 and design section Medallion Datahouse
- [ ] Task: Phase Verification & Checkpoint
    - [ ] Run focused tests, affected harness, typing, and provenance checks
    - [ ] Record evidence; do not claim live bronze landing complete

## Phase 2: Content-addressed receipts and partitioned Parquet landing

- [ ] Task: Write failing tests for bronze landing storage ([#169](https://github.com/edithatogo/global-medicines-atlas/issues/169))
    - [ ] Assert partitioned Arrow/Parquet is the portable bronze artefact
    - [ ] Assert receipts are content-addressed and bind payload digest, source identity, dates, and rights
    - [ ] Assert DuckDB and LanceDB are absent from bronze identity
    - [ ] Assert schema-on-read accepts source-native field variation without collapsing dimensions
    - [ ] Confirm the intended failure before implementation
- [ ] Task: Implement bronze landing
    - [ ] Reuse `receipts.py` and extend partitioned Parquet landing; do not treat DuckDB as bronze
    - [ ] Include source-native identifiers, provenance, dates, rights, and uncertainty columns
    - [ ] Fail closed on missing rights, provenance, or receipt fields
- [ ] Task: Phase Verification & Checkpoint
    - [ ] Run focused tests, coverage, typing, and licensing checks
    - [ ] Record partition identity and receipt digests in evidence

## Phase 3: Public ingest and governed-fixture landing

- [ ] Task: Write failing tests for in-scope bronze ingest ([#170](https://github.com/edithatogo/global-medicines-atlas/issues/170))
    - [ ] Assert each in-scope public/no-credential source can land raw bytes or has an explicit non-completion blocker
    - [ ] Assert already-governed fixtures land as bronze without becoming canonical silver
    - [ ] Assert credentialed sources cannot land through this path
    - [ ] Assert credentials and restricted bytes are never persisted
    - [ ] Confirm the intended failure before implementation
- [ ] Task: Implement public ingest and fixture landing for current scope
    - [ ] Use existing untrusted acquisition and first-cohort adapters
    - [ ] Land Medsafe, PHARMAC, ARTG, PBS, DPD/NOC, MHRA/NICE, EMA/Union Register, PMDA/NHI, Drugs@FDA, and CMS Part D fixtures
    - [ ] Leave NZULM bulk, NZHTS, AMT, embargoed PBS, dm+d/TRUD, EMA PMS, SPOR, and live RxNorm payloads excluded
- [ ] Task: Phase Verification & Checkpoint
    - [ ] Run focused, integration, and source-boundary tests
    - [ ] Measure completeness with S-012 denominators; missing coverage is not negative evidence

## Phase 4: Hugging Face archive boundary, regeneration, and completion evidence

- [x] Task: Write failing tests for archive boundary and regeneration ([#171](https://github.com/edithatogo/global-medicines-atlas/issues/171))
    - [x] Assert Hugging Face is an output/archive boundary and not an ingest origin
    - [ ] Assert repository Parquet and receipts remain authoritative
    - [ ] Assert deterministic regeneration from receipts and fixtures
    - [x] Assert restricted payloads cannot enter a public archive package
    - [x] Confirm the intended failure before implementation
- [x] Task: Bind the Hugging Face archive boundary without duplicating sibling archival work
    - [x] Reuse the sibling Hugging Face public-data archival path when it has landed
    - [x] Publish FDA, EMA, TGA, and Medsafe public artefacts through GitHub Actions `.github/workflows/data-layer-archive.yml`
    - [x] Keep credentialed EMA PMS/SPOR and NZULM/NZHTS metadata-only
    - [ ] Do not publish source-derived payloads without the rights gate
- [ ] Task: Record bronze-completion evidence for current scope
    - [ ] Update this track's evidence ledger with observable tests, coverage, and exclusions
    - [ ] Leave silver/gold/platinum unimplemented
- [ ] Task: Phase Verification & Checkpoint
    - [ ] Run focused tests then `uv run python scripts/test_goblin.py full` where the platform permits
    - [ ] Open a scoped `codex/` pull request, wait for required checks, repair, and merge
    - [ ] Classify unresolved Hugging Face publication as an external gate, never as bronze source-of-truth
