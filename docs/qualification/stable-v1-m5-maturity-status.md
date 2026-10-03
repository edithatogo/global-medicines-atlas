# Stable-v1 M5 maturity status, 2026-10-03

Seven of the eight blocking dimensions in the stable-v1 contract are M5 and
verified. **Source coverage remains M4/partial**, so the M5 maturity release
gate remains blocked. This does not replace the separate Australian federation,
Bronze current-scope, or final stable-release gates.

The refreshed [Bronze maturity report](../../quality/qualifications/bronze-maturity.json)
recognises the exact approved CMS Part D formulary and spending source-record
qualification and five accepted U.S. source-record products as direct Bronze
receipt evidence. The U.S. receipt includes an accepted admission, source-record
projection, and byte-identical clean-room recovery for those products. Its three
openFDA responses are 100-record canaries, not complete releases. An authorized
internal Orange Book refresh accepted the newly listed August 2026 FDA monthly
release, but 104 Archive-It requests still fail and 16 responses remain
quarantined, so its historical coverage is incomplete. No public release was
authorized or performed. Prompt 31 remains complete for its two CMS source IDs.
The separate Prompt 14 audit and its source-specific FDA drug-shortages
qualification are now reconciled. The source-specific receipt records
authorized internal retention, the complete current export and 129 monthly FDA
list snapshots, recovered source-record projection with byte-identical
Parquet, and verified private archive checksums. The older bounded U.S. Bronze
corpus row describes a separate quarantined acquisition and does not override
that later, specifically scoped evidence. A bounded current Orange Book
record projection is also counted as landed; this does not complete Prompt 16
or its historical family. The report was refreshed against exact merged
`main` commit `ab1a4a1ec9d9cc6889c5206f0f7fb2934965a261` after PR #687; the
source inventory and completeness finding are unchanged. The NorPD queue and
maturity reconciliation was merged in PR #697. This report is refreshed
against exact merged `main` commit
`752908d174175f3307f34eecc677711fb189b745`; the inventory still finds 115 of
157 in-scope public/no-credential sources without qualifying landing evidence.
The checked-in maturity JSON is refreshed against exact merged `main` commit
`f04283fe544acfbee2cb3022df7d4cc2225b5909` after PR #711. It preserves the
13-of-14 maturity result and the 157-source denominator.
The full-scope evaluator has landing evidence for 42 source IDs, while 28 have
direct successful receipts accepted by the receipt validator; 14 queue-marked
landings remain outside that stricter receipt cohort. See the separate
[receipt cohort and future-source list](./bronze-future-source-list.md). The
all-release Open Medic receipt added by PR #707 brought the direct-receipt
cohort to 28. The August 2026 MBS B1 receipt and B2 external reference remain
preserved, but the accepted admission has no durable preceding `landed` event
and does not supersede one. The MBS receipt is therefore deferred, leaving 28
qualified and 129 current-scope sources on the future list. Do not create a
retroactive lifecycle record from inference. The source-record projection
lineage and separate M-112 Australian federation gate remain unqualified. The
cohort does not change the 157-source denominator or this blocked result. The
report evaluates 13 of 14 mandatory Bronze properties as evidenced and leaves
completeness blocked. CMS Part D
Prompt 31 was already included in the prior denominator; its reconciled queue
and source-record evidence do not create another landing increment.
The Sweden count reflects one internally authorized, privately retained 2025
national aggregate acquisition; its coarse rights state remains unknown, and
no licensing, public release, redistribution, or complete Swedish coverage is
claimed. The Prompt 33 audit recognizes the approved private historic NorPD
2014-2018 aggregate report; it leaves Denmark without a live receipt, and
Norway's coarse source-rights state remains unknown.
Two fixture-only and 15 excluded sources remain outside that denominator.
Delegated detail-page coverage remains incomplete, and public release and
external publication remain unauthorized.
Credentialed and licensed feeds remain excluded from this denominator; missing
evidence is not a negative claim about the source.

The M-112 PBS authority reconciliation confirms exact historical publication
authorization and a prior anonymous digest receipt for the pinned PBS raw
archive. The broader source-rights ledger still records upstream reuse terms
as unknown; the finding does not authorize new acquisition, v4 admission, or
publication and does not reduce the Bronze denominator.

The M5 source-coverage dimension can be reconsidered only when the current
scope's completeness property is evidenced by source-specific rights,
admission/receipt and recovery records. The Australian federation gate also
requires the remaining M-105–M-112 acceptance evidence. Independent
reproduction, support readiness and final release authority must retain their
own verified states; a refreshed count or green CI alone does not promote
them.
