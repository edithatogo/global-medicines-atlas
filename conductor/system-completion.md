# System completion execution charter

## Execution objective and authority

Complete the shared system against the existing frozen source and object
inventories. The default execution scope adds no sources. Select work by the
shared capability or release gate it closes; dataset-specific work is eligible
when it is a demonstrated prerequisite for that gate.

The [machine-readable scheduling plan](./system-completion.json), checked by
`scripts/validate_context.py`, records the lanes and their prerequisites. This
charter sets scheduling priority. It does not change acceptance criteria,
qualify data, waive requirements, or authorize publication or release.

Use the [Stable v1 contract](../quality/qualifications/stable-v1-contract.json),
its [readiness reconciliation](../quality/qualifications/stable-v1-release-readiness-reconciliation.json),
the owning track receipts, and `scripts/reconcile_stable_v1_contract.py` for
gate states. Read their bound evidence before choosing work; do not infer
current status from historical plan sections. Conditional maintainer approval
remains subject to its recorded conditions. The current M-105 and M-107
dispositions remain effective until supported by their required evidence and
any applicable decision.

## Acceptance lanes

| Order | Lane | Completion evidence and owning tracks |
| --- | --- | --- |
| 1 | Shared Silver/Gold contracts and uncertainty | Qualify source-faithful schemas, field-state accounting, supported meanings, and relationship promotion/rejection behavior. Preserve every field and reconcile it as interpreted, native unresolved, or unavailable. Unsupported meanings remain explicit; universal interpretation is not required. Silver/Gold and consolidation tracks own their existing criteria. |
| 2 | Qualified v4 delivery and admission | Bind eligible outputs to exact identities, lineage, rights, required contract roles, and admission receipts. Complete each mandatory eligible-object obligation. Data-plane and producer tracks own these receipts. |
| 3 | API, CLI, Atlas and export consumers | Traverse qualified admitted data through actual consumers and exports, retaining provenance, coverage, uncertainty, bounded behavior, and exact revision/digest evidence. Platinum owns these checkpoints with producer support. |
| 4 | Independent recovery and compatibility | Qualify the required independent recovery target, restoration, checksum inventory, RPO/RTO, and declared consumer/package compatibility. Data-plane, Platinum, and Stable tracks retain their respective acceptance boundaries. |
| 5 | Federation acceptance and Stable promotion | Reconcile authoritative requirement and gate evidence, complete federation acceptance, then reproduce and verify the exact candidate and protected checks before exercising conditional Stable approval. Use the existing release harness and authority. |

These are dependency stages, not an instruction to serialize all work. Tasks
in independent lanes may proceed in parallel when their prerequisites are
satisfied and file/object ownership is explicit. A fixture or representative
reference-class canary can establish shared behavior; it cannot substitute for
mandatory eligible-object identity, lineage, rights, admission, recovery, or
consumer evidence. Candidate publication, byte verification, reader canaries,
semantic qualification, product acceptance, and release remain distinct.

## Task selection and stop conditions

Before starting each task, record:

1. the owning system lane and existing capability or gate;
2. the concrete observed failure or missing acceptance proof;
3. the bounded object, code, and evidence scope within the frozen inventory;
4. the expected receipt or observable result that closes the gap; and
5. the smallest meaningful validation and the unchanged evidence to reuse.

Choose the earliest unblocked gap on the system completion path. A dataset
task must explain why the shared gate requires that work. Stop extending a
dataset when the required contract behavior and evidence are established;
retain unresolved values explicitly and proceed to the next system gap.

When a task cannot advance a system gate, return it to the deferred backlog.
When a gate is blocked, record the exact missing evidence or authority and
continue independent eligible work under the existing bounded recovery policy.
Do not convert a blocked prerequisite into acceptance or declare the system
complete while mandatory gates remain open.

Broader Bronze coverage, new terminology, new sources, and optional frontier
experiments are deferred under the current instruction. Their existing
incomplete criteria and evidence remain visible. Reopen them only when needed
for a named mandatory system gate or when the maintainer changes scope.
A later direct maintainer scope instruction supersedes this scheduling scope;
record the change explicitly in the versioned plan and its validator. A scope
change still supplies no rights, admission, publication, or release authority.

Use targeted checks for the changed behavior and reuse unchanged receipts.
Broaden testing only for an identified integration concern or a required
coherent milestone. Existing protected CI lanes and final release checks remain
in effect; policy, scheduling, and evidence edits do not by themselves require
a full local suite. All rights, release, privacy, source integrity, and absolute
outbound communications guardrails continue to apply.
