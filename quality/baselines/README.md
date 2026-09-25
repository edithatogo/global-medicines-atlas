# Phase 3 quality baselines

`phase3.json` binds the first reviewed mutation and representative-performance
observations to exact GitHub Actions runs, commits, artifact identifiers, and
artifact digests.

The baseline has two distinct purposes:

1. prevent a pull request from silently worsening observed survivor debt or
   representative performance; and
2. preserve the independent promotion thresholds.

The mutation baseline is not a waiver. The immutable `phase3.json` observation
is 1,883 killed out of 2,250 mutants (83.688889%), above the separate 80%
promotion requirement. Its 365 survivors and two untested protocol methods
stay explicit test debt: none is waived or classified as equivalent without
mutant-level proof. The hosted mutation lane continues to emit a survivor
report for deterministic module/operator classification and remediation.

Linux CI enforces the immutable mutation baseline. Local macOS Mutmut runs
record counts as advisory because Objective-C framework initialization can
abort after fork and classify otherwise tested mutants as suspicious. The
receipt's `linux_authoritative` observation is `1` only on Linux; a macOS full
profile does not establish mutation qualification. Do not replace the baseline
with macOS counts.

Performance comparisons use a 25% envelope around the reviewed GitHub-hosted
Linux observation. The observation was replaced on 2026-08-21 from run
`32446719171`, artifact `9434423562`, after the hosted runner image and locked
analytical dependencies changed; the workload identity remained unchanged and
all absolute budgets passed. Absolute latency, throughput, CPU, and memory
budgets still apply independently. A dependency, runner, workload, or
dataset-identity change requires a reviewed baseline replacement with exact
hosted evidence rather than an unexplained threshold relaxation.
