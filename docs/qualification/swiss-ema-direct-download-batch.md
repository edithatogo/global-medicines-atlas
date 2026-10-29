# Swiss and EMA direct-download Bronze batch

## Scope and stop condition

User-authorized 29 October 2026. Exactly two existing catalogue IDs:
`ch-foph-specialities` and `eu-ema-json`. One current German Swiss SL export
and one unmodified EMA medicines JSON index at most. No linked documents,
other EMA feeds, historical backfill, schedules, new source IDs, interpretation,
Silver/Gold work, federation reopening or Stable release.

Preparation is finished when each profile has either an exact local candidate
with a readback checksum or a concrete blocked disposition. Public archival is
complete only after approved hosted publication and anonymous digest verification.
A blocked source remains open; a HEAD response or a local file is not completed
Bronze admission. No 42-source qualified cohort or deferred ledger is changed.

## Results

- EMA: one 6,795,698-byte JSON index retrieved with the existing
  `HttpPayloadRetriever`, one attempt, 32 MiB cap, 60-second timeout; parsed as
  JSON and verified against the written file. Existing `prepare_publication`
  binds all three candidate files without any remote write.
- Swiss: official host answers HEAD 200 for the German FHIR candidate,
  93,566,103 bytes. The official UI and resource index currently expose null
  links. The alternative candidate URL came from a third-party reference and
  was checked at the official host; current-release identity and data-specific
  rights remain unqualified. No Swiss payload was downloaded. Stop this row.

[Machine-readable dispositions](../../quality/qualifications/swiss-ema-bronze-20261029/batch.json)
retain exact URLs and limits. EMA attribution and third-party exclusions are
recorded in the local package README. This is a proposed rights assessment,
not a new licence or approval for external publication.

## Publication decision

Proposed new public dataset: `edithatogo/global-medicines-atlas-ema-bronze-20261029`.
Only `medicines.json`, `retrieval.json`, and `README.md`, as bound in
[publication-plan.json](../../quality/qualifications/swiss-ema-bronze-20261029/publication-plan.json).
Data SHA-256: `fe0bc6f7dea44ef112d7dac1ad63797132c674a1baeadc93f5775c68897ac76f`.
Existing approvals apply to exact older manifests and are not inherited.

After exact approval, use the existing publication transport from GitHub Actions;
verify the staged file digests against this plan before writing. A freshly
retrieved moving URL must match or produce a new candidate for review. Retain
anonymous remote digest verification and pinned revision before removing local
bytes. Do not upload from the workstation, widen the older international
archive, or treat an Actions artifact as durable public archival.

## Reproduction

The candidate is under `build/swiss-ema-bronze-20261029/ema-package` in the
owned worktree. Payload bytes are intentionally not committed. Run the following
with the repo-local Python 3.15.1 interpreter from a fresh output location only.
It fails if the destination exists, performs no upload and follows no document
links. Future retrieval may have a different digest. No new runner/framework is
introduced; the snippet composes existing public APIs.

```python
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
from global_medicines_atlas.source_catalog import (
    load_source_catalog,
    MedicineDataSource,
)
from global_medicines_atlas.data_layer_archive import (
    HttpPayloadRetriever,
    PayloadKind,
)
from global_medicines_atlas.publication_transport import (
    prepare_publication,
    PublicationTarget,
    PublicationDestination,
)

root = Path("build/swiss-ema-bronze-20261029/ema-package")
root.mkdir(exist_ok=False)
url = "https://www.ema.europa.eu/en/documents/report/medicines-output-medicines_json-report_en.json"
original = next(
    s for s in load_source_catalog() if s.source_id == "eu-ema-json"
)
data = original.model_dump(mode="json")
data.update(download_url=url)
source = MedicineDataSource.model_validate(data)
payload = HttpPayloadRetriever(
    max_bytes=32 * 1024 * 1024, max_attempts=1, timeout_seconds=60
).retrieve(source)
assert payload.kind == PayloadKind.LIVE_PUBLIC, payload.skip_reason
assert payload.uri == url
parsed = json.loads(payload.content)
assert isinstance(parsed, (dict, list))
assert sha256(payload.content).hexdigest() == payload.sha256
(root / "medicines.json").write_bytes(payload.content)
assert (
    sha256((root / "medicines.json").read_bytes()).hexdigest() == payload.sha256
)
(root / "README.md").write_text(
    """# EMA medicines JSON snapshot\n\nSource: European Medicines Agency (EMA).\nOfficial URL: https://www.ema.europa.eu/en/documents/report/medicines-output-medicines_json-report_en.json\nTerms: https://www.ema.europa.eu/en/about-us/about-website/legal-notice\n\nUnmodified public JSON index, captured for the bounded Bronze batch.\nEMA attribution is retained; no EMA endorsement is implied. EMA reproduction\npermissions exclude third-party content. Linked documents, images and other\ndownloads are not included. This is not complete EU medicine coverage, a\ncurrent-status guarantee, a clinical conclusion or a source-data licence grant.\nNo public upload has been authorized or performed.\n"""
)
metadata = {
    "source_id": source.source_id,
    "uri": url,
    "retrieved_at": payload.retrieved_at,
    "sha256": payload.sha256,
    "byte_count": len(payload.content),
    "content_type": payload.content_type,
    "attempts": payload.attempts,
    "top_level_type": type(parsed).__name__,
    "top_level_count": len(parsed),
    "byte_readback_verified": True,
    "publication_state": "not_uploaded",
    "rights_assessment": "proposed EMA attribution terms; maintainer publication decision pending",
    "linked_documents_downloaded": 0,
}
(root / "retrieval.json").write_text(json.dumps(metadata, indent=2) + "\n")
target = PublicationTarget(
    destination=PublicationDestination.HUGGING_FACE,
    repository="edithatogo/global-medicines-atlas-ema-bronze-20261029",
    revision="main",
    public_base_url="https://huggingface.co/datasets/edithatogo/global-medicines-atlas-ema-bronze-20261029/resolve/main",
)
plan, receipt = prepare_publication(
    root=root,
    release_version="bronze-ema-20261029",
    target=target,
    relative_paths=tuple(sorted(p.name for p in root.iterdir())),
    recorded_at=datetime.now(UTC),
)
for name, obj in [
    ("publication-plan.json", plan),
    ("prepared-receipt.json", receipt),
]:
    Path("quality/qualifications/swiss-ema-bronze-20261029", name).write_text(
        obj.model_dump_json(indent=2) + "\n"
    )
Path(
    "quality/qualifications/swiss-ema-bronze-20261029/retrieval.json"
).write_text(json.dumps(metadata, indent=2) + "\n")
print(json.dumps(metadata))
```
