# Runtime reader self-review

Scope: `d121004..78abde9`, Phase 4 transport/cache slice, not whole-track
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
- Remaining: full Test-Goblin and hosted exact-head qualification; production
  v4 receipt/admission integration, product consumers and public derived output.
  No existing MBS/PBS receipt was relabelled v4 and no source was reacquired.
