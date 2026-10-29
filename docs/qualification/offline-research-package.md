# Content-addressed local research packages

A research package can describe a local result with a `urn:sha256:` reference
instead of asserting that the result is publicly hosted. This form uses crate
schema version 2 and lineage schema version 3. Its lineage revision is the
assembly commit; inputs retain their own pinned source revisions and HTTPS
locations. The existing public form retains its HTTPS and revision requirements.

The metadata archive does not contain the result. Clean-room verification of a
local package requires the separately supplied canonical JSON result bytes and
checks their digest, row count, canonical ordering and query identity. The local
reference identifies bytes; it is not a downloadable URL or proof of publication.
The archive does not establish source availability, rights, admission or the
accuracy of source semantics. Those remain bound to their own receipts.

The implementation has focused synthetic validation. An actual admitted-source
package canary, exact-commit evidence and protected CI remain outstanding.
