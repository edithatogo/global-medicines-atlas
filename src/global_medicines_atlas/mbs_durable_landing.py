"""Build canonical MBS B1/B2 lifecycle only after anonymous raw verification."""

from __future__ import annotations

from datetime import datetime

from .bronze_admission import (
    BronzeAdmissionState,
    ValidationResult,
    create_admission_decision,
)
from .bronze_raw_evidence import (
    RawEvidenceKind,
    RawEvidenceManifest,
    RawEvidenceState,
    build_raw_evidence_record,
)
from .receipts import (
    EvidenceClass,
    RightsState,
    SourceReceipt,
    acquisition_event_from_receipt,
    require_publication_permitted,
    require_temporal,
)

MBS_DATASET = "edithatogo/australian-mbs-source-archive"
MBS_RAW_RESOLVE_ROOT = f"https://huggingface.co/datasets/{MBS_DATASET}/resolve"
GIT_OBJECT_ID_LENGTH = 40


def build_verified_mbs_lifecycle(
    receipt: SourceReceipt,
    *,
    raw_archive_revision: str,
    raw_object_path: str,
    decided_at: datetime,
    record_count: int,
    p7_record_count: int,
) -> dict[str, bytes]:
    """Create B1/B2 records after source bytes have passed anonymous readback.

    This function accepts no payload bytes. The caller must first obtain the
    immutable public raw revision and anonymously verify its exact digest.
    """
    if receipt.evidence_class is not EvidenceClass.LIVE:
        raise ValueError("durable MBS lifecycle requires a live source receipt")
    if not receipt.satisfies_live_gate:
        raise ValueError(
            "durable MBS lifecycle requires a successful retrieval"
        )
    if receipt.rights_state is not RightsState.PERMITTED:
        raise ValueError("durable MBS lifecycle requires permitted rights")
    if receipt.source.source_id != "au-mbs":
        raise ValueError("durable MBS lifecycle requires the MBS source")
    require_publication_permitted(receipt)
    if len(raw_archive_revision) != GIT_OBJECT_ID_LENGTH or any(
        char not in "0123456789abcdef" for char in raw_archive_revision
    ):
        raise ValueError("raw archive revision must be a pinned Git object id")
    if not raw_object_path.startswith("raw/mbs/releases/2026-08-01/"):
        raise ValueError("raw object path is outside the exact MBS release")
    if raw_object_path != (
        f"raw/mbs/releases/2026-08-01/{receipt.payload.sha256}.xml"
    ):
        raise ValueError("raw object path is not bound to the source digest")
    temporal = require_temporal(receipt.temporal)
    if temporal.source_version != "2026-08-01":
        raise ValueError(
            "source receipt differs from the authorized MBS release"
        )
    if (
        record_count < 1
        or p7_record_count < 0
        or p7_record_count > record_count
    ):
        raise ValueError("MBS source-record counts are inconsistent")
    reference = (
        f"{MBS_RAW_RESOLVE_ROOT}/{raw_archive_revision}/{raw_object_path}"
    )
    b2 = build_raw_evidence_record(
        receipt,
        raw_locator=reference,
        state=RawEvidenceState.EXTERNAL_REFERENCE_ONLY,
        retain_bytes=False,
        kind=RawEvidenceKind.PAYLOAD,
        media_type=(
            receipt.retrieval.http.content_type
            if receipt.retrieval.http is not None
            else None
        ),
    )
    b2_manifest = RawEvidenceManifest.from_rows((b2,))
    landed = create_admission_decision(
        acquisition_id=temporal.acquisition_id,
        content_id=receipt.payload.sha256,
        state=BronzeAdmissionState.LANDED,
        reason_codes=("mbs_raw_object_anonymously_verified",),
        validation_results=(
            ValidationResult(
                check_id="mbs-raw-anonymous-digest-verification",
                passed=True,
                message=(
                    f"revision:{raw_archive_revision}; path:{raw_object_path}; "
                    f"sha256:{receipt.payload.sha256}; bytes:{receipt.payload.byte_count}"
                ),
            ),
        ),
        actor="global-medicines-atlas:mbs-release-v1",
        decided_at=decided_at,
    )
    accepted = create_admission_decision(
        acquisition_id=temporal.acquisition_id,
        content_id=receipt.payload.sha256,
        state=BronzeAdmissionState.ACCEPTED,
        reason_codes=("mbs_xml_profile_passed",),
        validation_results=(
            ValidationResult(
                check_id="official-mbs-xml",
                passed=True,
                message=f"records:{record_count}; p7_records:{p7_record_count}",
            ),
        ),
        actor="global-medicines-atlas:mbs-release-v1",
        decided_at=decided_at,
        supersedes_decision_id=landed.decision_id,
    )
    objects = {
        f"bronze/receipts/au-mbs/{temporal.acquisition_id}.json": (
            receipt.canonical_json() + b"\n"
        ),
        f"bronze/acquisitions/au-mbs/{temporal.acquisition_id}.json": (
            acquisition_event_from_receipt(receipt).canonical_json() + b"\n"
        ),
        (
            f"bronze/admissions/au-mbs/{temporal.acquisition_id}/"
            f"{landed.decision_id}.json"
        ): (landed.model_dump_json(exclude_none=False) + "\n").encode(),
        (
            f"bronze/admissions/au-mbs/{temporal.acquisition_id}/"
            f"{accepted.decision_id}.json"
        ): (accepted.model_dump_json(exclude_none=False) + "\n").encode(),
        (
            f"bronze/raw-evidence/au-mbs/{temporal.acquisition_id}/manifest.json"
        ): b2_manifest.canonical_json(),
    }
    return dict(sorted(objects.items()))
