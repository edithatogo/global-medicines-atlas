# Maintainer-Owned Ecosystem Reuse

The machine-readable authority map is [`.context/ecosystem.toml`](../.context/ecosystem.toml).
Before adding a dependency, dataset, adapter, publication workflow, or domain
contract, check that registry and the maintainer's GitHub and Hugging Face
resources.

The rule is:

1. reuse or extend the declared maintainer-owned authority when its contract fits;
2. extract a shared package only after two repositories need a stable contract;
3. preserve repository, immutable snapshot, licence, and transformation provenance;
4. contribute improvements to the authoritative repository rather than maintaining
   divergent copies;
5. keep licensing, credentials, publication, and consequential claims as human gates.

`global-medicines-atlas` owns medicine identity and separate regulatory/funding
assertions. It consumes reimbursement evidence contracts, interoperates with
decision-analysis repositories, and adopts publication and evidence patterns. It
does not become a duplicate reimbursement lake, VOI engine, simulation runtime,
or licensed FHIR client.

Hugging Face publication is an output boundary, not an unreviewed source of
truth. Existing datasets are reused for publication mechanics unless their
records have independently passed the medicines source, licence, provenance,
and coverage gates.

## Pre-acquisition reuse gate

Before any acquire or download (including Drugs@FDA), search:

1. local clones and declared `local_boundary` paths;
2. maintainer GitHub repositories in this registry;
3. Hugging Face datasets, including
   `edithatogo/global-medicines-atlas-catalogue`;
4. the medicine source catalog (`medicine_source_catalog.json`).

Then choose exactly one of **reuse | link | mirror | extend | fork |
acquire-new**. acquire-new is last resort. Acquisition without this gate
fails. Each search is pinned in a versioned discovery snapshot (schema
`global-medicines-atlas.reuse-discovery`; see
[`schemas/reuse-discovery-snapshot-v1.json`](../schemas/reuse-discovery-snapshot-v1.json)).
The snapshot records query, revision, candidate digest, tool version,
generation time, expiry, and per-surface success/unavailable/incomplete state.
Success with no candidates means no candidate was found; unavailable or
incomplete means the search cannot support that conclusion. A stale snapshot
or skipped surface fails closed for `acquire-new`.

Refresh with `scripts/refresh_reuse_discovery.py`, consuming JSON indexes from
the existing authenticated `gh` or Hugging Face CLI context without writing
credentials. The pinned JSON supports offline reconstruction and is not a copy
of source payload bytes. The choice and snapshot ID are recorded on the
acquisition receipt, B1 manifest, and OpenLineage projection.
