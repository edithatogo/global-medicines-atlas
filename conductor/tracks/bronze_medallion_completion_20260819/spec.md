# Specification: Complete bronze medallion landing for current public scope

## Outcome

Complete the bronze (raw-as-landed) layer of the Global Medicines Atlas
medallion datahouse for current-scope public and no-credential catalog sources
and already-governed fixtures. Later medallion layers remain specified only as
boundaries. Hugging Face is an archive and output boundary, not the source of
truth.

## Authoritative inputs

- `conductor/product.md`, `conductor/requirements.md`, `conductor/design.md`
- `src/global_medicines_atlas/data/medicine_source_catalog.json` (schema v5)
- `docs/data-sources/SOURCE_RIGHTS.md`, `docs/data-sources/source-onboarding.md`
- `DATA_LICENSE.md`, `docs/ECOSYSTEM_REUSE.md`
- `src/global_medicines_atlas/receipts.py`, `src/global_medicines_atlas/columnar.py`
- Adapter and fixture contracts under `src/global_medicines_atlas/adapters/` and
  `tests/fixtures/`
- `quality/qualifications/publication-identities.json` (Hugging Face is a derived
  dataset distribution; catalogue-only today)
- Sibling Hugging Face archival work, when merged, for the public archive
  boundary; until then the plan treats Hugging Face as the bronze archive
  boundary without duplicating that track

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
- Treating Hugging Face as an ingest origin or as portable truth.
- Expanding bronze completion beyond first-cohort/global public sources and
  already-governed fixtures.

## Functional requirements

- Classify every catalog source as bronze-in-scope, fixture-only, or excluded,
  with the exclusion reason recorded.
- Land in-scope bytes as raw-as-landed Parquet partitions with source-native
  identifiers, provenance, dates, rights, uncertainty, and content-addressed
  receipts.
- Keep regulatory, funding, formulary, and terminology independent in bronze.
- Record missing coverage as not covered, never as negative evidence.
- Use Arrow/Parquet as portable bronze truth; DuckDB and LanceDB are derivatives.
- Bind Hugging Face as an archive/output boundary for lawful public bronze
  outputs only.
- Regenerate bronze landing deterministically from receipts and fixtures.
- Apply schema-on-read where native source schemas vary.

## Non-functional requirements

- Python 3.14 is the complete fallback; Mojo is optional and not required for
  bronze completion.
- Never inspect, commit, log, or publish credentials or restricted source bytes.
- Public ingest uses existing untrusted-acquisition controls (M-089).
- Tests precede implementation in every phase.
- External publication remains a human gate.

## Acceptance

- Failing tests exist for the bronze contract before landing code is added.
- Every in-scope public/no-credential source and governed fixture has a bronze
  landing path, receipt, rights expression, and partitioned Parquet identity, or
  an explicit documented blocker that is not treated as completion.
- Credentialed and restricted sources are excluded with durable catalog evidence.
- Hugging Face is referenced only as an archive boundary; repository Parquet and
  receipts remain authoritative.
- Focused tests, then the affected harness, prove regeneration and
  schema-on-read for landed partitions.
- Silver/gold/platinum code is absent from this track's implementation.

## External gates

- Hugging Face archival of public data (sibling track / maintainer-approved
  publication path).
- Source-by-source rights review before any source-derived archive payload.
- Maintainer approval of external dataset publication.
