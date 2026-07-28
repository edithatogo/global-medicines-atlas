# Specification: Operational Hardening

## Outcome

Deliver v0.8 release-candidate operations with observable sources, bounded
failures, security controls, performance budgets and tested recovery.

## Requirements

- M-042 to M-049, M-060, M-066, M-067, M-075 and M-076.
- Monitor source health, freshness, schema drift and adapter behavior.
- Maintain compatibility canaries for shared frontier dependencies.
- Test backup, restore, rollback and degraded read-only operation.

## Acceptance

- Scheduled monitors produce durable receipts and deduplicated escalation.
- Security and performance budgets block promotion when exceeded.
- Clean recovery and dependency rollback rehearsals pass.

## Out of scope

- Unbounded autonomous remediation or bypass of source terms.
