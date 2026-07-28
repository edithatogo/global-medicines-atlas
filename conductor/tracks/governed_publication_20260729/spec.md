# Specification: Governed Publication

## Outcome

Deliver v0.7 reproducible, consumer-verifiable release packages and a
dry-run-by-default Hugging Face publication path.

## Requirements

- M-004, M-005, M-052, M-060 to M-062, M-074 and S-004.
- Generate Parquet, Croissant, data cards, citations and coverage manifests.
- Generate SBOM, checksums and provenance attestations from reviewed inputs.
- Fail closed on unresolved rights, privacy, provenance or coverage gates.

## Acceptance

- Identical inputs produce semantically identical manifests and tables.
- Publication requires explicit environment and maintainer approval.
- Post-publication verification distinguishes prepared, uploaded and public.

## Out of scope

- Automatic publication of restricted or unreviewed source payloads.
