"""Contracts for complete internal FDA FAERS quarterly acquisition."""

from __future__ import annotations

import io
import json
import re
import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from global_medicines_atlas.faers_acquisition import (
    FAERSAuthorization,
    discover_faers_ascii_releases,
    exercise_faers_history,
)

ROOT = Path(__file__).resolve().parents[1]
AUTHORIZATION = ROOT / "quality/qualifications/faers-live-authorization.json"


def _authorization() -> dict[str, Any]:
    return json.loads(AUTHORIZATION.read_text(encoding="utf-8"))


def _zip(quarter: str) -> bytes:
    output = io.BytesIO()
    suffix = quarter.replace("-", "").replace("20", "", 1)
    with zipfile.ZipFile(output, "w") as archive:
        for prefix, header, row in (
            ("DEMO", "PRIMARYID$CASEID$CASEVERSION", "1$10$2"),
            ("DRUG", "PRIMARYID$DRUG_SEQ$DRUGNAME", "1$1$NATIVE"),
            ("INDI", "PRIMARYID$DRUG_SEQ$INDI_PT", "1$1$PAIN"),
            ("OUTC", "PRIMARYID$OUTC_COD", "1$OT"),
            ("REAC", "PRIMARYID$PT", "1$HEADACHE"),
            ("RPSR", "PRIMARYID$RPSR_COD", "1$MD"),
            ("THER", "PRIMARYID$DRUG_SEQ$START_DT", "1$1$20260101"),
        ):
            archive.writestr(
                f"ASCII/{prefix}{suffix}.txt", f"{header}\n{row}\n"
            )
        archive.writestr("README.docx", b"documentation")
    return output.getvalue()


def _index(first: str, last: str) -> bytes:
    def ordinal(value: str) -> int:
        year, quarter = value.split("-Q")
        return int(year) * 4 + int(quarter) - 1

    links: list[str] = []
    for value in range(ordinal(first), ordinal(last) + 1):
        year, offset = divmod(value, 4)
        quarter = offset + 1
        stem = "aers" if (year, quarter) < (2012, 4) else "faers"
        links.append(
            f'<a href="https://fis.fda.gov/content/Exports/'
            f'{stem}_ascii_{year}q{quarter}.zip">ASCII</a>'
        )
    return "\n".join(links).encode()


def test_authorization_is_exact_bounded_and_private_only() -> None:
    authorization = FAERSAuthorization.model_validate_json(
        AUTHORIZATION.read_bytes()
    )

    assert authorization.acquisition_authorized is True
    assert authorization.internal_retention_authorized is True
    assert authorization.public_release_authorized is False
    assert authorization.external_publication_authorized is False
    assert authorization.expected_first_release == "2004-Q1"
    assert authorization.expected_last_release == "2026-Q2"
    assert authorization.expected_release_count == 90


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("acquisition_authorized", False, "explicitly authorized"),
        ("internal_retention_authorized", False, "retention"),
        ("public_release_authorized", True, "internal-only"),
        ("external_publication_authorized", True, "internal-only"),
        ("expected_release_count", 89, "contiguous quarter count"),
    ],
)
def test_authorization_fails_closed_on_scope_drift(
    field: str, value: object, message: str
) -> None:
    payload = _authorization()
    payload[field] = value
    with pytest.raises(ValidationError, match=message):
        FAERSAuthorization.model_validate(payload)


def test_authorization_rejects_unofficial_duplicate_or_undiscoverable_docs() -> (
    None
):
    unofficial = _authorization()
    unofficial["documentation"][0]["url"] = "https://example.test/index"
    with pytest.raises(ValidationError, match="official FDA host"):
        FAERSAuthorization.model_validate(unofficial)

    duplicate = _authorization()
    duplicate["documentation"][1]["document_id"] = duplicate["documentation"][
        0
    ]["document_id"]
    with pytest.raises(ValidationError, match="IDs must be unique"):
        FAERSAuthorization.model_validate(duplicate)

    undiscoverable = _authorization()
    for document in undiscoverable["documentation"]:
        document["discover_releases"] = False
    with pytest.raises(ValidationError, match="must discover releases"):
        FAERSAuthorization.model_validate(undiscoverable)


def test_authorization_rejects_release_bound_or_identity_drift() -> None:
    release_bound = _authorization()
    release_bound["max_releases"] = 91
    with pytest.raises(ValidationError, match="max releases"):
        FAERSAuthorization.model_validate(release_bound)

    invalid_identity = _authorization()
    invalid_identity["expected_first_release"] = "not-a-quarter"
    with pytest.raises(ValidationError, match="release identity"):
        FAERSAuthorization.model_validate(invalid_identity)


def test_discovery_deduplicates_and_requires_contiguous_official_ascii() -> (
    None
):
    payload = (
        _index("2004-Q1", "2004-Q2")
        + b"""
    <a href="https://fis.fda.gov/content/Exports/aers_ascii_2004q1.zip">duplicate</a>
    <a href="https://example.com/faers_ascii_2004q3.zip">wrong host</a>
    <a href="https://fis.fda.gov/content/Exports/aers_sgml_2004q3.zip">alternate</a>
    """
    )

    releases = discover_faers_ascii_releases(payload)

    assert [item.release_id for item in releases] == ["2004-Q1", "2004-Q2"]
    assert all(item.representation == "ascii" for item in releases)


