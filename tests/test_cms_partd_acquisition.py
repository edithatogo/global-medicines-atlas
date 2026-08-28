"""Tests for the fail-closed CMS Medicare Part D inventory."""

from __future__ import annotations

import json
import zipfile
from hashlib import sha256
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, ValidationError

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
