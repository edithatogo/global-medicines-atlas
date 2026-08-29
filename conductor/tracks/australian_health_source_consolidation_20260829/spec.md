# Specification: Australian health source consolidation

## Objective

Consolidate the complete useful scope of the two Australian donor repositories
into Global Medicines Atlas without losing raw data, legacy comparison value,
Git provenance, or semantic distinctions. GMA becomes the canonical code and
governance authority; the raw and derived public data plane is delivered by the
dependent Hugging Face track.

## Authoritative inputs

- `edithatogo/aus_mbs_pbs_graph` at
  `64e764cebeb3826f98ce672cbb4affc65d06a92f`.
- `edithatogo/aus-health-data-scraper` at
  `931da0b9b6ae3e3cec0743568abb71a50d62b7cf`.
- The exact file/function/data reconciliation in `donor-assessment.md`.
- Decision 0009 and requirements M-105 through M-113.
- The maintainer's 2026-08-29 direction to include all datasets, including
  legacy data, and assertion of permission to redistribute the scoped raw
  payloads.

## Scope

1. Create a machine-readable donor inventory covering every tracked file,
   executable function, workflow, fixture, data object, and roadmap-only
   capability at the pinned commits.
2. Preserve donor repository/commit/licence, original path, byte count, digest,
   implementation state, and final disposition.
3. Add a first-class `au-mbs` source family and independent MBS service-benefit
   domain to the source catalogue, contracts, fixtures, adapters, coverage, and
   source-health systems.
4. Replace the guessed MBS parser with a bounded parser for the observed
   `MBS_XML/Data` release structure while preserving all source columns and
   supporting versioned future profiles.
5. Preserve the July 2025 5,989-row XML and July 2024 P7 workbook byte-for-byte;
   retain all workbook sheets and legacy annotations for historical comparison.
6. Reimplement PBS ZIP acquisition, safe member selection, PBS v3 namespace
   parsing, item/product/restriction fields, AMT references, and ATC codes using
   existing GMA receipt/admission contracts.
7. Preserve the donor PBS tag inspector as a bounded schema-inspection/debug
   capability and golden regression fixture.
8. Replace blocking/unbounded MBS HTML item/participant scraping with a
   catalogue-driven, timeout-bounded compatibility probe. Historical endpoints,
   filename conventions, and table parsing remain reproducible, but a 404 or
   empty output is a failed acquisition rather than a green data update.
9. Preserve generic HTML/XML-to-table behavior only behind typed source
   contracts. Do not concatenate heterogeneous tables into an unlabeled
   canonical CSV.
10. Preserve the seven zero-byte notebook paths and zero-byte temporary XML as
    historical placeholders in the donor inventory; do not claim they contain
    analytical work or source data.
11. Convert the unimplemented Neo4j, SNOMED CT-AU, AMT, ATC hierarchy, NLP/NER,
    temporal graph, Spark, and Airflow plans into explicit successor tasks.
    Their graph-relevant subset is implemented in the Silver/Gold and frontier
    tracks; restricted terminology bytes remain outside public scope unless
    separately authorized.
12. Prepare donor repository successor notices, compatibility canaries, and
    archival receipts. Do not archive either repository in this track without
    the final maintainer gate.

## Semantic boundary

MBS service items, groups, fees, benefits, notes, and participant measures are
not medicines. PBS items are funding/formulary evidence, not regulatory
approval. AMT and ATC identifiers are terminology/classification evidence, not
funding or clinical equivalence. Cross-domain relationships are Gold evidence
edges with method, confidence, time, and review status.

## Compatibility strategy

Every donor item receives exactly one disposition:

- `adopt`: compatible behavior enters GMA substantially unchanged;
- `adapt`: behavior is retained behind GMA safety, typing, provenance, and
  medallion contracts;
- `replace-with-equivalent`: the intended behavior is retained but defective or
  obsolete implementation is not promoted;
- `retain-legacy`: exact bytes/history remain for replay or comparison;
- `supersede`: a richer existing GMA capability proves complete replacement;
- `exclude-with-reason`: no functional/data value is promoted, but the donor
  inventory and archived Git history still preserve the artifact.

No item may be marked complete merely because a target filename exists.
Behavioral parity, byte fixity, or an explicit legacy-only receipt is required.

## Acceptance criteria

- **AC-01:** A schema-validated inventory covers 100% of tracked donor files and
  every Python function/workflow at the two pinned commits with no unclassified
  item.
- **AC-02:** The 8,194,522-byte July 2025 MBS XML with SHA-256
  `db873768c5795222455033e2bad28586f19bbf2a10c7d58f06a0671d9111a556`
  lands byte-for-byte, parses all 5,989 `Data` records, and preserves the union
  of 40 native fields plus the observed 34-to-37 fields-per-record variability
  without the donor's guessed `MBSItem` tag.
- **AC-03:** The 87,727-byte P7 workbook with SHA-256
  `2f1cbc2d2dcbb93be86f42c8dbbe9f5f9e8fb550cad38b6ee54d0e9bdd2e27b8`
  is retained as raw legacy evidence; all four sheets, dimensions, formulas,
  date/amount fields, annotations, and schema-era labels are inventoried and
  reproducibly projected without modifying the workbook.
- **AC-04:** PBS v3 ZIP/XML fixtures prove safe archive handling, pharmaceutical
  item code/name extraction, AMT-reference and ATC extraction, restrictions,
  effective dates, and source-native namespace preservation.
- **AC-05:** Item/participant compatibility acquisition has timeouts, bounded
  concurrency, destination policy, retry budgets, source-health receipts, and
  explicit non-empty-output checks. The observed six 404s from scheduled run
  `30677814193` reproduce a failed-data state, not successful acquisition.
- **AC-06:** Golden and negative tests characterize donor behavior, including
  the invalid trailing Markdown fence in `parse_pbs_xml.py`, the wrong MBS item
  tag, the processor path/type defect, empty notebook placeholders, malformed
  archives, hostile XML, schema drift, and heterogeneous HTML tables.
- **AC-07:** Current GMA adapter/coverage behavior remains compatible; no MBS
  result is emitted as a medicine status and no PBS record becomes regulatory
  evidence.
- **AC-08:** Public raw-data receipts exist for every non-empty donor data object
  through the dependent public-data track before any durable local source copy
  is removed.
- **AC-09:** Each donor repository has a verified successor notice, complete Git
  history remains reachable, downstream canaries pass, and the final archive
  gate remains pending until the maintainer approves the exact repositories.
- **AC-10:** Focused tests, routine and strict harnesses, provenance/rights
  validation, full Test-Goblin where supported, protected CI, review, and
  requirement-to-evidence traceability pass.

## Out of scope

- Treating donor roadmap prose as evidence that Neo4j, ontology ingestion,
  NLP/NER, Spark, or Airflow was already implemented.
- Publishing SNOMED CT-AU, AMT, UMLS, or RxNorm vocabulary bytes by implication.
- Interpreting MBS/PBS relationships as clinical advice or therapeutic
  equivalence.
- Deleting donor repositories or local dirty work.

## Dependencies and gates

- Public payload movement and local-cache cleanup depend on
  `public_hf_federated_data_plane_20260829`.
- Typed Silver and Gold outputs depend on
  `australian_benefits_silver_gold_20260829`.
- Donor archival is a final compatibility-archive human gate.
- Exact hosted publication receipts bind the maintainer's asserted permission
  to source/file/destination identities; unrelated licensed archives remain
  excluded.
