# Historical MBS workbook source-column semantics

Status: source-column meanings are partially qualified for the exact 91-workbook
historical cohort. Value interpretations, currency conversion, current-schedule
identity, and cross-era equivalence remain unqualified.

## Bound cohort and evidence

The cohort is the 91 exact MBS workbook-derived candidates listed in the
[cohort receipt](../../quality/qualifications/mbs-historical-workbook-cohort-20261023-39724026209-39891918206.json)
(SHA-256 `3bbcc74fee209cee521ce6ee85ef87f3ed13df2d202cb1f96effb02274b48546`)
at the existing archive revision `dee9a5b0580dfe394474dc26b372559462e157e7`.
The 91-output rights attestation is bound in
[the exact output attestation](../../quality/qualifications/australian-mbs-historical-workbook-91-derived-rights-attestation-20261023.json);
this qualification changes no rights, admission, publication, or canary state.

The exact-main [header cohort](../../quality/qualifications/mbs-historical-workbook-header-cohort-20261024-40040624592.json)
records 91 workbook/sheet profiles and 728 interpreted header bindings. A
normalized comparison of the bound profiles produces one common eight-column
contract across all 91 workbooks. The [value-shape cohort](../../quality/qualifications/mbs-historical-workbook-value-shape-cohort-20261025-40149410629.json)
records 38,771,742 rows per field, zero formulas, and zero source-error cells.
Its values are aggregate shapes only; no source values are emitted. The
successor [field-state reconciliation](../../quality/qualifications/mbs-workbook-field-state-reconciliation-20261025-shapes-40149410629.json)
keeps all 310,176,929 non-header cells `native_unresolved`.

The interpretation is bound in the machine-readable
[qualification receipt](../../quality/qualifications/mbs-historical-workbook-source-column-semantics-20261028.json).
It records the report inputs, source documentation, field meanings, and
unresolved limits. The official [Services Australia MBS item reports page](https://medicarestatistics.humanservices.gov.au/VEA0032/SAS.Web/statistics/mbs_item.html)
identifies the patient-demographic dimensions, claim-processing month, State or
Territory basis, service-adjustment rule, and the possibility of older item
numbers being reported under a current equivalent. The existing [data.gov.au
catalogue record](https://www.data.gov.au/data/dataset/medicare-benefits-schedule-mbs-group-by-patient-demographics-report/resource/492b39de-8c97-4bbf-880e-e97d933daa9c) identifies the historical 1993–2015 quarterly series and its
item, demographic, service, and total-benefit measures. The official page is
mutable; the metadata copy is recorded as a catalogue-description mirror rather
than a new data source.

## Bounded source-column meanings

| Source header | Qualified meaning | Kept unresolved |
| --- | --- | --- |
| `Year` | Year component of the report period paired with processing month | No service-year or fiscal-year claim; values are not converted |
| `Month` | Month in which the claim was processed, not when the service was provided | Native labels are preserved without month-number conversion |
| `Item_Number` | MBS item number referencing a Medicare service | Item numbers may change or be mapped to a current equivalent; no current identity or historical equivalence |
| `State` | State or Territory based on patient address at claim time | Category values and code normalization |
| `Age_Range` | Patient age-range demographic dimension | Band boundaries, reference date, suppression tokens, and value taxonomy |
| `Gender` | Patient gender demographic dimension | Historical labels, taxonomy, and suppression; no normalization or clinical-sex interpretation |
| `Services` | Reported service total after later-day adjustments | Values may be negative; services are not distinct patients |
| `Benefits ($)` | Reported total benefit amount associated with MBS items and State or Territory | Currency code, amount calculation, and adjustment treatment; no patient-payable or expenditure claim |

The header meanings do not promote any non-header value. Preserve all source
labels and values in their current candidate representation. Do not treat the
services column as a distinct-patient denominator or the benefits column as a
patient's payable benefit. Do not infer current MBS item validity from an old
item number.

## Value and era rules

- All 91 workbook profiles share the same normalized column contract, while
  workbook-specific sheet names, identities, periods, and profile digests stay
  separate.
- No formulas or source errors were observed in this cohort; no formula is
  evaluated. The separate July 2024 P7 workbook still preserves its formulas
  and OOXML errors without evaluation.
- The `Year`/`Month` pair is the historical report period; `Month` is the claim
  processing month. The output does not create a service date or a service-year
  value.
- Monetary lexemes remain native-unresolved. No currency conversion, rounding,
  payable-benefit interpretation, or calculation is introduced.
- Historical workbook columns are not pooled with current MBS CSV/API columns.
  Cross-era equivalence remains false unless established by exact-era evidence.
- PBS domain fields, MBS-to-PBS relationships, patient rates, current-status
  claims, and broader M-109 acceptance remain outside this qualification.

No source payload bytes or source-cell values were read for this qualification.
No new source, admission, consumer canary, or publication was added. M-109 and
the Stable v1 Australian federation gate remain blocked.
