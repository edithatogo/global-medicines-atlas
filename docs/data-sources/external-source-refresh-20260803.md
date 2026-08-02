# External source-surface refresh — 2026-08-03

This is an endpoint and access-surface refresh only. It is not live-source
qualification, rights approval, or permission to redistribute source bytes.

| Source | Official surface | Current disposition |
|---|---|---|
| NZULM/NZMT | HISO/NZ health data standards and NZ medicines authorities | Catalogue/fixture only; rights and current lawful payload remain open |
| PBS | [PBS API](https://data.pbs.gov.au/api/pbs-api.html), [PBS downloads](https://www.pbs.gov.au/info/browse/download) | Prefer API/CSV; legacy XML/text outputs are discontinued from May 2026; rate limits and terms require receipt |
| Drugs@FDA | [openFDA endpoint](https://api.fda.gov/drug/drugsfda.json), [FDA bulk files](https://www.fda.gov/drugs/drug-approvals-and-databases/drugsfda-data-files) | API and bulk surfaces identified; current payload, checksum, coverage, and rights receipt remain open |
| EMA | EMA medicines/PMS API documentation and official medicines data | Catalogue/fixture only; endpoint and licence validation remain open |
| PMDA | PMDA approvals and package-insert surfaces | Catalogue/fixture only; Japanese field mapping, translation, and rights review remain open |
| NHS dm+d | NHS dm+d/TRUD access surface | Catalogue only; licensed access and redistribution decision remain open |
| Canadian DPD | Health Canada DPD access surface | Catalogue/fixture only; lawful current payload and live receipt remain open |

## Required next evidence

For each source, record the authority URL, access mode, authentication class,
terms/licence, retrieval timestamp, checksum, schema fingerprint, coverage
denominator, temporal semantics, adapter parity result, and redistribution
disposition. Unknown or conditional rights remain blocked.

Regulatory approval, public funding, formulary inclusion, price, availability,
and terminology remain separate dimensions. No negative status is inferred from
absence in an incomplete source.
