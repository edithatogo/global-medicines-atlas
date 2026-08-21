# Public source rights and archives

## Overview

Review every source in the governed 172-source catalogue, record current
official rights evidence independently from sensitivity, and publish acquired
source data to public Hugging Face datasets only where redistribution is
affirmatively permitted and the maintainer has approved the exact publication
manifest. Preparation, validation, and review do not themselves authorize
publication.

## Authoritative inputs

- `src/global_medicines_atlas/data/medicine_source_catalog.json`
- `quality/qualifications/source-rights-disposition.json`
- `quality/qualifications/us-source-rights-review-packet.json`
- `conductor/decisions/0008-source-derived-dataset-licensing-batch.md`
- FDA website policies: https://www.fda.gov/about-fda/about-website/website-policies
- openFDA terms: https://open.fda.gov/terms/
- Each source authority's current official licence, copyright, terms, or
  written-permission page, observed and content-digested during this track.

## Requirements

1. Every catalogued `source_id` has exactly one machine-readable rights review
   with official evidence, observation time, redistribution disposition,
   attribution, exclusions, sensitivity, and review trigger.
2. Rights evidence is grouped by source authority or terms family where a
   single policy genuinely covers multiple enumerated source IDs; no silent
   jurisdiction-wide inference is permitted.
3. FDA-authored data is reviewed against current official terms and prepared
   for an exact-manifest public-release decision. Third-party, trademarked,
   separately licensed, or expressly excluded content is removed or
   quarantined rather than relicensed.
4. International sources with affirmative reusable terms become
   `approved_public_source`; ambiguous, silent, restrictive, credentialed, or
   sensitive sources retain explicit non-public dispositions.
5. Public eligibility and archive completion remain distinct. A dataset is
   archived only when source bytes were lawfully acquired, an admission
   decision permits projection, the public package passes rights/sensitivity
   checks, and the remote revision is digest-verified.
6. Public Hugging Face archives carry source-specific licence/attribution,
   provenance, content digests, temporal scope, coverage limitations,
   correction/withdrawal instructions, and no inferred regulatory, safety,
   efficacy, funding, or completeness claims.
7. Rights snapshots and generated matrices are deterministic and tested;
   credentials, restricted bytes, personal data, and local paths are excluded.

## Acceptance criteria

- AC-01: A deterministic validator proves 172/172 source rights dispositions
  and fails on missing, duplicate, stale, unsupported, or contradictory rows.
- AC-02: Every permissive decision cites an official policy and its captured
  digest; every unresolved source records the exact missing evidence.
- AC-03: All FDA source IDs have a source-specific rights disposition and any
  proposed public package has enforceable third-party exclusions, independent
  sensitivity controls, and an exact manifest awaiting or recording explicit
  maintainer approval.
- AC-04: Every affirmatively reusable international source is public-eligible;
  every other international source remains fail-closed with a reason.
- AC-05: Every acquired, admitted, public-eligible package is published to a
  public Hugging Face dataset and restored with matching SHA-256 digests.
- AC-06: Eligible sources lacking acquired bytes are reported as acquisition
  pending and are not misrepresented as archived datasets.
- AC-07: Focused tests, routine/strict validation, full test-goblin where the
  platform supports it, hosted CI, PR review, merge, track archive, and clean
  synchronized `main` all pass.

## Non-functional constraints

- GitHub and Hugging Face free tiers only.
- Immutable source payload and append-only receipts remain authoritative;
  Hugging Face is a public archive/output boundary, not source truth.
- Missing coverage is not negative evidence.
- Rights and sensitivity are independent and fail closed.
- Publication packages must be bounded to avoid free-tier resource abuse.

## External gates

The maintainer's instruction on 2026-08-21 authorizes proceeding with the
recommended staged, source-by-source rights workflow. It does not approve an
unspecified dataset or source-byte manifest for public release. Credentials,
restricted-source access, paid services, and permissions absent from official
evidence remain ungranted.

## Out of scope

- Inventing licence permission from public accessibility or government status.
- Publishing credentialed, personal, restricted, or third-party licensed bytes.
- Silver semantic normalization or clinical/policy conclusions.
- Claiming complete historical coverage where no denominator exists.
