# External blocker resolution plan

Status: executable, decision-gated, and fail-closed.

## Credential boundary

Use the already-authenticated `osf-cli` bearer-token session supplied by the
surrounding project environment. Discover only credential presence and
identity (`osf whoami --json`); never copy, print, commit, or persist token
values. If the surrounding environment stops supplying a valid token, pause
at the OSF gate and request re-authentication.

## Sequence

1. **OSF draft completion (reversible)**
   - Retrieve the OSF Preregistration schema v4 and its response keys.
   - Map only claims already present in the committed protocol, analysis plan,
     data-management statement, and citations.
   - Populate the private draft through the authenticated OSF API/CLI boundary.
   - Validate required text and select fields, then capture a draft receipt.
   - Do not submit, register, embargo, or publicize.

2. **Maintainer preview gate (human decision)**
   - Present the rendered draft, ethics applicability wording, data-foreknowledge
     selection, study-type selection, and blinding selection.
   - Recommended decision: approve the conservative descriptive/no-participant-
     data wording for private preview only.
   - If rejected, record revisions and repeat step 1; never infer approval.

3. **Hosted maintenance gates (read-only or App-authorized)**
   - Verify Renovate App installation and Dependency Dashboard issue using the
     repository API; retain the local Renovate configuration as canonical.
   - Reconcile stable-v1 issue #40/#43 and close only evidence-backed child
     tasks. Do not treat green CI as release signing or attestation.

4. **Evidence gates**
   - Acquire source-specific rights decisions, lawful current payloads, source
     receipts, coverage denominators, and adapter parity for issues #50/#51/#54.
   - Acquire deployment URL, readiness, live provenance, accessibility, and
     responsive interaction receipts for #61.
   - Acquire signed/attested release evidence and production DR authority for
     #40/#43. Local synthetic rehearsals remain clearly labelled.

5. **Publication gate (explicit approval required)**
   - Before any OSF submission or source-derived Hugging Face/Zenodo release,
     verify final preview, rights, licence, identifiers, checksums, and
     maintainer authority.
   - Submit only after a separate explicit approval; record immutable receipts
     and cross-link them to Conductor and GitHub.

## Blocker policy

Missing tokens, unresolved ethics wording, missing rights, absent live
receipts, unsigned artifacts, unavailable deployment evidence, or incomplete
OSF required fields keep the relevant gate blocked. Safe local validation and
documentation continue in parallel; no gate is cleared by inference.
