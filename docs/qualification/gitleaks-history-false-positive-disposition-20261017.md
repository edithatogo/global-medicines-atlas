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

The repository-root `.gitleaks.toml` extends Gitleaks defaults and adds one
allowlist scoped to `generic-api-key`. Its anchored matches require either the
exact `huggingface_api_revision` field and public revision recorded in the
qualification readback, or the exact `API` field and edge-set SHA-256 in the
candidate consumer receipt. The latter was reported in PR #1116 at line 525 of
the MBS track evidence. Both values were verified against their public
evidence records and are not credentials. The allowlist does not exclude a
rule, directory, filename, source record, or class of values. Local Gitleaks
8.30.1 discrimination checks report no finding for each exact field/value;
changed values and the same values under `api_key` remain findings. The
complete-history scanner remains enabled. The source records and Git history
are unchanged.

## Evidence

- PR #1094 check run `39007251575`, job `117322128729`;
- PR #1095 rebased check run `39008220332`, job `117324968229` (the same
  findings were attributed to merge commit `4781e94c7fbbd518201bbbf1c0d964e85f3da938`);
- redacted artifacts `gitleaks-history-report` (two findings per report);
- public revision readback:
  `quality/qualifications/australian-m109-source-era-identities-20261017.json`;
- Gitleaks 8.30.1 local discrimination check: exact field/value passed;
  changed value and wrong field each remained findings.
