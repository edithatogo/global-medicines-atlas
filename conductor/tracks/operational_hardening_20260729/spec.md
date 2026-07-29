# Specification: Operational Hardening

## Outcome

Deliver v0.8 release-candidate operations with observable sources, bounded
failures, security controls, performance budgets and tested recovery.

## Requirements

- M-042 to M-049, M-060, M-066, M-067, M-075, M-076 and M-079 to M-082.
- Monitor source health, freshness, schema drift and adapter behavior.
- Maintain compatibility canaries for shared frontier dependencies.
- Test backup, restore, rollback and degraded read-only operation.
- Verify repository rulesets, security settings, labels and project views
  against their version-controlled declarations.
- Exercise the threat model, incident path, dependency supply chain and
  offline/rate-limited CI behavior.

## Acceptance

- Scheduled monitors produce durable receipts and deduplicated escalation.
- Security and performance budgets block promotion when exceeded.
- Clean recovery and dependency rollback rehearsals pass.
- Hosted repository controls and documentation checks have dated receipts;
  configuration files alone are not treated as proof.

## Out of scope

- Unbounded autonomous remediation or bypass of source terms.
