# Live source and deployment qualification

This register implements the local qualification boundary for [#54](https://github.com/edithatogo/global-medicines-atlas/issues/54) and [#61](https://github.com/edithatogo/global-medicines-atlas/issues/61).

The authoritative machine-readable record is
[`external-qualification-register.json`](../../quality/qualifications/external-qualification-register.json).

## Current result

The repository is qualified to execute bounded catalog, fixture, source-health,
and deployment-contract checks. It is **not** qualified to claim current live
source coverage, production deployment, or accessibility of a deployed atlas.

The current source maturity record contains 96 catalogued sources: 36 at M0,
58 at M1, and 2 at M2. It contains zero live source receipts. Committed
fixtures and public URLs are not live evidence.

## #54 live-source boundary

Each source must be promoted independently only after all of the following are
present:

- lawful source-specific access and redistribution decision;
- current payload and immutable retrieval receipt;
- authority, jurisdiction, retrieval time, checksum, schema fingerprint, and
  coverage denominator;
- adapter-output parity and drift result; and
- separate regulatory, funding, formulary, and terminology dimensions.

The register calls out the current high-priority FDA/Drugs@FDA, DPD, PBS,
EMA, NHS dm+d, NZULM/NZMT, and PMDA gates. No source-specific live claim is
made by this commit.

## #61 deployment boundary

Production readiness remains unqualified until clean installation and service
start from built artifacts, live health/readiness verification, production-data
provenance and coverage checks, and browser-based accessibility, keyboard, and
responsive checks are captured in durable receipts.

Local fixture qualification, CI health, and source-health implementation do
not satisfy those external observations. No deployment, credentialed source
acquisition, or publication action is performed here.

## Promotion rule

The register must remain blocked when any required evidence is absent. A future
source or deployment receipt may be appended only with the exact artifact,
endpoint, authority, time, checksum, coverage, and rights evidence it supports.
The presence of a URL or a passing workflow must not promote a source or
deployment automatically.
