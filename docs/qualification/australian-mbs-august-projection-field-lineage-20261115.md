# August MBS Bronze projection field lineage

The [v2 lineage vocabulary](../../quality/qualifications/australian-mbs-august-projection-v2-field-lineage-20261115.json)
and [qualification report](../../quality/qualifications/australian-mbs-august-projection-field-lineage-qualification-20261115.json)
bind all eight existing August 2026 MBS schedule projections to their exact
source digest, output digest, source receipt, rights attestation and historical
producer code. Four paths are frozen M-112 members at revision `243f9ff…`;
the other four are outside that inventory at revision `b925a8a…`. The two
revisions and their paths are not interchangeable.

Each output has 85 field-lineage records: 40 source XML child names and 40
corresponding text-or-null values map into the nested Parquet `fields` list;
three native identity fields and the source record position map to
`source_record_id`; and the record position maps to `source_ordinal`. Missing
XML children are not represented as present elements. Empty child text maps to
null. The source-record identifier is a producer-generated composite, not a
participant identifier. For `p7.parquet` the retained producer code selects
exact native `Group=P7`; `source.parquet` retains all source records.

The four frozen outputs have retained exact-byte in-memory reproduction
at an earlier archive revision, joined to the frozen revision by the same
path, digest and size. The other four have a footer-adjusted reproduction:
PyArrow 26 output matched after substitution of the writer-version marker for
the historical PyArrow 25 marker. The historical PyArrow 25 writer was not
executed; this is not represented as an unmodified historical producer replay.
Historical code blobs for all four producers were checked separately against
12 fixed Git object hashes. The prior source-profile privacy assessment is
preserved; it is not an exhaustive screening of every datum.

This is structural source-to-output lineage, not acceptance of release-linked
field meanings, cross-era equivalence, current status, clinical interpretation,
v4 admission, consumer delivery or independent recovery. The existing
[f9f9 disposition](../../quality/qualifications/australian-mbs-august-f9f9-prefix-disposition-20261028.json)
requires independently verifiable replica evidence before those two outputs
can be admitted. No source or projection payload, participant or cohort-derived
data was read for this lineage packet, and no dataset was acquired or published.

With the qualified repo-local Python 3.15.1 interpreter, run
`python -m scripts.qualify_mbs_august_projection_field_lineage --check --check-producer-code`.
The fixed Git commits must exist locally for the optional producer-code check;
the regular `--check` uses only digest-bound repository metadata. Focused
regressions are in `tests/test_reconcile_m112_mbs_bronze_projection_lineage.py`.
