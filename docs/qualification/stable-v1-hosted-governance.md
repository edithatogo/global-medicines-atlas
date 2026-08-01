# Stable v1 hosted governance qualification

This qualification records point-in-time, authenticated, read-only GitHub
evidence for `edithatogo/global-medicines-atlas` and the linked
[Global Medicines Atlas Conductor project](https://github.com/users/edithatogo/projects/35).
Snapshot acquisition and qualification are read-only. On 2026-08-01, separately
authorized hardening added five already-mandatory workflow contexts to classic
`main` branch protection and an active destructive-update ruleset. Neither
action altered Project #35, issues, workflow definitions, security features, or
releases, and neither action was performed by the acquisition.

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
`0917a7d7f1de1b865ca2fc0a6d1a73d5b5aa3204`. Repository identity, the active
`Protect main from destructive updates` ruleset, classic branch protection,
all 28 required checks and their producer application IDs, security controls,
issue hierarchy, project identity, project fields, five project views, and all
six enabled project workflows verify. The ruleset applies to the default branch
with active enforcement; classic protection independently blocks force pushes
and deletions, requires linear history and resolved conversations, and retains
zero required approving reviews.

The overall state is `qualified`. Project #35 remains linked to
`edithatogo/global-medicines-atlas`; Phase 1 and Phase 2 are `Done`/`Verified`,
while the still-open Phase 3 item remains `Todo`/`Unverified` behind its human
gate. The two risk/evidence views retain their expected custom fields.

## Authorized branch-protection hardening

Immediately before the mutation, an authenticated `GET` of classic `main`
protection confirmed the same 23-context set recorded in the prior committed
snapshot (`sha256:a05b124720864e447781e2f30cfca572dffeb4eb49e0ddbc6dce8eb9196ae6ca`,
bound to `main` commit `0c980c06305decb23432060d2708851890c64230`).
The scoped `POST` to [classic main protection](https://api.github.com/repos/edithatogo/global-medicines-atlas/branches/main/protection/required_status_checks/contexts)
added five contexts, removed none, returned 200, and a second authenticated
`GET` confirmed 28 contexts. All added contexts are bound to the GitHub Actions
application (`app_id=15368`); `codecov/patch` remains bound to Codecov
(`app_id=254`).

The exact before set was:

```text
CodeQL
Context and repository policy
Dependency audit and SBOM
Dependency review
Mojo nightly / smoke
Python 3.14 / coverage
Python 3.14 / dependencies
Python 3.14 / e2e
Python 3.14 / edge
Python 3.14 / gremlins
Python 3.14 / integration
Python 3.14 / mutation
Python 3.14 / package
Python 3.14 / profile
Python 3.14 / property
Python 3.14 / regeneration
Python 3.14 / representative performance
Python 3.14 / routine
Python 3.14 / smoke
Python 3.14 / strict
Python 3.14 / unit
Repository and history leak detection
codecov/patch
```

The exact addition set was:

```text
Consumer / linux / Python 3.14
Consumer / macos / Python 3.14
Consumer / windows / Python 3.14
Python 3.14 / governed recovery rehearsal
Python 3.14 / operational exercises
```

Therefore the exact after set is the union of those two disjoint sets (28),
with an empty removal set. The required contexts now comprise 26 mandatory
`main`-push jobs, the PR-only `Dependency review` job, and the external
`codecov/patch` status. Tests derive the 26 job names from the current workflow
matrices and fixed job names, preventing another hand-maintained count from
silently omitting a lane.

The post-change branch-protection observation digest is
`68e624d5cdd74a1066ad9ba6ce74112050efe895befddcc568d4f0de69581ac8`.
The full snapshot digest is
`8acdd6d66666076cf2dfcfc0901d0ffea4f6f55372388d899c3c7e4a762fbc9a`.
The derived qualification receipt digest is
`cf7ad5e998b69b1fc5f35f7fe0b154eca279eb373a991078a2d589544502a072`.
Project #35 retained response digest
`b53e1e504c3635f0c7e708ca4ada3c7c8b4a306997ba1b4909062ae4c34e103c`,
and the active-ruleset observation has digest
`a91f26f9b6f2293c2f5fb986c4b6cf8e166612dcec3d549ac27652f453f17e0f`.

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
not be accepted solely because regeneration succeeded. `github_mutated=false`
means the acquisition and qualification code made no write call; it does not
erase the separately documented, authorized hardening action that preceded the
snapshot.

## Durable artifacts

- `quality/snapshots/stable-v1-hosted-governance.json` and its digest sidecar;
- `quality/qualifications/stable-v1-hosted-governance.json` and its digest
  sidecar; and
- JSON Schemas under `schemas/stable-v1-hosted-governance-*-v1.json`.

The receipt does not qualify organisation-level controls, rendered ProjectV2
UI behavior, external publication, a licence decision, or stable-release
approval. Those remain separate authority and release gates.
