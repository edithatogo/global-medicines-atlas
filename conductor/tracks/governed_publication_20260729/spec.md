# Specification: Governed Publication

## Outcome

Deliver v0.7 reproducible, consumer-verifiable release packages and a
dry-run-by-default Hugging Face publication path.

## Requirements

- M-004, M-005, M-052, M-060 to M-062, M-074, M-080, M-083 and S-004.
- Generate Parquet, Croissant, data cards, citations and coverage manifests.
- Generate SBOM, checksums and provenance attestations from reviewed inputs.
- Fail closed on unresolved rights, privacy, provenance or coverage gates.
- Qualify immutable release artifacts before creating a public GitHub release
  or external dataset revision.

## Acceptance

- Identical inputs produce semantically identical manifests and tables.
- Publication requires explicit environment and maintainer approval.
- Post-publication verification distinguishes prepared, uploaded and public.
- Version, changelog, citation, licence, SBOM and attestation metadata agree.

## Out of scope

- Automatic publication of restricted or unreviewed source payloads.
