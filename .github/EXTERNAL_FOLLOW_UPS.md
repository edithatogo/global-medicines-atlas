# Hosted GitHub follow-ups

Committed policy is not evidence that a hosted setting is enabled. Verify these
items through GitHub after this branch is merged:

- retain automated branch protection and add a focused active `main` ruleset
  blocking branch deletion and non-fast-forward updates;
- block force pushes and branch deletion, with emergency-only maintainer bypass;
- enable private vulnerability reporting, dependency graph, Dependabot alerts,
  and code scanning where the repository plan supports them;
- synchronize `.github/labels.yml` to repository labels;
- configure GitHub Project views for roadmap, jurisdiction, external gates,
  security, dependencies, and releases while retaining Conductor as canonical;
- verify repository description, topics, homepage, licence detection, citation,
  and discussions/support links;
- verify Apache-2.0 licence detection and the bounded CC-BY-4.0 derived-data
  policy after merge; neither grants rights in third-party medicine data;
- verify Renovate creates its Dependency Dashboard before retiring any other
  dependency-update mechanism;
- run the software-only, pre-publication qualification workflow for the release
  candidate; dataset publication remains a separate rights-qualified process.

Release Drafter and OpenSSF Scorecard are intentionally not added until their
official action revisions and required permissions can be verified and pinned
to immutable full commit SHAs.
