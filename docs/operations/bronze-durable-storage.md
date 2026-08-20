# Bronze durable-storage and sensitivity contract

Bronze payload bytes are written through
`global_medicines_atlas.bronze_storage.PayloadStore`. The local filesystem
implementation is for development and deterministic tests. It is not evidence
of production durability.

Durable operation uses `ObjectStoragePayloadStore` with provider clients that
implement two narrow calls: conditional immutable put and version-addressed
get. The core package therefore does not require an AWS, Azure, or GCP SDK and
never receives credentials in a receipt. Provider integration must return an
object version identifier and, when selected, Object Lock/WORM evidence.

A durable `DurabilityPolicy` is rejected unless it declares:

- versioning, Object Lock, or WORM;
- primary and replica regions in separate geographic failure domains;
- primary and replica administrative domains under separate control;
- checksum-inventory and restore-rehearsal cadences;
- positive RPO and RTO values in seconds.

Each landing writes `storage/<source_id>/<acquisition_id>.json`. That append-only
receipt binds the acquisition/content IDs and checksum to the primary and every
replica URI and provider version. `create_checksum_inventory()` reads and
hashes all copies. For durable policies, `rehearse_restore()` restores the
policy-matching independent replica into an empty target, verifies its checksum,
records the replica source role, measures elapsed time, and records whether the
declared RTO was met. Scheduling and deploying these operations belongs to the
operator; passing fixture tests does not qualify a production RPO or RTO.

Rights and sensitivity are separate gates. `SourceReceipt.sensitivity` records
intrinsic sensitivity, possible/present personal data, publication disposition,
and reason codes. `require_publication_permitted()` requires both permitted
rights and a permitted publication disposition. Public pharmacovigilance or
free-text regulatory data should normally remain `review_required` until its
disclosure risk has been assessed.
