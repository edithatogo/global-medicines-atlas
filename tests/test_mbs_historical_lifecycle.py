"""Tests for metadata-only lifecycle reconstruction of archived MBS objects."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

import pytest

from global_medicines_atlas.bronze_admission import (
    BronzeAdmissionRecord,
    BronzeAdmissionState,
)
from global_medicines_atlas.bronze_raw_evidence import (
    RawEvidenceManifest,
    RawEvidenceState,
)
from global_medicines_atlas.mbs_historical_lifecycle import (
    append_manifest_rows,
    build_historical_mbs_lifecycle,
)
from global_medicines_atlas.receipts import (
    AcquisitionEvent,
    EvidenceClass,
    SourceReceipt,
)

_PAYLOAD = b"source bytes are never passed to the builder"
_DIGEST = hashlib.sha256(_PAYLOAD).hexdigest()
_COMMIT = "a" * 40


def sidecar() -> dict[str, Any]:
    return {
        "archive_path": (
            "raw/mbs/releases/Downloads-20260701/MBS-XML-20260701.XML"
        ),
        "byte_count": len(_PAYLOAD),
        "category": "monthly_schedule_xml",
        "final_url": "https://www.mbsonline.gov.au/official/MBS.xml",
        "period_label": "Downloads-20260701",
        "retrieved_at": "2026-10-05T08:20:30Z",
        "schema_id": "global-medicines-atlas.australian-harvest-receipt",
        "schema_version": 1,
        "sha256": _DIGEST,
        "source_id": "au-mbs",
        "source_url": "https://www.mbsonline.gov.au/official/MBS.xml",
    }


def authorization() -> dict[str, Any]:
    return {
        "authorized_at": "2026-09-06",
        "allowed_domains": ["www.mbsonline.gov.au", "mbsonline.gov.au"],
        "allowed_sources": ["au-mbs"],
        "categories": [
            "monthly_schedule_xml",
            "basic_service_description",
            "relative_value_guide",
        ],
        "dataset": "edithatogo/australian-mbs-source-archive",
        "external_publication_authorized": True,
        "maintainer_asserted_redistribution_permission": True,
    }


def lifecycle() -> dict[str, bytes]:
    return build_historical_mbs_lifecycle(
        sidecar(),
        authorization=authorization(),
        authorization_commit=_COMMIT,
        archive_revision="b" * 40,
        observed_sha256=_DIGEST,
        observed_byte_count=len(_PAYLOAD),
        decided_at=datetime(2026, 10, 18, tzinfo=UTC),
    )


def _build(
    *,
    source: dict[str, Any] | None = None,
    rights: dict[str, Any] | None = None,
    commit: str = _COMMIT,
    revision: str = "b" * 40,
    decided_at: datetime | None = None,
) -> dict[str, bytes]:
    current_sidecar = sidecar() if source is None else source
    current_rights = authorization() if rights is None else rights
    return build_historical_mbs_lifecycle(
        current_sidecar,
        authorization=current_rights,
        authorization_commit=commit,
        archive_revision=revision,
        observed_sha256=_DIGEST,
        observed_byte_count=len(_PAYLOAD),
        decided_at=decided_at or datetime(2026, 10, 18, tzinfo=UTC),
    )


@pytest.mark.unit
def test_mbs_historical_lifecycle_records_landed_reference_only_state() -> None:
    bundle = lifecycle()
    assert len(bundle) == 4

    receipt_path, receipt_bytes = next(
        (path, payload)
        for path, payload in bundle.items()
        if path.startswith("bronze/receipts/")
    )
    receipt = SourceReceipt.model_validate_json(receipt_bytes)
    assert receipt.temporal is not None
    assert receipt_path.endswith(f"{receipt.temporal.acquisition_id}.json")
    assert receipt.evidence_class is EvidenceClass.HISTORICAL
    assert receipt.payload.sha256 == _DIGEST
    assert receipt.payload.byte_count == len(_PAYLOAD)
    assert receipt.sensitivity is not None
    assert receipt.sensitivity.publication.value == "review_required"

    event = AcquisitionEvent.model_validate_json(
        next(
            payload
            for path, payload in bundle.items()
            if path.startswith("bronze/acquisitions/")
        )
    )
    assert receipt.temporal is not None
    assert event.acquisition_id == receipt.temporal.acquisition_id
    assert event.evidence_class is EvidenceClass.HISTORICAL

    raw_manifest = RawEvidenceManifest.model_validate_json(
        next(
            payload
            for path, payload in bundle.items()
            if path.startswith("bronze/raw-evidence/")
        )
    )
    assert (
        raw_manifest.rows[0].state is RawEvidenceState.EXTERNAL_REFERENCE_ONLY
    )
    assert raw_manifest.rows[0].payload_sha256 is None
    assert raw_manifest.rows[0].byte_count is None
    assert "/resolve/" + "b" * 40 + "/" + sidecar()["archive_path"] in (
        raw_manifest.rows[0].external_reference or ""
    )

    admission = BronzeAdmissionRecord.model_validate_json(
        next(
            payload
            for path, payload in bundle.items()
            if path.startswith("bronze/admissions/")
        )
    )
    assert admission.state is BronzeAdmissionState.LANDED
    assert admission.reviewer_status == "unreviewed"
    assert all(result.passed for result in admission.validation_results)
    assert not any(path.endswith("accepted.json") for path in bundle)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("observed_sha256", "observed_byte_count"),
    [("0" * 64, len(_PAYLOAD)), (_DIGEST, len(_PAYLOAD) + 1)],
)
def test_lifecycle_rejects_digest_or_size_drift(
    observed_sha256: str, observed_byte_count: int
) -> None:
    with pytest.raises(ValueError, match="differ"):
        build_historical_mbs_lifecycle(
            sidecar(),
            authorization=authorization(),
            authorization_commit=_COMMIT,
            archive_revision="b" * 40,
            observed_sha256=observed_sha256,
            observed_byte_count=observed_byte_count,
            decided_at=datetime(2026, 10, 18, tzinfo=UTC),
        )


@pytest.mark.unit
def test_lifecycle_rejects_source_domain_or_category_outside_authority() -> (
    None
):
    denied = sidecar()
    denied["source_url"] = "https://example.invalid/MBS.xml"
    denied["final_url"] = denied["source_url"]
    with pytest.raises(ValueError, match="authorization"):
        build_historical_mbs_lifecycle(
            denied,
            authorization=authorization(),
            authorization_commit=_COMMIT,
            archive_revision="b" * 40,
            observed_sha256=_DIGEST,
            observed_byte_count=len(_PAYLOAD),
            decided_at=datetime(2026, 10, 18, tzinfo=UTC),
        )

    denied_category = sidecar()
    denied_category["category"] = "medicine_level"
    with pytest.raises(ValueError, match="sidecar"):
        build_historical_mbs_lifecycle(
            denied_category,
            authorization=authorization(),
            authorization_commit=_COMMIT,
            archive_revision="b" * 40,
            observed_sha256=_DIGEST,
            observed_byte_count=len(_PAYLOAD),
            decided_at=datetime(2026, 10, 18, tzinfo=UTC),
        )


@pytest.mark.unit
def test_manifest_append_preserves_existing_rows_and_refuses_overwrite() -> (
    None
):
    bundle = lifecycle()
    existing = {"bytes": 3, "path": "README.md", "sha256": "c" * 64}
    manifest = {
        "dataset": "edithatogo/australian-mbs-source-archive",
        "file_count": 1,
        "files": [existing],
        "generated_at": "2026-10-17T00:00:00Z",
        "schema_id": "global-medicines-atlas.harvest-manifest",
        "schema_version": 1,
    }
    encoded = append_manifest_rows(
        manifest,
        bundle,
        generated_at=datetime(2026, 10, 18, tzinfo=UTC),
    )
    updated = json.loads(encoded)
    assert updated["file_count"] == 5
    assert updated["files"][0] == existing
    with pytest.raises(ValueError, match="rewrite"):
        append_manifest_rows(
            updated,
            bundle,
            generated_at=datetime(2026, 10, 18, tzinfo=UTC),
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("field", "value"),
    [("source_id", None), ("category", " ")],
)
def test_historical_lifecycle_requires_sidecar_identity_fields(
    field: str, value: Any
) -> None:
    source = sidecar()
    source[field] = value
    with pytest.raises(ValueError, match="is required"):
        _build(source=source)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("commit", "revision"),
    [("bad", "b" * 40), (_COMMIT, "g" * 40)],
)
def test_historical_lifecycle_requires_pinned_git_identities(
    commit: str, revision: str
) -> None:
    with pytest.raises(ValueError, match="must be pinned"):
        _build(commit=commit, revision=revision)


@pytest.mark.unit
def test_historical_lifecycle_rejects_http_final_url_and_missing_rights() -> (
    None
):
    insecure = sidecar()
    insecure["final_url"] = "http://www.mbsonline.gov.au/official/MBS.xml"
    with pytest.raises(ValueError, match="readback differs"):
        _build(source=insecure)

    no_permission = authorization()
    no_permission["external_publication_authorized"] = False
    with pytest.raises(ValueError, match="authorization"):
        _build(rights=no_permission)


@pytest.mark.unit
@pytest.mark.parametrize(
    "decided_at",
    [
        datetime(2026, 10, 18),  # ruff: ignore[call-datetime-without-tzinfo] -- rejected naive-time fixture
        datetime(2026, 10, 4, tzinfo=UTC),
    ],
)
def test_historical_lifecycle_requires_ordered_aware_timestamps(
    decided_at: datetime,
) -> None:
    expected = (
        "timestamps must be aware"
        if decided_at.tzinfo is None
        else "cannot precede"
    )
    with pytest.raises(ValueError, match=expected):
        _build(decided_at=decided_at)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("manifest", "error_type", "message"),
    [
        ({"files": [], "file_count": 0}, ValueError, "unsupported"),
        (
            {
                "schema_id": "global-medicines-atlas.harvest-manifest",
                "schema_version": 1,
                "file_count": 1,
                "files": [],
            },
            ValueError,
            "unsupported",
        ),
        (
            {
                "schema_id": "global-medicines-atlas.harvest-manifest",
                "schema_version": 1,
                "file_count": 1,
                "files": [None],
            },
            TypeError,
            "invalid MBS root manifest row",
        ),
        (
            {
                "schema_id": "global-medicines-atlas.harvest-manifest",
                "schema_version": 1,
                "file_count": 1,
                "files": [{"path": 2}],
            },
            TypeError,
            "invalid MBS root manifest row",
        ),
        (
            {
                "schema_id": "global-medicines-atlas.harvest-manifest",
                "schema_version": 1,
                "file_count": 2,
                "files": [{"path": "same"}, {"path": "same"}],
            },
            ValueError,
            "duplicate",
        ),
    ],
)
def test_manifest_append_rejects_invalid_parent_shape(
    manifest: dict[str, Any], error_type: type[Exception], message: str
) -> None:
    with pytest.raises(error_type, match=message):
        append_manifest_rows(
            manifest,
            {},
            generated_at=datetime(2026, 10, 18, tzinfo=UTC),
        )


@pytest.mark.unit
def test_manifest_append_rejects_duplicate_and_malformed_rows() -> None:
    base = {
        "schema_id": "global-medicines-atlas.harvest-manifest",
        "schema_version": 1,
        "file_count": 1,
    }
    for rows in ([{"path": None}], [{"path": "same"}, {"path": "same"}]):
        manifest = {**base, "file_count": len(rows), "files": rows}
        expected = (
            "invalid MBS root manifest row"
            if rows[0]["path"] is None
            else "duplicate"
        )
        with pytest.raises((TypeError, ValueError), match=expected):
            append_manifest_rows(
                manifest,
                {},
                generated_at=datetime(2026, 10, 18, tzinfo=UTC),
            )
