# Global medicines source census

Reviewed: 2026-07-29

The governed machine-readable census is
`src/global_medicines_atlas/data/medicine_source_catalog.json`. Schema version
5 records formats, authentication, product grain, historical scope, native
identifiers, verification date, supported-interface status, and the highest
locally evidenced integration layer. It also uses controlled labels for
information domains, record entities, status semantics, geographic and
population scope, languages, change semantics, and available fields. The
published JSON Schema is `schemas/international-resource-v5.json`.
Generic acquisition profiles describe
transport policy only; they do not claim a source-specific parser.
`documentation_url` identifies human-facing specifications or portals;
`api_url` is reserved for an operational service base or resource endpoint.
Schema-v5 rows must explicitly declare every governance field and cannot
inherit compatibility placeholders.

## Measured scope

- 34 jurisdiction/regional denominator entries.
- At least 95 distinct official source surfaces.
- Regulatory and funding/formulary evidence remain separate dimensions.
- Only `global-rxnorm` and `us-drugsfda` are marked parser-implemented in this
  census. Fixture-only projectors for other sources remain distinct from
  source-qualified parsers and do not advance catalog integration maturity.
- No source has a current live receipt in the committed catalog.

Executable implementations are declared separately by
`builtin_source_capabilities()`. The capability registry distinguishes
acquisition, fixture-parser, source-parser, canonical-projection, live-receipt,
and production-qualification evidence. Every implementation identifier maps
to exactly one catalog source ID. Capability absence is meaningful: no source
currently claims live-receipt or production-qualification evidence.

`catalogued`, `acquisition`, `parser`, `fixture`, and `live_receipt` are
successive evidence layers. A documented API or download can be acquisition
ready without having a parser. Interactive searches are explicitly
`interactive_only`; internal or undocumented website endpoints are not
promoted to supported APIs.

## Foundational jurisdictions

| Jurisdiction | Regulatory/terminology evidence | Funding/formulary evidence |
|---|---|---|
| New Zealand | [NZULM bulk](https://info.nzulm.org.nz/data-access), [NZHTS FHIR](https://www.healthnz.govt.nz/health-professionals/guidance-standards/topic/data-and-standards/health-information-standards/nz-health-terminology-service-nzhts), [Medsafe search and documents](https://www.medsafe.govt.nz/DbSearch/) | [PHARMAC Schedule XML](https://schedule.pharmac.govt.nz/pub/Schedule/) and [HML XML](https://schedule.pharmac.govt.nz/pub/HML/archive/) |
| Australia | [ARTG and TGA datasets](https://www.tga.gov.au/resources/datasets), [AMT](https://www.healthterminologies.gov.au/) | [PBS public API](https://data.pbs.gov.au/api/pbs-api.html), controlled embargo service, API CSV, and historical XML |
| United States | [Drugs@FDA bulk](https://www.fda.gov/drugs/drug-approvals-and-databases/drugsfda-data-files), [openFDA](https://open.fda.gov/apis/drug/drugsfda/), [Orange Book](https://www.fda.gov/drugs/drug-approvals-and-databases/orange-book-data-files), NDC, DailyMed SPL, GSRS/UNII, and RxNorm/RxNav | [CMS Medicaid datasets](https://data.medicaid.gov/datasets) and Medicare Part D reference files are catalogued download/search surfaces until dataset-specific endpoints are qualified |
| European Union | [EMA JSON](https://www.ema.europa.eu/en/about-us/about-website/download-website-data-json-data-format), Article 57, PMS FHIR, SPOR, and the [Union Register](https://ec.europa.eu/health/documents/community-register/html/index_en.htm) | Reimbursement is national; EU authorisation is never treated as funding |

## Global expansion

The catalog includes primary official records for:

- United Kingdom: dm+d/TRUD, MHRA, Drug Tariff, NICE and eMIT.
- Canada: Health Canada DPD/NOC, Ontario ODB, Nova Scotia Pharmacare and
  Canada’s Drug Agency recommendations.
- Japan: PMDA approvals/documents and MHLW NHI prices.
- South Korea: MFDS, HIRA reimbursement, standard-code and ATC mappings.
- Singapore: HSA register/change listings and MOH subsidies.
- Switzerland: Swissmedic lists/AIPS and FOPH Specialities List/FHIR.
- Brazil: ANVISA registration/open data and CMED price ceilings.
- France: [BDPM bulk files](https://base-donnees-publique.medicaments.gouv.fr/index.php/telechargement),
  including product/presentation and SMR/ASMR evidence.
- Norway: [FEST](https://www.dmp.no/en/about-us/distribution-of-data-on-medicinal-products/electronic-prescription-support-system-fest/downloading-fest-and-safest)
  and the DMP FHIR service.
- Sweden: NPL/NSL open XML and TLV subsidy search.
- South Africa: SAHPRA, Essential Medicines List and Single Exit Price.
- Colombia: INVIMA CUM files and register search.
- Saudi Arabia: SFDA registered-drug API and HIRA-like national funding
  sources where officially documented.
- United Arab Emirates: EDE register and DHA price files.

Discovery-only records also cover official surfaces in Argentina, Chile,
Germany, Denmark, the Netherlands, Bahrain, India, Mexico, Malaysia, Thailand,
the Philippines, Indonesia, Qatar, Kuwait, Oman, Nigeria, and the GCC regional
process. These stay catalogued until access terms, completeness, pagination,
identifiers and change semantics are qualified.

## Interpretation controls

- Authorised does not mean marketed or available.
- NDC, terminology, product-document or substance identifiers do not prove
  approval.
- Price-listed does not mean reimbursed.
- Formulary inclusion does not mean universal eligibility.
- HTA recommendation does not mean final funding.
- Regional EMA/GCC status does not replace national status.
- Missing source records mean unknown or uncovered unless explicit coverage
  evidence supports a stronger conclusion.

Bulk snapshots are preferred for reproducibility. Documented APIs support
validation or deltas. Undocumented web endpoints are not production
interfaces. Every future parser and live acquisition must add fixture or
receipt evidence before its integration layer can advance.

The supported API set is deliberately narrow. It currently includes exact
service endpoints for PBS, Health Canada DPD, EMA PMS FHIR, NZHTS FHIR,
Drugs@FDA/openFDA, NDC, DailyMed v2, and RxNav. TRUD, NICE syndication,
Norwegian FEST/FHIR, SPOR, CMS dataset portals, GSRS, Nova Scotia Pharmacare,
and PBS embargo access remain restricted, documented-download, interactive,
or unverified until an exact operational endpoint and access contract are
receipt-qualified. Native formats are retained: FHIR JSON/XML, FEST XML/ZIP,
SPL XML/JSON/ZIP, RxNorm RRF/XML/JSON, and Orange Book delimited text/ZIP are
not flattened into generic JSON/CSV claims.
