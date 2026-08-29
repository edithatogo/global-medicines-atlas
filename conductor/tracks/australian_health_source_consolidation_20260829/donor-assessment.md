# Pinned donor assessment and completeness baseline

## Bottom line

Both repositories are related to GMA, but they are not equivalent to each
other or to current GMA. `aus_mbs_pbs_graph` contains early MBS/PBS file
acquisition and parser experiments plus an unimplemented knowledge-graph
roadmap. `aus-health-data-scraper` contains MBS HTML/XML tabular scraping,
monthly automation, fixtures, and one substantive P7 workbook; PBS is only a
TODO. Current GMA has a governed but minimal synthetic PBS adapter and no MBS
source/domain implementation. The donor functionality and data therefore add
real scope.

The recommendation is to incorporate all of it, with semantic and maturity
labels. Working behavior becomes governed production behavior; defective
behavior gets an equivalent replacement; exact legacy bytes remain available
for comparison; roadmap-only ideas become explicit future tasks.

## Repository baselines

| Repository | Pinned commit | Code licence | Current hosted state |
|---|---|---|---|
| `edithatogo/aus_mbs_pbs_graph` | `64e764cebeb3826f98ce672cbb4affc65d06a92f` | Apache-2.0 | public, unarchived, last pushed 2025-07-12 |
| `edithatogo/aus-health-data-scraper` | `931da0b9b6ae3e3cec0743568abb71a50d62b7cf` | Apache-2.0 | public, unarchived, last pushed 2025-07-11 |

The local checkout of `aus-health-data-scraper` contains unrelated dirty and
untracked work. This assessment uses a clean clone of the hosted pinned commit
and does not modify or rely on that dirty checkout.

## Exact data denominator

| Donor/path | Bytes and digest | Observed structure | Required disposition |
|---|---|---|---|
| `aus_mbs_pbs_graph/scripts/parsing/MBS-XML-20250701 Version 3.XML` | 8,194,522 bytes; SHA-256 `db873768c5795222455033e2bad28586f19bbf2a10c7d58f06a0671d9111a556` | Root `MBS_XML`; 5,989 `Data` records; 40 distinct native fields, with 34–37 fields in individual records | B2 exact public MBS archive, legacy/current comparison cohort, source-faithful Bronze projection |
| `aus_mbs_pbs_graph/temp_mbs_download.xml` | zero bytes | Empty placeholder | Retain path/state in donor inventory; never count as payload or coverage |
| `aus-health-data-scraper/data/source/MBS - 2024.07 - Group P7 (Genetics).xlsx` | 87,727 bytes; SHA-256 `2f1cbc2d2dcbb93be86f42c8dbbe9f5f9e8fb550cad38b6ee54d0e9bdd2e27b8` | Four sheets: `Sheet1` A1:AV161, `Sheet2` A1:B161, `Sheet1 (2)` A1:AV183, `Sheet3` A1:A21; includes fees/benefits, dates, descriptions, annotations, and formulas/errors | B2 exact public MBS legacy archive plus typed schema-era projection; retain every sheet |
| seven tracked `legacy_scripts/*.ipynb` files | zero bytes each | Empty historical notebook placeholders | Retain names and zero-byte digests/history; do not call them analyses |
| three test fixtures | non-empty HTML/XML, digests retained by Git | Minimal item, participant, and MBS P7 examples | Adopt as characterized compatibility fixtures after safety review |
| `data/raw/.gitkeep`, `data/processed/.gitkeep` | empty directory sentinels | No raw or processed dataset | Supersede with public-HF destinations; not data coverage |

No PBS source payload is tracked by either donor repository.

## Implemented behavior and disposition

