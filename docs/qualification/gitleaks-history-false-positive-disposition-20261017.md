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

The exact-head history check for M-112 v3 replay PR #1199 also reported 33
`generic-api-key` matches. A redacted Gitleaks report showed that every matched
value is a 64-character lowercase hexadecimal SHA-256 digest: two public
dataset-access metadata response digests repeated across the per-object role
report under `dataset_access_response_sha256`, and one deterministic replay-plan
digest under `idempotency_key`. The values were
matched to those evidence fields without printing the redacted scanner values.
They are content/response identities, not credentials. The allowlist adds only
the two exact access-response digest field/value pairs and the one exact replay
idempotency digest field/value pair; it does not allowlist those fields with
changed values or allow any of the values under `api_key`.

PR #1211 adds another exact-head replay readback pair. Its redacted history
report identified the same deterministic `idempotency_key` in the run's plan
and execution receipt. The value is a SHA-256-shaped replay identity, not a
credential. The allowlist adds only that exact field/value match; changed
values and other field names remain findings.

## Evidence

- PR #1094 check run `39007251575`, job `117322128729`;
- PR #1095 rebased check run `39008220332`, job `117324968229` (the same
  findings were attributed to merge commit `4781e94c7fbbd518201bbbf1c0d964e85f3da938`);
- redacted artifacts `gitleaks-history-report` (two findings per report);
- public revision readback:
  `quality/qualifications/australian-m109-source-era-identities-20261017.json`;
- PR #1199 redacted Gitleaks report: 33 findings in three exact evidence
  identities, all confirmed SHA-256-shaped;
- public dataset-access identities:
  `quality/qualifications/australian-m112-v4-contract-role-evidence-qualification-20261020.json`;
- replay idempotency identity:
  `quality/qualifications/australian-m112-v3-replay-plan-20261020.json`;
- Gitleaks 8.30.1 local discrimination check: exact field/value passed;
  changed value and wrong field each remained findings.
- PR #1211 redacted Gitleaks report: two findings for the exact replay
  idempotency field/value in the plan and execution receipt.

PR #1218 adds two findings for the same deterministic replay-plan `idempotency_key` in the plan and execution receipt. The value is a SHA-256-derived identity verified against the planner formula, not a credential. The exact field/value pair is allowlisted; changed values and other field names remain detectable.

PR #1225 adds two findings for the Q3 2016 demographics replay's deterministic
`idempotency_key` in its plan and execution receipt. The value is derived by
the replay planner from the partition and snapshot identities; it is not used
for authentication or authorization. The allowlist includes only this exact
field/value pair. Changed values and other field names remain detectable.

PR #1232 adds two findings for the Q1 2016 demographics replay's deterministic
`idempotency_key` in its plan and execution receipt. Both records match, and
the value recomputes from the replay planner's partition and snapshot identity
formula. It is not used for authentication or authorization. The allowlist
includes only this exact field/value pair; changed values and other field names
remain detectable.

PR #1241's complete-history scan found the Q3 July HR replay's deterministic
`idempotency_key` in its plan and execution receipt. The redacted report
identified two matches. The value recomputes from the replay planner's exact
partition and snapshot identities and is not used for authentication or
authorization. The allowlist adds only this exact field/value pair; changed
values and other field names remain detectable.


The Q1 HR replay plan and execution receipt from run `39533443472` carry the
same deterministic `idempotency_key`. The key recomputes as SHA-256 of the
canonical JSON array of its partition ID and snapshot ID; it is not an access
credential. The additional allowlist pattern matches only this exact value in
this exact field. Mutated values and credential field names remain rejected.

## 2026-10-28 exact PBS replay identity

PR #1361 head `bc0b3b349d38e4fb287714ce59bd6a6bef1de16c` failed the
redacted history scan in run `40672929147`, job `122764005322`. Its one finding
was line 54 of
`quality/qualifications/australian-m112-pbs-utilisation-v3-replay-plan-20261028.json`:
the deterministic replay idempotency field. The harness independently computes
that value from the canonical partition and snapshot IDs.

The configuration adds only that exact field/value pair to the existing
allowlist. Controls reject a changed digest or a credential-field substitution;
a native synthetic API-key control remains detected by Gitleaks 8.30.1. The
same scanner version checked the complete target/head history with the revised
configuration: 1,232 commits and approximately 366.88 MB, no leaks found.
The hosted failure remains recorded; the corrected PR head requires new CI.

## Six PBS native replay receipts

The six completed PBS replay receipts retain six deterministic idempotency
identities. The first was already qualified with the replay plan; the other
five are added as exact field/value exceptions. The harness recomputes every
value from the canonical partition and snapshot IDs and continues to reject
changed values or credential-field substitutions. A native synthetic API-key
control remains detected. No rule, path, filename or value class is excluded.
