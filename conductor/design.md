# System Design

## Architectural Position

The local workspace is the canonical global monorepository. `nzmedicines` becomes a preserved upstream history, NZULM/NZMT FHIR adapter, and fixture source. Portable canonical data remains separate from source-native FHIR projections and derived search indexes.

```mermaid
flowchart LR
    subgraph Sources["Jurisdiction source systems"]
        NZ["NZULM/NZMT, Medsafe, PHARMAC, NZF"]
        AU["TGA and PBS"]
        US["FDA, CMS and RxNorm/RxNav"]
        GL["Additional regulators and funders"]
    end

    subgraph Acquisition["Governed acquisition"]
        REG["Source and licence registry"]
        ADP["Versioned source adapters"]
        SNAP["Immutable source snapshots"]
    end

    subgraph Canonical["Canonical evidence core"]
        MED["Medicine and product identities"]
        ASSERT["Regulatory and funding assertions"]
        MAP["Cross-jurisdiction mappings"]
        PROV["Provenance, coverage and uncertainty"]
    end

    subgraph Engines["Execution and storage"]
        MOJO["Mojo kernels"]
        PY["Python 3.14 reference fallback"]
        POLARS["Polars and Arrow"]
        PARQUET["Parquet"]
        DUCK["DuckDB"]
        LANCE["LanceDB derived index"]
        LEX["Optional Tantivy lexical index"]
    end

    subgraph Products["Reviewed outputs"]
        CLI["CLI and read-only API"]
        ATLAS["Global comparison atlas"]
        HF["Hugging Face dataset and Space"]
        RELEASE["Signed release packages"]
    end

    Sources --> REG
    REG --> ADP
    ADP --> SNAP
    SNAP --> MED
    SNAP --> ASSERT
    MED --> MAP
    ASSERT --> PROV
    MAP --> PROV
    MED --> POLARS
    ASSERT --> POLARS
    MOJO <--> PY
    MOJO --> POLARS
    PY --> POLARS
    POLARS --> PARQUET
    PARQUET --> DUCK
    PARQUET --> LANCE
    PARQUET --> LEX
    DUCK --> CLI
    LANCE --> CLI
    LEX --> CLI
    CLI --> ATLAS
    PROV --> HF
    PROV --> RELEASE
```

## NZ Adapter and Migration Boundary

```mermaid
flowchart TB
    GH["Original nzmedicines Git history"]
    BUNDLE["Verified complete Git bundle"]
    SNAPSHOT["Immutable upstream snapshot at 6a8ecfae"]
    LOCAL["Existing local NZULM/NZMT assets"]
    INVENTORY["File-level reconciliation inventory"]
    ADAPTER["NZ source adapter"]
    FIXTURES["FHIR and NZMT fixtures"]
    PROJECTION["Validated FHIR projection"]
    CANON["Canonical medicines evidence model"]
    MIRROR["Compatibility mirror and migration notice"]

    GH --> BUNDLE
    GH --> SNAPSHOT
    SNAPSHOT --> INVENTORY
    LOCAL --> INVENTORY
    INVENTORY --> ADAPTER
    INVENTORY --> FIXTURES
    ADAPTER --> CANON
    FIXTURES --> PROJECTION
    PROJECTION --> CANON
    BUNDLE --> MIRROR
    INVENTORY --> MIRROR
```

The upstream snapshot is evidence, not the editable implementation surface. Adapted code and schemas live in first-party package paths; retained upstream resources remain traceable to their original commit and file.

## Medicine Evidence Model

```mermaid
erDiagram
    JURISDICTION ||--o{ AUTHORITY : contains
    AUTHORITY ||--o{ SOURCE : publishes
    SOURCE ||--o{ SOURCE_RELEASE : versions
    SOURCE_RELEASE ||--o{ SOURCE_RECORD : contains
    MEDICINE ||--o{ PRODUCT : has
    MEDICINE ||--o{ IDENTIFIER : identified_by
    PRODUCT ||--o{ IDENTIFIER : identified_by
    SOURCE_RECORD }o--|| MEDICINE : asserts_about
    SOURCE_RECORD }o--o| PRODUCT : optionally_asserts_about
    SOURCE_RECORD ||--o{ REGULATORY_ASSERTION : supports
    SOURCE_RECORD ||--o{ FUNDING_ASSERTION : supports
    MEDICINE }o--o{ MEDICINE : mapped_to
    PRODUCT }o--o{ PRODUCT : mapped_to
    MAPPING ||--o{ REVIEW : evaluated_by
    ANALYTICAL_RUN ||--o{ OUTPUT : produces
    SOURCE_RELEASE ||--o{ ANALYTICAL_RUN : enters
```

