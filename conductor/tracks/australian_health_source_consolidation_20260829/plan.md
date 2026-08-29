# Plan: Australian health source consolidation

## Phase 1: Freeze the donor denominator (AC-01, AC-06)

- [x] Write failing tests for a complete two-repository inventory and ensure an
  omitted tracked file, function, workflow, or data artifact fails. (`7b830ea`)
- [x] Confirm the intended failure before implementation. (`7b830ea`)
- [x] Generate the machine-readable inventory from the two pinned commits,
  including paths, modes, sizes, digests, languages, functions, data roles,
  implementation state, and disposition. (`7b830ea`)
- [x] Characterize the invalid PBS parser, guessed MBS tag, processor path/type
  bug, zero-byte artifacts, and green-with-no-data scheduled workflow.
  (`7b830ea`)
- [ ] Preserve complete donor Git histories and Apache-2.0 code provenance
  without modifying the dirty local donor checkout.
- [ ] Phase Verification & Checkpoint: inventory denominator and regression
  failures are receipt-bound and independently reproducible.

## Phase 2: Add the independent MBS source domain (AC-02, AC-03, AC-07)

- [x] Write failing parser, admission, temporal, coverage, and semantic-boundary
  tests for `MBS_XML/Data`, all 40 native fields across the variable 34-to-37
  fields per record, and all 5,989 records. (`4871201`)
- [x] Confirm the intended failure before implementation. (`4871201`)
- [x] Add `au-mbs` source catalogue entries, source profiles, receipts, adapter
  registration, source-health checks, and versioned acquisition surfaces.
  (`4871201`)
- [x] Implement bounded source-faithful MBS XML parsing without Silver
  harmonisation in Bronze. (`4871201`)
- [x] Add a source-native workbook admission/profile and deterministic
  projection for all four P7 workbook sheets while retaining formula/error and
  schema-era information. (`4871201`)
- [x] Prove that MBS outputs cannot satisfy medicine regulatory, PBS funding,
  formulary, terminology, utilization, or clinical assertion contracts.
  (`4871201`)
- [x] Phase Verification & Checkpoint: exact raw digests, record counts, fields,
  dates, and independent-domain semantics pass. (`4871201`)

## Phase 3: Replace the PBS experiment with governed v3 support (AC-04, AC-07)

- [ ] Write failing tests for ZIP safety, PBS namespaces, item/product identity,
  restrictions, AMT references, ATC codes, effective dates, malformed XML,
  duplicate members, traversal names, decompression limits, and drift.
- [ ] Confirm the intended failure before implementation.
- [ ] Extend the existing `au_pbs` adapter and catalogue/source profile rather
  than creating a second PBS authority.
- [ ] Implement receipt-bound download, immutable ZIP preservation, member
  manifests, source-native Parquet, and the bounded tag-inspection command.
- [ ] Preserve the donor CLI input/output expectations through compatibility
  tests where they are useful; do not preserve its syntax error.
- [ ] Phase Verification & Checkpoint: donor intended behavior is covered by a
  valid, safe, typed implementation.

## Review Fixes: MBS source-domain phase

- [x] Bind source-batch identities as literals and bind the catalogue download
  surface to the exact versioned July 2025 XML rather than a generic page.
  (`dc6001a`)
- [x] Exercise exact-qualification, hostile-shape, archive-relationship, Git
  failure, and malformed-inventory branches above the 91% coverage floor.
  (`da37c55`)
- [x] Assign every new donor test module to the governed routine unit lane and
  rerun the routine harness with the compatible local Python fallback.
  (`85b6a51`)

## Phase 4: Replace the monthly scraper safely (AC-05, AC-06)

- [ ] Write failing tests for month ranges, historical URL generation,
  item/participant naming, timeouts, retries, rate limits, 404s, empty output,
  mixed HTML tables, XML P7 filtering, and deterministic projections.
- [ ] Confirm the intended failure before implementation.
- [ ] Reuse GMA HTTP destination, admission, receipt, source-health, and
  catalogue-driven scheduling controls.
- [ ] Keep old endpoint behavior as a compatibility probe and source-drift
  fixture; use current official MBS releases for production acquisition.
- [ ] Replace heterogeneous `pandas.concat` output with source/table identities
  and explicit schema contracts.
- [ ] Require artifact and receipt evidence before a scheduled run reports data
  acquisition success.
- [ ] Phase Verification & Checkpoint: the August 2026 no-data run fails closed
  and a valid fixture run emits deterministic, typed products.

## Phase 5: Preserve design intent and prepare archival (AC-01, AC-08, AC-09)

- [ ] Map Neo4j, SNOMED CT-AU, AMT, ATC hierarchy, NLP/NER, temporal graph,
  Spark, and Airflow commitments to existing GMA capabilities or successor
  tasks; label each as implemented, preview, rejected, or separately gated.
- [ ] Verify public raw/data receipts from the Hugging Face data-plane track.
- [ ] Publish compatibility and successor notices in both donor repositories,
  link exact GMA/Hugging Face destinations, and run downstream canaries.
- [ ] Prepare non-destructive GitHub archive commands and a rollback checklist;
  stop at the compatibility-archive gate for the exact two repositories.
- [ ] Phase Verification & Checkpoint: no donor scope is unaccounted for and no
  archive action has occurred without the final human gate.

## Phase 6: Integrated qualification (AC-10)

- [ ] Run focused tests, Ruff, `ty`, BasedPyright, provenance, rights,
  deterministic regeneration, security, coverage, and compatibility lanes.
- [ ] Run `uv run python scripts/test_goblin.py full` where platform support
  permits; record Linux-authoritative Mojo/mutmut evidence separately.
- [ ] Run Conductor review, fix findings, open a scoped pull request, wait for
  required hosted checks, merge, and reconcile evidence.
- [ ] Keep archive tasks pending until the exact parity/publication package and
  maintainer approval are recorded.
