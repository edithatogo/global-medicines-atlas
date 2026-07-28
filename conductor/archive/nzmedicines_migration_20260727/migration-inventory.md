# Migration Inventory

**Upstream repository:** `https://github.com/edithatogo/nzmedicines`  
**Upstream commit:** `6a8ecfae67f15d635750d11d5f446b93d76c1865`  
**Status:** Complete metadata-level inventory and disposition reconciliation.

## Inventory Artefacts

- Machine-readable manifest: [`nz-asset-inventory.json`](./nz-asset-inventory.json)
- Review matrix: [`nz-asset-disposition.csv`](./nz-asset-disposition.csv)
- Deterministic generator: `scripts/generate_nz_asset_inventory.py`
- Completeness tests: `tests/test_nz_asset_inventory.py`

The inventory contains 162 unique assets: 137 local assets and all 25 files
from the preserved upstream snapshot. Local source payloads were inventoried
from filesystem metadata to avoid hydrating restricted or unrelated OneDrive
content. All upstream files were resident and received individual SHA-256
digests.

| Disposition | Assets | Meaning in this migration |
|---|---:|---|
| `adopted` | 108 | Source-native NZULM/NZMT, Medsafe, subsidy, mapping, or governance input |
| `adapted` | 24 | Existing maintainer-owned code, tests, documentation, database, or derived export to evolve |
| `fixture` | 25 | Upstream FHIR/index examples and small local Medsafe samples retained for deterministic tests |
| `superseded` | 3 | Duplicate release archives or upstream workflow retained only for restoration/provenance |
| `excluded` | 2 | Ephemeral SQLite WAL/SHM sidecars |

## Disposition Vocabulary

- `adopted`: used directly in the first-party implementation.
- `adapted`: transformed while preserving provenance.
- `superseded`: richer local implementation exists.
- `fixture`: retained for deterministic tests or examples.
- `excluded`: not incorporated, with a recorded reason.

## Reconciled Families

| Family | Disposition | Reconciliation result |
|---|---|---|
| Local NZMT hierarchy and relationship dumps | adopted, local-only review required | Canonical source input for MP, MPUU, MPP, TP, TPUU, TPP, CTPP, substance, pack, container, and relationship structures |
| Local embedded Medsafe tables | adopted, local-only review required | Regulatory input; remains distinct from funding and subsidy assertions |
| Local subsidy, prescribing, HML, and PS tables | adopted, local-only review required | Funding/formulary input; remains distinct from Medsafe registration |
| Local ATC, SNOMED CT, GTIN, pharmacode, and related-ID mappings | adopted, local-only review required | Mapping input with source-native identifiers retained |
| Local governance, schema, release, and ownership documents | adopted, local-only review required | Rights, schema, and interpretation evidence; no public redistribution inferred |
| Existing NZULM ingestor and integration code | adapted | Maintainer-owned implementation to evolve behind canonical source contracts |
| Existing Medsafe exports and databases | adapted | Derived parity/migration surfaces, not authoritative source copies |
| `medications/*.json` | fixture | FHIR projection and adapter parity examples |
| generated index files | fixture | Golden inputs for deterministic regeneration |
| `substance/*.json` | fixture | Projection parity examples against broader local substance tables |
| `document-references/*.json` | fixture | Structure-only fixtures; referenced NZF content requires separate rights/currentness review |
| `.github/workflows/regenerate-indexes.yml` | superseded | Preserved for provenance; target workflow must be tested and supply-chain hardened |
| `readme.md` | adapted | Mapping rationale retained without unsupported conformance/currentness claims |

## Local Capability Evidence

The local workspace contains:

- `terminology/nzulm/ingestor.py`;
- the visible 2023 NZULM/NZMT dump and documentation family;
- MP, MPUU, MPP, TP, TPUU, TPP and CTPP tables;
- Medsafe product, application, ingredient, package, route and status tables;
- SNOMED CT, ATC, GTIN, pharmacode and relationship tables;
- subsidy, prescribing, HML, and PS funding/formulary tables;
- existing SQLite, CSV, Parquet, XLSX, comparison, script, documentation, and
  test surfaces;
- first-party provenance-bearing NZ FHIR adapter code and tests.

The upstream FHIR artifacts are therefore treated as fixture and projection
inputs. They do not supersede the richer local source ingestion surface.

## Conflicts and Local-Only Enhancements

| Finding | Resolution |
|---|---|
| The local release is a static 2023 corpus | Retain for reproducibility and adapter development; prohibit current-status claims until a refreshed official source is onboarded |
| The upstream FHIR repository contains sparse examples rather than complete national coverage | Retain as fixtures; use local NZMT hierarchy and status tables as source inputs |
| Medsafe information occurs both inside NZULM tables and in later derived exports | Preserve both; require source date/provenance and parity checks before choosing an assertion |
| Regulatory and subsidy/formulary data coexist in the local corpus | Model them as separate assertion classes and never infer one from the other |
| NZF DocumentReference fixtures point to separately governed content | Preserve structure only; do not redistribute or treat linked content as captured evidence |
| `nzulm_2023.zip` exists at two paths | Preserve both pending digest comparison; extracted source family is the working input |
| `nzulm.db` and Medsafe SQLite files are derived/opaque | Use as migration and parity inputs; regenerate canonical Parquet/DuckDB outputs from governed sources |
| 132 of 137 local assets are OneDrive placeholders | Keep inventory metadata-only; hydrate narrowly only when an approved implementation/test needs payload content |
| Upstream index regeneration uses an unpinned inline workflow | Supersede with first-party deterministic generation and hardened CI |
| Existing local code predates the canonical global model | Adapt and test it rather than discarding maintainer-owned work |

## Verification

`scripts/generate_nz_asset_inventory.py --check` verifies the preserved
upstream tree without requiring local-only payloads. It binds every upstream
path, size, SHA-256 digest, source commit, and disposition to a fixed aggregate
tree digest and the independently verified Git bundle identity recorded in
`nzmedicines-preservation.json`.

`scripts/generate_nz_asset_inventory.py --check --check-local` additionally
requires governed local assets and compares the complete inventory with a
fresh metadata-only scan. Tests require exactly one disposition and SHA-256
digest for every upstream file, unique paths for every row, non-empty
rationale/conflict/enhancement fields, and fail-closed local-only rights
boundaries for source payloads.
