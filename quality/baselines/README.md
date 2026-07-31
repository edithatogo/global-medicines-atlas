# Phase 3 quality baselines

`phase3.json` binds the first reviewed mutation and representative-performance
observations to exact GitHub Actions runs, commits, artifact identifiers, and
artifact digests.

The baseline has two distinct purposes:

1. prevent a pull request from silently worsening observed survivor debt or
   representative performance; and
2. preserve the independent promotion thresholds.

The mutation baseline is not a waiver. The observed score is 72.560335%, below
the declared 80% promotion requirement, so v0.8 promotion remains blocked even
when a later run does not regress. The hosted mutation lane emits a survivor
report for deterministic module/operator classification and remediation.

Performance comparisons use a 25% envelope around the reviewed GitHub-hosted
Linux observation. Absolute latency, throughput, CPU, and memory budgets still
apply independently. A dependency, runner, workload, or dataset-identity
change requires a reviewed baseline replacement rather than an in-place edit
that erases historical evidence.
