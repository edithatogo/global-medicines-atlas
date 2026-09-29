# Source metadata append contract

`federation_metadata_append.prepare_metadata_append` prepares one canonical
source-specific JSON document at a content-addressed `metadata/source/` path.
It reuses the governed source metadata profiles, binds their raw and B1 receipt
digests to a complete caller-supplied baseline, and preserves existing cards,
manifests, source bytes and receipts. The embedded revision identifies the
source release; the separately supplied parent revision identifies the exact
current archive head used for compare-and-swap. They may differ when approved
derived objects have since been appended to the archive.

This is offline preparation and validation. It has no upload implementation,
does not accept credentials, and does not establish independent authority for
caller-supplied inventories. `verify_metadata_append` revalidates the prepared
transaction and requires the complete unchanged baseline plus its one exact
addition, a new immutable revision, the expected parent, public/non-gated
state, and matching anonymously retrieved metadata bytes.

## Hosted integration and execution record

`.github/workflows/australian-source-metadata.yml` now runs
`scripts/publish_source_metadata.py` for one reviewed `mbs` or `pbs` profile
and a required exact `expected_parent_revision` input.
The transport uses exactly one Hub add operation and `parent_commit` CAS;
it has no remove operation or dataset creation/visibility mutation. A current
head differing from the expected parent is rejected before writing. The durable
receipt labels parent evidence as server-enforced CAS and records the source
release revision separately.

Anonymous downloads use the existing DNS-bound transport and approved Hub
delivery hosts. Each isolated download subprocess has an absolute 60-second
deadline and is killed on expiry, with byte bounds checked before writes.
Inventories are capped at 10,000 entries, 512 MiB per object and 2 GiB per
snapshot (up to 4 GiB across before/after plus metadata); the workflow has a
30-minute timeout. An issue receipt projection exceeding 60,000 characters is
rejected before any append. Exact issue receipt readback must succeed before
temporary source cache cleanup. Tests mock the SDK and transport. PBS hosted
execution is recorded below; the MBS run remains pending.

The hosted implementation runs only from the approved GitHub Actions
environment, bind the reviewed default-branch commit and durable issue intent,
and independently obtain a complete baseline inventory at the exact expected
CAS parent. The metadata document separately retains the source release
revision. Hash every baseline object and retain byte counts; API sibling names
alone do not establish byte preservation. Submit only an add operation with
the Hub `parent_commit` precondition equal to the expected parent revision.
Never use the existing PBS replace-all publisher
(`.github/workflows/australian-pbs-hf-publication.yml`,
`upload_folder(..., delete_patterns=['*'])`) for this transaction.

After the append, persist the server-enforced CAS acknowledgement and observe
public non-gated identity, anonymously restore/hash all siblings, then run the
verifier. Persist a durable issue receipt containing code commit, workflow/run,
dataset, parent and new revisions, metadata path/bytes/SHA-256, complete before
and after inventories and anonymous verification outcome. Cleanup must follow
verified durable receipt persistence. A failed append leaves the prior source
revision intact and must not trigger deletion or a dataset-wide privacy change.

PBS execution is verified from reviewed main commit
`aa3d74a1c315b51d48688e5409283cf32cacd9cc` in workflow run `36520821504`.
Issue #340 comments `5883535694`, `5883535989`, and `5883538920` contain the
durable intent, server-enforced CAS acknowledgement, and anonymous verification
receipt. The new revision is
`48fd7345fb09277bb5b85644dba72804633a2abb`; the eight original sibling
digests are preserved and the metadata object digest is
`cb7f9647d77372faa091664a1337e70574a5dee4afe6a55a535fb204ed16f2b8`.

MBS execution is verified from reviewed main commit
`85ad454850dd43814530f4340fa6247776cb4cfc` in workflow run `36532129354`.
Issue #340 comments `5885053897`, `5885054280`, and `5885067299` contain the
durable intent, server-enforced CAS acknowledgement, and anonymous verification
receipt. The new revision is
`243f9ff5498816af6e4d9ae4db60528728f01834`; the 49 baseline object digests
are preserved and the 2,900-byte metadata object at
`metadata/source/au-mbs/1067278e06e40edc15994dedc9789f5130aea4727c9dcf3be276f475743e896e.json`
has SHA-256
`1067278e06e40edc15994dedc9789f5130aea4727c9dcf3be276f475743e896e`.
The public Hub API reports the archive as public and non-gated, and an
independent anonymous GET at the exact revision reproduced the recorded byte
count and digest. The embedded source release remains
`75f9f20a36ddb829dfe0ca88660664570782be02`; the transaction CAS parent was
`ba82cd1d0f9b0f28514df431b8da3a6c207d76fa`.

The MBS source release remains pinned to
`75f9f20a36ddb829dfe0ca88660664570782be02`. Its archive advanced to
`ba82cd1d0f9b0f28514df431b8da3a6c207d76fa` when candidate-only Silver v4
objects were appended and anonymously verified (issue #340 comment
`5859624790`). The MBS metadata append must therefore keep the source release
revision in the document while using the newer exact archive head as its CAS
parent. The workflow and append contract carry these identities separately;
the append is complete and verified as recorded above. Any head drift fails
before intent or mutation.

## Interrupted verification recovery

The workflow persists and reads back a bot-authored `cas_acknowledged` receipt
immediately after the Hub commit response and before anonymous verification.
If verification is interrupted, pass that issue-comment ID as
`recovery_receipt`. Both the acknowledgement and its linked prior intent must
be bot-authored comments on issue 340 with matching exact plan fields. Recovery
must pass `expected_parent_revision` equal to the original `parent_revision`
in the CAS acknowledgement; do not pass the current acknowledged dataset head
as the parent. The runner rejects a mismatch before reading Hub objects.
Recovery requires the acknowledged revision still be the dataset head,
rehashes the original baseline and the complete resulting sibling set, and
emits verified receipt evidence without another append.

Parent evidence remains the authenticated workflow's recorded successful
server-enforced CAS response; no independent Git ancestry claim is made.
An ambiguous commit response, or interruption before acknowledgement becomes
durable, remains a manual reconciliation boundary. Date-sorted commit lists
are not accepted as parent evidence. Recovery preserves the exact reviewed
code commit requirement and cannot silently adopt an unrelated newer head.
