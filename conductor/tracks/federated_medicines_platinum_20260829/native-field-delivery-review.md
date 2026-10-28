# Review Report: Native-field consumer delivery

## Summary

The implementation exposes bounded native-field observations through the
existing admission-aware service and additive API, CLI and Atlas paths. Review
was performed by the implementing agent; no independent reviewer is claimed.

## Verification Checks

- [x] **Plan Compliance**: Partial. The shared delivery capability and paging
  are implemented; real derived-output admission and consumer canaries remain
  open, as do semantic overlays, recovery and release acceptance.
- [x] **Style Compliance**: Ruff and formatting pass; typed production modules
  pass ty and BasedPyright.
- [x] **New Tests**: Both query engines, native nulls and empty collections,
  invalid type/selector/offset controls, later pages, query-receipt identity,
  API/Atlas/CLI synthetic integration and keyboard recovery are covered.
- [x] **Test Coverage**: Partial. Focused and broader selections passed; protected
  CI and its patch-coverage result remain necessary for the final PR head.
- [ ] **Test Results**: One local release-fixture performance case still fails
  after one bounded follow-up. The earlier local full invocation stopped at
  coverage; it did not complete later full-profile stages. Its production
  source pins predate the selector and pagination fixes. No current-tree local
  full pass is asserted.

## Limits and disposition

Two independent hosted PBS producer jobs succeeded with identical current
packages and the same native-core digest as the earlier candidate. Their exact
Parquet digest differs from that earlier candidate, so its exact rights record
has not been assigned to the new bytes. A bounded local historical-writer probe
failed to build without the Arrow SDK; it establishes no platform-wide failure.
The resulting current output is not published or admitted.

The implementation uses verified immutable inputs and bounded result limits.
The existing query runtime check is post-execution, not preemptive. Offset pages
rely on the selected engine's scan order and the caller retaining the exact
object identity; real-source paging and performance remain unqualified.
