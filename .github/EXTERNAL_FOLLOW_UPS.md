# Hosted GitHub follow-ups

Committed policy is not evidence that a hosted setting is enabled. Verify these
items through GitHub after this branch is merged:

- create an active `main` ruleset requiring pull requests, current branches,
  successful Test-Goblin, security/context, CodeQL, dependency-review, and
  Codecov checks, resolved conversations, linear history, and squash merges;
- block force pushes and branch deletion, with emergency-only maintainer bypass;
- enable private vulnerability reporting, dependency graph, Dependabot alerts,
  and code scanning where the repository plan supports them;
- synchronize `.github/labels.yml` to repository labels;
- configure GitHub Project views for roadmap, jurisdiction, external gates,
  security, dependencies, and releases while retaining Conductor as canonical;
- verify repository description, topics, homepage, licence detection, citation,
  and discussions/support links;
- obtain an explicit maintainer decision on the repository software licence,
  then add the complete authoritative licence text and update package and
  citation metadata; do not allow that licence to imply rights in restricted
  or third-party medicine data;
- replace the current post-publication release workflow with a pre-publication
  qualified release process before publishing a stable release.

Release Drafter and OpenSSF Scorecard are intentionally not added until their
official action revisions and required permissions can be verified and pinned
to immutable full commit SHAs.
