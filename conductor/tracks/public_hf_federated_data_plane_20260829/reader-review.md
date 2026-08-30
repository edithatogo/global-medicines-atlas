# Runtime reader self-review

Scope: `c9102e3..2787188`, Phase 4 transport/cache slice, not whole-track
completion or a second-maintainer approval.

- Correctness: schema-pinned validation and existing v4 semantics precede all
  requests. Exact caller-admitted contract bytes are mandatory. Online reads
  check anonymous public/non-gated revision and byte size/digest every time;
  offline behavior is explicit. Cache identity includes the complete contract.
- Resource and concurrency safety: private temporary spools, chunked I/O,
  object/cache/entry/open-result bounds, LRU expiry checks, per-hop destination
  validation, HTTP timeouts and deadline checks. Result contexts are independent
  of cache lifetime; errors close their scratch files.
- Authority: the caller must authenticate source/rights/receipt/lineage evidence
  before admitting a document. The reader is not a self-authorization engine.
  Live raw reads fail outside Actions; only synthetic payloads were exercised.
- Security: reuse validated-IP transport, fixed public HTTPS host allowlist,
  no env credentials/proxies or cookie replay, no arbitrary URL/schema fetch,
  no upload or source/visibility mutation. Dependency versions unchanged;
  existing jsonschema is available only through the optional federation extra.
- Review correction: a new live-raw workstation guard failed as intended before
  implementation, then passed. Initial collection failed on the missing reader
  module. These are recorded red checkpoints, not retrospective assumptions.
- Applicable Python guide: Ruff/ty/strict BasedPyright passed; non-Python/UI
  platform guidance is not applicable. 89 focused tests passed with 100% reader
  branch coverage. Isolated locked consumer installed the federation extra and
  imported the runtime without test groups.
- Result-stream correction (`2787188`): the writable temporary-file API allowed
  caller mutation after verification. A regression failed before a read-only
  buffered view was introduced. 90 focused tests pass, reader 100% branch
  coverage and strict typing pass. The earlier functional commit `78abde9`
  was rebased as `2ed6d8d`; prior ledger observations retain their original IDs.
- Installed-consumer correction (`637ab07`): bare jsonschema silently skipped
  date-time validation without its optional format plugins. The federation
  extra now includes already-locked `format-nongpl`, and startup fails if a
  required format checker is missing. Isolated locked consumer rejects invalid
  timestamps; 91 focused tests pass with reader 100% branch coverage.
- Local full Test-Goblin terminated on 3.14.5 after 2,986 passed, five failed,
  one skipped and 96.56% coverage. Two optional-extra lock-digest receipt
  mismatches were repaired (39 focused receipt/matrix tests pass); two release
  tests require 3.14.6 and product PERF-QUERY measured 471.581ms against250ms.
  No threshold was weakened. Static/context and wheel/sdist clean-consumer
  probes passed. The run crossed review corrections and is not an exact-final-
  head whole-harness claim; no duplicate full run was started.
- Expiry cleanup correction (`9f2b929`): automated P2 review found expired
  spools stayed open after offline rejection. The red test observed the open
  file; all expired entries now close on open/occupancy inspection. 91 tests,
  reader100% branch coverage, Ruff and strict typing pass. Idle-reader close
  remains explicit; no background timer or hard-real-time cleanup is claimed.
- CI environment correction (`66561b2`): unit CI installs test-goblin without
  optional runtime extras. Required format plugins are now explicit in that
  test group too. The locked isolated test-goblin environment passes all130
  reader/contract/receipt/matrix tests; no package versions changed.
- Remaining: hosted exact-head qualification; production
  v4 receipt/admission integration, product consumers and public derived output.
  No existing MBS/PBS receipt was relabelled v4 and no source was reacquired.