## RxNav-in-a-Box Boundary

```mermaid
sequenceDiagram
    participant Adapter as Terminology adapter
    participant Health as Local health check
    participant RxNav as RxNav-in-a-Box
    participant Cache as Governed local cache
    participant Fallback as Deterministic fallback
    participant Review as Mapping review queue

    Adapter->>Health: Check configured local service
    alt Service healthy
        Adapter->>RxNav: Read-only concept or approximate-match query
        RxNav-->>Adapter: RxCUI candidates
        Adapter->>Cache: Record derived result and provenance
    else Service unavailable
        Adapter->>Fallback: Run offline fixture or deterministic local matcher
        Fallback-->>Adapter: Classified fallback candidates
    end
    Adapter->>Review: Emit candidates with method and confidence
```

## Work Traceability

```mermaid
flowchart LR
    REQ["MoSCoW requirement"]
    DESIGN["Design component or ADR"]
    TRACK["Conductor track"]
    ISSUE["GitHub parent issue"]
    SUB["GitHub subissue"]
    TEST["Executable acceptance evidence"]
    RECEIPT["Evidence ledger or release receipt"]

    REQ --> DESIGN
    DESIGN --> TRACK
    TRACK <--> ISSUE
    ISSUE --> SUB
    SUB --> TEST
    TEST --> RECEIPT
    RECEIPT --> TRACK
```

## Deployment Boundary

- Windows development uses Python directly and Mojo through WSL.
- Linux CI is authoritative for Mojo.
- DuckDB, LanceDB, and optional lexical indexes are regenerable from portable governed artifacts.
- Public datasets contain only reviewed redistributable material.
- Credentials, restricted terminology payloads, and local source caches remain outside Git.

## Bronze Internal Strata and Medallion Boundary

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
over B1/B2, not a fourth evidentiary source of truth. Projections may aid
inspection, recovery, lineage, or querying, but cannot replace the B1 event
history or B2 evidence identity. Silver remains source-faithful typed or
harmonised structures; Gold remains cross-jurisdiction matched evidence;
Platinum remains products and presentation.

```mermaid
flowchart TB
    B0["B0 Source Index<br/>versioned source surfaces"]
    B1["B1 Acquisition Metadata<br/>append-only events and receipts"]
    B2["B2 Raw Evidence<br/>immutable bytes or rights-constrained reference"]
    PROJ["Rebuildable Bronze projections<br/>Source-faithful Parquet · archive-member manifests<br/>OpenLineage · Iceberg · DuckDB · catalogues"]
    QUAL["Three-strata qualification<br/>corpus landing · delete-and-rebuild · fail-closed gate probes<br/>three_strata_qualified independent of bronze_mature; see quality/qualifications/bronze-three-strata-qualification.json"]
    SILVER["Silver<br/>source-faithful typed or harmonised structures"]
    GOLD["Gold<br/>cross-jurisdiction matched evidence"]
    PLATINUM["Platinum<br/>products and presentation"]

    B0 -->|select and identify| B1
    B1 -->|records identity and authority| B2
    B1 --> PROJ
    B2 --> PROJ
    QUAL -.->|proves| B0
    QUAL -.->|proves| B1
    QUAL -.->|proves| B2
    QUAL -.->|deletes and rebuilds| PROJ
    B1 --> SILVER
    B2 --> SILVER
    SILVER --> GOLD
    GOLD --> PLATINUM
```

Within B1, authority flows only from native append-only records. The portable
manifest is a deterministic query view; OpenLineage and table catalogues are
interoperability projections over that view and the same native evidence.

```mermaid
flowchart LR
    RECEIPT["SourceReceipt<br/>native authority"]
    EVENT["AcquisitionEvent<br/>native authority"]
    ADMISSION["Admission history<br/>native authority"]
    RAW["B2 object<br/>digest + immutable locator"]
    MANIFEST["B1 acquisition manifest<br/>deterministic projection"]
    INTEROP["OpenLineage + catalogues<br/>interoperability projections"]

    RECEIPT --> MANIFEST
    EVENT --> MANIFEST
    ADMISSION --> MANIFEST
    RAW -->|"reference only"| MANIFEST
    MANIFEST --> INTEROP
```

