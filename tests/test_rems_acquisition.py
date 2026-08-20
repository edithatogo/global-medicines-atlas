"""Contracts for the bounded FDA REMS acquisition family."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from pydantic import AnyHttpUrl, ValidationError

from global_medicines_atlas.rems_acquisition import (
    FDARemsAuthorization,
    exercise_fda_rems,
    parse_current_detail_inventory,
    parse_document_inventory,
)

ROOT = Path(__file__).resolve().parents[1]
AUTHORIZATION = ROOT / "quality/qualifications/fda-rems-live-authorization.json"
BASE = "https://www.accessdata.fda.gov/scripts/cder/rems/index.cfm"


def _authorization(tmp_path: Path) -> Path:
    raw = json.loads(AUTHORIZATION.read_text(encoding="utf-8"))
    raw["expected_current_detail_count"] = 2
    raw["expected_current_document_count"] = 3
    raw["request_interval_seconds"] = 0
    path = tmp_path / "authorization.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


def _index() -> bytes:
    return b"""
    <a href="/scripts/cder/rems/index.cfm?event=IndvRemsDetails.page&REMS=1">One</a>
    <a href="/scripts/cder/rems/index.cfm?event=RemsDetails.page&REMS=2#tabs-3">Two</a>
    <a href="https://example.test/scripts/cder/rems/index.cfm?event=RemsDetails.page&REMS=3">Unsafe</a>
    """


def _detail(rems_id: str) -> bytes:
    shared = (
        '<a href="https://www.accessdata.fda.gov/drugsatfda_docs/rems/shared.pdf" '
        'title="Shared document">PDF</a>'
    )
    unique = (
        f'<a href="https://www.accessdata.fda.gov/drugsatfda_docs/rems/{rems_id}.pdf" '
        f'title="Document {rems_id}">PDF</a>'
    )
    excluded = '<a href="https://example.test/not-fda.pdf">External</a>'
    return f"<html>{shared}{unique}{excluded}</html>".encode()


def _csv(path: str) -> bytes:
    if "csvModification" in path:
        return b'\n"REMSID","VersionID","Version_Date"\n"1","7","01/01/2026"\n'
    if "csvRemsProduct" in path:
        return b'\n"REMSID","REMS_Product_ID","Trade_Name"\n"1","8","One"\n'
    if "csvReleased" in path:
        return b'\n"REMSID","Application_Number","REMS_Name"\n"1","123","One"\n'
    return b'\n"REMSID","Drug Name","Inactive_Flag"\n"1","One","Active"\n'


def test_authorization_is_bounded_internal_and_rights_fail_closed() -> None:
    authorization = FDARemsAuthorization.model_validate_json(
        AUTHORIZATION.read_bytes()
    )
    assert authorization.acquisition_authorized is True
    assert authorization.internal_retention_authorized is True
    assert authorization.public_redistribution_rights_approved is False
    assert authorization.public_release_authorized is False
    assert authorization.external_publication_authorized is False
    assert authorization.expected_current_detail_count == 72
    assert authorization.expected_current_document_count == 829


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("acquisition_authorized", False, "explicitly authorized"),
        ("internal_retention_authorized", False, "internal retention"),
        ("public_release_authorized", True, "internal-only"),
        (
            "public_redistribution_rights_approved",
            True,
            "remain fail closed",
        ),
        ("index_url", "https://example.test/rems", "official FDA host"),
    ],
)
def test_authorization_rejects_scope_widening(
    field: str, value: object, message: str
) -> None:
    raw = json.loads(AUTHORIZATION.read_text(encoding="utf-8"))
    raw[field] = value
    with pytest.raises(ValidationError, match=message):
        FDARemsAuthorization.model_validate(raw)


def test_inventory_parsers_preserve_relationships_and_reject_conflicts() -> (
    None
):
    details = parse_current_detail_inventory(
        _index(), base_url=AnyHttpUrl(BASE)
    )
    assert [item.rems_id for item in details] == ["1", "2"]
    documents = parse_document_inventory(
        (detail, _detail(detail.rems_id)) for detail in details
    )
    assert len(documents) == 3
    shared = next(
        item for item in documents if str(item.url).endswith("shared.pdf")
    )
    assert shared.rems_ids == ("1", "2")
    assert shared.titles == ("Shared document",)

    conflicting = _index() + (
        b'<a href="/scripts/cder/rems/index.cfm?event=RemsDetails.page&REMS=1">'
        b"Conflict</a>"
    )
    with pytest.raises(ValueError, match="conflicting detail"):
        parse_current_detail_inventory(conflicting, base_url=AnyHttpUrl(BASE))


def test_runner_archives_every_mocked_surface_and_keeps_publication_fail_closed(
    tmp_path: Path,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        query = request.url.query.decode()
        if request.url.path.endswith(".pdf"):
            return httpx.Response(
                200,
                content=b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF\n",
                headers={"content-type": "application/pdf"},
            )
        if not query:
            return httpx.Response(
                200, content=_index(), headers={"content-type": "text/html"}
            )
        if query == "event=RemsData.page":
            return httpx.Response(
                200,
                content=b"<html>REMS data definitions</html>",
                headers={"content-type": "text/html"},
            )
        if query.startswith("event=csv"):
            return httpx.Response(
                200,
                content=_csv(query),
                headers={"content-type": "text/csv"},
            )
        if "RemsDetails.page" in query:
            rems_id = request.url.params["REMS"]
            return httpx.Response(
                200,
                content=_detail(rems_id),
                headers={"content-type": "text/html"},
            )
        raise AssertionError(f"unexpected request: {request.url}")

    output = tmp_path / "output"
    manifest = exercise_fda_rems(
        repository_root=ROOT,
        output_dir=output,
        authorization_path=_authorization(tmp_path),
        transport=httpx.MockTransport(handler),
        observed_at=datetime(2026, 8, 21, tzinfo=UTC),
    )
    assert manifest.current_detail_inventory_count == 2
    assert manifest.current_document_inventory_count == 3
    assert manifest.document_succeeded_count == 3
    assert manifest.document_failed_count == 0
    assert manifest.surface_count == 11
    assert manifest.succeeded_count == 11
    assert manifest.failed_count == 0
    assert manifest.accepted_count == 10
    assert manifest.quarantined_count == 1
    assert manifest.recovered_count == 10
    assert manifest.parsed_source_record_count == 4
    assert manifest.source_record_projection_count == 4
    assert manifest.recovered_source_record_projection_count == 4
    assert manifest.source_record_parquet_pairs_byte_identical == 4
    assert manifest.public_redistribution_rights_approved is False
    assert manifest.prompt_complete is False
    assert (output / "fda-rems-live.private.tar").is_file()
    assert (
        (output / "SHA256SUMS").read_text().startswith(manifest.archive_sha256)
    )


def test_runner_rejects_document_retry_outside_inventory(
    tmp_path: Path,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        query = request.url.query.decode()
        if not query:
            payload, media = _index(), "text/html"
        elif query == "event=RemsData.page":
            payload, media = b"<html>data</html>", "text/html"
        elif query.startswith("event=csv"):
            payload, media = _csv(query), "text/csv"
        else:
            payload, media = _detail(request.url.params["REMS"]), "text/html"
        return httpx.Response(
            200, content=payload, headers={"content-type": media}
        )

    with pytest.raises(ValueError, match="retry scope"):
        exercise_fda_rems(
            repository_root=ROOT,
            output_dir=tmp_path / "unsafe-retry",
            authorization_path=_authorization(tmp_path),
            transport=httpx.MockTransport(handler),
            observed_at=datetime(2026, 8, 21, tzinfo=UTC),
            document_urls=frozenset({
                "https://www.accessdata.fda.gov/other.pdf"
            }),
        )
