# Stable v1 hosted governance qualification

This qualification records point-in-time, authenticated, read-only GitHub
evidence for `edithatogo/global-medicines-atlas` and the linked
[Global Medicines Atlas Conductor project](https://github.com/users/edithatogo/projects/35).
It does not alter repository settings, issues, project items, views, workflows,
security features, or releases.

## Evidence boundary

The committed snapshot records normalized responses and SHA-256 identities for:

- repository identity, the `main` default-branch commit, merge controls, and
  security-analysis settings;
- repository rulesets, classic branch protection, all required checks, and
  Actions permissions;
- code-scanning setup, private vulnerability reporting, automated security
  fixes, vulnerability alerts, and accessibility of Dependabot, CodeQL, and
  secret-scanning alert endpoints;
- issues #44 and #40–#43 with their native parent/subissue relationships; and
- ProjectV2 #35 identity, linked default repository, fields and options, views,
  workflows, and the stable-v1 project items.

Each observation is independently classified as `available`,
`permission_unavailable`, `not_supported`, or `failed`. Permission or feature
unavailability limits the qualification but is never represented as an
operational failure. Unexpected request or normalization failures reject the
receipt.

## Current result

The snapshot is bound to `main` commit
`f2748e3fea21d35c163091cc9e320130c0bca992`. Repository identity, classic
branch protection, 24 required checks, security controls, issue hierarchy,
project identity, project fields, and all six project workflows verify.
GitHub currently reports zero repository rulesets; the receipt records this
exactly and verifies the observed classic branch protection instead.

The overall state is `partial`, for two bounded reasons:

- `Gates & High Risk` does not expose `Gate` and `Priority`, while
  `Evidence & Review Due` does not expose `Evidence State` and `Gate`; and
- closed Phase 1 project item #41 remains `In Progress`/`Partial`, while closed
  Phase 2 item #42 remains `Unverified`.

These are hosted ProjectV2 configuration drifts, not repository-code failures.
They were not changed because this increment is explicitly read-only.

## Reproduction

Offline verification uses only committed evidence and performs no network call:

```console
uv run --python 3.14.6 --group dev python scripts/qualify_stable_v1_hosted_governance.py
```

An authorized operator can refresh the snapshot with read-only GitHub calls:

```console
uv run --python 3.14.6 --group dev python scripts/qualify_stable_v1_hosted_governance.py --acquire
```

Review the diff after acquisition. A changed receipt can reflect legitimate
hosted changes, permission changes, API drift, or a control regression; it must
not be accepted solely because regeneration succeeded.

## Durable artifacts

- `quality/snapshots/stable-v1-hosted-governance.json` and its digest sidecar;
- `quality/qualifications/stable-v1-hosted-governance.json` and its digest
  sidecar; and
- JSON Schemas under `schemas/stable-v1-hosted-governance-*-v1.json`.

The receipt does not qualify organisation-level controls, rendered ProjectV2
UI behavior, external publication, a licence decision, or stable-release
approval. Those remain separate authority and release gates.
