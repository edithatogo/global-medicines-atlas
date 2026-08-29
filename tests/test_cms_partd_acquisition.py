"""Tests for the fail-closed CMS Medicare Part D inventory."""

from __future__ import annotations

import json
import stat
import zipfile
import zlib
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from pydantic import AnyHttpUrl, ValidationError
from scripts.qualify_cms_partd_shard import qualify_shard

from global_medicines_atlas import cms_partd_acquisition as cms
from global_medicines_atlas.cms_partd_acquisition import (
    CMSPartDAuthorization,
    inspect_cms_partd_payload,
    parse_cms_partd_inventory,
    recover_cms_partd_private_archive,
    write_cms_partd_private_archive,
)

AUTHORIZATION = (
    Path(__file__).resolve().parents[1]
    / "quality/qualifications/cms-partd-acquisition-authorization.json"
)
WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github/workflows/cms-partd-publication.yml"
)
SPENDING_URLS = (
    "https://data.cms.gov/data-api/v1/dataset/7e0b4365-fd63-4a29-8f5e-e0ac9f66a81b/data",
    "https://data.cms.gov/data-api/v1/dataset/da5ff50b-e5da-42de-b68b-6cfac1f64f35/data",
    "https://data.cms.gov/sites/default/files/2026-06/98218f98-166c-4723-8438-c344a4ef96a6/DSD_PTD_RY26_P04_V10_DY24_BGM.csv",
)


def _digest(urls: tuple[str, ...]) -> str:
    return sha256(("\n".join(sorted(urls)) + "\n").encode()).hexdigest()


def _authorization(**updates: object) -> CMSPartDAuthorization:
    raw = json.loads(AUTHORIZATION.read_text(encoding="utf-8"))
    raw.update(updates)
    return CMSPartDAuthorization.model_validate(raw)


def _catalog(urls: tuple[str, ...], *, license_url: str | None = None) -> bytes:
    dataset = {
        "@context": "https://schema.org/",
        "@type": "Dataset",
        "license": license_url or "https://www.usa.gov/government-works",
        "distribution": [
            {
                "@type": "DataDownload",
                "contentUrl": url,
                "encodingFormat": (
                    "application/zip" if url.endswith(".zip") else "text/csv"
                ),
            }
            for url in urls
        ],
    }
    return (
        '<html>ordinary text<script type="application/ld+json">'
        + json.dumps(dataset)
        + "</script></html>"
    ).encode()


def _formulary_urls(count: int = 30) -> tuple[str, ...]:
    return tuple(
        "https://data.cms.gov/sites/default/files/2026-07/"
        f"00000000-0000-4000-8000-{index:012d}/SPUF_2026_{index:08d}.zip"
        for index in range(count)
    )


def test_inventory_binds_both_public_resource_families() -> None:
    formulary = _formulary_urls()
    authorization = _authorization(
        expected_formulary_url_set_sha256=_digest(formulary)
    )
    inventory = parse_cms_partd_inventory(
        _catalog(formulary),
        _catalog(SPENDING_URLS),
        authorization=authorization,
    )
    assert inventory.formulary_release_count == 30
    assert inventory.spending_resource_count == 3
    assert (
        sum(str(url).endswith(".csv") for url in inventory.spending_urls) == 1
    )
    authorization.require_payload_authority()
    authorization.require_publication_authority()


def test_cms_publication_is_hosted_public_and_anonymously_verified() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert "private=False" in workflow
    assert "CommitOperationDelete" in workflow
    assert "Invalidate stale CMS Part D completion markers" in workflow
    assert "'bronze/qualification.json'" in workflow
    assert "'state': 'public'" in workflow
    assert "'state': 'staged_private'" not in workflow
    assert "needs: [inventory, finalize]" in workflow
    assert "Restore anonymously and verify digest" in workflow
    assert "--output receipt.json" in workflow
    assert "expected=$(jq -r '.sha256' receipt.json)" in workflow
    assert '"$observed" != "$expected"' in workflow
    assert "public-verification.json" in workflow
    assert "anonymous_digest_match" in workflow
    assert "HfApi().dataset_info" in workflow
    assert "max-parallel: 8" in workflow
    assert "max-parallel: 16" in workflow
    assert "Qualify hosted Bronze shard" in workflow
    assert "CommitOperationAdd" in workflow
    assert "max(r['qualified_at'] for r in shard_reports)" in workflow
    assert "already_published" in workflow
    assert "public_receipt['sha256'] == receipt['sha256']" in workflow
    assert "receipt = public_receipt" in workflow
    assert "path.startswith('bronze/shards/')" in workflow
    assert "bronze/shards/{os.environ['SOURCE_IDENTITY']}" not in workflow


