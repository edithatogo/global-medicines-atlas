# Specification: Produce free-tier datahouse decision evidence

## Overview

Use only standard GitHub-hosted Actions and Hugging Face free-tier repositories
to reduce the remaining uncertainty around object-versioning workflows,
high-update table formats, cross-provider recovery, and technology promotion.
The work produces evidence for the accountable maintainer; it does not claim
production durability, create a paid dependency, or promote a technology.

Only repository-authored synthetic fixtures, schemas, benchmark code, and
non-sensitive receipts may be published. Source-derived bytes remain excluded
unless an acquisition-specific rights decision independently permits their
publication.

## Authoritative inputs

- `conductor/archive/datahouse_interoperability_experiments_20260820/`, merged
  at `409fd7e2c036cde96fb6a5f7fde761f756fdea84` and reviewed at
  `cea518f61fd0ee810a9bdae711b573f624c7bc29`.
- `src/global_medicines_atlas/rights_policy.py`, fail-closed publication policy.
- `quality/qualifications/object-versioning-prerequisite.json` and
  `quality/qualifications/delta-hudi-prerequisite.json`.
- Apache License 2.0 in `LICENSE`, covering repository-authored contributions.
- GitHub Actions billing and usage documentation, observed 2026-08-20:
  `https://docs.github.com/en/billing/concepts/product-billing/github-actions`.
- Hugging Face storage and repository documentation, observed 2026-08-20:
  `https://huggingface.co/docs/hub/storage-limits` and
  `https://huggingface.co/docs/hub/en/repositories`.
- Pinned Iceberg, Delta Lake, Apache Hudi, lakeFS, DuckLake, Python, and lockfile
  identities recorded by the predecessor track.

## Functional requirements

### Rights and publication boundary

- Inventory every proposed public artifact by origin, licence, sensitivity,
  content digest, and publication decision.
- Permit public release only for repository-authored synthetic or aggregate
  evidence covered by Apache-2.0 and expressly approved by the maintainer.
- Exclude credentials, source-derived payload bytes, personal data, restricted
  source material, and licence-uncertain artifacts.
- Publish a dataset card and machine-readable manifest before any Hugging Face
  upload; bind the resulting repository revision to the evidence ledger.

### Free-tier storage and workflow mechanics

- Exercise commit, branch, divergent update, conflict detection, merge,
  rollback, retention simulation, checksum inventory, and restoration using a
  disposable GitHub-hosted environment.
- When a Hugging Face repository can be created without a paid plan, replicate
  only the approved synthetic evidence package and rehearse restoration into a
  clean workspace.
- Measure observed experimental RPO and RTO while explicitly rejecting WORM,
  Object Lock, guaranteed geographic replication, or production-SLA claims.
- Treat GitHub and Hugging Face history as mutable workflow evidence, not as
  authoritative Bronze storage receipts.

### Workload-demand and table-format evidence

- Measure update, delete, and multi-writer requirements from governed Atlas
  receipts and source histories without inventing demand from synthetic data.
- Run an identical bounded synthetic workload against the Iceberg-ready
  baseline, Delta Lake, and Apache Hudi where current free-tier runners and
  pinned runtimes support execution.
- Record setup failures, runtime incompatibility, or runner exhaustion as
  evidence rather than weakening the workload.
- Measure correctness, update/delete semantics, conflict behavior, recovery,
  compaction, portability, elapsed time, peak process memory where observable,
  dependency footprint, and reconstruction from governed inputs.

### Maintainer decision packet

- Separate observed results, inference, unmet prerequisites, and external
  claims for every experiment.
- Classify each technology as `adopt_candidate`, `continue_experiment`,
  `reject`, `superseded`, or `not_justified`.
- Include benefits, limitations, costs, supply-chain considerations, Python
  3.14 compatibility, rollback, and the exact decision still reserved to the
  maintainer.

## Acceptance criteria

- AC-01: A fail-closed rights manifest proves which experiment artifacts may be
  public and why; excluded artifacts remain absent from public packages.
- AC-02: A reproducible GitHub-hosted object-versioning mechanics receipt covers
  branching, conflicts, rollback, inventory, restoration, and measured
  experimental RPO/RTO.
- AC-03: If authorized free-tier Hugging Face access is available, an approved
  synthetic package is published and restored with matching content digests;
  otherwise a precise failure receipt is produced.
- AC-04: A workload-demand receipt uses actual governed repository evidence and
  does not infer real demand from the synthetic benchmark.
- AC-05: Iceberg-ready, Delta, and Hudi evaluations use the same workload and
  publish comparable results or reproducible implementation-specific failures.
- AC-06: Core Python 3.14 and Bronze recovery remain independent of all
  experiment dependencies.
- AC-07: The final decision packet is schema-validated, digest-bound, and makes
  no production durability, public-source redistribution, or promotion claim.
- AC-08: Focused, affected, security, provenance, licence, regeneration, and
  hosted checks pass before merge and archive.

## Non-functional constraints

- Use only free-tier GitHub and Hugging Face services and standard runners.
- Keep workloads bounded, disposable, synthetic, and reproducible.
- Do not log, commit, or publish credentials.
- Preserve immutable payload and per-object receipt authority.
- Python 3.14 remains the complete core fallback.
- Missing capability or free-tier guarantees remain explicit negative evidence.

## External gates

- Hugging Face repository creation and public publication are authorized only
  for the rights-cleared synthetic evidence package described here.
- Source-derived byte publication remains acquisition-specific and is not
  authorized by this track.
- WORM/Object Lock, guaranteed independent replication, and production RPO/RTO
  remain unmet unless separately evidenced by a qualifying provider contract.
- Production dependency promotion, migration, or deployment remains a final
  maintainer decision after the evidence packet is reviewed.

## Out of scope

- Paid services, larger GitHub runners, or Hugging Face paid compute.
- Publishing any existing regulatory or pharmacovigilance source payload.
- Treating GitHub Actions artifacts or Hugging Face Git/Xet history as WORM.
- Changing Bronze maturity or canonical medicine semantics.
- Production migration or availability/SLA claims.

