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
qualification, but the current report confirms that public identity. The
machine-readable assessment records artifact `12066023734`, its downloaded
JSON body digest (`de159badf4af83e0963f7a57518910e009e79b864717059b3e4389de9efcf606`),
and the distinct embedded candidate report digest
(`a61681c48e4627f9076dc972e05f1ef61d2edbbd70715ccda26c0d860361cfa3`).

For this exact era, the source release has 5,989 records and 40 mapped native
fields (239,560 field occurrences). The existing value-free parity receipt
covers six tables with 5,989 rows each. The fresh report also confirms declared
schema compatibility for all six tables, with table values matching the
unprofiled projection and legacy metadata unchanged. Its `declared_only` label
applies to schema-profile compatibility. Separately, the exact-era field-
semantics crosswalk maps all 40 contract fields to official July 2025 XML
definitions, and the exact-source date receipt qualifies the `DD.MM.YYYY`
profile across all 11 native date fields. These are source-era semantic
evidence, not Silver admission. The hosted run retained no source bytes and
performed no publication.

Decision 0009 and the exact-source publication authorization supply maintainer
authority for the scoped MBS/PBS public data plane and exact MBS source. The
parity receipt's `rights_conclusion=false` records that the parity receipt did
not make an independent rights conclusion; it does not negate that authority.
The parity receipt still explicitly says `production_admission=false` and
`production_promotion=false`, which remain the state of that receipt. This
assessment records the applicable authority basis without making a new legal
interpretation or claiming admission.

## Exact proposed input boundary

The candidate admission review, if its existing rights and acceptance records
are reconciled, is limited to these July 2025 MBS v3 objects: `services`,
`hierarchy`, `descriptions`, `fees`, `benefits`, and `caps`, at the pinned
revision and digests in the assessment JSON. This permits MBS-only service and
benefit evidence. It does not add P7, another MBS era, PBS, terminology
vocabularies, participant denominators, or cross-domain/clinical claims.

Before using these tables to qualify Gold, the repository needs a current
immutable Silver admission receipt bound to the six public object digests and
the existing exact-source authority basis. No such admission is present yet.
After that prerequisite, M-110 still requires typed graph nodes and edges,
source lineage/spans, temporal validity, review state, and negative controls
over the admitted inputs. Full M-109 and M-112 remain separately incomplete.

The structured predicate assessment and bounded next gate are in the linked
JSON receipt; no source status or acceptance marker is advanced here.
