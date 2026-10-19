# Australian Gold relationship screening and match behaviour

This assessment separates evidence-bearing source relations from cross-source
matching candidates. It does not promote a candidate, establish clinical
equivalence, or claim M-110 acceptance.

## Relationship screening

| Relationship | Decision | Evidence boundary |
| --- | --- | --- |
| `source_record_has_benefit` | Qualifies as a source-explicit, within-record MBS evidence edge for the scoped July 2025 XML v3 candidate: 5,989 rows, 11,978 nodes, and 5,989 edges. | Both nodes and the edge bind the same source record, B1 receipt, source digest and catalog version. The edge remains `not_reviewed`; confidence is not applicable to a same-record fact; valid time remains unselected. It does not identify a medicine, establish an MBS-PBS link, or assert clinical equivalence. Exact-main consumer readback is recorded in [run 39045806438](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39045806438). The source input was admitted only for M-110 graph qualification, not as full M-109 or M-110 acceptance. |
| `source_contains_entity` | Qualifies only as exact source-tree structure under the PBS graph contract. | The exercised PBS graph input is synthetic. No real PBS relationship denominator or PBS Silver admission is established. |
| Source document declares an authority | Qualifies only as a literal provenance statement when bound to its exact receipt. | The exercised producer projection is synthetic; it does not establish a canonical organization identity. |
| Cross-record or cross-source semantic match | Does not qualify for Gold acceptance on current evidence. | The endpoints lack complete, independently qualified source-era semantics, paired lineage and rights evidence, negative-control outcomes, and exact-edge review. Co-occurrence, lexical similarity, shared generic codes, synthetic parity, and unreviewed scores are insufficient. |

The machine-readable screen is in
[`australian-gold-relationship-screening-20261019.json`](../../quality/qualifications/australian-gold-relationship-screening-20261019.json).
It records the scoped MBS result as source-explicit evidence while keeping
review, source-era completeness, temporal validity, and overall acceptance
separate.

## Match behaviour assessment

The previous evaluator tests used manually supplied predictions, so they did
not exercise the current candidate generator against its labelled cases. The
new assessment runs `generate_candidates` itself over every case in the
six-case matching fixture and then calculates the existing precision, recall,
confidence, coverage, abstention, and selective-risk metrics. The fixture is
self-authored and synthetic; endpoint attributes are limited to names and
identifiers.

| Lexical threshold | Precision | Recall | Candidate recall@5 | Coverage | Selective risk | False positives | False negatives | ECE |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.65 | 0.50 | 0.50 | 0.50 | 0.67 | 0.50 | 2 | 2 | 0.441 |
| 0.80 | 0.67 | 0.50 | 0.50 | 0.50 | 0.33 | 1 | 2 | 0.326 |
| 0.95 | 0.67 | 0.50 | 0.50 | 0.50 | 0.33 | 1 | 2 | 0.326 |
| 0.99 | 1.00 | 0.50 | 0.50 | 0.33 | 0.00 | 0 | 2 | 0.000 |

At the default threshold, the generator emits two negative lexical matches: an
incorrect strength match and an adversarially similar ingredient name. It
abstains on the synthetic brand/generic positive and the ambiguous pack case.
Raising the threshold removes the false candidates only by reducing coverage;
at 0.99, the two remaining predictions are exact-identifier cases. The zero
ECE at that operating point comes from those two confidence-1 identifier
predictions and is not calibration evidence.

Reproduce the report with:

```console
uv run python scripts/evaluate_matching_fixture.py \
  --output quality/qualifications/matching-behavior-synthetic-20261019.json
```

The value-free assessment artifact records the fixture digest, threshold
sweep, grouped mapping-level metrics, per-case candidates and explicit
limitations. It is a synthetic diagnostic, and `promotion_eligible` is false.
No threshold is selected for production from this small fixture.

## Remaining qualification evidence

Completing Gold relationship promotion requires a rights-cleared, admitted
real-source denominator across the relevant MBS and PBS eras; independent
endpoint lineage and qualified meanings; exact-edge negative controls and
append-only review decisions; and a representative, sealed, human-adjudicated
holdout for each scored mapping method. Calibration then needs source- and
mapping-level coverage, precision/recall, confidence reliability, and abstention
analysis without selecting thresholds on the holdout. The current results
identify observable matcher failure modes, but do not close those gates.
