# Specification: Complete bronze medallion landing for current public scope

## Outcome

Complete the bronze layer of the Global Medicines Atlas medallion datahouse for
current-scope public and no-credential catalog sources and already-governed
fixtures. Later medallion layers remain specified only as boundaries. Hugging
Face is an archive and output boundary, not the source of truth.

The immutable source payload and its content-addressed receipt are evidentiary
truth; source-faithful Parquet is the portable analytical representation;
table/catalogue layers are rebuildable metadata over those artefacts.

## Internal Bronze strata

Bronze comprises three internal Bronze strata, not additional medallion levels.
**B0 Source Index** is the versioned index of agencies, datasets, APIs, and
source surfaces; indexing does not imply acquisition, coverage, qualification,
or currency. **B1 Acquisition Metadata** is the append-only record of
acquisition events, receipts, temporal identity, rights state, reuse decisions,
HTTP or other retrieval evidence, admission state, and provenance
relationships. **B2 Raw Evidence** is immutable source-native bytes, or a
rights-constrained immutable reference when bytes cannot lawfully be retained.

Source-faithful Parquet, archive-member manifests, OpenLineage, Iceberg,
DuckDB, and other query/catalogue objects are rebuildable Bronze projections
over B1/B2, not a fourth evidentiary source of truth. Silver remains
source-faithful typed or harmonised structures; Gold remains
cross-jurisdiction matched evidence; Platinum remains products and
presentation. This classification changes no acquisition ID, content digest,
existing receipt, or evidence semantic.

## Authoritative inputs

- `conductor/product.md`, `conductor/requirements.md`, `conductor/design.md`
- `src/global_medicines_atlas/data/medicine_source_catalog.json` (schema v5)
- `docs/data-sources/SOURCE_RIGHTS.md`, `docs/data-sources/source-onboarding.md`
- `DATA_LICENSE.md`, `docs/ECOSYSTEM_REUSE.md`, `.context/ecosystem.toml`
- `src/global_medicines_atlas/receipts.py`, `src/global_medicines_atlas/columnar.py`
- Adapter and fixture contracts under `src/global_medicines_atlas/adapters/` and
  `tests/fixtures/`
- `quality/qualifications/publication-identities.json` (Hugging Face is a derived
  dataset distribution)
- Hugging Face catalogue `edithatogo/global-medicines-atlas-catalogue` at
  revision `760723adc9c2f8e8946eebe9bcada7aff212095e`

## In-scope bronze sources

First-cohort and global catalog entries with `authentication: none` and access
mode other than `licensed_feed`, plus already-governed fixtures.

Public/no-credential catalog candidates include ARTG and public PBS surfaces,
TGA events, Health Canada DPD/NOC and provincial lists, EMA public downloads and
the Union Register, MHRA/NICE/NHS tariff public surfaces, WHO WLA, PMDA/NHI
public surfaces, Medsafe/PHARMAC public surfaces, Drugs@FDA, Orange Book,
openFDA, DailyMed, GSRS, and CMS public pages that require no credential.

Already-governed fixtures include Medsafe, PHARMAC, ARTG, PBS, DPD, NOC, MHRA,
NICE, EMA medicines, Union Register, PMDA, MHLW NHI, Drugs@FDA, and CMS Part D
synthetic fixtures.

## Out of scope

- Silver, gold, and platinum implementation (W-007).
- Credentialed or licensed-feed catalog sources (W-008), including NZULM bulk,
  NZHTS FHIR, AMT RF2, PBS embargo, dm+d/TRUD, EMA PMS FHIR, and SPOR.
- Live RxNorm/UMLS source payloads; those remain fixture-only under M-052.
- Clinical advice, global-coverage claims, or publishing restricted bytes.
- Treating Hugging Face as an ingest origin or as evidentiary truth.
- Expanding bronze completion beyond first-cohort/global public sources and
  already-governed fixtures.
- Requiring Iceberg or Marquez in the Python 3.14 core install.
- Production deployment credentials or claims that an object-store RPO/RTO has
  been qualified merely because its fail-closed contract passes locally.
- Actual Iceberg REST interoperability, Iceberg v3, DuckLake, lakeFS,
  cryptographic batch/Merkle attestations, and Delta/Hudi comparisons. These
  remain roadmap experiments and do not block Bronze completion.
- Graph, vector, OMOP, cross-source semantic normalization, and Rust
  terminology work. These consume Bronze or Silver outputs later.

## Functional requirements

- Classify every catalog source as bronze-in-scope, fixture-only, or excluded,
  with the exclusion reason recorded.
