# Live Atlas manual assessment and FDA mapping decision — 3 November 2026

## Scope and ownership

Chat `01a19600-56dd-73a2-9ff5-4a2484a54493` owns this follow-up in
`/Volumes/PortableSSD/GitHub/global-medicines-atlas`, branch
`codex/61-manual-mapping`. Target: https://global-medicines-atlas.onrender.com/,
initial deployed revision `283fd61023eaa37ff3c0f9441f4d3c70266a96b0`.
Reuse PR #1405's nine-state axe, HTTP, provenance and viewport evidence.
No new acquisition, publication, release or interpretation of clinical advice.

## Direct interaction observations

The Codex internal browser exposed named medicine, jurisdiction and clock
controls; the document has a title, English language, heading hierarchy,
main landmark, visible scope disclosure and explicit unknown-evidence copy.
Keyboard Tab initially focused Scope and provenance before the skip link.
The next Tab and Enter activated the skip link and focused `atlas-results`.
Submitting exact `us-drugsfda:ANDA040104:001` returned the named
HYDROXYCHLOROQUINE SULFATE result and explicit product identity. ArrowDown
expanded the combobox and selected its named option. Enter selected the
canonical identity, collapsed suggestions, and updated the live status.
Tab then reached jurisdiction without a trap. DOM readback found that
`aria-activedescendant` still referenced the now hidden option.

Fixes: move the scope disclosure to the end of the existing header, retaining
its visibility and landmark while restoring the skip link as the first focus
stop. Clear active descendant, active index and selected-option state whenever
the suggestion list closes. Extend the existing browser interaction regression
and streaming-header regression; do not introduce another browser harness.

## Accessibility acceptance limits

These observations are direct keyboard and accessibility-tree assessment,
not a screen-reader speech/output assessment. No assistive-technology speech
session was available through the verified CLI/internal-browser route. Prior
axe results cover automated rules only. Screen-reader task traversal and the
remaining applicable manual WCAG criteria are unverified, not passed or N/A.
Full WCAG conformance and issue #61 completion remain false. A passing scan
must not change either flag.

## FDA application/product mapping qualification

Authoritative definitions inspected directly:

- https://open.fda.gov/apis/drug/drugsfda/understanding-the-api-results/
- https://open.fda.gov/fields/drugsfda_reference.pdf
- https://www.fda.gov/drugs/drug-approvals-and-databases/drugsfda-data-files

The FDA schema keys Products by application and product number. Submissions
are keyed by application, submission type and submission number; their date
is the date the status was applied to that submission. There is no product
number in the Submissions table. MarketingStatus has a product key but no
effective-date field. Therefore an application join establishes membership,
not which products a dated action affected or a continuing validity interval.
The observed archive's 633 dated actions (89 ORIG, 544 SUPPL; 630 AP, 3 TA)
cannot be cross-joined into 183 product histories. Original approval does not
establish that every product currently listed existed at that original date.
Tentative approval and supplements cannot be silently promoted to original
product approval. Retrieval time cannot replace source-effective time.

Disposition: application/product membership is supported; product-level
submission applicability and continuing validity remain unresolved. This is a
confirmed schema limitation of the admitted source, not absent dates or an
account/hosting prerequisite. Product-specific approval documents or another
existing source with product/date evidence must be bound to each affected
product before promotion. No source was downloaded locally or newly published.
No temporal regulatory assertions are fabricated to satisfy this gate.
