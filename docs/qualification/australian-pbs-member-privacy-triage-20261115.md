# PBS member privacy metadata triage

The [reproducible report](../../quality/qualifications/australian-pbs-member-privacy-triage-20261115.json)
uses retained metadata only. Across the existing unassessed PBS and
reimbursement inventory, 1,722 paths have 1,721 distinct digest-and-size pairs.
The single two-path group is the previously identified April 2026 XML archive
and its alias. Matching digest and size help identify a possible shared content
review; they do not clear privacy or transfer path-specific rights and lineage.

For the exact September 2025 API archive, the prior inventory names 33 CSV
members. Eight names contain broad review labels relating to prescribing,
organisations or copayments. The other 25 names do not match those chosen
labels. This is a filename screen only: a match does not establish sensitive
content, and absence of a match does not establish safety. The retained member
list has no member-level content digests, field profiles or values. All 33
members and the archive remain unassessed.

The earlier XML schema-path screen is a separate member-scoped structural
observation and does not clear either complete ZIP. All 1,722 PBS and
reimbursement paths remain blocked from payload reads and consumer use until
adequate source-specific privacy evidence is available. This packet adds no
privacy clearance, source, dataset publication, rights decision or admission;
it reads no participant, cohort-derived or unassessed payload bytes.

To reproduce the metadata-only report with Python 3.15.1, run
`python -m scripts.qualify_pbs_member_privacy_triage --check`. The focused test
file is `tests/test_qualify_pbs_schema_privacy_context.py`.