def test_cms_shard_qualification_projects_and_recovers(tmp_path: Path) -> None:
    payload = tmp_path / "release.zip"
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("formulary.csv", b"plan_id,ndc\nP1,0001\n")
    url = AnyHttpUrl(_formulary_urls(1)[0])
    identity = sha256(str(url).encode()).hexdigest()
    output = tmp_path / "qualified"
    report = qualify_shard(
        payload,
        url=url,
        family="formulary",
        identity=identity,
        hub_path=f"data/formulary/{identity}/release.zip",
        expected_sha256=sha256(payload.read_bytes()).hexdigest(),
        output=output,
        qualified_at=datetime(2026, 8, 29, tzinfo=UTC),
    )
    assert report["clean_room_recovered_payload_count"] == 1
    assert report["archive_member_count"] == 1
    assert (output / "payload-manifest.parquet").is_file()
    assert (output / "archive-members.parquet").is_file()
    assert (output / "qualification.json").is_file()
    assert not report["source_bytes_retained_on_runner"]


def test_cms_spending_shard_emits_typed_empty_member_manifest(
    tmp_path: Path,
) -> None:
    payload = tmp_path / "spending.csv"
    payload.write_bytes(b"Brnd_Name,Tot_Spndng_2024\nExample,1.25\n")
    url = AnyHttpUrl(SPENDING_URLS[-1])
    identity = sha256(str(url).encode()).hexdigest()
    output = tmp_path / "qualified"
    report = qualify_shard(
        payload,
        url=url,
        family="spending",
        identity=identity,
        hub_path=f"data/spending/{identity}/spending.csv",
        expected_sha256=sha256(payload.read_bytes()).hexdigest(),
        output=output,
        qualified_at=datetime(2026, 8, 29, tzinfo=UTC),
    )
    assert report["archive_member_count"] == 0
    members = pq.read_table(output / "archive-members.parquet")
    assert members.num_rows == 0
    assert members.schema.field("byte_count").type == pa.int64()


def test_configured_spending_inventory_matches_current_official_resources() -> (
    None
):
    authorization = _authorization()
    assert (
        _digest(SPENDING_URLS) == authorization.expected_spending_url_set_sha256
    )
    assert authorization.expected_formulary_url_set_sha256 == (
        "d960c4e537dfab9f7c078e8953e5e70ee69c5a26e48141585a38cb6369deeb8f"
    )


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"acquisition_authorized": True}, "pending CMS Part D decision"),
        ({"public_release_authorized": True}, "pending CMS Part D decision"),
        ({"agreement_url": "https://example.test/terms"}, "official hosts"),
        ({"license_url": "https://example.test/license"}, "licence identity"),
    ],
)
def test_authorization_rejects_scope_widening(
    updates: dict[str, object], message: str
) -> None:
    raw = json.loads(AUTHORIZATION.read_text(encoding="utf-8"))
    raw.update({
        "decision_status": "pending",
        "decision_date": None,
        "acquisition_authorized": False,
        "internal_retention_authorized": False,
        "public_release_authorized": False,
        "external_publication_authorized": False,
        **updates,
    })
    with pytest.raises(ValidationError, match=message):
        CMSPartDAuthorization.model_validate(raw)


def test_approved_internal_scope_requires_date_and_retention() -> None:
    approved = _authorization(
        decision_status="approved_internal",
        decision_date="2026-08-21",
        acquisition_authorized=True,
        internal_retention_authorized=True,
        public_release_authorized=False,
        external_publication_authorized=False,
    )
    approved.require_payload_authority()
    with pytest.raises(PermissionError, match="publication is not authorized"):
        approved.require_publication_authority()
    with pytest.raises(ValidationError, match="requires dated authority"):
        _authorization(
            decision_status="approved_internal",
            decision_date=None,
            acquisition_authorized=True,
            internal_retention_authorized=True,
            public_release_authorized=False,
            external_publication_authorized=False,
        )


def test_approved_public_scope_requires_every_authority() -> None:
    approved = _authorization(
        decision_status="approved_public",
        decision_date="2026-08-27",
        acquisition_authorized=True,
        internal_retention_authorized=True,
        public_release_authorized=True,
        external_publication_authorized=True,
    )
    approved.require_payload_authority()
    approved.require_publication_authority()
    with pytest.raises(ValidationError, match="approved public CMS Part D"):
        _authorization(
            decision_status="approved_public",
            decision_date="2026-08-27",
            acquisition_authorized=True,
            internal_retention_authorized=True,
            public_release_authorized=True,
            external_publication_authorized=False,
        )


