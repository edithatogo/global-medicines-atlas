# Autonomous Track Execution Policy

## Purpose

Conductor tracks run continuously through safe, in-scope work. The agent does
not pause for routine confirmation, phase boundaries, commits, pull requests,
green-check merges, documentation synchronization, or selection of the next
unblocked task. It engages the accountable maintainer only when a real
decision, authority grant, credential boundary, or consequential human gate
cannot be resolved from repository evidence.

This policy adapts the Plan Mode, structured-interaction, extension-policy, and
self-correction ideas introduced in upstream Conductor 0.4.x to Codex. It does
not claim that upstream Conductor provides unattended background execution.

## Default execution loop

For each active track, the agent must:

1. reconcile the registry, metadata, plan, source, tests, Git history, hosted
   checks, issues, and durable external receipts;
2. select the next safe, unblocked task and mark it `[~]`;
3. implement and verify it using `conductor/workflow.md`;
4. record evidence before marking it `[x]`;
5. complete phase verification without requesting ceremonial confirmation;
6. run `conductor-review`, apply findings, and repeat verification;
7. open a scoped pull request, repair failures, wait for required checks, and
   merge when all required checks pass;
8. reconcile Conductor and GitHub state, archive a completed track, and move to
   the next unblocked track.

Status updates are informational and must not be phrased as approval requests.
The absence of a user response is not a blocker for safe work already in scope.

## Decision boundary

The agent pauses only when at least one of these conditions applies:

- two or more materially different choices remain and repository evidence does
  not determine the choice;
- credentials, new authority, expenditure, legal or rights interpretation, or
  access to restricted data is required;
- an irreversible or public external action is required;
- a public release, external publication, compatibility archive, or
  consequential clinical or policy claim is proposed;
- scope would materially expand beyond the approved track;
- the same blocking condition persists after three bounded, evidence-driven
  attempts and no safe alternative can advance the track;
- safety, privacy, provenance, or source-integrity controls require human
  judgment.

Routine implementation details, reversible refactors, test fixes, dependency
choices already governed by `tech-stack.md`, and evidence-backed selection of
the next task are not decisions requiring interruption.

## Decision request contract

A blocking decision request contains exactly one decision and:

1. states the decision and why it is needed now;
2. presents two or three mutually exclusive options;
3. lists the recommended option first and labels it **Recommended**;
4. gives the rationale, material trade-offs, and consequences of each option;
5. identifies what work continues or remains blocked while awaiting the answer;
6. accepts a maintainer-defined alternative.

The agent must not ask an open-ended question when useful options can be
derived. It must not bundle unrelated decisions into one request.

## Bounded self-correction

When an operation fails, the agent:

1. captures the exact failure and checks whether the underlying state changed;
2. attempts up to three evidence-driven corrections, varying the approach
   rather than repeating the same command;
3. uses safe alternatives and continues non-blocked work in parallel;
4. records persistent failures and their attempted remedies in track evidence;
5. escalates only when the decision boundary is reached.

Rate limits, queued CI, transient network failures, and unchanged monitored
state are waiting conditions, not decision requests. Destructive recovery,
control weakening, fabricated evidence, and bypassing a human gate are never
valid self-corrections.

## Checkpoints and recovery

- Task, phase, review, pull-request, and archive transitions are resumable from
  committed plan markers and append-only evidence.
- Every hosted claim includes a durable URL, exact commit, and observed state.
- A task stays `[~]` after interruption unless evidence proves completion or
  the work is explicitly returned to `[ ]`.
- Before resuming, the agent checks for dirty work, divergent branches, stale
  check runs, superseding user instructions, and changed external state.
- Automatic merging is permitted only for scoped pull requests whose required
  checks pass and whose changes do not cross a human gate.

## Upstream feature disposition

| Upstream Conductor 0.4.x feature | Project disposition |
| --- | --- |
| Plan Mode integration | Adopt the separation of planning and execution; repository plans remain authoritative |
| Extension-native policies | Adopt through this versioned repository policy and machine validation |
| Structured option prompts | Adopt for every blocking decision |
| Setup self-correction | Generalize to the bounded three-attempt protocol |
| Mandatory phase manual confirmation | Override; use automated evidence and interrupt only at the decision boundary |
| Automatic extension updates | Do not adopt silently; refresh the bundled Codex skill through a reviewed dependency change |

