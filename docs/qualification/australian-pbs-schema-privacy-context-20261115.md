# PBS schema privacy context

This metadata-only assessment groups the existing schema-path inventory for
one April 2026 PBS XML member. It binds the member digest to the two existing
archive identities with the same parent ZIP digest and size. The
[reproducible report](../../quality/qualifications/australian-pbs-schema-privacy-context-20261115.json)
preserves both exact dataset revisions and their unassessed dispositions.
No unassessed payload or participant or cohort-derived data was read.

Of the member's 5,163 fully qualified schema paths, 224 contain a patient- or
person-related token. Their top-level contexts are `schedule` (104),
`previous-list` (91), `prescribing-texts-list` (22) and `RDF` (7). A broader
contact pattern, including the word `contact`, matches 44 paths: 22 under
`organisations-list` and 22 under `previous-list`. The earlier count of 32
used a narrower email, phone and address pattern.

Eight patient-related paths also end in a generic XML `id` attribute: two are
on `patient` elements and six are descendants of `maximum-patient-charge`.
This is structural co-occurrence, not a finding of patient identifiers. The
specific labels `patient-id`, `participant-id`, `medicare-number`,
`date-of-birth`, `birth-date` and `dob` had zero lexical matches. This short
list is not exhaustive, and no values were screened. These are counts of
schema paths, not people, records or contact details. Namespace-qualified
paths remain distinct even when their local names coincide.

The separately retained September 2025 API archive inventory lists 33 CSV
members. Eight member names contain broad review terms such as organisation,
prescriber or copayment. Those filenames are not a field or value assessment.
The archive's existing acquisition metadata still records unknown sensitivity.

The two April archive identities, the September archive and all other
previously unassessed PBS-related objects remain unassessed. Member-level
schema evidence does not screen the rest of a ZIP, establish absence of
personal data or authorize an admission, consumer read or publication.

Reproduce using the qualified repository-local Python 3.15.1:

```sh
build/federation-env/bin/python -m scripts.qualify_pbs_schema_privacy_context --check
```
