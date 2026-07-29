# Release input fixtures

These committed inputs exist only to exercise deterministic, rights-safe
`workflow_dispatch` dry runs. They contain two self-authored synthetic medicine
rows under the reserved `ZZ-FIXTURE` jurisdiction and `.invalid` evidence URLs.
They contain no regulatory, funding, reimbursement, personal, confidential, or
third-party medicine data.

The receipt's `qualified` state means only that the exact synthetic staged bytes
passed the fixture checks. It is not maintainer approval, production
qualification, permission to publish, or evidence about a real jurisdiction.
The verifier records `no-maintainer-approval`, and the workflow rejects these
inputs whenever `publish=true`.

Content identities:

- contract canonical SHA-256:
  `617aa047ca16ed352e1512c6f0d099e6522caa80ae988dd0b2a8c8c753212385`
- reviewed rows SHA-256:
  `0969818f7ceb6d3c1913ae44ed1674437bb730228d7fc6507fd64205d989368a`
- staged package SHA-256:
  `c1ba9fb0b292ad6a691ca37856fba76ce91556b4d1a76baa96df82e7baa3ce0b`

The release SBOM is the complete transitive closure of
`[project.dependencies]` and requested runtime extras in `uv.lock`. Dependency
groups used only for testing, Test-Goblin, typing, profiling, edge testing,
security tooling, building, and repository maintenance are intentionally
dev-only and excluded unless a runtime dependency also reaches the same
package.
