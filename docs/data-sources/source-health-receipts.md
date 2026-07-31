# Source-health receipts

Source-health checks produce deterministic, metadata-only receipts. They do
not retain response bodies and do not establish regulatory completeness,
funding coverage, or source authority.

## Contract

Schema version 1 records:

- the expected update cadence and, when supplied by the source, its
  `Last-Modified` timestamp;
- freshness age and whether the observation falls within the expected cadence;
- the current consecutive-failure count and bounded retry-attempt metadata;
- a stable deduplication key for one source, probe state, status code, and
  sanitized failure class;
- an escalation transition: `none`, `open`, `deduplicated`, or `resolved`;
- adapter-output parity as `matched`, `changed`, or `not_assessed`; and
- a content-addressed receipt identifier over the complete receipt body except
  the identifier itself.

The adapter parity fields contain only SHA-256 fingerprints. They do not retain
adapter records or source payloads.

## Escalation semantics

An unavailable observation increments the prior consecutive-failure count.
The default threshold is three failures:

1. the threshold-crossing receipt opens an escalation;
2. later receipts with the same failure class use the same deduplication key
   and report `deduplicated` while that escalation remains open;
3. an available or blocked observation resets the failure count; and
4. the first non-failure receipt after an open escalation reports `resolved`.

Blocked sources do not count as failures because their access limitation is
already known. Operators persist receipts in append-only, date-partitioned
storage and use the deduplication key as the external issue or alert identity.

## Freshness limits

Freshness is assessed only when both a positive expected cadence and a valid
source-update timestamp are available. Missing or malformed update metadata
produces `null`, not an inferred stale or fresh claim. A source is fresh when
its non-negative age is less than or equal to the expected cadence.

## Privacy and determinism

Receipt observations replace variable exception messages with a bounded
failure class. URLs, query parameters, headers, credentials, response bodies,
and medicine-level records must not enter a durable receipt.
