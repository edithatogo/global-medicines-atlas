# Federated track audit: 2026-09-02

This read-only audit reconciles the three active federation tracks with the
default branch, their public GitHub issues and anonymously observable Hugging
Face state. It does not authenticate private estate state, mutate a collection,
publish data, approve a recovery destination, or promote a preview dependency.

## Integrity reconciliation

- `public_hf_federated_data_plane_20260829` was marked planned in the registry
  while its metadata and plan were in progress and several implementation
  slices had merged. The registry is corrected to in progress.
- All three metadata timestamps predated their latest durable evidence. They
  now record this audit time without changing status or acceptance claims.
- GitHub issues [#340](https://github.com/edithatogo/global-medicines-atlas/issues/340),
  [#342](https://github.com/edithatogo/global-medicines-atlas/issues/342), and
  [#343](https://github.com/edithatogo/global-medicines-atlas/issues/343) are
  open, consistently reflecting incomplete tracks.
- Repository foundations are merged through public-collection reconciliation
  in PR #412, frontier prerequisites in PR #413, and the Platinum resolver in
  PR #414. Their green checks prove those exact repository slices only.

## Anonymous public data-plane observation

The official public Hub API returned the following exact, non-private,
non-gated dataset heads:

| Dataset | Observed revision |
| --- | --- |
| `edithatogo/australian-mbs-source-archive` | `75f9f20a36ddb829dfe0ca88660664570782be02` |
| `edithatogo/australian-pbs-source-archive` | `31ec854ef9fc82f30a0dbe743fdf50a2e5bd24a7` |
| `edithatogo/global-medicines-atlas-international-open` | `654f71c84cdb17b4032396bcbc961bef8757fb19` |
| `edithatogo/global-medicines-atlas-international-permissive-20260821` | `87d3b54ac932018c276a1c50033ac287520cf85e` |
| `edithatogo/global-medicines-atlas-cms-partd-20260827` | `abcff8ebd1f624c4bbb0a87d903b184388c98254` |
| `edithatogo/reimbursement-atlas` | `8e062578f14e12cf3238700a93946339da9c5d88` |

This observation verifies public metadata, not every object digest. Existing
hosted receipts remain the byte-level authority for already qualified objects.

The public `Health Economics and Outcomes Research` collection contains four
datasets, including both Australian source archives. Its reimbursement-atlas
note still says the origin is unresolved, and the two Australian members have
no explanatory notes. `Policy AUS` was not present in the anonymous public
collection denominator. That proves only that it was not publicly observable;
it does not authorize inspection of, or a visibility change to, private state.

## Repository-owned remaining work

### Public Hugging Face federated data plane

1. Retain the missing Phase 1 intended-failure evidence or explicitly record
   why it is irrecoverable; do not infer it from later green tests.
2. Finish v4 producer adoption and independent typed admission, then emit the
   non-empty Australian benefits medallion manifest.
3. Complete data cards, Croissant, citations, provenance, coverage, rights,
   correction/withdrawal and version histories for each public authority.
4. Qualify continuing exact archive/container bytes and the complete producer
   denominator; publish derived products only after their individual gates.
5. Prepare exact desired collection and estate-registry inputs for hosted
   mutation. The mutation itself remains an external-publication gate.
6. Prepare an independent-recovery contract and verifier. Selecting and
   publishing to an administratively independent destination remains a human
   gate.
7. Run integrated qualification and reconcile exact hosted/public receipts.

### Federated medicines Platinum

1. Complete Phase 1 DuckDB/Polars projection and predicate-pushdown adapters,
   durable query-result evidence envelopes, and empty-machine public-fixture
   qualification.
2. Implement the shared typed CLI/API service, bounded deterministic
   pagination, provenance envelopes, rate/size controls and OpenAPI canaries.
3. Implement accessible historical and evidence-graph product views without
   collapsing service-benefit, funding, regulatory, formulary or terminology
   dimensions.
4. Add pinned reimbursement-atlas and donor-successor compatibility canaries.
5. Prepare deterministic research exports and complete product qualification.
   Public release and consequential interpretation remain human gates.

### Federated medallion frontier experiments

1. Phase 1 is merged and green at PR #413; its evidence ledger previously
   stopped at hosted-pending and is superseded by this exact merge receipt.
2. Phases 2 through 5 remain unstarted: remote query/Xet, isolated Iceberg,
   additive research attestations, and graph/semantic projection experiments.
3. Phase 6 must measure threat, cost, dependencies, fallback and withdrawal and
   assign a fail-closed disposition to every row. This track may recommend but
   cannot itself promote a production dependency.

## Dependency order

The first safe implementation route is to finish the repository-only Platinum
query adapter and result-envelope contract against synthetic and already
admitted fixtures. Live collection mutation, derived-data publication,
independent recovery publication, and technology promotion are kept outside
that slice.
