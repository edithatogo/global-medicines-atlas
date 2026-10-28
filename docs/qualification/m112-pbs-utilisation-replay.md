# Exact PBS utilisation raw-B2 replay

The metadata-only M-112 replay path now accepts the six frozen PBS utilisation
objects at `edithatogo/australian-pbs-utilisation-archive` revision
`9f1d53cd50eea251b326da42a96f3ac72ebce97a`. This prepares the missing v3 replay
role under the existing federation contract. Preparation is not a successful
hosted replay, v4 admission, or consumer canary.

The qualifier checks fixed digests for the rights-lineage reconciliation,
exact six-file rights attestation, frozen inventory, source-receipt readback,
published-object verification, and B1/B2 lineage reports. Each selected path
must join to the same source ID, revision, byte count, digest, acquisition,
receipt, and immutable B2 reference. Local lifecycle metadata is independently
hashed against the retained lineage output bindings. The acquisition's original
unknown rights state is preserved; the current maintainer attestation is bound
as separate evidence and remains not independently reviewed.

`scripts/qualify_m112_v3_replay.py --target-path <exact-path> --output <plan>`
produces a deterministic v3 registration plan. The retained first plan is
`quality/qualifications/australian-m112-pbs-utilisation-v3-replay-plan-20261028.json`.
Its filename-derived period label makes no claim about source measure semantics.

After the change merges and required checks pass, the existing
`australian-m112-v3-replay.yml` workflow can run on the exact main commit with
one of those six paths. Before downloading, the executor reconstructs the PBS
plan from bound repository evidence and requires exact equality. The hosted
step downloads anonymously into a temporary directory, checks SHA-256 and byte
count without parsing values, and removes temporary bytes even on verification
failure. Its aggregate receipt is retained as a workflow artifact.

No new source, public dataset mutation, rights conclusion, or v4 admission is
performed by this preparation. Existing MBS replay plans retain their original
bytes. Further roles and the actual hosted receipts must be qualified before
any PBS v4 admission or consumer delivery. Independent recovery and the wider
Stable v1 federation gate remain open.

## Medallion v1 conformance

`scripts/qualify_m112_v1_conformance.py --cohort pbs` builds the exact six-object
candidate manifest at
`quality/qualifications/australian-m112-pbs-utilisation-v1-conformance-20261028.json`.
The same command with `--check` verifies byte-identical regeneration. It uses
the PBS-specific attestation only after the exact identity, publication and
B1/B2 evidence checks pass; it does not expand the existing MBS rights bases.
The default MBS command and its sixteen-object output retain their prior bytes.

All six PBS artifacts remain `candidate`, and all six layer promotions remain
`blocked` for incomplete v4 roles. The attestation reason records that the
instrument was not independently reviewed. This conformance manifest needs a
durable exact-main readback before it can supply a v4 candidate receipt role.

## Discovery role candidate

The metadata-only readback in
`quality/qualifications/australian-m112-pbs-utilisation-v4-discovery-role-candidate-20261028.json`
confirms anonymous public access to the frozen PBS revision, membership in the
public Health Economics and Outcomes Research collection, and one exact entry
in estate-registry revision `4802d56a340646043fc91bed218c1e8a958f42c2`.
The registry catalog matched its retained SHA-256. Its `not_assessed` state
remains a registry assessment state; it does not replace the separate exact
rights attestation. No source object was downloaded or rehashed by this check.
The candidate still needs a durable exact-main receipt binding in a complete
v4 contract; discovery membership alone performs no admission.
