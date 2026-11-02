# Historical NZULM 2023 recovery and publication

The maintainer explicitly authorized recovery of the historical corpus,
publication of everything permitted through GitHub Actions, and anonymous
SHA-256 verification on 2 November 2026. This follows the completed rights
review [#51](https://github.com/edithatogo/global-medicines-atlas/issues/51)
and archived [migration #6](https://github.com/edithatogo/global-medicines-atlas/issues/6).
It does not resume Australian federation or authorize a Stable release.

## Recovered source and integrity

A metadata-only local search covered 674,219 directories and found no original
corpus. The retained cloud archive's inclusion manifest then located its
historical names. Recovery of 133 matching files from that container found
only zero-filled content, including invalid ZIP and Office files. Those files
are rejected as source payloads. Matching names and sizes did not prove recovery.
The incomplete container stream was stopped after the selected extraction;
its historical full-container checksum is not claimed as freshly verified.

An independent private Google Drive copy provided a valid 36,527,993-byte ZIP:

`757fb82b383f8d4d67ad7a1f7e26c25c2eaf05081a80290f4849f586fe58ffd9`

All 108 member names and lengths match the historical inventory after
case-folding the original Windows filenames. The ZIP's `version.txt` identifies
build `2023-11-27T11:56:38+13:00`, Pharmac edition December 2023, published
1 December 2023. The original download agreement, ownership statement and
disclaimer were checked. The valid recovered source remains private.
No cloud identifiers, signed URLs, access configuration or private evidence
are included in this repository or the public package.

## Exact publication scope

The [approved manifest](../../quality/source-batches/nzulm-2023-recovered/manifest.json)
binds 102 unchanged members, **205,732,694 source bytes**, to individual hashes.
Reading each selected member to EOF verifies its original ZIP CRC as well as
its length and SHA-256. The six exact SNOMED mapping/guide members are excluded
and never opened by the packaging function. The original mixed ZIP is excluded.
No NZF content, full SNOMED/AMT release or proprietary RxNorm vocabulary is added.

[Package terms](../../quality/source-batches/nzulm-2023-recovered/rights.json)
retain the original NZULM notices, attribution to all originators, the supplied
Pharmac CC BY 3.0 NZ terms, Medsafe's commercial-use restriction and the WHO
Collaborating Centre's noncommercial/no-modification conditions for ATC material.
The [official WHO notice](https://atcddd.fhi.no/copyright_disclaimer/) was checked
in addition to the previous source-specific review. The individual file bytes
are not transformed or relicensed. Mixed supplier terms are labelled explicitly.
The source agreement's historical clinical wording does not become an Atlas
claim of current clinical fitness.

Target: `edithatogo/nzulm-2023-source-archive`, public and ungated. The 102 source
members plus `README.md`, `rights.json` and `manifest.json` are the only public
objects. Duplicate publication is prevented by creating a new dataset with
`exist_ok=False`; an existing target is an investigation condition, not a retry.

## Execution and recovery boundary

`scripts/publish_nzulm_2023.py` supports offline preparation. Publication requires
an exact main commit and an actual GitHub Actions workflow dispatch, the existing
production environment and HF token, the approved source digest, and the exact
member inventory. Local upload attempts stop before preparation or credential
use. The existing shared publication transport records intent and verifies every
uploaded object anonymously at the resulting immutable revision.

The recovered source is private, so the hosted runner needs a short-lived read
URL in temporary protected secret `NZULM_2023_RECOVERY_URL`. No account token,
refresh token or rclone configuration is transferred. The source URL is never a
workflow input, committed value or receipt field. The workflow downloads it
without printing it and uploads only public-safe publication receipts. A fresh
URL is obtained only when the merged workflow can run; it expires shortly and
the temporary secret is removed after the run's terminal result. The separate
AGENTS.md credential-publication gate applies to this handoff; the maintainer's
source-data publication approval remains effective.

Preparation and focused verification are complete. Hosted publication and
anonymous readback are recorded separately when observed; this document does
not treat a valid source, approved manifest, PR or workflow as proof of upload.
Failed download or preflight has no upload receipt. After any uncertain write,
inspect the dataset and retained run receipts before another attempt. Keep the
recovered source until hosted anonymous digest verification is recorded.

## Ownership

Chat `01a19600-56dd-73a2-9ff5-4a2484a54493` owns this lane in
`/Volumes/PortableSSD/GitHub/global-medicines-atlas`, branch
`codex/nz-2023-recovery-publication`, based on `14e57ab32ddfc0845dedb03ec0c57e23b2b43539`.
Scope: the exact recovery manifest, publication package metadata, bounded
publisher/workflow and tests, this report, and the archived migration follow-up
ledger. Private recovery stays outside the checkout. Prior ownership remains
history. No source payload is committed, no shared login is replaced and no
other writer's checkout or native operation is changed.
