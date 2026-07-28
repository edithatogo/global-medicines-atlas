# Global medicines source census

Reviewed: 2026-07-29

The machine-readable catalog is
`src/global_medicines_atlas/data/medicine_source_catalog.json`. It records
source access rather than claiming ingestion coverage.

## Discovery method

1. Start with WHO's global medicines/health-product database directory and
   regulatory-system/WLA material to identify authorities.
2. Locate each authority's product-level marketing-authorisation register.
3. Separately locate national or subnational HTA, reimbursement, formulary,
   and public-price sources.
4. Prefer stable bulk downloads, then documented APIs, then governed searchable
   registers. Record licensed feeds without bypassing access controls.
5. Verify source-specific rights, cadence, identifiers, status semantics, and
   temporal fields before implementing an ingestor.

WHO authority maturity or WLA status describes regulatory-system capability. It
is not evidence that a particular medicine is approved. Likewise, terminology,
NDC assignment, pricing, or formulary inclusion must not be promoted into a
regulatory assertion.

## Initial verified cohort

| Jurisdiction | Regulatory surfaces | Funding/formulary surfaces |
|---|---|---|
| New Zealand | Medsafe product/application search; local NZULM/NZMT assets | Pharmac production Schedule/HML XML |
| Australia | ARTG public register | PBS public API and XML/downloads |
| United States | Drugs@FDA bulk/openFDA; Orange Book | CMS Part D plan formulary and pricing files |
| European Union | Commission Union Register dataset; EMA medicine downloads | Member-state responsibility; onboard nationally |
| United Kingdom | MHRA Products | NICE syndication/appraisal Excel; NHS dm+d terminology feed |
| Canada | Health Canada DPD API/bulk; NOC extracts | Provincial formularies and CDA-AMC decisions require expansion |
| Japan | PMDA approval/review information | MHLW NHI drug-price Excel lists |

## Global and terminology sources

- WHO medicines and health-product database directory.
- WHO-listed/benchmarked regulatory authorities as a jurisdiction discovery
  denominator.
- RxNorm monthly/weekly files and RxNav-compatible API.
- Future candidates: WHO ATC/DDD under its applicable licence, SNOMED CT where
  nationally licensed, UNII, GSRS, IDMP/SPOR, and jurisdiction-native
  terminologies.

## Next priority cohorts

- Brazil: Anvisa medicine register/open-data surfaces and CONITEC/SUS sources.
- South Korea: MFDS approvals and HIRA reimbursement.
- Singapore: HSA register and MOH subsidy lists.
- Switzerland: Swissmedic and Federal Office of Public Health specialty list.
- India: CDSCO plus national/state procurement and reimbursement sources.
- South Africa: SAHPRA and national essential-medicines/tender sources.
- Regional expansion: Gulf, Latin American, African, ASEAN, and EU national
  registers.

Every cohort remains incomplete until both source discovery and executable
receipt-backed ingestion are measured.
