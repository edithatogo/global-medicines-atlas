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
