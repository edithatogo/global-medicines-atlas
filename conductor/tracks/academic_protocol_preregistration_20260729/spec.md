# Specification: Academic Protocol and Preregistration

## Outcome

Produce an academically defensible, OSF-ready protocol and covering
preregistration for global comparison of medicine regulatory approval and
public funding, linked reproducibly to the software, lawful datasets and
versioned research outputs.

## Functional requirements

- Define research questions, estimands, jurisdictions, source-selection rules,
  inclusion and exclusion criteria, and the unit and validity of comparison.
- Preserve regulatory approval and funding as separate outcomes.
- Define source-native and canonical entity granularities, indications,
  populations, temporal scope, comparison-validity states and material
  mismatches.
- Pre-specify matching, adjudication, missingness, conflict, sensitivity,
  validation and uncertainty methods.
- Maintain a prospective amendment history and deviation register.
- Bind protocol, software, fixture, schema and lawful data identities to
  immutable versions and checksums.
- Prepare OSF registration text, structured attachments and a publication
  linkage matrix for GitHub, Hugging Face, Zenodo and OSF.

## Non-functional requirements

- The protocol must be reproducible from governed fixtures without network
  access and distinguish fixture evidence from live-source qualification.
- Public artifacts must not contain or imply redistribution rights for
  restricted medicine payloads.
- Automated evidence must remain distinguishable from independent human
  adjudication and maintainer approval.
- Amendments after registration must be dated, reasoned and non-destructive.

## Acceptance

- Protocol, analysis plan, preregistration cover, deviation register and
  reproducibility instructions are version controlled and internally linked.
- Every planned outcome and comparison maps to M-090 validity semantics and
  source provenance.
- A clean rehearsal regenerates the submission bundle and verifies hashes,
  schemas, citations and executable examples.
- External OSF, Zenodo, Hugging Face and DOI states are verified by durable
  identifiers or explicitly recorded as pending.
- Submission or publication occurs only after explicit maintainer approval.

## Out of scope

- Clinical recommendations, individual patient inference or causal claims not
  supported by the approved design.
- Claims of exhaustive global coverage.
- Publishing restricted source data.
- Treating preregistration as evidence that the planned analyses were executed.
