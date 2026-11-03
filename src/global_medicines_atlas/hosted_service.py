"""Rebuild a bounded, historical FDA discovery cache on a hosted runner.

The source contains application action dates, not reviewed product validity intervals. No temporal regulatory, funding or
formulary assertions are invented to populate the existing comparison service.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import duckdb
import httpx
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .columnar import temporal_assertions_to_arrow
from .coverage import coverage_to_arrow
from .serving import MINIMUM_CURSOR_SECRET_BYTES
from .serving import create_app as configured_app
from .terminology import normalize_name

REVISION = "9476e7894ed60a603ec9542d7f438d12c5eca726"
DATASET = "edithatogo/global-medicines-atlas-fda-public"
BASE = f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/"
PAYLOAD_SHA = "10c7a53e09494d2f5682e7e2ff2c9309cc3281c63d44c5a322a94c2d0958165f"
ADMISSION_SHA = (
    "494955cd39d346c629423b151925b0e655050e4e4764008df3c33322a6608ed5"
)
SOURCE = "us-openfda-drugsfda"
MAX_BYTES = 2 * 1024 * 1024


def verified_download(member: str, expected: str) -> bytes:
    """Read only an exact pinned public member, without any account token."""
    if member not in {
        "data/us-openfda-drugsfda.json",
        "acquisition-admission-receipts.json",
    }:
        raise ValueError("unapproved archive member")
    response = httpx.get(BASE + member, follow_redirects=True, timeout=60)
    response.raise_for_status()
    data = response.content
    if len(data) > MAX_BYTES or hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("archive member size or digest differs")
    return data


def catalogue(payload: bytes) -> tuple[int, list[tuple[str, str, str]]]:
    """Preserve explicit application/product identities and names only."""
    document = json.loads(payload)
    applications = document["results"]
    if not isinstance(applications, list) or not applications:
        raise ValueError("source applications must be a nonempty list")
    typed_applications = cast("list[dict[str, Any]]", applications)
    products: dict[str, tuple[str, str, str]] = {}
    for application in typed_applications:
        number = application["application_number"]
        if not isinstance(number, str) or not number.strip():
            raise ValueError("missing native application identity")
        for product in application.get("products", []):
            native = product.get("product_number")
            name = product.get("brand_name")
            if not isinstance(native, str) or not native.strip():
                raise ValueError("missing native product identity")
            if not isinstance(name, str) or not name.strip():
                raise ValueError("missing source-native product name")
            identity = f"us-drugsfda:{number}:{native}"
            row = (identity, name, number)
            if identity in products:
                raise ValueError("duplicate native product identity")
            products[identity] = row
    if not products:
        raise ValueError("source has no named products")
    return len(typed_applications), [products[k] for k in sorted(products)]


def prepare_database(destination: Path, payload: bytes) -> dict[str, Any]:
    """Build a disposable catalogue; unknown temporal evidence stays absent."""
    if destination.exists():
        raise ValueError("refuse to overwrite an existing database")
    applications, products = catalogue(payload)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(destination)) as connection:
        connection.register("assertions", temporal_assertions_to_arrow(()))
        connection.register("coverage", coverage_to_arrow(()))
        connection.execute(
            "CREATE TABLE temporal_assertions AS SELECT * FROM assertions"
        )
        connection.execute(
            "CREATE TABLE temporal_coverage AS SELECT * FROM coverage"
        )
        connection.execute("""
            CREATE TABLE medicine_concepts (
                concept_id VARCHAR, preferred_name VARCHAR, concept_type VARCHAR);
            CREATE TABLE medicine_names (
                concept_id VARCHAR, name VARCHAR, name_type VARCHAR, normalized_name VARCHAR);
            CREATE TABLE medicine_identifiers (
                concept_id VARCHAR, identifier_system VARCHAR, identifier_value VARCHAR);
            CREATE TABLE medicine_concept_jurisdictions (
                concept_id VARCHAR, jurisdiction VARCHAR);
            CREATE TABLE medicine_sources (
                source_id VARCHAR, jurisdiction VARCHAR, authority VARCHAR,
                regulatory_system VARCHAR, funding_system VARCHAR);
        """)
        connection.executemany(
            "INSERT INTO medicine_concepts VALUES (?, ?, 'product')",
            [(identity, name) for identity, name, _ in products],
        )
        connection.executemany(
            "INSERT INTO medicine_names VALUES (?, ?, 'source_native', ?)",
            [
                (identity, name, normalize_name(name))
                for identity, name, _ in products
            ],
        )
        connection.executemany(
            "INSERT INTO medicine_identifiers VALUES (?, 'https://www.fda.gov/drugsatfda/application', ?)",
            [(identity, number) for identity, _, number in products],
        )
        connection.executemany(
            "INSERT INTO medicine_concept_jurisdictions VALUES (?, 'US')",
            [(identity,) for identity, _, _ in products],
        )
        connection.execute(
            "INSERT INTO medicine_sources VALUES (?, 'US', 'US Food and Drug Administration', 'Drugs@FDA', NULL)",
            [SOURCE],
        )
    return {
        "dataset": DATASET,
        "revision": REVISION,
        "source_id": SOURCE,
        "jurisdiction": "US",
        "source_uri": BASE + "data/us-openfda-drugsfda.json",
        "source_sha256": hashlib.sha256(payload).hexdigest(),
        "archive_scope": "bounded 2026-08-21 historical snapshot",
        "application_count": applications,
        "product_count": len(products),
        "canary_concept_id": products[0][0],
        "global_population_denominator": None,
        "coverage_complete": False,
        "synthetic_data": False,
        "production_data_qualified": False,
        "temporal_assertion_count": 0,
        "blockers": [
            "Product-level validity intervals and application-to-product action mappings remain unqualified; native submission action dates must not be treated as continuing approval"
        ],
    }


def prepare_hosted(destination: Path) -> dict[str, Any]:
    """Check the original admission before downloading the permitted payload."""
    entries = json.loads(
        verified_download("acquisition-admission-receipts.json", ADMISSION_SHA)
    )
    selected = [entry for entry in entries if entry["source_id"] == SOURCE]
    if len(selected) != 1:
        raise ValueError("ambiguous source admission")
    entry = selected[0]
    required = {
        "admission_state": "accepted",
        "rights_state": "permitted",
        "source_records_projected": True,
        "payload_sha256": PAYLOAD_SHA,
        "source_record_count": 100,
    }
    if any(entry.get(k) != v for k, v in required.items()):
        raise ValueError("source admission does not permit this projection")
    payload = verified_download("data/us-openfda-drugsfda.json", PAYLOAD_SHA)
    if len(payload) != entry["payload_byte_count"]:
        raise ValueError("payload byte count differs")
    receipt = prepare_database(destination, payload)
    if receipt["application_count"] != entry["source_record_count"]:
        raise ValueError("application denominator differs")
    return receipt


def create_app() -> ASGIApp:
    """Run the existing read-only service with an explicit scope banner."""
    secret = os.environ.get("GMA_CURSOR_SECRET") or os.environ.get(
        "SPACE_SIGNING_SECRET"
    )
    if not secret or len(secret.encode()) < MINIMUM_CURSOR_SECRET_BYTES:
        raise ValueError("platform signing secret unavailable")
    commit = os.environ.get("GMA_APPLICATION_COMMIT", "")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("exact application commit unavailable")
    root = Path(os.environ.get("GMA_HOSTED_CACHE", tempfile.gettempdir()))
    root.mkdir(parents=True, exist_ok=True)
    database = (
        Path(tempfile.mkdtemp(prefix="boot-", dir=root)) / "catalogue.duckdb"
    )
    receipt = prepare_hosted(database)
    receipt["application_commit"] = commit
    receipt["python_version"] = platform.python_version()
    application = configured_app(
        database_path=str(database.resolve()), cursor_secret=secret
    )

    async def scoped(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"] == "/deployment.json":
            await JSONResponse(receipt)(scope, receive, send)
            return

        chunks: list[bytes] = []

        async def banner(message: Message) -> None:
            if (
                scope.get("path") == "/"
                and message["type"] == "http.response.start"
            ):
                message["headers"] = [
                    (k, v)
                    for k, v in message["headers"]
                    if k.lower() != b"content-length"
                ]
            if (
                scope.get("path") == "/"
                and message["type"] == "http.response.body"
            ):
                chunks.append(message.get("body", b""))
                if message.get("more_body", False):
                    return
                message["body"] = b"".join(chunks).replace(
                    b"</header>",
                    b'<p role="note">Historical FDA catalogue candidate. Regulatory, funding and temporal evidence remain unqualified. <a href="/deployment.json">Scope and provenance</a></p></header>',
                    1,
                )
            await send(message)

        await application(scope, receive, banner)

    return scoped
