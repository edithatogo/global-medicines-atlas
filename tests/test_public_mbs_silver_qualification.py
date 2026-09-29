"""Hosted-only public MBS candidate qualifier controls."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from functools import partial
from typing import Any, cast

import httpx
import pytest
from pydantic import AnyUrl
from scripts import qualify_public_mbs_silver as command

from global_medicines_atlas.mbs_silver_qualification import (
    MbsSilverQualification,
)
from global_medicines_atlas.receipts import (
    AcquisitionMethod,
    AcquisitionStatus,
    EvidenceClass,
    PayloadEvidence,
    RetrievalEvidence,
    RightsState,
    SourceIdentity,
    SourceReceipt,
    TransformationEvidence,
)


@pytest.fixture(autouse=True)
def stub_public_v4_network_readback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def verified(_report: MbsSilverQualification) -> dict[str, object]:
        return {
            "status": "verified",
            "current_revision": "c" * 40,
            "verified_object_count": 9,
            "candidate_only": True,
        }

    monkeypatch.setattr(
        command,
        "_read_public_v4_identity",
        verified,
    )


class _Response:
    def __init__(self, payload: bytes, *, fail_status: bool = False) -> None:
        self.payload = payload
        self.fail_status = fail_status

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def raise_for_status(self) -> None:
        if self.fail_status:
            raise ValueError("unexpected HTTP redirect")

    def iter_bytes(self):
        yield self.payload


class _Client:
    def __init__(
        self,
        payload: bytes,
        official_payload: bytes | None = None,
        *,
        official_redirect: bool = False,
        **kwargs: object,
    ) -> None:
        assert kwargs["follow_redirects"] is True
        assert kwargs["trust_env"] is False
        assert isinstance(kwargs["timeout"], httpx.Timeout)
        assert kwargs["timeout"].read == 60
        assert kwargs["max_redirects"] == 3
        assert kwargs["transport"] is not None
        self.payload = payload
        self.official_payload = official_payload or payload
        self.official_redirect = official_redirect

    def __enter__(self) -> _Client:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def stream(self, method: str, url: str, **kwargs: object) -> _Response:
        assert method == "GET"
        if url == command.SOURCE_URI:
            assert not kwargs
            return _Response(self.payload)
        assert url == command.OFFICIAL_MBS_V3_URI
        assert kwargs == {"follow_redirects": False}
        return _Response(
            self.official_payload, fail_status=self.official_redirect
        )


def _client_factory(
    payload: bytes,
    official_payload: bytes | None = None,
    *,
    official_redirect: bool = False,
) -> Any:
    return cast(
        "Any",
        partial(
            _Client,
            payload,
            official_payload,
            official_redirect=official_redirect,
        ),
    )


def test_qualifies_only_digest_bound_public_bytes_in_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = b"<MBS_XML><Data><ItemNum>00123</ItemNum></Data></MBS_XML>"
    monkeypatch.setattr(command, "LEGACY_MBS_BYTES", len(payload))
    monkeypatch.setattr(
        command, "LEGACY_MBS_SHA256", hashlib.sha256(payload).hexdigest()
    )
    monkeypatch.setattr(
        command, "OFFICIAL_RELEASED_AT", command.date(2025, 6, 16)
    )
    monkeypatch.setattr(command.httpx, "Client", _client_factory(payload))

    result = command.qualify(exact_commit="a" * 40)

    qualification = cast("dict[str, object]", result["qualification"])
    assert qualification["source_record_count"] == 1
    tables = cast("list[dict[str, object]]", qualification["tables"])
    assert sum(cast("int", table["field_count"]) for table in tables) == 40
    assert qualification["promotion_status"] == "candidate_only"
    assert qualification["blockers"] == ["public_v4_identity_unverified"]
    assert result["resolved_blockers"] == ["public_v4_identity_unverified"]
    assert result["current_blockers"] == []
    assert (
        cast("dict[str, object]", result["official_release_check"])[
            "matched_pinned_archive"
        ]
        is True
    )
    assert result["publication_performed"] is False
    assert result["source_bytes_retained"] is False
    candidate_report = {
        "qualification": qualification,
        "public_v4_identity": result["public_v4_identity"],
        "resolved_blockers": result["resolved_blockers"],
        "current_blockers": result["current_blockers"],
        "quality_diagnostics": result["quality_diagnostics"],
        "official_release_check": result["official_release_check"],
    }
    expected_digest = hashlib.sha256(
        json.dumps(
            candidate_report, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    assert result["candidate_report_sha256"] == expected_digest
    assert cast("int", result["candidate_report_byte_count"]) > 0
    assert "payload" not in result
    diagnostics = cast("dict[str, object]", result["quality_diagnostics"])
    assert diagnostics["source_values_included"] is False


def test_quality_diagnostics_locate_field_and_row_without_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = (
        b"<MBS_XML><Data><ItemNum>00123</ItemNum>"
        b"<ItemStartDate>not-a-date</ItemStartDate>"
        b"<Benefit85>123456.78</Benefit85></Data>"
        b"<Data><ItemNum>00456</ItemNum>"
        b"<Benefit85>bad-amount</Benefit85></Data></MBS_XML>"
    )
    monkeypatch.setattr(command, "LEGACY_MBS_BYTES", len(payload))
    monkeypatch.setattr(
        command, "LEGACY_MBS_SHA256", hashlib.sha256(payload).hexdigest()
    )
    monkeypatch.setattr(
        command, "OFFICIAL_RELEASED_AT", command.date(2025, 6, 16)
    )
    monkeypatch.setattr(command.httpx, "Client", _client_factory(payload))

    result = command.qualify(exact_commit="a" * 40)

    assert cast("dict[str, object]", result["qualification"])["blockers"] == [
        "public_v4_identity_unverified",
        "quality_findings_present",
    ]
    diagnostics = cast("dict[str, object]", result["quality_diagnostics"])
    findings = cast(
        "list[dict[str, object]]",
        diagnostics["quality_finding_source_ordinals"],
    )
    invalid = [item for item in findings if item["status"] == "invalid"]
    assert invalid == [
        {
            "table": "benefits",
            "field": "Benefit85",
            "status": "invalid",
            "source_ordinals": [0, 1],
        },
        {
            "table": "services",
            "field": "ItemStartDate",
            "status": "invalid",
            "source_ordinals": [0],
        },
    ]
    amount_reasons = cast(
        "list[dict[str, object]]",
        diagnostics["invalid_amount_reason_source_ordinals"],
    )
    assert amount_reasons == [
        {
            "table": "benefits",
            "field": "Benefit85",
            "reason": "integer_width_exceeded",
            "source_ordinals": [0],
        },
        {
            "table": "benefits",
            "field": "Benefit85",
            "reason": "strict_numeric_grammar_mismatch",
            "source_ordinals": [1],
        },
    ]
    assert diagnostics["source_values_included"] is False
    assert "not-a-date" not in json.dumps(result)
    assert "123456.78" not in json.dumps(result)
    assert "bad-amount" not in json.dumps(result)
    assert (
        result["candidate_report_sha256"]
        == hashlib.sha256(
            json.dumps(
                {
                    "qualification": result["qualification"],
                    "public_v4_identity": result["public_v4_identity"],
                    "resolved_blockers": result["resolved_blockers"],
                    "current_blockers": result["current_blockers"],
                    "quality_diagnostics": diagnostics,
                    "official_release_check": result["official_release_check"],
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
    )


@pytest.mark.parametrize(
    ("actual_bytes", "expected_bytes", "expected_sha", "message"),
    [
        (b"abc", 4, hashlib.sha256(b"abc").hexdigest(), "byte count"),
        (b"abc", 3, "0" * 64, "digest"),
    ],
)
def test_rejects_public_object_identity_drift(
    monkeypatch: pytest.MonkeyPatch,
    actual_bytes: bytes,
    expected_bytes: int,
    expected_sha: str,
    message: str,
) -> None:
    monkeypatch.setattr(command, "LEGACY_MBS_BYTES", expected_bytes)
    monkeypatch.setattr(command, "LEGACY_MBS_SHA256", expected_sha)
    monkeypatch.setattr(command.httpx, "Client", _client_factory(actual_bytes))

    with pytest.raises(ValueError, match=message):
        command.qualify(exact_commit="a" * 40)


def test_official_release_mismatch_keeps_era_blocker_and_hash_only_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = b"<MBS_XML><Data><ItemNum>00123</ItemNum></Data></MBS_XML>"
    official_payload = payload + b" "
    monkeypatch.setattr(command, "LEGACY_MBS_BYTES", len(payload))
    monkeypatch.setattr(
        command, "LEGACY_MBS_SHA256", hashlib.sha256(payload).hexdigest()
    )
    monkeypatch.setattr(
        command.httpx, "Client", _client_factory(payload, official_payload)
    )

    result = command.qualify(exact_commit="a" * 40)

    qualification = cast("dict[str, object]", result["qualification"])
    assert qualification["blockers"] == [
        "public_v4_identity_unverified",
        "real_source_era_unqualified",
    ]
    release_check = cast("dict[str, object]", result["official_release_check"])
    assert release_check["matched_pinned_archive"] is False
    assert (
        release_check["source_sha256"]
        == hashlib.sha256(official_payload).hexdigest()
    )
    assert release_check["source_byte_count"] == len(official_payload)
    assert "<MBS_XML>" not in json.dumps(result)


def test_official_release_redirect_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = b"<MBS_XML><Data><ItemNum>00123</ItemNum></Data></MBS_XML>"
    monkeypatch.setattr(command, "LEGACY_MBS_BYTES", len(payload))
    monkeypatch.setattr(
        command, "LEGACY_MBS_SHA256", hashlib.sha256(payload).hexdigest()
    )
    monkeypatch.setattr(
        command.httpx,
        "Client",
        _client_factory(payload, official_redirect=True),
    )

    with pytest.raises(ValueError, match="redirect"):
        command.qualify(exact_commit="a" * 40)


def test_invalid_amount_decimal_probe_is_value_free(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native_spellings = (
        "1e2",
        "1_000",
        "1,000",
    )
    records = b"".join(
        (
            f"<Data><ItemNum>{index + 1:05d}</ItemNum>"
            f"<Benefit85>{spelling}</Benefit85></Data>"
        ).encode()
        for index, spelling in enumerate(native_spellings)
    )
    payload = b"<MBS_XML>" + records + b"</MBS_XML>"
    monkeypatch.setattr(command, "LEGACY_MBS_BYTES", len(payload))
    monkeypatch.setattr(
        command, "LEGACY_MBS_SHA256", hashlib.sha256(payload).hexdigest()
    )
    monkeypatch.setattr(command.httpx, "Client", _client_factory(payload))

    result = command.qualify(exact_commit="a" * 40)

    diagnostics = cast("dict[str, object]", result["quality_diagnostics"])
    probes = cast(
        "list[dict[str, object]]",
        diagnostics["invalid_amount_decimal_probe_source_ordinals"],
    )
    assert probes == [
        {
            "table": "benefits",
            "probe": "decimal_constructor_rejected",
            "source_ordinals": [2],
        },
        {
            "table": "benefits",
            "probe": "exponent_notation",
            "source_ordinals": [0],
        },
        {
            "table": "benefits",
            "probe": "underscore_separator",
            "source_ordinals": [1],
        },
    ]

    def string_values(value: object) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            mapping = cast("dict[str, object]", value)
            return [
                text
                for nested in mapping.values()
                for text in string_values(nested)
            ]
        if isinstance(value, list):
            items = cast("list[object]", value)
            return [text for nested in items for text in string_values(nested)]
        return []

    emitted_values = string_values(result)
    assert all(spelling not in emitted_values for spelling in native_spellings)
    assert diagnostics["source_values_included"] is False


@pytest.mark.parametrize("commit", ["", "A" * 40, "a" * 39, "z" * 40])
def test_requires_exact_lowercase_commit(commit: str) -> None:
    with pytest.raises(ValueError, match="exact commit"):
        command.qualify(exact_commit=commit)


def test_workflow_is_exact_main_read_only_and_never_publishes() -> None:
    workflow = (
        command.ROOT
        / ".github/workflows/australian-mbs-silver-qualification.yml"
    ).read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert "REQUESTED_COMMIT" in workflow
    assert 'test "${GITHUB_SHA}" = "${REQUESTED_COMMIT}"' in workflow
    assert "permissions: {}" in workflow
    assert "contents: read" in workflow
    assert "issue" not in workflow.lower()
    assert "publish" not in workflow.lower()
    assert "source-retained" not in workflow.lower()


def _public_v4_fixture(
    report: Any,
) -> tuple[bytes, bytes, bytes, list[dict[str, Any]], dict[str, Any]]:
    dataset = "edithatogo/australian-mbs-source-archive"
    revision = "b" * 40
    prefix = "silver/mbs/v4/2025-07-v3"
    table_bytes = {
        f"{prefix}/{name}.parquet": f"table-{name}".encode()
        for name in (
            "services",
            "hierarchy",
            "descriptions",
            "fees",
            "benefits",
            "caps",
        )
    }
    public_qualification = {
        "schema_id": "global-medicines-atlas.mbs-silver-qualification",
        "schema_version": 1,
        "candidate_only": True,
        "field_count": report.field_count,
        "field_occurrence_count": report.field_occurrence_count,
        "qualification": report.model_dump(mode="json"),
    }
    qualification_bytes = json.dumps(
        public_qualification, sort_keys=True, separators=(",", ":")
    ).encode()
    source_receipt_bytes = json.dumps(
        {
            "source": {"source_id": report.source_id},
            "payload": {
                "sha256": report.source_sha256,
                "byte_count": report.source_byte_count,
            },
            "rights_state": "permitted",
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    objects: list[dict[str, Any]] = [
        {
            "path": path,
            "byte_count": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "role": "source_faithful_silver_table",
        }
        for path, data in table_bytes.items()
    ]
    objects.extend([
        {
            "path": f"{prefix}/qualification.json",
            "byte_count": len(qualification_bytes),
            "sha256": hashlib.sha256(qualification_bytes).hexdigest(),
            "role": "value_free_qualification",
        },
        {
            "path": f"{prefix}/source-receipt.json",
            "byte_count": len(source_receipt_bytes),
            "sha256": hashlib.sha256(source_receipt_bytes).hexdigest(),
            "role": "b1_source_receipt",
        },
    ])
    manifest = {
        "schema_id": "global-medicines-atlas.mbs-silver-v4-manifest",
        "schema_version": 1,
        "dataset": dataset,
        "destination_prefix": prefix,
        "candidate_only": True,
        "qualification_sha256": report.qualification_sha256,
        "source": {
            "source_id": report.source_id,
            "sha256": report.source_sha256,
            "byte_count": report.source_byte_count,
        },
        "objects": objects,
    }
    manifest_bytes = json.dumps(
        manifest, sort_keys=True, separators=(",", ":")
    ).encode()
    all_objects = [
        *objects,
        {
            "path": f"{prefix}/manifest.json",
            "byte_count": len(manifest_bytes),
            "sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        },
    ]
    tree_entries: list[dict[str, Any]] = []
    for obj in all_objects:
        row: dict[str, Any] = {
            "path": obj["path"],
            "size": obj["byte_count"],
        }
        if str(obj["path"]).endswith(".parquet"):
            row["lfs"] = {
                "oid": obj["sha256"],
                "size": obj["byte_count"],
            }
        tree_entries.append(row)
    publication_receipt = {
        "dataset": dataset,
        "revision": revision,
        "prefix": prefix,
        "candidate_only": True,
        "anonymous_digest_verification": "passed",
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "verified_objects": all_objects,
    }
    return (
        manifest_bytes,
        qualification_bytes,
        source_receipt_bytes,
        tree_entries,
        publication_receipt,
    )


def _candidate_report() -> Any:
    payload = b"<MBS_XML><Data><ItemNum>00123</ItemNum></Data></MBS_XML>"
    evidence = PayloadEvidence.from_bytes(payload)
    receipt = SourceReceipt(
        receipt_id="synthetic:public-mbs-v4",
        source=SourceIdentity(
            catalog_id="au-mbs",
            source_id="au-mbs",
            jurisdiction="AUS",
            authority="Synthetic",
            dataset_title="Synthetic MBS",
            catalog_version="synthetic-v1",
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl("https://fixtures.invalid/mbs"),
            retrieved_at=datetime(2026, 9, 1, tzinfo=UTC),
            acquisition_method=AcquisitionMethod.LOCAL_FIXTURE,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=evidence,
        rights_state=RightsState.UNKNOWN,
        evidence_class=EvidenceClass.SYNTHETIC,
        transformation=TransformationEvidence(
            transformation_id="synthetic",
            transformation_sha256="a" * 64,
            output_sha256=evidence.sha256,
            output_byte_count=evidence.byte_count,
        ),
    )
    return command.qualify_mbs_silver(payload, receipt, date_format="mbs-dmy")


def test_public_v4_readback_binds_outputs_and_keeps_candidate_only() -> None:
    report = _candidate_report()
    fixture = _public_v4_fixture(report)

    evidence = command.verify_public_v4_identity(
        report,
        current_revision="c" * 40,
        manifest_bytes=fixture[0],
        qualification_bytes=fixture[1],
        source_receipt_bytes=fixture[2],
        tree_entries=fixture[3],
        publication_receipt=fixture[4],
    )

    assert evidence["status"] == "verified"
    assert evidence["verified_object_count"] == 9
    assert evidence["table_count"] == 6
    assert evidence["projection_denominator_matches_public_v4"] is True
    assert evidence["candidate_only"] is True


def test_public_v4_readback_rejects_lfs_identity_drift() -> None:
    report = _candidate_report()
    fixture = list(_public_v4_fixture(report))
    tree_entries = cast("list[dict[str, Any]]", fixture[3])
    tree_entries[0]["lfs"]["oid"] = "0" * 64

    with pytest.raises(ValueError, match="public v4 object identity differs"):
        command.verify_public_v4_identity(
            report,
            current_revision="c" * 40,
            manifest_bytes=cast("bytes", fixture[0]),
            qualification_bytes=cast("bytes", fixture[1]),
            source_receipt_bytes=cast("bytes", fixture[2]),
            tree_entries=tree_entries,
            publication_receipt=cast("dict[str, Any]", fixture[4]),
        )


def test_public_v4_readback_rejects_a_promoted_publication_claim() -> None:
    report = _candidate_report()
    fixture = list(_public_v4_fixture(report))
    publication_receipt = cast("dict[str, Any]", fixture[4])
    publication_receipt["candidate_only"] = False

    with pytest.raises(ValueError, match="manifest or publication receipt"):
        command.verify_public_v4_identity(
            report,
            current_revision="c" * 40,
            manifest_bytes=cast("bytes", fixture[0]),
            qualification_bytes=cast("bytes", fixture[1]),
            source_receipt_bytes=cast("bytes", fixture[2]),
            tree_entries=cast("list[dict[str, Any]]", fixture[3]),
            publication_receipt=publication_receipt,
        )
