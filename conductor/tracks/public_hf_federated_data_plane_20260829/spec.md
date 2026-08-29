# Specification: public Hugging Face federated data plane

## Objective

Move every publication-approved Australian MBS/PBS raw payload and derived
dataset to an appropriate public Hugging Face dataset and collection, at an
immutable revision with anonymous digest verification. Eliminate durable
workstation-only data while preserving bounded local processing caches and an
independently recoverable copy.

## Authority and safety boundary

The maintainer explicitly directed that the scoped raw MBS/PBS payloads be
public and asserted redistribution permission. Hosted workflows must bind that
authorization to each exact source/file/destination manifest. The assertion is
not generalized to SNOMED CT-AU, AMT, UMLS, RxNorm vocabulary bytes, unrelated
rare-disease sources, private application code, or future unenumerated data.

Publishing means making bytes externally public. Upload and visibility changes
therefore occur in GitHub Actions using the protected `HF_TOKEN`; local tooling
may inventory, hash, package, and validate but must fail closed on upload.

## Dataset topology

Create or adopt these non-overlapping public authorities:

1. **Australian MBS source archive** — exact source-native XML, XLSX, HTML or
   other official payloads, legacy donor payloads, archive-member/document
   manifests, B1 receipts, source cards, and version history.
2. **Australian PBS source archive** — exact source-native ZIP/XML/API exports,
   archive members, B1 receipts, source cards, and version history.
3. **Australian benefits medallion dataset** — rebuildable Bronze projections,
   typed Silver MBS/PBS tables, Gold evidence-graph tables, Platinum products,
   field lineage, promotions, coverage, and federation contracts. Raw objects
   remain referenced from the source archives rather than silently duplicated.
4. **Legacy composite compatibility dataset** — the existing
   `edithatogo/global-medicines-atlas-international-open` revision
   `654f71c84cdb17b4032396bcbc961bef8757fb19`, made public only as an explicitly
   legacy composite after exact-manifest and anonymous restore verification.

Final repository names are recorded before creation and remain stable. A source
archive and derived dataset may share collections, but not authority or paths.

## Federation/distribution v4

Publish a byte-versioned v4 JSON Schema and positive/negative fixtures that
bind:

- producing repository and contract authority;
- source, acquisition, medallion layer, and Bronze stratum;
- Hub dataset, immutable revision, path, visibility, gated state, byte count,
  SHA-256, and Xet/LFS identity where observable;
- hosted workflow/run/commit and anonymous clean-room verification;
- rights/authorization receipt and independent sensitivity/publication state;
- collection membership and public dataset-estate registry entry;
- schema era, legacy/current comparison cohort, effective/retrieval time;
- primary/replica role, RPO/RTO, checksum inventory, and restore evidence;
- transient cache origin, expiry, cleanup receipt, and offline behavior; and
- downstream repositories and compatibility canaries.

The schema is additive to medallion v1-v3. It cannot weaken layer promotion,
field-lineage, backfill/replay, or B0/B1/B2 semantics.

## Collection alignment

- Make the existing `Policy AUS` collection public when the first exact
  Australian dataset is added; do not publish it merely as an empty shell.
- Add Australian raw and derived datasets to `Policy AUS` with layer/source
  notes and to `Health Economics and Outcomes Research` where their analysis
  role fits.
- Replace the stale reimbursement-atlas collection note with its observed
  public medallion/HEOR role and current revision.
- Register all datasets and collection memberships in the public
  `dataset-estate-registry`.
- Collection membership never authorizes data or proves payload completeness.

## Local-data policy

Repository fixtures remain small, synthetic, rights-safe test inputs. Real raw
and derived datasets are not committed to Git. A developer or runner may use a
bounded temporary materialization, content-addressed cache, or streaming read.
Cleanup is allowed only after the hosted workflow records the public revision
and a token-free clean-room restore reproduces all exact digests. Cache cleanup
must never delete the only copy.

## Private estate disposition

The audit identified three private datasets. The exact legacy composite is a
public candidate because its 42-file manifest is byte-for-byte identical to an
already-public composite. The licensed ontology archive and the rare-burden
source archive remain private because their scopes contain licensed or
unresolved material outside this decision. The unrelated private Space and two
empty reserved collections are not made public merely to maximize a count.

## Acceptance criteria

- **AC-01:** A versioned estate inventory covers every maintainer-owned model,
  dataset, Space, and collection and records current visibility, revision,
  scope, rights/publication state, GMA relevance, and disposition.
- **AC-02:** The legacy composite at revision `654f71c...` is publicized only by
  a hosted exact-revision workflow after its `manifest.json` SHA-256
  `d058b78789cd8c2d0a19467063890d32c0757add10998d307422c3ec1550df86`
  and 42 payload entries match the already-public manifest; a token-free restore
  verifies every payload digest and a durable receipt records the unchanged
  revision and public/non-gated state.
- **AC-03:** Every non-empty donor data artifact and every subsequently approved
  MBS/PBS raw payload exists in the appropriate public source archive with B1
  receipt, exact B2 bytes, data card, licence/permission reference, checksum,
  version/effective dates, and anonymous verification.
- **AC-04:** Every generated Australian Bronze projection, Silver table, Gold
  graph table, and Platinum product has a public dataset destination and v4
  identity; no durable derived dataset exists only locally.
- **AC-05:** `Policy AUS`, `Health Economics and Outcomes Research`, and the
  public estate registry expose accurate, non-stale membership and notes.
- **AC-06:** Local publication attempts fail. Cleanup tests prove that temporary
  bytes survive failed/partial/private/unverified uploads and are removed only
  after hosted public anonymous verification.
- **AC-07:** Checksum inventory and clean-room restore exercise both the public
  Hub copy and a geographically/administratively independent approved replica;
  a duplicate in the same HF account is labelled compatibility, not independent
  durability.
- **AC-08:** Licensed/unresolved private datasets remain private with a concise
  fail-closed reason; no credential or restricted byte is inspected, logged,
  copied, or exposed.
- **AC-09:** Schema/semantic tests for v4, focused publication tests, security,
  provenance, rights, full harness where supported, hosted checks, and
  requirement-to-evidence traceability pass.

## Dependencies and gates

- Donor raw denominator comes from
  `australian_health_source_consolidation_20260829`.
- Derived layers depend on their producing Silver/Gold/Platinum tracks.
- Exact MBS/PBS source/file/destination authorization is satisfied by the
  maintainer assertion only when recorded in a non-secret manifest receipt.
- Any independent non-HF recovery publication remains a distinct external
  publication gate.
