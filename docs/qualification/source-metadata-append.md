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

## Prepared hosted integration (execution pending)

`.github/workflows/australian-source-metadata.yml` now runs
`scripts/publish_source_metadata.py` for one reviewed `mbs` or `pbs` profile.
The transport uses exactly one Hub add operation and `parent_commit` CAS;
it has no remove operation or dataset creation/visibility mutation. A current
head differing from the profile's pinned source revision is rejected before
writing. The durable receipt labels parent evidence as server-enforced CAS.

Anonymous downloads use the existing DNS-bound transport and approved Hub
delivery hosts. Each isolated download subprocess has an absolute 60-second
deadline and is killed on expiry, with byte bounds checked before writes.
Inventories are capped at 10,000 entries, 512 MiB per object and 2 GiB per
snapshot (up to 4 GiB across before/after plus metadata); the workflow has a
30-minute timeout. An issue receipt projection exceeding 60,000 characters is
rejected before any append. Exact issue receipt readback must succeed before
temporary source cache cleanup. Tests mock the SDK and transport; no hosted
execution or publication has been performed for this workflow.

The hosted implementation runs only from the approved GitHub Actions
environment, bind the reviewed default-branch commit and durable issue intent,
and independently obtain a complete baseline inventory at the pinned source
revision. Hash every baseline object and retain byte counts; API sibling names
alone do not establish byte preservation. Submit only an add operation with
the Hub `parent_commit` precondition equal to the prepared parent revision.
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

Hosted execution and external publication remain unverified until a reviewed
main commit is dispatched and its public durable receipts are observed.

## Interrupted verification recovery

The workflow persists and reads back a bot-authored `cas_acknowledged` receipt
immediately after the Hub commit response and before anonymous verification.
If verification is interrupted, pass that issue-comment ID as
`recovery_receipt`. Both the acknowledgement and its linked prior intent must
be bot-authored comments on issue 340 with matching exact plan fields. Recovery
requires the acknowledged revision still be the dataset head, rehashes the
original baseline and the complete resulting sibling set, and emits verified
receipt evidence without another append.

Parent evidence remains the authenticated workflow's recorded successful
server-enforced CAS response; no independent Git ancestry claim is made.
An ambiguous commit response, or interruption before acknowledgement becomes
durable, remains a manual reconciliation boundary. Date-sorted commit lists
are not accepted as parent evidence. Recovery preserves the exact reviewed
code commit requirement and cannot silently adopt an unrelated newer head.
