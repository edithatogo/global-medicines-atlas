# Source-health failure-isolation plan

Issue: GitHub #54; implementation PR: #151.

## Problem

A metadata-only source-health run must inspect a cohort of independent official
access surfaces. A DNS, socket, or other operating-system failure for one
source must not abort observations for every other source. The result must
remain fail-closed: the affected source is unavailable, not healthy.

## Options considered

### Option A — Per-source unavailable observation (Recommended)

Catch bounded transport, policy, parsing, and OS-level failures inside the
single-source probe and return an explicit `UNAVAILABLE` observation. Continue
the stable-order cohort scan.

Trade-offs: the run can complete with partial availability, so consumers must
inspect each source state and must not interpret the aggregate as complete
coverage. This is the best fit for independent-source monitoring and preserves
source-level provenance.

### Option B — Abort the complete cohort on any failure

Propagate the first error and mark the entire run failed.

Trade-offs: simple control flow, but one transient or misconfigured endpoint
hides all other source observations and prevents useful diagnosis. Rejected for
routine health monitoring.

### Option C — Retry indefinitely or globally before recording failure

Retry DNS/transport errors until a global threshold is reached.

Trade-offs: may improve transient success but risks long-running workflows,
rate-limit violations, repeated access to restricted services, and delayed
visibility of persistent failures. Bounded per-source retries may be added
later only with explicit budgets and receipts; it is not a substitute for
failure isolation.

## Implemented plan

1. Keep the existing bounded request size, timeout, redirect, destination
   allowlist, and metadata-only response policy.
2. Extend the single-source failure boundary to include `OSError`, covering DNS
   and socket resolution failures.
3. Return `ProbeState.UNAVAILABLE`, no status code when no HTTP response exists,
   and a non-sensitive failure-class detail.
4. Continue probing remaining sources in stable source-id order.
5. Add a regression test using a resolver that raises `OSError`.
6. Validate the focused source-health suite and retain explicit source-level
   availability semantics in receipts.

## Contingencies and follow-up

- If failure rates are high, investigate endpoint drift, DNS, firewall, and
  allowlist configuration separately; do not weaken destination controls.
- If a source needs retries, add bounded exponential backoff with a per-source
  budget, `Retry-After` handling, and a receipt field for attempts.
- If an endpoint returns oversized or malformed data, preserve the existing
  unavailable/unreadable state and do not retain response bytes.
- A successful health probe never clears rights, coverage, schema-parity, or
  live-qualification gates.

## Acceptance criteria

- One source's DNS failure does not abort the cohort.
- The failing source is explicitly `UNAVAILABLE`.
- No response body or credential is persisted by the probe.
- Existing private-network and destination-allowlist protections remain intact.
- Focused tests pass and hosted required checks are green before merge.