## Single-Maintainer Context Control Plane

```mermaid
flowchart LR
    AGENT["AGENTS.md invariants and human gates"]
    MANIFEST[".context/project.toml"]
    CONDUCTOR["Requirements, design, tracks, and evidence"]
    VALIDATOR["Context-drift validator"]
    HARNESS["Test-Goblin profiles"]
    SECURITY["Zizmor, dependency audit, CodeQL, and SBOM"]
    PR["Sole-maintainer pull request"]
    RECEIPT["Hosted checks and durable receipts"]

    AGENT --> VALIDATOR
    MANIFEST --> VALIDATOR
    CONDUCTOR --> VALIDATOR
    VALIDATOR --> HARNESS
    HARNESS --> PR
    SECURITY --> PR
    PR --> RECEIPT
    RECEIPT --> CONDUCTOR
```

Automation supplies independent evidence, not a fictional independent
reviewer. Credentials, licensing, publication, release, archival, and
consequential-interpretation decisions remain explicit maintainer gates.

## Version and Maturity Control Plane

```mermaid
flowchart TB
    ROADMAP["Versioned roadmap v0.1 to v1.0"]
    MOSCOW["MoSCoW requirements"]
    MODEL["M0 to M5 maturity model"]
    TRACKS["Non-overlapping Conductor tracks"]
    ISSUES["GitHub parent issues and subissues"]
    HARNESS["Tests, security, coverage and performance"]
    RECEIPTS["Source, build and release receipts"]
    GATE{"Release gate satisfied?"}
    RELEASE["Promoted version"]
    HOLD["Remain at current maturity"]

    ROADMAP --> MOSCOW
    MOSCOW --> TRACKS
    MODEL --> TRACKS
    TRACKS <--> ISSUES
    ISSUES --> HARNESS
    HARNESS --> RECEIPTS
    RECEIPTS --> GATE
    GATE -->|Yes| RELEASE
    GATE -->|No| HOLD
    HOLD --> TRACKS
```

## Product Delivery and Hardening

```mermaid
flowchart LR
    SOURCES["Receipt-backed jurisdiction sources"]
    TEMPORAL["Bitemporal evidence and conflicts"]
    MATCH["Reviewable medicine mappings"]
    QUERY["DuckDB and portable query layer"]
    API["Versioned read-only API and CLI"]
    ATLAS["Accessible comparison atlas"]
    PUBLICATION["Governed Parquet and Hugging Face package"]
    OBSERVE["Source health and schema drift"]
    QUALIFY["Clean-room reproduction and stable-v1 qualification"]

    SOURCES --> TEMPORAL
    TEMPORAL --> MATCH
    TEMPORAL --> QUERY
    MATCH --> QUERY
    QUERY --> API
    API --> ATLAS
    QUERY --> PUBLICATION
    OBSERVE --> SOURCES
    OBSERVE --> API
    PUBLICATION --> QUALIFY
    ATLAS --> QUALIFY
```

## Source Information and Adapter Capability Contract

```mermaid
flowchart LR
    AUTHORITY["Authoritative resource"]
    CATALOG["Versioned source-information schema"]
    DOMAINS["Information domains and status semantics"]
    CAPABILITY["Unified adapter capability registry"]
    ACQUIRE["Bounded acquisition"]
    PARSE["Source-native parser"]
    PROJECT["Canonical schema v2 projection"]
    RECEIPT["Immutable health and transformation receipts"]

    AUTHORITY --> CATALOG
    CATALOG --> DOMAINS
    CATALOG --> CAPABILITY
    CAPABILITY --> ACQUIRE
    ACQUIRE --> PARSE
    PARSE --> PROJECT
    ACQUIRE --> RECEIPT
    PARSE --> RECEIPT
    PROJECT --> RECEIPT
```

Each catalog entry labels the entities and information it actually contains.
Regulatory status, funding eligibility, prices, terminology relationships and
safety information remain distinct domains. Capability declarations distinguish
synthetic fixtures from live acquisition and production qualification.

## Canonical Discovery and Consumer Boundary

