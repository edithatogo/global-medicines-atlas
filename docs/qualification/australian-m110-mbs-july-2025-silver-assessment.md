# M-110 MBS July 2025 Silver input assessment

Status: exact-era candidate revalidated; Silver admission and M-110 remain
blocked. This is an input assessment, not a rights conclusion, admission
receipt, graph qualification, or acceptance of M-109, M-110, or M-112.

## What current evidence establishes

The exact-main read-only qualification [run 38947544328](https://github.com/edithatogo/global-medicines-atlas/actions/runs/38947544328)
ran on `7fe32a8830d9576ebcc4b431031d59e6809ef379`. It matched the pinned
official MBS-XML-20250701 Version 3 release, verified the existing public
v4 identity at revision `3d2d528439bddf6f42e8e700c88917f0960a9f38`, and
reconciled all six table objects and their exact digests. The resolved
`public_v4_identity_unverified` finding is stale in the committed candidate
qualification, but the current report confirms that public identity. Its
aggregate digest is recorded in the
[machine-readable assessment](../../quality/qualifications/australian-m110-mbs-july-2025-silver-assessment-20261017.json).

For this exact era, the source release has 5,989 records and 40 mapped native
fields (239,560 field occurrences). The existing value-free parity receipt
covers six tables with 5,989 rows each. The fresh report also confirms declared
schema compatibility for all six tables, with table values matching the
unprofiled projection and legacy metadata unchanged. The schema profile remains
`declared_only`; this is not independent semantic validation or an admission.
The hosted run retained no source bytes and performed no publication.

Decision 0009 supplies maintainer authority for the scoped Australian MBS/PBS
public data plane. The existing parity receipts nevertheless state
`rights_conclusion=false`, `production_admission=false`, and
`production_promotion=false`. This assessment preserves those states rather
than inferring that publication authority itself is a completed derived-rights
conclusion or Silver admission.

## Exact proposed input boundary

The candidate admission review, if its existing rights and acceptance records
are reconciled, is limited to these July 2025 MBS v3 objects: `services`,
`hierarchy`, `descriptions`, `fees`, `benefits`, and `caps`, at the pinned
revision and digests in the assessment JSON. This permits MBS-only service and
benefit evidence. It does not add P7, another MBS era, PBS, terminology
vocabularies, participant denominators, or cross-domain/clinical claims.

Before using these tables to qualify Gold, the repository needs a current
immutable Silver admission receipt bound to the six public object digests and
the applicable exact-source rights disposition. No such admission is present
yet. After that prerequisite, M-110 still requires typed graph nodes and edges,
source lineage/spans, temporal validity, review state, and negative controls
over the admitted inputs. Full M-109 and M-112 remain separately incomplete.

The structured predicate assessment and bounded next gate are in the linked
JSON receipt; no source status or acceptance marker is advanced here.
