# Hugging Face estate observation

`quality/qualifications/hf-estate-20260830.json` is an authenticated-visible
metadata inventory, not a payload archive, rights decision or publication
receipt. Its 93 entries cover 4 models, 73 datasets, 6 Spaces and 10 collections
returned by two consistent owner-filtered scans. Both scans exhausted below
their explicit caps. Six entries are private and retain only pseudonymous
identities, visibility, revision/fixity metadata and conservative dispositions.

## Reproduce safely

With the existing Hugging Face CLI authenticated as the intended owner:

```sh
uv run python scripts/observe_hf_estate.py --owner edithatogo \
  --output quality/qualifications/hf-estate-20260830.json
```

The observed CLI version is 1.15.0. This is metadata-only local tooling; it
does not download repository files or publish anything. The wrapper permits
only the exact owner identity and bounded listing commands, rejects other Hub
endpoints, and rejects upload, mutation, credential-listing and arbitrary flag
requests. Authentication is managed by the CLI; no token is accepted as an
argument, inspected, copied, printed or persisted by this tool.

Each command has a 120-second timeout and an 8 MiB output ceiling. Temporary
metadata capture is automatically closed and removed, including on failure;
it is not a source-payload cache. Raw CLI errors are not echoed. Dataset and
model listings request only identifiers, revision, privacy and gating. Space
listings request identifiers, revision and privacy. Collection descriptions,
titles, notes and member names are not written into the public snapshot.
The selected collection member identities and update clock are digest-bound
so equal-size membership changes cannot silently pass the second scan.

The CLI defaults are unsafe for a completeness claim: 30 repositories and
10 collections. This observer requests 1,001 repositories per kind and 100
collections, rejecting equality with the cap rather than claiming exhaustion.
The collection service rejects expanded requests above 100. A larger estate
requires a reviewed pagination extension; never just raise this endpoint cap.

## What the snapshot proves

The runtime contract and generated JSON Schema require all four kinds,
including empty listings; matching owner identity; explicit privacy and gating;
immutable reported Git heads; stable repeated observations; and per-kind
counts/digests. Deleting an entry breaks its observed denominator. A repository
whose head is explicitly unreported retains null, not a fabricated revision.
Collections have no Git revision and use selected-metadata fixity instead.

Private names are pseudonymized with deterministic hashes. This is not a claim
of anonymity or a substitute for confidentiality review. Credentials, cards,
descriptions and restricted contents are absent. Visibility is never used to
infer rights, permission, acquisition, freshness or recoverability.

`rights_state` and `publication_state` are always `not_assessed` **by this
inventory**. These observation fields do not supersede the authoritative source
rights ledger or the exact MBS/PBS publication receipts. Known Australian and
registry identities receive relevance labels only; other scope remains
unassessed. Private surfaces retain `retain_private`; public surfaces receive
`review_required`, never an automatic publication or promotion instruction.

## Remaining qualification boundaries

Two stable listings prove the authenticated-visible denominator, not that a
fine-grained credential exposes every resource owned by the account. The
snapshot therefore keeps `credential_visibility_attested: false`. Whole-account
completeness remains unproven until visibility scope is independently attested;
no credential expansion is performed here. This limitation remains in AC-01.

The snapshot does not change Hub visibility, populate collections, update the
public estate-registry dataset, emit live v4 publication receipts, perform
anonymous payload recovery, or authorize an independent replica. Those remain
distinct tasks. The existing exact-publication tests and receipts remain the
authority for the legacy composite and MBS/PBS archives.

## Reuse

This extends GMA frozen-model, schema and content-bound inventory conventions
and its existing CLI-produced reuse-discovery snapshot pattern. The inspected
reimbursement-atlas scripts provide dataset publication checks and staging,
not complete model/dataset/Space/collection enumeration. No new dependency or
second publication authority was introduced.