def test_pending_scope_cannot_acquire_payloads() -> None:
    pending = _authorization(
        decision_status="pending",
        decision_date=None,
        acquisition_authorized=False,
        internal_retention_authorized=False,
        public_release_authorized=False,
        external_publication_authorized=False,
    )
    with pytest.raises(
        PermissionError, match="acquisition decision is pending"
    ):
        pending.require_payload_authority()


@pytest.mark.parametrize(
    ("formulary", "spending", "message"),
    [
        (_formulary_urls(29), SPENDING_URLS, "formulary release inventory"),
        (
            _formulary_urls(),
            (
                *SPENDING_URLS[:-1],
                "https://data.cms.gov/sites/default/files/extra.json",
            ),
            "spending resource inventory",
        ),
        (
            (
                *_formulary_urls()[:-1],
                "https://data.cms.gov/sites/default/files/not-a-zip.csv",
            ),
            SPENDING_URLS,
            "formulary inventory must contain ZIP",
        ),
    ],
)
def test_inventory_rejects_resource_drift(
    formulary: tuple[str, ...], spending: tuple[str, ...], message: str
) -> None:
    updates: dict[str, object] = {}
    if len(formulary) == 30:
        updates["expected_formulary_url_set_sha256"] = _digest(formulary)
    if spending == SPENDING_URLS:
        updates["expected_spending_url_set_sha256"] = _digest(spending)
    authorization = _authorization(**updates)
    with pytest.raises(ValueError, match=message):
        parse_cms_partd_inventory(
            _catalog(formulary), _catalog(spending), authorization=authorization
        )


def test_spending_inventory_requires_one_csv_after_identity_validation() -> (
    None
):
    formulary = _formulary_urls()
    spending = (
        *SPENDING_URLS[:2],
        "https://data.cms.gov/data-api/v1/dataset/extra/data",
    )
    authorization = _authorization(
        expected_formulary_url_set_sha256=_digest(formulary),
        expected_spending_url_set_sha256=_digest(spending),
    )
    with pytest.raises(ValueError, match="must contain one CSV"):
        parse_cms_partd_inventory(
            _catalog(formulary), _catalog(spending), authorization=authorization
        )


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b"<html></html>", "expected one"),
        (
            b'<script type="application/ld+json">[]</script>',
            "expected one",
        ),
        (
            _catalog(SPENDING_URLS, license_url="https://example.test/license"),
            "licence drifted",
        ),
        (
            _catalog(("https://example.test/file.zip",)),
            "must stay on data.cms.gov",
        ),
    ],
)
def test_catalog_parser_fails_closed(payload: bytes, message: str) -> None:
    formulary = _formulary_urls()
    authorization = _authorization(
        expected_formulary_url_set_sha256=_digest(formulary)
    )
    with pytest.raises(ValueError, match=message):
        parse_cms_partd_inventory(
            payload, _catalog(SPENDING_URLS), authorization=authorization
        )


def test_streaming_payload_evidence_preserves_archive_members(
    tmp_path: Path,
) -> None:
    path = tmp_path / "release.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("formulary.csv", b"plan_id,ndc\nP1,0001\n")
        archive.writestr("pricing.csv", b"plan_id,cost\nP1,1.25\n")
    evidence = inspect_cms_partd_payload(
        path,
        url=AnyHttpUrl(_formulary_urls(1)[0]),
        family="formulary",
    )
    assert evidence.byte_count == path.stat().st_size
    assert evidence.sha256 == sha256(path.read_bytes()).hexdigest()
    assert [member.path for member in evidence.archive_members] == [
        "formulary.csv",
        "pricing.csv",
    ]
    assert (
        evidence.archive_members[0].sha256
        == sha256(b"plan_id,ndc\nP1,0001\n").hexdigest()
    )


@pytest.mark.parametrize(
    "member", ["../escape.csv", "/absolute.csv", "C:/x.csv"]
)
def test_streaming_payload_evidence_rejects_unsafe_members(
    tmp_path: Path, member: str
) -> None:
    path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(member, b"unsafe")
    with pytest.raises(ValueError, match="unsafe member path"):
        inspect_cms_partd_payload(
            path, url=AnyHttpUrl(_formulary_urls(1)[0]), family="formulary"
        )


