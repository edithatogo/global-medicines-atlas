# Phase 3 quality baselines

`phase3.json` binds the first reviewed mutation and representative-performance
observations to exact GitHub Actions runs, commits, artifact identifiers, and
artifact digests.

The baseline has two distinct purposes:

1. prevent a pull request from silently worsening observed survivor debt or
   representative performance; and
2. preserve the independent promotion thresholds.

The mutation baseline is not a waiver. The reviewed score is 83.701799%, above
the declared 80% promotion requirement. The remaining 317 survivors stay
explicit test debt: none is waived or classified as equivalent without
mutant-level proof. The hosted mutation lane continues to emit a survivor
report for deterministic module/operator classification and remediation.

Performance comparisons use a 25% envelope around the reviewed GitHub-hosted
Linux observation. Absolute latency, throughput, CPU, and memory budgets still
apply independently. A dependency, runner, workload, or dataset-identity
change requires a reviewed baseline replacement rather than an in-place edit
that erases historical evidence.
