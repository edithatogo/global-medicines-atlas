# Source metadata append contract

`federation_metadata_append.prepare_metadata_append` prepares one canonical
source-specific JSON document at a content-addressed `metadata/source/` path.
It reuses the governed source metadata profiles, binds their raw and B1 receipt
digests to a complete caller-supplied baseline, and preserves existing cards,
manifests, source bytes and receipts. The embedded revision describes the
source baseline, not the future commit that adds the metadata document.

This is offline preparation and validation. It has no upload implementation,
does not accept credentials, and does not establish independent authority for
caller-supplied inventories. `verify_metadata_append` revalidates the prepared
transaction and requires the complete unchanged baseline plus its one exact
addition, a new immutable revision, the expected parent, public/non-gated
state, and matching anonymously retrieved metadata bytes.

## Required hosted integration

The next implementation must run only from the approved GitHub Actions
environment, bind the reviewed default-branch commit and durable issue intent,
and independently obtain a complete baseline inventory at the pinned source
revision. Hash every baseline object and retain byte counts; API sibling names
alone do not establish byte preservation. Submit only an add operation with
the Hub `parent_commit` precondition equal to the prepared parent revision.
Never use the existing PBS replace-all publisher
(`.github/workflows/australian-pbs-hf-publication.yml`,
`upload_folder(..., delete_patterns=['*'])`) for this transaction.

After the append, independently observe the new commit's parent and public
non-gated identity, anonymously restore/hash all siblings, then run the
verifier. Persist a durable issue receipt containing code commit, workflow/run,
dataset, parent and new revisions, metadata path/bytes/SHA-256, complete before
and after inventories and anonymous verification outcome. Cleanup must follow
verified durable receipt persistence. A failed append leaves the prior source
revision intact and must not trigger deletion or a dataset-wide privacy change.

No hosted integration or publication is claimed by the offline tests.