| Donor behavior | Evidence | Current GMA gap | Disposition |
|---|---|---|---|
| Download a hard-coded July 2025 MBS XML | `download_mbs.py` | No MBS acquisition/source family | Adapt to catalogue-driven, versioned, receipt-bound MBS acquisition |
| Stream/print initial MBS items | `parse_mbs_xml.py` | No MBS parser | Replace: donor guesses `MBSItem`, but actual repeated tag is `Data`; preserve failure as regression evidence |
| Download and extract PBS ZIP | `download_pbs.py` | Only minimal fixture adapter | Adapt with archive safety, immutable ZIP, member manifest, receipts, limits, and current release discovery |
| Parse PBS v3 pharmaceutical items, names, AMT references, and ATC codes | `parse_pbs_xml.py` | Minimal non-v3 adapter lacks AMT/ATC | Replace with valid typed implementation; donor file does not compile because of a trailing Markdown fence |
| Print the first PBS pharmaceutical item for tag inspection | `identify_pbs_tags.py` | No bounded schema inspector | Adapt as a debug/qualification command over admitted bytes |
| Generate inclusive YYYYMM ranges | `month_range` | No donor-compatible helper | Adopt behind validation and property tests |
| Scrape MBS item pages by item/month | `scrape_items` | No MBS HTML compatibility path | Replace with bounded compatibility probe; observed URLs are stale |
| Scrape MBS participant pages by month | `scrape_participants` | No participant source contract | Replace with typed source contract and current-source discovery |
| Extract Group P7 records from simple MBS XML | `process_mbs_xml` | No P7 projection | Adapt as a source-filtered projection, never the only MBS representation |
| Extract and clean every HTML table | `process_html_file` | General parser tools exist but no donor parity | Characterize and adapt only with table/source identity; do not hide parse errors |
| Concatenate HTML/XML tables to CSV | `combine_and_save_data` | GMA uses typed Parquet/contracts | Replace with typed source tables; donor mixes heterogeneous schemas and has a path/type defect |
| Monthly test/scrape/commit workflow | `monthly_run.yml` | GMA has source-health/hosted publication foundations | Replace with source-health-aware acquisition and public HF publication; never commit raw data to Git |

## Observed operational evidence

The most recent monthly workflow run reviewed, GitHub Actions run
`30677814193` on 2026-08-01, was green but all six configured MBS URLs returned
404, processing found no files, and the commit step reported no changes. This
is workflow execution evidence, not acquisition or coverage evidence. The GMA
replacement must classify this as an unavailable/source-drifted data run.

The donor processor's successful no-data path also masks a latent contract
error: `main.py` passes strings and a file-like path to a function that calls
`.mkdir()` and appends another `dataset.csv` when data exists. The intended
combine/export behavior is retained; the defective implementation is not.

## Roadmap-only capabilities

The following are described but not implemented in either donor repository:

- Neo4j schema/loading and Cypher query service;
- SNOMED CT-AU RF2 acquisition and graph loading;
- complete AMT and ATC hierarchy acquisition/loading;
- official AMT/SNOMED mapping ingestion;
- NLP/NER of MBS descriptions, PBS restrictions, conditions, and indications;
- temporal MBS/PBS knowledge graph and evidence-reviewed MBS-PBS links;
- Spark, Airflow, distributed processing, production API, or user interface;
- PBS integration in `aus-health-data-scraper`.

They are still incorporated as design commitments: source-faithful portions
enter the Silver/Gold track, optional Neo4j/Cypher and advanced federation enter
the frontier track, and restricted terminology acquisition remains separately
gated. They must not appear in a current-functionality comparison as already
working features.

## What the old repositories do that GMA does not yet do

1. Hold an exact full July 2025 MBS XML payload and an exact July 2024 P7
   genetics workbook.
2. Represent MBS services, fees, benefits, participant pages, and a P7-specific
   analysis surface at all.
3. Attempt PBS v3 namespace parsing and AMT/ATC extraction.
4. Provide donor-compatible PBS tag inspection and MBS HTML table workflows.
5. Schedule a monthly MBS scrape, albeit one that currently succeeds without
   data.
6. State a concrete Australian MBS-PBS evidence-graph vision.

GMA already provides stronger provenance, safety, typing, temporal, medallion,
coverage, publication, and matching foundations. The tracks combine those
foundations with the missing donor scope rather than maintaining three partial
systems.