- Preserve source payload bytes (JSON/XML/CSV/ZIP/PDF or whatever arrived)
  byte-for-byte where rights permit. Produce source-faithful Parquet alongside
  payloads. Parsers will improve and be wrong; Parquet is not the payload.
- Emit a mandatory `acquisition_manifest.parquet` with one row per acquisition
  and an optional adapter-specific `source_records.parquet` with one row per
  source-native record. Preserve native names and types where feasible, attach
  record/acquisition/content/schema-fingerprint linkage, and do not perform
  cross-country semantic normalization in Bronze.
- Keep binary payloads byte-faithful. Extracted text, layout, tables, and chunks
  are separate derived datasets, never replacement-decoded source records.
- Keep regulatory, funding, formulary, and terminology independent in bronze.
- Record missing coverage as not covered, never as negative evidence.
- The immutable source payload and its content-addressed receipt are
  evidentiary truth; source-faithful Parquet is the portable analytical
  representation; table/catalogue layers are rebuildable metadata over those
  artefacts. DuckDB and LanceDB are derivatives.
- Bind Hugging Face as an archive/output boundary for lawful public bronze
  outputs only.
- Regenerate analytical Parquet deterministically from payloads and receipts
  without changing the acquisition ID.
- Apply schema-on-read where native source schemas vary.

### Pre-acquisition reuse gate (Must)

Before any acquire/download, including Drugs@FDA, Conductor and acquisition
code must:

1. Search local clones.
2. Search maintainer GitHub repositories declared in `.context/ecosystem.toml`.
3. Search Hugging Face, including
   `edithatogo/global-medicines-atlas-catalogue`.
4. Search the source registry (`medicine_source_catalog.json`).
5. Explicitly choose one of **reuse | link | mirror | extend | fork |
   acquire-new**.
6. Record that choice in receipts, OpenLineage, and track evidence.

acquire-new is last resort. Acquisition without the gate fails. This exists to
stop independent copies of the same public data. Reuse
`docs/ECOSYSTEM_REUSE.md` and `.context/ecosystem.toml`; do not invent a
parallel registry.

### Temporal identity (Must)

Every acquisition receipt distinguishes as independent fields, never collapsed:

1. source published / effective time — when the authority says the artefact is
   from or takes effect (source-native; missing is missing, not retrieved_at)
2. retrieved_at — when we fetched it
3. valid_from / valid_to — only where the source supplies validity; do not
   invent
4. immutable acquisition/version ID — stable identity for this acquisition
   (content-addressed and/or explicit version id); does not change if we
   re-parse

OpenLineage projection carries these as facets without replacing native
receipts.

### Admission-gated projection (Must)

Bronze landing follows one ordered lifecycle: verify the candidate bytes and
basic archive safety, persist the immutable payload and acquisition evidence,
append a `landed` admission event, inspect the staged payload, and append an
`accepted` or `quarantined` decision that supersedes the landed event. Parquet,
transformation-run receipts, Iceberg-ready metadata, and OpenLineage may be
created only after acceptance. Deterministic regeneration and recovery resolve
the latest durable admission decision and fail closed unless it is accepted.
Later automated or human decisions are new append-only events that reference
the decision they supersede; no admission record is overwritten.

### Separate Parquet products (Must)

The acquisition manifest records source, jurisdiction, acquisition/content
identity, temporal and rights/admission states, URI and media type, immutable
payload location/digest, parser availability, and reuse disposition. An adapter
may additionally emit source records with source-native fields and types plus
durable linkage. Each product has its own actual-byte transformation receipt,
Iceberg-ready identity, and OpenLineage event. Rebuilds reproduce only products
whose parser identity and adapter input are available. The canonical
medicine/product model remains Silver.

### Durable payload storage and sensitivity (Must)

All payload persistence resolves through one storage contract. Local
content-addressed filesystem storage is explicitly development-only. Durable
operation uses a versioned object-store boundary and is invalid unless its
policy and append-only receipt evidence versioning or Object Lock/WORM,
geographically and administratively independent replication, checksum
inventory cadence, restore-rehearsal cadence, and explicit RPO/RTO targets.
Landing retains a local materialization only for safe inspection and parsing;
the acquisition manifest and lineage identify the authoritative object URI.

Licensing rights and data sensitivity are independent. Every receipt carries a
fail-closed classification for intrinsic sensitivity, possible personal data,
and publication disposition. Public or redistributable rights do not override
a sensitivity review or publication prohibition.

### Iceberg-ready (Should)

