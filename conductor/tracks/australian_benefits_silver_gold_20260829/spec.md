# Specification: Australian benefits Silver and Gold

## Objective

Implement the first production Silver and Gold medallion layers for Australian
MBS/PBS evidence. Silver preserves source-native structure while adding types
and explicit harmonisation. Gold expresses reviewable, temporal relationships
among services, medicines, terminology, restrictions, and conditions.

## Silver contracts

### MBS

Provide versioned, source-faithful tables for:

- service items and subitems;
- categories, groups, subgroups, and subheadings;
- descriptions, notes, and description-effective periods;
- schedule fees, derived fees, benefit amounts/types, caps, and fee-effective
  periods;
- provider/item/fee classifications and source change flags;
- participant/service-count measures where a valid source provides them; and
- legacy P7 annotations such as element, class, technology, disease, tissue,
  exome, prenatal, declining-list membership, formulas, and error states.

The July 2025 XML schema and July 2024 workbook sheets are separate schema eras.
Harmonised views retain source row identity and column lineage to each era.
Amounts use explicit currencies and decimal semantics; source blanks, formula
errors, missing dates, and cessation dates remain distinguishable.

### PBS

Provide versioned, source-faithful tables for:

- schedules/releases and namespace/schema identity;
- pharmaceutical items and source-native item codes;
- products/presentations, names, forms, strengths, manufacturers where present;
- listing/funding status and effective/cessation time;
- restrictions, authority requirements, indications/source text where present;
- pricing, contribution, benefit, and fee fields where present;
- AMT/SNOMED CT identifier references without redistributing restricted
  vocabulary content; and
- ATC codes and hierarchy-version references under their own rights contract.

No Silver table treats PBS listing as ARTG approval or an AMT/ATC identifier as
funding evidence.

## Gold evidence graph

Use normalized node and edge tables as the authoritative portable graph form.
Optional NetworkX, Cypher, Neo4j, RDF, or other projections are rebuildable.

Node classes include MBS service/item, PBS item/presentation, canonical medicine
concept, ingredient, restriction, source document, organization, MBS group,
AMT reference, ATC concept reference, condition candidate, and review case.

Every edge records:

- stable edge ID and typed source/target node IDs;
- relation type and semantic dimension;
- mapping method (`official`, `source-explicit`, `deterministic`, `lexical`,
  `ontology-assisted`, `embedding/NLP-candidate`, or `reviewed`);
- confidence/calibration and review state;
- supporting source IDs, revisions, paths, native row/element identifiers, and
  text spans only where redistribution permits;
- valid/effective and retrieval time;
- rights and sensitivity state;
- contradiction/conflict links and supersession; and
- negative-control outcome and comparison-validity state.

MBS-PBS links require explicit evidence such as source-native cross-reference,
reviewed shared condition/restriction evidence, or a declared candidate method.
Co-occurrence, lexical similarity, a shared ATC/AMT/SNOMED token, or absence
does not become an authoritative relationship.

## Historical comparison

Gold includes typed change events and comparison cohorts for:

- added, ceased, renumbered, or superseded MBS/PBS items;
- changed fees, benefits, products, prices, restrictions, descriptions, and
  mappings;
- schema-era and methodology drift;
- source availability/failure periods; and
- unresolved conflicts between official snapshots and legacy annotations.

Historical presence/absence is not current status, and missing snapshots are
not negative evidence.

## Acceptance criteria

- **AC-01:** Versioned Arrow/Parquet schemas and JSON contracts cover every
  observed field in the MBS XML, all four P7 workbook sheets, and PBS v3 fixture
  denominator; dropped/renamed/harmonised fields have field-lineage evidence.
- **AC-02:** Silver generation is deterministic, typed, source-faithful,
  streaming/bounded, and independently rebuildable from exact public B1/B2
  identities. Duplicate/native-null/formula-error/time/currency behavior has
  golden and property tests.
- **AC-03:** MBS and PBS dimensions remain independent in schemas, APIs,
  promotions, and coverage. Tests reject service-as-medicine,
  PBS-as-regulatory, terminology-as-funding, and absence-as-negative evidence.
- **AC-04:** Gold node/edge schemas require method, confidence, evidence,
  revision, time, rights, review, and negative-control state and reject
  unsupported or semantically overbroad links.
- **AC-05:** Official/source-explicit, deterministic, lexical/NLP candidate, and
  reviewed edges remain queryably distinct; promotion requires calibrated
  thresholds and review evidence.
- **AC-06:** Historical/current comparisons report complete denominators,
  schema-era drift, source failures, and uncertainty and reproduce known
  legacy-versus-current changes without silently overwriting history.
- **AC-07:** Graph tables, Silver tables, lineage, coverage, and promotions are
  published to pinned public Hugging Face revisions under v4; local databases
  and graph stores are reproducible caches only.
- **AC-08:** Focused, property, metamorphic, mutation, typing, security,
  provenance, rights, coverage, performance, full harness where supported,
  hosted review, and requirement/evidence gates pass.

## Non-goals and gates

- No individual clinical advice, therapeutic equivalence, or patient pathway
  conclusion.
- No publication of restricted SNOMED CT-AU/AMT vocabulary bytes; public IDs
  or mappings require their own recorded basis.
- No mandatory Neo4j or graph service; optional exports are frontier work.
- No Gold promotion from an NLP/vector score alone.

## Dependencies

- Source bytes and adapters:
  `australian_health_source_consolidation_20260829`.
- Public immutable identities:
  `public_hf_federated_data_plane_20260829`.
- Product delivery: `federated_medicines_platinum_20260829`.
