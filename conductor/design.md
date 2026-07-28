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
