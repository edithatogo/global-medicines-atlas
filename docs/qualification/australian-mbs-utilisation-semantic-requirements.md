# Exact-cohort MBS utilisation semantic requirements

Status: requirements defined; semantic execution and processing admission pending.

The [metadata review](../../quality/qualifications/australian-mbs-utilisation-semantic-requirements-20261005.json)
joins all fourteen approved immutable objects to the two official catalogue
packages and their exact resource identifiers. It records four CKAN schema
queries with `limit=0` and no returned data records. Dataset payload bytes and
cell values were not accessed on the workstation. Current catalogue notes
provide requirements to test against the archived payloads; they do not
prove the content or historical applicability of those notes by themselves.

The pinned raw revision remains `dee9a5b0580dfe394474dc26b372559462e157e7`.
Twelve objects have structural-profile evidence, and the two oversized ZIPs
retain their resource holds. Rights approval, native lifecycle evidence,
structural validation, source semantics and processing admission remain
separate. This review changes none of those prior decisions or receipts.

## Evidence that changes the validation design

Both represented [demographics](https://data.gov.au/data/api/3/action/package_show?id=8a19a28f-35b0-4035-8cd5-5b611b3cfa6f)
and [group](https://data.gov.au/data/api/3/action/package_show?id=5335e112-d91e-47ba-b5f8-5364c8e428dc)
resource notes describe adjusted service totals. Reversals can exceed new
claims, producing a negative monthly total. A blanket non-negative-services
rule would therefore reject a documented source condition. Signed totals
must be preserved and checked under the selected native numeric profile;
benefit precision must be preserved without floating-point loss.

The notes identify processing month separately from service date and locate
geography using the patient's address at claiming. Neither source field may
be relabelled as service date or provider location. Reporting-period metadata
also cannot supply a source publication or effective timestamp.

| Resource family | Documented catalogue coverage | Required boundary |
| --- | --- | --- |
| Demographics Q1 CSV and XLSX | January through March 2016 | Verify payload periods before selecting a common profile |
| Demographics Q2 CSV | Current through May 2016 | Keep separate from the June workbook |
| Demographics Q2 XLSX | April through June 2016 | Do not demand equality with the May CSV |
| Demographics Q3 CSV and XLSX | July 2016 only | Do not assume a complete third quarter |
| Group CSV and XLSX | Year-to-date through July 2016 | Qualify the start date from native evidence |
| Group historical ZIPs | Catalogue descriptions both identify 1993–2015 | One local filename says 2013–2015; inventory native members before asserting coverage |
| Demographics historical ZIPs | Distinct documented ranges from July 1993 through December 2012 | Member periods and completeness remain unverified |

The schema-only queries also reveal different catalogue eras. Q1 and Q2
advertise compact names such as `MonthofProcessing`, `ItemNumber` and
`AgeRange`; Q3 advertises spaced names. The group schema adds `Group` and
`Sub-Group`. Numeric/text type declarations differ across these resources.
Preserve these hints separately. Do not silently normalise actual headers or
use catalogue types as conversion rules. CKAN `_id` is not assumed to be a
source-native MBS identifier. The reported CKAN row totals are metadata and
are not qualified archived payload denominators.

## Required semantic and admission checks

1. Bind each result to its exact raw digest, acquisition, source era and rights
   record. Keep source-native identifiers lexical, including their formatting.
2. Inventory native CSV headers, worksheet table regions, shared-string
   references, cell/formula/type presence and archive-member metadata before
   choosing mappings. Unsupported layouts remain unqualified.
3. Preserve absent, empty, zero, suppressed and unknown states distinctly.
   Retain markers verbatim. An unqualified historical marker cannot be filled
   with zero or guessed from current interactive-report conventions.
4. Validate exact signed numeric representations, processing-period tokens,
   geography and demographics under source-specific profiles. Do not infer
   unique patients from services or synthesize population denominators.
5. Define row grain and compatible periods before duplicate/total checks.
   Report overlap or disagreement; do not silently deduplicate or force
   differently scoped CSV and workbook resources to reconcile.
6. Retain documented processed-service scope and exclusions. Item identifiers
   may change over time. These statistics cannot establish current item
   availability, entitlement, medicine identity or clinical conclusions.
7. Persist public-safe semantic outcomes independently of admission. Join the
   real SourceReceipt/storage/transformation/lineage controls required by the
   existing Bronze protocol; the historical reference import cannot fabricate
   those missing fields. Any promotion needs a native per-object admission
   record with the actual evidence and review state.
8. Run source-byte checks only in protected main Actions under bounded
   resources. Independently read back durable receipts before cleanup. A held
   object cannot block unrelated eligible objects, and an infrastructure
   failure remains inconclusive. Derived dataset publication, v4 consumers
   and M-112 acceptance remain separate gates.

These requirements are a recorded specification, not an executable admission
policy or a claim that semantic tests have passed.

## Next bounded implementation

Implement an exact-reference hosted header inventory for the four standalone
CSV objects already structurally verified. Check immutable byte identity;
read the header only; emit source-native header metadata, its canonical
digest and field count, with no data records or source-cell values. Compare
candidate schema eras explicitly and preserve unexpected fields. Selection
must join the reviewed cohort and prior structural receipts, use the existing
protected environment and acquisition concurrency, and record independent
outcomes before cleanup.

That first step selects no ZIP or workbook and grants no processing admission.
Worksheet semantic inventory and archive-member metadata qualification follow
under their own bounded profiles. Both oversized ZIP holds remain unchanged.