Parquet files remain Parquet and remain valid without Iceberg. Define stable
table identities, namespaces, schemas, partition specifications, append-only
evolution rules, and snapshot-to-acquisition relationships so those files can
be registered as Iceberg tables. An Iceberg REST catalogue over bronze is
optional and lives behind an optional dependency extra. Iceberg row lineage,
branching, and tagging may be evaluated as catalogue aliases; Atlas
acquisition provenance remains authoritative. Do not migrate bronze
evidentiary truth into Iceberg metadata. Python 3.14 core must not require
Iceberg. Leave small tables unpartitioned. For configured large recurring
products, prefer a month transform over a source-release field and fall back
to acquisition month; optionally bucket high-volume native record identifiers.
Never partition on jurisdiction or source identifier already held constant by
table identity, or on mutable rights, admission, or review status.

### OpenLineage projection (Must)

Receipts remain richer native provenance. Emit OpenLineage-compatible Datasets,
Jobs, and Runs from receipts (source, storage, table-catalogue facets). The
source payload, source-faithful Parquet, and optional table/catalogue
representation are distinct datasets. Parquet derives from the payload via
ColumnLineage. Catalogue identity is a Symlinks alternative of Parquet, never
of the payload. Acquisition identity, temporal identity, reuse disposition,
rights state, and content digests are projected into facets. Do not collapse
payload identity into Parquet, Iceberg, or storage-table identity. No Marquez
in the default install. Use real OpenLineage field names (`eventType`,
`eventTime`, `producer`, `schemaURL`, `run`, `job`, `inputs`, `outputs`,
`storageLayer`, `fileFormat`, `symlinks`, `columnLineage`).

Acquisition and transformation are separate OpenLineage runs linked by the
standard Parent Run facet; their native append-only IDs remain explicit in GMA
run facets. Every GMA custom facet has a committed JSON Schema, uses the
OpenLineage `gma_` key-prefix convention, and resolves through a schema URL
pinned to an immutable commit. Use standard Catalog and Dataset Type facets,
and attach admission/integrity checks to the transformation payload input with
the standard Data Quality Assertions facet rather than a bespoke equivalent.

## Non-functional requirements

- Python 3.14 is the complete fallback; Mojo is optional and not required for
  bronze completion.
- Never inspect, commit, log, or publish credentials or restricted source bytes.
- Public ingest uses existing untrusted-acquisition controls (M-089).
  Truncated downloads, corrupt or malicious ZIP/tar payloads, decompression
  bombs, path traversal, MIME/extension mismatches, malformed XML/JSON/CSV,
  schema poisoning, collisions, unexpected source mutation, replayed
  acquisitions, checksum mismatches, and hostile filenames are inspected in
  place. Untrusted bytes are landed; processing is quarantined; forensic
  receipts are preserved. Iceberg metadata is not the integrity authority.
- Tests precede implementation in every phase.
- External publication remains a human gate.

### Source-family landing factory

The source catalogue is the authoritative work inventory. A deterministic
factory assigns every catalogue row to one of six reusable acquisition
families: static files, archive releases, paginated REST APIs, regulator search
exports, document collections, or reproducible manual exports. It emits a
standard adapter configuration, acquisition instructions, and exactly one
current disposition for every source.

Sparse source overrides may record a failure receipt, reuse reference, manual
procedure, or additional landing evidence. Overrides cannot move a
credentialed source into public acquisition. Unresolved rights fail closed,
and a blocker remains a queue item rather than landing evidence. The generated
JSON queue, JSON Schema, and Conductor Markdown projection are deterministic
and contain no Silver transformation contract.

## Acceptance

- Failing tests exist for the bronze contract before landing code is added.
- Acquisition without the reuse gate fails; each disposition is representable;
  acquire-new is last resort.
- Every catalogue source occurs exactly once in the generated source-family
  queue, and all landing dispositions and adapter families remain explicit even
  when their current count is zero.
- Temporal fields are distinct; substituting retrieved_at for published time
  fails; valid_* are absent when the source did not supply them; acquisition ID
  is immutable across Parquet regeneration.
- Every in-scope public/no-credential source and governed fixture has a bronze
  landing path, payload, receipt, rights expression, and source-faithful Parquet
  identity, or an explicit documented blocker that is not treated as completion.
- Credentialed and restricted sources are excluded with durable catalog evidence.
- Hugging Face is referenced only as an archive boundary.
- Silver/gold/platinum code is absent from this track's implementation.

## External gates

- Hugging Face archival of public data (sibling track / maintainer-approved
  publication path).
- Source-by-source rights review before any source-derived archive payload.
- Maintainer approval of external dataset publication.
