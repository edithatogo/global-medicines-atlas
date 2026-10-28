# Offline research package review

Review scope: local content-addressed distribution, lineage and verification
changes, reviewed by the implementing agent on 2026-10-29. No independent
reviewer is claimed.

The local representation is explicitly versioned, requires an output digest,
retains pinned source identities, binds the assembly commit, and verifies the
separate canonical result. Public HTTPS validation and existing public metadata
shape remain in force. Revalidation rejects forged model copies; tests cover
mixed scopes, altered result bytes, invalid canonical JSON and source binding.

Focused and broader affected tests: 103 passed on Python 3.15.1; branch-aware
coverage for the three affected modules was 99.63%. Ruff, formatting and ty
passed. These synthetic results do not establish a real source canary, hosted
checks, public publication or federation acceptance. The required real-source
canary follows an exact merged code revision.
