# Stable v1 Qualification

## Accessibility testing excluded — 3 November 2026

The maintainer explicitly removed accessibility testing from project scope.
Manual and automated accessibility audits, screen-reader/assistive-technology
qualification, WCAG conformance testing and accessibility-specific acceptance
are excluded from every current Conductor track and from the roadmap. They
are not deferred work or a pending completion gate. Do not schedule further
accessibility testing without new explicit maintainer direction. Historical
results and unverified assessments remain evidence, not conformance claims.
Existing working UI features and tests are retained; this scope change does
not delete regressions, weaken protected CI, or mark unperformed tests passed.
All other source, temporal-data, rights, production and release gates remain.

- [Specification](./spec.md)
- [Implementation Plan](./plan.md)
- [Metadata](./metadata.json)
- [Evidence](./evidence.jsonl)