def test_streaming_payload_evidence_rejects_duplicate_and_empty_archives(
    tmp_path: Path,
) -> None:
    duplicate = tmp_path / "duplicate.zip"
    with zipfile.ZipFile(duplicate, "w") as archive:
        archive.writestr("same.csv", b"first")
        archive.writestr("same.csv", b"second")
    with pytest.raises(ValueError, match="duplicate member paths"):
        inspect_cms_partd_payload(
            duplicate,
            url=AnyHttpUrl(_formulary_urls(1)[0]),
            family="formulary",
        )

    empty = tmp_path / "empty.zip"
    with zipfile.ZipFile(empty, "w"):
        pass
    with pytest.raises(ValueError, match="archive is empty"):
        inspect_cms_partd_payload(
            empty,
            url=AnyHttpUrl(_formulary_urls(1)[0]),
            family="formulary",
        )


def test_streaming_payload_evidence_reads_member_bytes_for_crc(
    tmp_path: Path,
) -> None:
    path = tmp_path / "corrupt.zip"
    with zipfile.ZipFile(
        path, "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        archive.writestr("formulary.csv", b"plan_id,ndc\nP1,0001\n" * 100)
    with zipfile.ZipFile(path) as archive:
        info = archive.getinfo("formulary.csv")
        offset = (
            info.header_offset
            + 30
            + len(info.filename.encode())
            + len(info.extra)
            + max(1, info.compress_size // 2)
        )
    corrupted = bytearray(path.read_bytes())
    corrupted[offset] ^= 0xFF
    path.write_bytes(corrupted)

    with pytest.raises((ValueError, zipfile.BadZipFile, zlib.error)):
        inspect_cms_partd_payload(
            path,
            url=AnyHttpUrl(_formulary_urls(1)[0]),
            family="formulary",
        )


def test_external_zip_decoder_streams_exact_member(tmp_path: Path) -> None:
    path = tmp_path / "external.zip"
    payload = b"plan_id,ndc\nP1,0001\n" * 100
    with zipfile.ZipFile(
        path, "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        archive.writestr("formulary.csv", payload)
    with zipfile.ZipFile(path) as archive:
        info = archive.getinfo("formulary.csv")
    assert (
        cms._stream_cms_zip_member_with_7z(path, info)
        == sha256(payload).hexdigest()
    )


def test_unsupported_zip_decoder_requires_archive_path() -> None:
    archive = SimpleNamespace(
        filename=None,
        open=lambda _info: (_ for _ in ()).throw(NotImplementedError),
    )
    with pytest.raises(ValueError, match="requires an archive path"):
        cms._stream_cms_zip_member(archive, SimpleNamespace())


def test_unsupported_zip_decoder_delegates_to_7z(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "deflate64.zip"
    archive = SimpleNamespace(
        filename=str(path),
        open=lambda _info: (_ for _ in ()).throw(NotImplementedError),
    )
    info = SimpleNamespace(filename="formulary.csv")
    monkeypatch.setattr(
        cms,
        "_stream_cms_zip_member_with_7z",
        lambda archive_path, member_info: (
            "delegated"
            if (archive_path, member_info) == (path, info)
            else "unexpected"
        ),
    )
    assert cms._stream_cms_zip_member(archive, info) == "delegated"


def test_external_zip_decoder_requires_7z(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cms.shutil, "which", lambda _name: None)
    with pytest.raises(ValueError, match="requires 7-Zip"):
        cms._stream_cms_zip_member_with_7z(
            tmp_path / "archive.zip",
            SimpleNamespace(filename="formulary.csv", file_size=0),
        )


@pytest.mark.parametrize(
    ("stdout", "returncode", "stderr", "file_size", "message", "killed"),
    [
        (None, 0, b"", 0, "stdout pipe", False),
        (BytesIO(b"too long"), 0, b"", 2, "exceeded declared size", True),
        (BytesIO(b"short"), 2, b"decoder failed", 5, "decoder failed", False),
        (BytesIO(b"short"), 0, b"", 6, "size diverged", False),
    ],
)
def test_external_zip_decoder_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stdout: BytesIO | None,
    returncode: int,
    stderr: bytes,
    file_size: int,
    message: str,
    *,
    killed: bool,
) -> None:
    process = SimpleNamespace(
        stdout=stdout,
        returncode=returncode,
        killed=False,
        communicate=lambda: (b"", stderr),
    )

    def kill() -> None:
        process.killed = True

    process.kill = kill
    monkeypatch.setattr(cms.shutil, "which", lambda _name: "/usr/bin/7z")
    monkeypatch.setattr(
        cms.subprocess, "Popen", lambda *_args, **_kwargs: process
    )
    with pytest.raises((RuntimeError, ValueError), match=message):
        cms._stream_cms_zip_member_with_7z(
            tmp_path / "archive.zip",
            SimpleNamespace(filename="formulary.csv", file_size=file_size),
        )
    assert process.killed is killed


@pytest.mark.parametrize(
    ("configure", "message", "total"),
    [
        (lambda info: setattr(info, "flag_bits", 1), "encrypted", 0),
        (
            lambda info: (
                setattr(info, "create_system", 3),
                setattr(info, "external_attr", stat.S_IFLNK << 16),
            ),
            "symbolic link",
            0,
        ),
        (
            lambda info: setattr(
                info, "file_size", cms._CMS_ZIP_MAX_MEMBER_BYTES + 1
            ),
            "member byte limit",
            0,
        ),
        (
            lambda _info: None,
            "expanded byte limit",
            cms._CMS_ZIP_MAX_EXPANDED_BYTES + 1,
        ),
        (
            lambda info: (
                setattr(info, "file_size", cms._CMS_ZIP_MAX_RATIO + 1),
                setattr(info, "compress_size", 1),
            ),
            "decompression ratio",
            0,
        ),
    ],
)
def test_streaming_payload_evidence_enforces_member_limits(
    configure: Callable[[zipfile.ZipInfo], object], message: str, total: int
) -> None:
    info = zipfile.ZipInfo("member.csv")
    configure(info)
    with pytest.raises(ValueError, match=message):
        cms._validate_cms_zip_info(
            info,
            observed=set(),
            total_expanded_bytes=total,
        )


def test_streaming_payload_evidence_enforces_entry_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "release.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("member.csv", b"value")
    monkeypatch.setattr(cms, "_CMS_ZIP_MAX_ENTRIES", 0)
    with pytest.raises(ValueError, match="entry count limit"):
        inspect_cms_partd_payload(
            path,
            url=AnyHttpUrl(_formulary_urls(1)[0]),
            family="formulary",
        )


def test_private_archive_streams_and_recovers_exact_payloads(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.zip"
    second = tmp_path / "second.csv"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    archive = tmp_path / "cms.private.tar"
    digest, byte_count = write_cms_partd_private_archive(
        (("payloads/first", first), ("payloads/second", second)), archive
    )
    assert digest == sha256(archive.read_bytes()).hexdigest()
    assert byte_count == archive.stat().st_size
    recovered = recover_cms_partd_private_archive(
        archive,
        tmp_path / "clean-room",
        {
            "payloads/first": sha256(b"first").hexdigest(),
            "payloads/second": sha256(b"second").hexdigest(),
        },
    )
    assert recovered == 2


def test_private_archive_rejects_duplicate_or_unsafe_inputs(
    tmp_path: Path,
) -> None:
    payload = tmp_path / "payload"
    payload.write_bytes(b"payload")
    with pytest.raises(ValueError, match="input is invalid"):
        write_cms_partd_private_archive(
            (("payload", payload), ("payload", payload)),
            tmp_path / "duplicate.tar",
        )
    with pytest.raises(ValueError, match="unsafe member path"):
        write_cms_partd_private_archive(
            (("../payload", payload),), tmp_path / "unsafe.tar"
        )

    existing = tmp_path / "existing.tar"
    existing.write_bytes(b"already present")
    with pytest.raises(FileExistsError, match="already exists"):
        write_cms_partd_private_archive((("payload", payload),), existing)


def test_private_archive_recovery_fails_closed(tmp_path: Path) -> None:
    payload = tmp_path / "payload"
    payload.write_bytes(b"payload")
    archive = tmp_path / "corpus.tar"
    write_cms_partd_private_archive((("payload", payload),), archive)

    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "existing").write_bytes(b"existing")
    with pytest.raises(FileExistsError, match="must be empty"):
        recover_cms_partd_private_archive(
            archive, occupied, {"payload": sha256(b"payload").hexdigest()}
        )

    with pytest.raises(ValueError, match="inventory diverged"):
        recover_cms_partd_private_archive(
            archive,
            tmp_path / "wrong-inventory",
            {"different": sha256(b"payload").hexdigest()},
        )

    with pytest.raises(ValueError, match="digest diverged"):
        recover_cms_partd_private_archive(
            archive,
            tmp_path / "wrong-digest",
            {"payload": sha256(b"different").hexdigest()},
        )