```mermaid
flowchart LR
    NATIVE["Source-native records"]
    SCHEMA["Canonical medicine schema v2"]
    DB["Versioned DuckDB projection"]
    SEARCH["Bounded lexical and identifier discovery"]
    API["Versioned API and OpenAPI contract"]
    CLI["CLI"]
    ATLAS["Accessible atlas"]
    PACKAGE["Clean-installed wheel or sdist"]

    NATIVE --> SCHEMA
    SCHEMA --> DB
    DB --> SEARCH
    SEARCH --> API
    API --> CLI
    API --> ATLAS
    PACKAGE --> API
```

Discovery returns native and canonical identifiers, match method, provenance
and jurisdiction scope. SQL keyset pagination and database schema metadata keep
large queries bounded and migration-aware.

## Comparison Validity Boundary

```mermaid
flowchart LR
    LEFT["Source-native entity and status A"]
    RIGHT["Source-native entity and status B"]
    MAP["Typed mapping and normalization evidence"]
    SCOPE["Indication, population, time and benefit scope"]
    VALID{"Comparison validity"}
    OK["Valid comparison"]
    PART["Partial comparison with material mismatch"]
    NO["Unavailable or inappropriate comparison"]

    LEFT --> MAP
    RIGHT --> MAP
    MAP --> SCOPE
    SCOPE --> VALID
    VALID --> OK
    VALID --> PART
    VALID --> NO
```

Comparison validity is an explicit output, not an inference from name or
terminology similarity. The system retains source-native legal and funding
meanings and must not imply therapeutic equivalence, substitutability or equal
benefit when entity, indication, population, temporal or benefit-design scopes
do not support that conclusion.

## Governed Research and Dataset Identity

```mermaid
flowchart LR
    COMMIT["GitHub commit and release"]
    CATALOG["Lawful source-catalog dataset"]
    BENCH["Synthetic matching benchmark"]
    HF["Hugging Face dataset card and Croissant"]
    ZENODO["Zenodo concept DOI and version DOI"]
    PROTOCOL["In-repo protocol artefacts"]
    RECEIPT["Checksums, licence and provenance"]

    COMMIT --> CATALOG
    COMMIT --> BENCH
    COMMIT --> PROTOCOL
    CATALOG --> HF
    BENCH --> HF
    HF --> ZENODO
    PROTOCOL --> ZENODO
    CATALOG --> RECEIPT
    BENCH --> RECEIPT
```

The source catalog and lawful synthetic benchmark are separate products with
separate licences and identifiers. Rights-restricted medicine payloads remain
outside public publication packages. Creating external records or publishing a
release remains an explicit maintainer gate. OSF is deprecated and is not a
live publication identity.