def test_runner_acquires_by_verified_ranges_lands_recovers_and_archives(
    tmp_path: Path,
) -> None:
    auth = _authorization()
    auth.update(
        expected_first_release="2026-Q1",
        expected_last_release="2026-Q2",
        expected_release_count=2,
        max_releases=2,
        max_total_bytes=1024 * 1024,
        range_chunk_bytes=128,
    )
    authorization = tmp_path / "authorization.json"
    authorization.write_text(json.dumps(auth), encoding="utf-8")
    index = _index("2026-Q1", "2026-Q2")
    archives = {
        "2026-Q1": _zip("2026-Q1"),
        "2026-Q2": _zip("2026-Q2"),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("FPD-QDE-FAERS.html"):
            return httpx.Response(
                200, content=index, headers={"content-type": "text/html"}
            )
        if request.url.host == "www.fda.gov":
            return httpx.Response(
                200,
                content=b"<html>documentation</html>",
                headers={"content-type": "text/html"},
            )
        match = re.search(r"(20\d{2})q([1-4])", request.url.path, re.IGNORECASE)
        assert match is not None
        release_id = f"{match.group(1)}-Q{match.group(2)}"
        payload = archives[release_id]
        range_header = request.headers.get("range")
        assert range_header is not None
        start_text, end_text = range_header.removeprefix("bytes=").split("-")
        start = int(start_text)
        end = min(int(end_text), len(payload) - 1)
        content = payload[start : end + 1]
        return httpx.Response(
            206,
            content=content,
            headers={
                "content-type": "application/zip",
                "content-range": f"bytes {start}-{end}/{len(payload)}",
                "content-length": str(len(content)),
                "last-modified": "Thu, 30 Jul 2026 20:59:44 GMT",
            },
        )

    output = tmp_path / "output"
    manifest = exercise_faers_history(
        repository_root=ROOT,
        output_dir=output,
        authorization_path=authorization,
        transport=httpx.MockTransport(handler),
        observed_at=datetime(2026, 8, 21, tzinfo=UTC),
    )

    assert manifest.release_count == 2
    assert manifest.succeeded_count == 4
    assert manifest.failed_count == 0
    assert manifest.accepted_count + manifest.quarantined_count == 4
    assert all(
        item.admission_state == "accepted"
        for item in manifest.items
        if item.kind == "quarterly_release"
    )
    assert manifest.recovered_count == manifest.accepted_count
    assert manifest.source_record_projection_count == 2
    assert manifest.source_record_rows == 14
    assert manifest.recovered_source_record_projection_count == 2
    assert manifest.source_record_parquet_pairs_byte_identical == 2
    assert manifest.quarter_coverage_complete is True
    assert manifest.external_publication_performed is False
    assert (output / "faers-history.private.tar").is_file()
    assert (
        (output / "SHA256SUMS").read_text().startswith(manifest.archive_sha256)
    )

    with pytest.raises(FileExistsError, match="finalized"):
        exercise_faers_history(
            repository_root=ROOT,
            output_dir=output,
            authorization_path=authorization,
            transport=httpx.MockTransport(handler),
            observed_at=datetime(2026, 8, 22, tzinfo=UTC),
            resume=True,
        )

    repaired_item = next(
        item
        for item in manifest.items
        if item.item_id == "2026-Q2" and item.acquisition_id is not None
    )
    product = (
        output
        / "runs/corpus/bronze/parquet/us-fda-faers"
        / repaired_item.acquisition_id
        / "source_records.parquet"
    )
    product.unlink()
    shutil.rmtree(output / "runs/corpus/clean-room")
    for filename in (
        "faers-history.private.tar",
        "faers-history.manifest.json",
        "SHA256SUMS",
    ):
        (output / filename).unlink()

    resumed = exercise_faers_history(
        repository_root=ROOT,
        output_dir=output,
        authorization_path=authorization,
        transport=httpx.MockTransport(
            lambda _: pytest.fail("resume must not reacquire retained payloads")
        ),
        observed_at=datetime(2026, 8, 22, tzinfo=UTC),
        resume=True,
    )

    assert resumed.release_count == 2
    assert resumed.source_record_projection_count == 2
    assert resumed.source_record_parquet_pairs_byte_identical == 2
    assert product.is_file()


def test_runner_rejects_inventory_gap_before_release_download(
    tmp_path: Path,
) -> None:
    auth = _authorization()
    auth.update(
        expected_first_release="2026-Q1",
        expected_last_release="2026-Q2",
        expected_release_count=2,
        max_releases=2,
    )
    authorization = tmp_path / "authorization.json"
    authorization.write_text(json.dumps(auth), encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("FPD-QDE-FAERS.html"):
            return httpx.Response(
                200,
                content=_index("2026-Q1", "2026-Q1"),
                headers={"content-type": "text/html"},
            )
        return httpx.Response(
            200,
            content=b"<html>documentation</html>",
            headers={"content-type": "text/html"},
        )

    with pytest.raises(ValueError, match="inventory does not match"):
        exercise_faers_history(
            repository_root=ROOT,
            output_dir=tmp_path / "output",
            authorization_path=authorization,
            transport=httpx.MockTransport(handler),
            observed_at=datetime(2026, 8, 21, tzinfo=UTC),
        )


def test_runner_rejects_nonempty_output_and_naive_time(tmp_path: Path) -> None:
    nonempty = tmp_path / "nonempty"
    nonempty.mkdir()
    (nonempty / "preserved.txt").write_text("do not overwrite")
    with pytest.raises(FileExistsError, match="must be empty"):
        exercise_faers_history(
            repository_root=ROOT,
            output_dir=nonempty,
            authorization_path=AUTHORIZATION,
        )
    assert (nonempty / "preserved.txt").read_text() == "do not overwrite"

    with pytest.raises(ValueError, match="timezone-aware"):
        exercise_faers_history(
            repository_root=ROOT,
            output_dir=tmp_path / "naive-time",
            authorization_path=AUTHORIZATION,
            observed_at=datetime(2026, 8, 21, tzinfo=UTC).replace(tzinfo=None),
        )
