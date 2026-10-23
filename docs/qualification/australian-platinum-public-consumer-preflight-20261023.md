# M-111 and M-112 live consumer and recovery readback — 2026-10-23

## Result

The bounded candidate consumer checkpoint is complete for the exact July 2025
MBS v3 same-record edge set: API, CLI, Atlas, and Chromium traversed the same
5,989 reviewed candidate edges across six pages on exact `main` commit
`78e857839aad8298060c65eb5ef03a4e3114827a`. The current aggregate receipt is
[`australian-mbs-gold-candidate-consumers-20261023-39939296038.json`](../../quality/qualifications/australian-mbs-gold-candidate-consumers-20261023-39939296038.json);
hosted run [39939296038](https://github.com/edithatogo/global-medicines-atlas/actions/runs/39939296038)
passed. All four surfaces returned the same ordered edge-ID digest. The
bounded date and decimal scalar queries also matched across DuckDB and Polars.

The receipt remains `candidate_only`. Its nested relationship disposition is
`reviewed_candidate`; the top-level `review_state=not_reviewed` preserves the
immutable pre-review graph state. This is the maintainer-reviewed same-record
assertion only. It does not establish overall M-110 acceptance, M-112
federation acceptance, independently admitted public-product queries, new
rights, or a public release. Source payload values were not retained, the
temporary Parquet workspace was removed, and no dataset was mutated.

## Primary restore reconciliation

The eight currently admitted M-112 raw B2 objects already bind the exact
anonymous clean-room restore receipt and checksum inventory in their v4
contracts. The new
[`australian-m112-primary-recovery-readback-20261023.json`](../../quality/qualifications/australian-m112-primary-recovery-readback-20261023.json)
reconciles all eight contract identities against the immutable public
28-object manifest and the hosted restore receipt. The receipt's issue-comment
body digest was fetched and verified; the pinned public manifest SHA-256 is
`9e9848f32287cdb8141d65f2f2741916cf7e391e396ac2fcaf5794eccdaa3bab`.

This closes the identity join for existing primary-copy restore evidence for
the eight admitted objects. Every contract explicitly sets `independent=false`,
leaves the region unverified and RPO/RTO null, and points to the same HF
administrative domain. No independent replica or production disaster-recovery
claim is made. The frozen M-112 denominator remains 1,759, with 8 admitted,
8 `FederatedReader` canaries, and 1,751 deferred.

## Remaining release gates

The exact six-table Silver product remains candidate-only and is scoped for
candidate qualification and consumer canaries. The current canary is not a
successful query against an independently admitted public product. M-111
product admission and release therefore remain open, as do an independent
recovery target and qualified RPO/RTO. No new source, admission, canary,
publication, or rights conclusion was added by this readback.
