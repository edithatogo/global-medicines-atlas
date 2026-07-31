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
    OSF["OSF protocol and preregistration"]
    RECEIPT["Checksums, licence and provenance"]

    COMMIT --> CATALOG
    COMMIT --> BENCH
    CATALOG --> HF
    BENCH --> HF
    HF --> ZENODO
    OSF --> ZENODO
    COMMIT --> OSF
    CATALOG --> RECEIPT
    BENCH --> RECEIPT
```

The source catalog and lawful synthetic benchmark are separate products with
separate licences and identifiers. Rights-restricted medicine payloads remain
outside public publication packages. Creating external records or publishing a
release remains an explicit maintainer gate.

The Phase 1 research contract is the machine-readable
`research/protocol/academic-protocol-v1.json`, validated by
`schemas/academic-protocol-v1.json` and rendered offline to
`docs/research/academic-protocol.md`. It binds the governed source catalog and
M-090 comparison-validity vocabulary to the protocol/methods work in GitHub
[#67](https://github.com/edithatogo/global-medicines-atlas/issues/67).

The Phase 3 OSF rehearsal is generated from
`research/preregistration/osf-preregistration-v1.json` into a committed,
checksum-addressed submission directory. The builder performs no network or
platform action; the validator fails closed unless submission remains offline
and maintainer review remains incomplete. Protocol, analysis plan, amendment
history, deviation register, citations, and data-management and ethics
statements are separate attachments so their identities remain auditable.

```mermaid
flowchart LR
    CONTRACT["Strict preregistration contract"]
    SOURCE["Protocol and analysis attachments"]
    BUILD["Deterministic offline builder"]
    BUNDLE["OSF-ready draft bundle"]
    VERIFY["Schema and checksum validator"]
    GATE{"Maintainer and rights approval"}
    OSF["External OSF registration"]

    CONTRACT --> BUILD
    SOURCE --> BUILD
    BUILD --> BUNDLE
    BUNDLE --> VERIFY
    VERIFY --> GATE
    GATE -->|pending| BUNDLE
    GATE -->|explicit approval only| OSF
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
provenance, credentials and already-published datasets.