The Phase 1 research contract is the machine-readable
`research/protocol/academic-protocol-v1.json`, validated by
`schemas/academic-protocol-v1.json` and rendered offline to
`docs/research/academic-protocol.md`. It binds the governed source catalog and
M-090 comparison-validity vocabulary to the protocol/methods work in GitHub
[#67](https://github.com/edithatogo/global-medicines-atlas/issues/67).

The historical Phase 3 OSF-format rehearsal remains in
`research/preregistration/` as a superseded offline artefact. It is not a live
submission path. The persistent public identity is the in-repo protocol plus
Zenodo DOI `10.5281/zenodo.21734811`.

```mermaid
flowchart LR
    CONTRACT["Strict preregistration contract"]
    SOURCE["Protocol and analysis attachments"]
    BUILD["Deterministic offline builder"]
    BUNDLE["In-repo rehearsal bundle"]
    VERIFY["Schema and checksum validator"]
    ZENODO["Zenodo archival identity"]

    CONTRACT --> BUILD
    SOURCE --> BUILD
    BUILD --> BUNDLE
    BUNDLE --> VERIFY
    VERIFY --> ZENODO
```

## Untrusted Acquisition and Failure Containment

```mermaid
flowchart LR
    NETWORK["Approved authoritative destination"]
    EGRESS{"Scheme, redirect, DNS and IP policy"}
    FETCH["Bounded fetch and per-host resilience"]
    QUARANTINE["Immutable quarantine and digest"]
    PARSE["Bounded fail-closed parser"]
    NORMAL["Validated source-native records"]
    CANON["Canonical projection"]
    RELEASE{"Rights, licence, provenance and approval gate"}
    PUBLIC["Lawful publication artifact"]
    INCIDENT["Quarantine, revoke, withdraw and replace"]

    NETWORK --> EGRESS
    EGRESS -->|allow| FETCH
    EGRESS -->|reject| INCIDENT
    FETCH --> QUARANTINE
    QUARANTINE --> PARSE
    PARSE -->|valid| NORMAL
    PARSE -->|invalid or excessive| INCIDENT
    NORMAL --> CANON
    CANON --> RELEASE
    RELEASE -->|approved| PUBLIC
    RELEASE -->|blocked| INCIDENT
```

Acquired bytes are untrusted even when an authority is official. Logs retain
source IDs, digests and bounded outcomes but redact credentials, query strings
and source payloads. Compromise recovery covers upstream data, signing
provenance, credentials and already-published datasets. Bronze inspects
truncated bodies, hostile archives, media mismatches, poison identity fields,
replays, and checksum failures without rewriting landed bytes; admission
quarantines processing and keeps the payload as forensic evidence.

## Medallion Datahouse

The medicines comparison product is implemented as a four-layer medallion
datahouse. Bronze is the current completion horizon. Silver, gold, and platinum
are sketched so later tracks have a stable boundary; they are not implemented
by the bronze-completion track.

```mermaid
flowchart TB
    subgraph Sources["Authoritative sources"]
        PUB["Public / no-credential catalog sources"]
        FIX["Already-governed fixtures"]
        REST["Credentialed or restricted sources"]
    end

    subgraph Bronze["Bronze — current completion horizon"]
        GATE["Pre-acquisition reuse gate"]
        INGEST["Governed public ingest"]
        PAYLOAD["Immutable source payload"]
        RECEIPT["Content-addressed receipts"]
        TIME["Temporal identity"]
        MANIFEST["acquisition_manifest.parquet — one acquisition row"]
        RECORDS["source_records.parquet — optional native records"]
        CATALOGUE["Rebuildable table/catalogue metadata"]
    end

    subgraph Later["Later layers — sketched only"]
        SILVER["Silver: source-faithful normalized tables"]
        GOLD["Gold: matched cross-jurisdiction evidence"]
        PLATINUM["Platinum: comparison products"]
    end

    subgraph Derivatives["Not bronze"]
        DUCK["DuckDB analytical views"]
        LANCE["LanceDB / optional indexes"]
    end

    subgraph Archive["Output boundary"]
        HF["Hugging Face public bronze archive"]
    end

    PUB --> GATE
    GATE -->|"reuse / link / mirror / extend / fork / acquire-new"| INGEST
    FIX --> PAYLOAD
    REST -.->|"catalogued, out of this horizon"| PAYLOAD
    INGEST --> PAYLOAD
    PAYLOAD --> RECEIPT
    PAYLOAD --> TIME
    RECEIPT --> MANIFEST
    TIME --> MANIFEST
    PAYLOAD --> RECORDS
    MANIFEST --> CATALOGUE
    RECORDS --> CATALOGUE
    CATALOGUE --> SILVER
    MANIFEST --> SILVER
    RECORDS --> SILVER
    SILVER --> GOLD
    GOLD --> PLATINUM
    MANIFEST --> DUCK
    RECORDS --> DUCK
    MANIFEST --> LANCE
    RECORDS --> LANCE
    PAYLOAD --> HF
    MANIFEST --> HF
    RECORDS --> HF
```

Hugging Face is an archive and publication boundary for reviewed public bronze
outputs. It is not an ingest origin and not the source of truth. The immutable
source payload and its content-addressed receipt are evidentiary truth;
source-faithful Parquet is the portable analytical representation;
table/catalogue layers are rebuildable metadata over those artefacts. The
sibling Hugging Face archival track owns remote publication mechanics; this
design consumes that boundary.

### Bronze landing

Bronze landing preserves the bytes a source published together with a
content-addressed receipt. That payload-and-receipt pair is evidentiary truth.
Source-faithful Parquet is produced alongside it as two explicit analytical
products: mandatory `acquisition_manifest.parquet`, with one row per
acquisition, and optional adapter-specific `source_records.parquet`, with one
row per source-native record. The latter preserves native names and types where
feasible and carries record, acquisition, content, and schema-fingerprint
linkage without cross-country semantic normalization. Binary documents remain
immutable payloads; extracted text, layout, tables, and chunks are separate
derived datasets. Regulatory, funding, formulary, and terminology land in
independent partitions or tables. Missing coverage is recorded as not covered,
never as unapproved or unfunded. Canonical medicine and product normalization
remains a Silver responsibility.

```mermaid
flowchart LR
    CATALOG["medicine_source_catalog.json"]
    ECO[".context/ecosystem.toml"]
    LOCAL["Local clones"]
    GH["Maintainer GitHub repos"]
    HFSEARCH["Hugging Face including catalogue"]
    GATE{"reuse / link / mirror / extend / fork / acquire-new"}
    FETCH["Bounded public ingest"]
    FIXTURE["Governed fixture bytes"]
    PAYLOAD["Immutable payload bytes"]
    RECEIPT["Content-addressed receipt"]
    TIME["source published, retrieved_at, valid_from/to, acquisition_id"]
    MANIFEST["acquisition_manifest.parquet"]
    RECORDS["optional source_records.parquet"]
    OL["OpenLineage projection"]
    ICE["Iceberg-ready table identity"]
    HF["Hugging Face archive boundary"]
    BLOCK["Remain catalogued; no bronze completion claim"]

    CATALOG --> GATE
    ECO --> GATE
    LOCAL --> GATE
    GH --> GATE
    HFSEARCH --> GATE
    GATE -->|acquire-new last resort| FETCH
    GATE -->|reuse or link existing copy| PAYLOAD
    GATE -->|credentialed or restricted| BLOCK
    FETCH --> PAYLOAD
    FIXTURE --> PAYLOAD
    PAYLOAD --> RECEIPT
    PAYLOAD --> TIME
    RECEIPT --> MANIFEST
    TIME --> MANIFEST
    PAYLOAD --> RECORDS
    RECEIPT --> OL
    PAYLOAD --> OL
    MANIFEST --> OL
    RECORDS --> OL
    ICE --> OL
    MANIFEST --> ICE
    RECORDS --> ICE
    MANIFEST --> HF
    RECORDS --> HF
```

### Pre-acquisition reuse gate

Before any download, including Drugs@FDA, Conductor and acquisition code search
local clones, maintainer GitHub repositories, Hugging Face (including
`edithatogo/global-medicines-atlas-catalogue` at the pinned catalogue
revision), and the source registry. They then choose exactly one of
**reuse | link | mirror | extend | fork | acquire-new**. The choice is recorded
on the receipt, in OpenLineage facets, and in track evidence. acquire-new is
last resort when no payload copy exists. Acquisition without this gate fails.
This gate exists to stop independent repositories accumulating copies of the
same public data. It reuses `docs/ECOSYSTEM_REUSE.md` and
`.context/ecosystem.toml` rather than a parallel registry.

### Temporal identity

Every acquisition receipt distinguishes, as independent fields:

1. source published / effective time (source-native; missing stays missing)
2. retrieved_at (when we fetched)
3. valid_from / valid_to only where the source supplied validity
4. immutable acquisition/version ID (content-addressed; unchanged by re-parse)

Substituting retrieved_at for published time is forbidden. OpenLineage carries
these as facets without replacing native receipts.

Current bronze-completion scope is first-cohort and global catalog sources whose
authentication is none and whose access is not a licensed feed, plus already
governed fixtures (Medsafe, PHARMAC, ARTG, PBS, DPD/NOC, MHRA/NICE, EMA/Union
Register, PMDA/NHI, Drugs@FDA, CMS Part D, and related synthetic fixtures).
Credentialed catalog entries remain out of this horizon, including NZULM bulk,
NZHTS FHIR, AMT RF2, PBS embargo, dm+d/TRUD, EMA PMS, and SPOR. RxNorm/UMLS
source payloads remain fixture-only because restricted terminology bytes are
not public bronze.

Source landing is driven by `medicine_source_catalog.json`, not a handwritten
module per source. `source_landing_factory.py` maps catalogue metadata into six
standard acquisition families and generates the complete machine-readable
work queue plus its schema and Conductor projection. The queue assigns exactly
one fail-closed disposition to each source and carries reusable instructions,
endpoint, formats, pagination shape, evidence scope, next action, and priority.
Exceptional failure, reuse, or manual evidence lives in a sparse versioned
override file. These are acquisition configurations: the existing reuse,
rights, credential, untrusted-byte admission, and content-addressed receipt
gates remain authoritative, and no Silver normalization is generated.

Bronze table identity already includes jurisdiction and source identifier, so
those constants are not repeated as physical partition keys. Small tables are
unpartitioned. A configured large recurring product is partitioned by
source-release month when the source supplies a temporal field, otherwise by
acquisition month; high-volume record identifiers may additionally use a
bounded bucket transform. Mutable rights, admission, and review state are
never physical partitions. Each landed file carries source-native identifiers,
retrieval and effective dates, receipt digest, uncertainty, and an explicit
rights expression. The same acquisition carries an independent sensitivity
classification: intrinsic sensitivity, possible personal data, and
publication disposition are never inferred from licensing rights.

Authoritative payload persistence is storage-neutral. Development uses a
content-addressed local filesystem. Durable operation writes the same content
key to a versioned or Object-Locked primary object store and at least one
geographically and administratively independent replica, then records provider
version identities in an append-only storage receipt. Landing uses a local
materialization for inspection and source parsing, while the acquisition
manifest and OpenLineage payload dataset retain the authoritative object URI.
Periodic checksum inventories read every physical copy; durable restore
rehearsals read the policy-matching independent replica into an empty target,
hash the bytes, and compare measured
elapsed time with the declared RTO. A durable policy is invalid without an
explicit RPO, RTO, inventory cadence, and rehearsal cadence.
Python 3.14 is the complete fallback path. DuckDB and LanceDB may read bronze
Parquet; they do not store bronze evidentiary truth. Iceberg REST registration
is optional and must not be imported by Python 3.14 core. Iceberg-ready
metadata records namespace `bronze`, explicit temporal/bucket transforms when
scale evidence activates them, append-only schema evolution, and snapshot
aliases bound to `acquisition_id`. Iceberg metadata is rebuildable catalogue
state; payload bytes and receipts remain evidentiary truth.

### Lineage and identity graph

Native receipts remain authoritative. OpenLineage is a projection. The source
payload, source-faithful Parquet, and optional Iceberg-ready catalogue are
three datasets. ColumnLineage records Parquet as derived from payload bytes.
Symlinks record the catalogue as an alternative identity of Parquet, never of
the payload. Acquisition identity, clocks, reuse disposition, rights, and
content digests appear as facets.

Acquisition and transformation are distinct OpenLineage runs with deterministic
UUIDs over their native append-only IDs; the standard Parent Run facet links
transformation back to acquisition. Standard Dataset Type facets classify
source, payload, Parquet, and catalogue datasets; the standard Catalog facet
describes the optional Iceberg catalogue; and the payload transformation input
carries standard Data Quality Assertions derived from durable admission and
integrity results. GMA-only facets use `gma_`-prefixed keys and committed JSON
Schemas under `schemas/openlineage/`, with raw GitHub schema URLs pinned to the
commit containing those schemas rather than `blob/main` or another branch.

```mermaid
flowchart LR
    SRC["gma.source"]
    PAY["gma.payload content_id"]
    PQ["gma.parquet analytical digest"]
    CAT["gma.catalogue Iceberg-ready table"]

    SRC --> PAY
    PAY -->|"ColumnLineage DIRECT IDENTITY"| PQ
    PQ -->|"Symlinks TABLE"| CAT
    CAT -->|"Symlinks LOCATION"| PQ
```

### Later layers (sketch only)

```mermaid
flowchart TB
    BRONZE["Bronze Parquet and receipts"]
    SILVER["Silver: typed source-faithful tables, still independent dimensions"]
    GOLD["Gold: reviewable mappings, confidence, comparison validity"]
    PLATINUM["Platinum: API, CLI, atlas, governed publication products"]

    BRONZE --> SILVER
    SILVER --> GOLD
    GOLD --> PLATINUM
```

Silver may normalize names, units, and identifiers while retaining every
source-native key. Gold may emit cross-jurisdiction mapping candidates with
M-090 validity states. Platinum may serve comparison products. None of those
behaviours are in the bronze-completion track.

Actual Iceberg REST and Iceberg v3 interoperability, DuckLake, lakeFS-style
workflows, cryptographic batch or Merkle attestations, and Delta/Hudi
comparisons remain non-blocking experiments. Graph, vector, OMOP, semantic
normalization, and Rust terminology capabilities consume Bronze or Silver
outputs later and are not Bronze qualification evidence.
