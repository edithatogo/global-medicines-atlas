"""Main-Actions-only anonymous qualification of one pinned public PBS archive."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any, cast
from urllib.parse import urljoin, urlsplit

import httpx

from .acquisition import AcquisitionPolicy, BoundIPAddressTransport
from .adapters.au_pbs import read_pbs_v3_member
from .pbs_historical_qualification import qualify_pbs_historical_projections
from .pbs_member_identity import build_pbs_xml_member_binding
from .receipts import SourceReceipt

DATASET = "edithatogo/australian-pbs-source-archive"
REVISION = "31ec854ef9fc82f30a0dbe743fdf50a2e5bd24a7"
INFO_URL = f"https://huggingface.co/api/datasets/{DATASET}/revision/{REVISION}"
HOSTS = ("huggingface.co", "us.aws.cdn.hf.co")
MAX_REPORT_BYTES = 48_000


@dataclass(frozen=True)
class PinnedFile:
    """Reviewed file bytes in the already-public immutable archive revision."""

    path: str
    sha256: str
    byte_count: int


MANIFEST = PinnedFile(
    "manifest.json",
    "e6c9abbc62bd44fc47049306a92cc8efc9700031908586262c2b82a907546460",
    7513,
)
RECEIPT = PinnedFile(
    "bronze/2026-04-01/source-receipt.json",
    "a5eb06cf7e655eb0e0d8fe5d244297721ebede51e96c237333f7dffd76e1ccd1",
    3143,
)
ARCHIVE = PinnedFile(
    "raw/2026-04-01/2026-04-01-XML-V3.zip",
    "f3e7af3610637b85577d0518ef50d3be9e692888e9acd3b5897d313706365c20",
    11156706,
)
MEMBER = PinnedFile(
    "bronze/2026-04-01/sch-2026-04-01-r1.xml",
    "73d34185fe6ae7fd9a788a68448e20934b38553d42361117faa96cdb07f54f43",
    313437585,
)
MEMBER_SOURCE_PATH = "sch-2026-04-01-r1.xml"


def file_url(pin: PinnedFile) -> str:
    """Return the immutable public location for a fixed reviewed input."""
    return f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/{pin.path}"


def _context(exact_commit: str) -> dict[str, str]:
    expected = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": "edithatogo/global-medicines-atlas",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_SHA": exact_commit,
    }
    if (
        any(os.environ.get(key) != value for key, value in expected.items())
        or re.fullmatch(r"[0-9a-f]{40}", exact_commit) is None
        or re.fullmatch(r"[1-9][0-9]*", os.environ.get("GITHUB_RUN_ID", ""))
        is None
        or re.fullmatch(
            r"[1-9][0-9]*", os.environ.get("GITHUB_RUN_ATTEMPT", "")
        )
        is None
    ):
        raise ValueError(
            "PBS qualification requires exact main Actions context"
        )
    return {
        "workflow_commit": exact_commit,
        "run_id": os.environ["GITHUB_RUN_ID"],
        "run_attempt": os.environ["GITHUB_RUN_ATTEMPT"],
    }


def _safe_url(url: str, initial: str) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in HOSTS
        or parsed.username is not None
        or parsed.port not in {None, 443}
        or parsed.fragment
    ):
        raise ValueError("unapproved anonymous PBS destination")
    if parsed.hostname == "huggingface.co":
        initial_path = urlsplit(initial).path
        cache_path = initial_path.replace(
            f"/datasets/{DATASET}/resolve/{REVISION}/",
            f"/api/resolve-cache/datasets/{DATASET}/{REVISION}/",
        )
        if parsed.path not in {initial_path, cache_path} or (
            parsed.query
            and any(
                part.split("=", 1)[0] not in {"download", "etag"}
                for part in parsed.query.split("&")
            )
        ):
            raise ValueError("mutable or unrelated PBS redirect")


def _read(client: httpx.Client, url: str, limit: int, deadline: float) -> bytes:
    initial = url
    for _ in range(4):
        _safe_url(url, initial)
        if time.monotonic() > deadline:
            raise ValueError("PBS retrieval deadline exceeded")
        client.cookies.clear()
        with client.stream("GET", url) as response:
            if response.is_redirect:
                location = response.headers.get("location")
                if location is None:
                    raise ValueError("PBS redirect missing location")
                url = urljoin(url, location)
                continue
            if response.status_code != HTTPStatus.OK:
                raise ValueError("anonymous PBS retrieval failed")
            if (
                response.headers.get("content-encoding", "identity")
                != "identity"
            ):
                raise ValueError("PBS content encoding must be identity")
            data = bytearray()
            for chunk in response.iter_bytes(64 * 1024):
                if len(data) + len(chunk) > limit:
                    raise ValueError("PBS retrieval exceeds byte limit")
                if time.monotonic() > deadline:
                    raise ValueError("PBS retrieval deadline exceeded")
                data.extend(chunk)
            return bytes(data)
    raise ValueError("PBS redirect limit exceeded")


def _file(client: httpx.Client, pin: PinnedFile, deadline: float) -> bytes:
    data = _read(client, file_url(pin), pin.byte_count, deadline)
    if (
        len(data) != pin.byte_count
        or hashlib.sha256(data).hexdigest() != pin.sha256
    ):
        raise ValueError("PBS pinned file digest/size mismatch")
    return data


def _public(client: httpx.Client, deadline: float) -> None:
    raw: object = json.loads(_read(client, INFO_URL, 1024 * 1024, deadline))
    if not isinstance(raw, dict):
        raise TypeError("PBS exact public revision required")
    info = cast("dict[str, Any]", raw)
    if (
        info.get("id") != DATASET
        or info.get("sha") != REVISION
        or info.get("private") is not False
        or info.get("gated") is not False
    ):
        raise ValueError("PBS exact public revision required")


def run_hosted_qualification(
    exact_commit: str, *, transport: httpx.BaseTransport | None = None
) -> dict[str, Any]:
    """Fetch only pinned metadata and ZIP anonymously on exact main Actions.

    Original B1 is restored, never recreated or relabelled. Extracted XML must
    match the existing public member digest/size/path. Reuse bounded DNS-pinned
    transport and permit only observed public Hub/CDN hosts; no implicit tokens,
    cookies, proxies, mutable revisions or unrestricted redirects. The transport
    hook is for synthetic tests; it cannot bypass context/URL/digest validation.
    Return bounded aggregate metadata only, not bytes, sample text or signed URLs.
    This does not publish datasets, select dates or establish semantic admission.
    """
    context = _context(exact_commit)
    started_at = datetime.now(UTC).isoformat()
    deadline = time.monotonic() + 300
    policy = AcquisitionPolicy(allowed_hosts=HOSTS, timeout_seconds=30)
    with httpx.Client(
        transport=transport or BoundIPAddressTransport(policy=policy),
        trust_env=False,
        follow_redirects=False,
        timeout=30,
        headers={"Accept-Encoding": "identity"},
    ) as client:
        try:
            _public(client, deadline)
            manifest = json.loads(_file(client, MANIFEST, deadline))
            receipt_bytes = _file(client, RECEIPT, deadline)
            archive = _file(client, ARCHIVE, deadline)
            _public(client, deadline)
        except httpx.HTTPError:
            raise ValueError("anonymous PBS transport failed") from None
    for name, pin in (
        ("archive", ARCHIVE),
        ("member", MEMBER),
        ("source_receipt", RECEIPT),
    ):
        entry = manifest[name]
        if (
            entry["path"] != pin.path
            or entry["sha256"] != pin.sha256
            or (
                name != "source_receipt"
                and entry["size_bytes"] != pin.byte_count
            )
        ):
            raise ValueError("PBS manifest pin mismatch")
    if (
        manifest["source_id"] != "au-pbs-historical-xml"
        or manifest["destination_dataset"] != DATASET
        or manifest["member"]["source_path"] != MEMBER_SOURCE_PATH
    ):
        raise ValueError("PBS manifest source identity mismatch")
    parent = SourceReceipt.model_validate_json(receipt_bytes)
    member, xml = read_pbs_v3_member(archive)
    if (
        member.path != MEMBER_SOURCE_PATH
        or member.sha256 != MEMBER.sha256
        or member.size_bytes != MEMBER.byte_count
    ):
        raise ValueError("PBS extracted member pin mismatch")
    binding = build_pbs_xml_member_binding(archive, parent)
    qualification = qualify_pbs_historical_projections(
        archive, xml, parent, binding
    )
    report = {
        "schema_version": 1,
        "status": "passed",
        **context,
        "dataset": DATASET,
        "revision": REVISION,
        "manifest_sha256": MANIFEST.sha256,
        "source_receipt_file_sha256": RECEIPT.sha256,
        "archive_path": ARCHIVE.path,
        "member_path": MEMBER.path,
        "member_retrieval": "extracted-from-verified-archive",
        "anonymous_public_checks": 2,
        "qualification": qualification,
        "publication_performed": False,
        "retrieval_started_at": started_at,
        "qualification_completed_at": datetime.now(UTC).isoformat(),
        "run_url": f"https://github.com/edithatogo/global-medicines-atlas/actions/runs/{context['run_id']}",
        "public_objects": {
            name: asdict(pin)
            for name, pin in (
                ("manifest", MANIFEST),
                ("source_receipt", RECEIPT),
                ("archive", ARCHIVE),
                ("member", MEMBER),
            )
        },
        "source_publication_receipt": "https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-5466488482",
    }
    if len(json.dumps(report, sort_keys=True).encode()) > MAX_REPORT_BYTES:
        raise ValueError("PBS aggregate report exceeds byte limit")
    return report


def failure_report() -> dict[str, Any]:
    """Return a bounded failure receipt without exception text or unsafe env."""
    context = {}
    for name, key, pattern in (
        ("workflow_commit", "GITHUB_SHA", r"[0-9a-f]{40}"),
        ("run_id", "GITHUB_RUN_ID", r"[1-9][0-9]*"),
        ("run_attempt", "GITHUB_RUN_ATTEMPT", r"[1-9][0-9]*"),
    ):
        value = os.environ.get(key, "")
        context[name] = value if re.fullmatch(pattern, value) else "unavailable"
    return {
        "schema_version": 1,
        "status": "failed",
        **context,
        "dataset": DATASET,
        "revision": REVISION,
        "reason": "qualification-did-not-complete",
        "publication_performed": False,
    }
