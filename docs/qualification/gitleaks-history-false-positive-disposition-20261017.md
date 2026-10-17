# Gitleaks history findings disposition (2026-10-17)

## Observed findings

The full-history Gitleaks 8.30.1 check for PR #1094 reported two
`generic-api-key` findings in commit `701c8f422195139711b626ac23d96a0d79324a95`:

- `conductor/tracks/australian_benefits_silver_gold_20260829/evidence.jsonl`,
  line 474;
- `conductor/tracks/australian_health_source_consolidation_20260829/evidence.jsonl`,
  line 157.

The findings match the `observed.huggingface_api_revision` field in each
record. A redacted report was inspected without printing matched values; the
two field values were independently confirmed to equal the public MBS archive
revision recorded in the M-109 metadata readback. They are public Git revision
identities, not credentials.

The merge commit for PR #1094 (`4781e94c7fbbd518201bbbf1c0d964e85f3da938`)
was subsequently reported with the same two paths, rules, and line numbers.
The merged evidence records retain the same already-classified public revision
fields, so the exact merge-commit fingerprints are also listed below.

## Disposition

The two exact Gitleaks fingerprints are listed in the repository-root
`.gitleaksignore`, following the [Gitleaks fingerprint exception
format](https://github.com/gitleaks/gitleaks#additional-configuration). No
rule, directory, filename, or class of findings is excluded. The
complete-history scanner remains enabled, and any new finding with a different
commit, path, rule, or line still fails the check. The source records and Git
history are unchanged.

## Evidence

- PR #1094 check run `39007251575`, job `117322128729`;
- redacted artifact `gitleaks-history-report` (two findings);
- public revision readback:
  `quality/qualifications/australian-m109-source-era-identities-20261017.json`;
- Gitleaks 8.30.1 local full-history scan after the exact-fingerprint
  dispositions: passed with no findings; hosted exact-head check pending.
