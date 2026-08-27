"""Tests for the fail-closed CMS Medicare Part D inventory."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest
from pydantic import ValidationError

from global_medicines_atlas.cms_partd_acquisition import (
    CMSPartDAuthorization,
    parse_cms_partd_inventory,
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
