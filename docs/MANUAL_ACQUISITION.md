# Reproducible manual acquisition

Sources whose generated Bronze landing queue state is
`manual_only_documented_acquisition` receive a deterministic
`ManualAcquisitionRecipe`. Recipes are projections of the existing exhaustive
queue, never a second source registry. They describe the public interface,
bounded navigation and completeness evidence without authorising access to
credentials, anti-bot bypasses, or unresolved terms.

An operator may use `scripts/manual_acquisition.py list` and `init` to prepare a
bounded session. After downloading only permitted public outputs, `validate`
hashes every named file and emits a `ManualAcquisitionReceipt`. The receipt
requires a pinned reuse discovery snapshot and permitted rights, records
deviations and page/export counts, and contains no credentials. Missing files,
unavailable surfaces, or rights questions remain explicit blocked or temporary
states. Optional HAR/WARC attachments are evidence only and are never required.

The validated files and receipt are handed to the ordinary B1/B2 Bronze landing
path; this workflow does not create a parallel payload or receipt system.
