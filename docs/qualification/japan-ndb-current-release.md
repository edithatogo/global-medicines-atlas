# Japan NDB current public release metadata

The current MHLW landing page identifies the **11th NDB Open Data** release,
published 16 June 2026. It covers FY2024 claims and FY2023 specific health
checkup data. Its prescription-drug tables report quantities by
pharmacological class and source-defined sex/age, prefecture, and service-month
strata. The page's 2 September 2026 refresh changed reference materials and
states that it did not change aggregate data.

The current edition is newer than the sixth-edition Tableau surface recorded
in the 21 August discovery receipt. It does not establish a patient count by
medicine item or a funding-status listing. No table links were followed and no
source rows or payload bytes were accessed. The value-free metadata receipt is
[`japan-ndb-current-release-metadata-20260930.json`](../../quality/qualifications/japan-ndb-current-release-metadata-20260930.json).

MHLW's [website terms](https://www.mhlw.go.jp/chosakuken/index.html) say PDL
1.0 applies unless a separate rule applies. PDL 1.0 permits copying and
adaptation with attribution, while excluding content governed by another rule
and placing third-party-rights checks on the user. The NDB edition page does
not state whether any dataset-specific rule or third-party restriction applies.
This is not a project licensing conclusion. Acquisition and internal retention
remain unauthorized until the accountable maintainer records a source-specific
decision.

The catalog currently models this source under funding and product-identity
metadata even though its live source surface is aggregate utilisation. That
taxonomy mismatch must be corrected in the source-catalog contract before the
current-edition fields are promoted into source semantics; this metadata
receipt does not relabel it or imply funding, formulary, regulatory, or
product-level claims.
