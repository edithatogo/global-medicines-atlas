# ADR 0005: Autonomous track execution

## Status

Accepted on 2026-07-31 by the accountable maintainer.

## Decision

All active Conductor tracks use the execution contract in
`conductor/autonomy.md`. Safe work proceeds autonomously across tasks, phases,
reviews, pull requests, green-check merges, track archival, and selection of
the next unblocked track.

Human interaction is reserved for genuine decision and authority boundaries.
Every decision request must present mutually exclusive options, put the
recommendation first, and explain its rationale and trade-offs.

## Rationale

Repeated ceremonial approvals provide little risk reduction in a
single-accountable-maintainer repository. Durable plans, tests, receipts,
protected checks, scoped pull requests, and explicit human gates provide
stronger controls while allowing the implementation loop to continue.

Upstream Conductor 0.4.x adds Plan Mode, native policies, structured questions,
and setup self-correction. These are useful patterns, but upstream still
requires interactive track selection and phase confirmation. The project
therefore adopts the new mechanisms while retaining its own evidence-gated
autonomy boundary.

## Consequences

- “Proceed” is no longer required between routine tasks or phases.
- An interruption signals a real unresolved decision, authority requirement,
  or exhausted recovery path.
- External publication, credentials, rights determinations, public releases,
  compatibility archival, and consequential interpretation remain human
  gates.
- The policy is validated from every active track's metadata to prevent silent
  regression to an interactive execution mode.

