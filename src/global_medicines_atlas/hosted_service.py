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
from urllib.parse import parse_qs

import duckdb
import httpx
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .columnar import temporal_assertions_to_arrow
from .coverage import coverage_to_arrow
from .fda_action_evidence import reviewed_action_mappings
from .orange_book_events import SHA256 as ORANGE_SHA
from .orange_book_events import URI as ORANGE_URI
from .orange_book_events import product_events
from .serving import MINIMUM_CURSOR_SECRET_BYTES
from .serving import create_app as configured_app
from .submission_events import project_submission_events
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
MAX_SUBMISSION_OFFSET = 100_000
MAX_SUBMISSION_PAGE = 100
MAX_SUBMISSION_QUERY_BYTES = 512


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


def download_orange_book(expected_bytes: int) -> bytes:
    """Bound the response while streaming, then verify its immutable digest."""
    if not 0 < expected_bytes <= MAX_BYTES:
        raise ValueError("Orange Book admission size exceeds bound")
    chunks: list[bytes] = []
    count = 0
    with httpx.stream(
        "GET", ORANGE_URI, follow_redirects=True, timeout=60
    ) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            count += len(chunk)
            if count > expected_bytes:
                raise ValueError("Orange Book payload exceeds admitted size")
            chunks.append(chunk)
    archive = b"".join(chunks)
    if (
        count != expected_bytes
        or hashlib.sha256(archive).hexdigest() != ORANGE_SHA
    ):
        raise ValueError("Orange Book payload differs")
    return archive


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


def materialize_approval_events(
    destination: Path, events: list[dict[str, Any]]
) -> dict[str, int]:
    """Persist source-native events and account for every catalogue product."""
    qualifications = {
        "exact_product_approval_date",
        "non_exact_native_date",
        "conflicting_dates",
        "unmatched",
    }
    if any(event["qualification"] not in qualifications for event in events):
        raise ValueError("unrecognised approval-event qualification")
    if len({event["concept_id"] for event in events}) != len(events):
        raise ValueError("duplicate approval-event concept")
    if any(
        (event["qualification"] == "exact_product_approval_date")
        != (event["approval_date"] is not None)
        for event in events
    ):
        raise ValueError("approval-event exact date differs from qualification")
    if any(
        event.get("approval_before_date") is not None
        and (
            event["qualification"] != "non_exact_native_date"
            or event["approval_before_date"] != "1982-01-01"
        )
        for event in events
    ):
        raise ValueError("approval-event bound differs from qualification")
    rows = [
        (
            event["concept_id"],
            event["qualification"],
            event["approval_date"],
            event.get("approval_before_date"),
            json.dumps(event, sort_keys=True),
        )
        for event in events
    ]
    with duckdb.connect(str(destination)) as connection:
        catalogue_count = connection.execute(
            "SELECT count(*) FROM medicine_concepts"
        ).fetchall()[0][0]
        if catalogue_count != len(rows):
            raise ValueError(
                "approval-event denominator differs from catalogue"
            )
        connection.execute(
            "CREATE TABLE product_approval_events (concept_id VARCHAR PRIMARY KEY, qualification VARCHAR NOT NULL, approval_date DATE, approval_before_date_exclusive DATE, evidence_json VARCHAR NOT NULL)"
        )
        connection.executemany(
            "INSERT INTO product_approval_events VALUES (?, ?, ?, ?, ?)", rows
        )
        missing = connection.execute(
            "SELECT count(*) FROM medicine_concepts c LEFT JOIN product_approval_events e ON c.concept_id = e.concept_id WHERE e.concept_id IS NULL"
        ).fetchall()[0][0]
        if missing:
            raise ValueError("approval-event identities differ from catalogue")
        counts = dict(
            connection.execute(
                "SELECT qualification, count(*) FROM product_approval_events GROUP BY qualification"
            ).fetchall()
        )
    return {state: counts.get(state, 0) for state in sorted(qualifications)}


def materialize_submission_events(
    destination: Path, events: list[dict[str, Any]]
) -> None:
    """Persist source-native application events without creating status intervals."""
    rows = [
        (
            event["source_path"],
            event["application_number"],
            event["application_ordinal"],
            event["submission_ordinal"],
            event["submission_status_date"],
            json.dumps(event, sort_keys=True),
        )
        for event in events
    ]
    if len({row[0] for row in rows}) != len(rows):
        raise ValueError("duplicate submission event source path")
    with duckdb.connect(str(destination)) as connection:
        connection.execute(
            "CREATE TABLE application_submission_events (source_path VARCHAR PRIMARY KEY, application_number VARCHAR NOT NULL, application_ordinal INTEGER NOT NULL, submission_ordinal INTEGER NOT NULL, status_date DATE, evidence_json VARCHAR NOT NULL)"
        )
        if rows:
            connection.executemany(
                "INSERT INTO application_submission_events VALUES (?, ?, ?, ?, ?, ?)",
                rows,
            )
        count = connection.execute(
            "SELECT count(*) FROM application_submission_events"
        ).fetchall()[0][0]
        if count != len(events):
            raise ValueError("submission event database count differs")


def submission_page(database: Path, query: bytes) -> dict[str, Any]:
    """Read a bounded page of application-level source events."""
    if len(query) > MAX_SUBMISSION_QUERY_BYTES:
        raise ValueError("submission query too long")
    params = parse_qs(
        query.decode("ascii"), keep_blank_values=True, max_num_fields=3
    )
    if set(params) - {"offset", "limit", "application_number"} or any(
        len(v) != 1 for v in params.values()
    ):
        raise ValueError("invalid query parameters")
    offset = int(params.get("offset", ["0"])[0])
    limit = int(params.get("limit", ["50"])[0])
    application = params.get("application_number", [""])[0]
    if (
        not 0 <= offset <= MAX_SUBMISSION_OFFSET
        or not 1 <= limit <= MAX_SUBMISSION_PAGE
        or (
            application
            and not re.fullmatch(r"(?:NDA|ANDA|BLA)\d{6}", application)
        )
    ):
        raise ValueError("invalid bounded submission query")
    with duckdb.connect(str(database), read_only=True) as connection:
        count = connection.execute(
            "SELECT count(*) FROM application_submission_events WHERE (? = '' OR application_number = ?)",
            [application, application],
        ).fetchall()[0][0]
        records = connection.execute(
            "SELECT evidence_json FROM application_submission_events WHERE (? = '' OR application_number = ?) ORDER BY application_ordinal, submission_ordinal LIMIT ? OFFSET ?",
            [application, application, limit, offset],
        ).fetchall()
    return {
        "scope": "Historical application-submission source records; not product approval or continuing regulatory status.",
        "offset": offset,
        "limit": limit,
        "total": count,
        "next_offset": offset + len(records)
        if offset + len(records) < count
        else None,
        "events": [json.loads(record[0]) for record in records],
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
    orange = [e for e in entries if e["source_id"] == "us-fda-orange-book"]
    if (
        len(orange) != 1
        or orange[0].get("admission_state") != "accepted"
        or orange[0].get("payload_sha256") != ORANGE_SHA
    ):
        raise ValueError("Orange Book admission differs")
    archive = download_orange_book(orange[0]["payload_byte_count"])
    _, products = catalogue(payload)
    events = product_events(archive, {p[0] for p in products})
    receipt["approval_event_coverage"] = materialize_approval_events(
        destination, events
    )
    submission_events, submission_summary = project_submission_events(
        payload,
        source_uri=BASE + "data/us-openfda-drugsfda.json",
        source_revision=REVISION,
        source_sha256=PAYLOAD_SHA,
    )
    if (
        submission_summary["application_denominator"]
        != receipt["application_count"]
    ):
        raise ValueError("submission application denominator differs")
    materialize_submission_events(destination, submission_events)
    receipt["submission_event_summary"] = submission_summary
    reviewed = reviewed_action_mappings(payload)
    with duckdb.connect(str(destination)) as connection:
        connection.execute(
            "CREATE TABLE reviewed_product_actions (concept_id VARCHAR PRIMARY KEY, evidence_json VARCHAR NOT NULL)"
        )
        if reviewed:
            connection.executemany(
                "INSERT INTO reviewed_product_actions VALUES (?, ?)",
                [
                    (item["concept_id"], json.dumps(item, sort_keys=True))
                    for item in reviewed
                ],
            )
    receipt["reviewed_action_mapping_count"] = len(reviewed)
    receipt["approval_events"] = events
    receipt["approval_event_summary"] = {
        "source_id": "us-fda-orange-book",
        "matched_exact_date_count": sum(
            e["qualification"] == "exact_product_approval_date" for e in events
        ),
        "bounded_before_1982_count": sum(
            e["approval_before_date"] == "1982-01-01" for e in events
        ),
        "catalogue_product_denominator": len(events),
        "historical_rights_state": orange[0]["rights_state"],
        "effective_rights_state": "permitted",
        "superseding_review": "quality/qualifications/source-rights-review-ledger.json#us-fda-orange-book",
        "event_only": True,
        "continuing_approval_established": False,
    }
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
    receipt.pop("approval_events", None)
    receipt["application_commit"] = commit
    receipt["python_version"] = platform.python_version()
    application = configured_app(
        database_path=str(database.resolve()), cursor_secret=secret
    )

    async def scoped(scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] == "http"
            and scope["path"] == "/reviewed-product-actions.json"
        ):
            if scope["method"] != "GET":
                await JSONResponse(
                    {"detail": "Method not allowed"},
                    status_code=405,
                    headers={"Allow": "GET"},
                )(scope, receive, send)
            else:
                with duckdb.connect(
                    str(database), read_only=True
                ) as connection:
                    rows = connection.execute(
                        "SELECT evidence_json FROM reviewed_product_actions ORDER BY concept_id"
                    ).fetchall()
                await JSONResponse({
                    "application_commit": commit,
                    "scope": "Reviewed historical product actions; no continuing status is asserted.",
                    "events": [json.loads(row[0]) for row in rows],
                })(scope, receive, send)
            return
        if (
            scope["type"] == "http"
            and scope["path"] == "/submission-events.json"
        ):
            if scope["method"] != "GET":
                await JSONResponse(
                    {"detail": "Method not allowed"},
                    status_code=405,
                    headers={"Allow": "GET"},
                )(scope, receive, send)
                return
            try:
                result = submission_page(
                    database, scope.get("query_string", b"")
                )
            except ValueError:
                await JSONResponse(
                    {"detail": "Invalid bounded submission query"},
                    status_code=400,
                )(scope, receive, send)
                return
            result["application_commit"] = commit
            await JSONResponse(result)(scope, receive, send)
            return
        if scope["type"] == "http" and scope["path"] == "/approval-events.json":
            with duckdb.connect(str(database), read_only=True) as connection:
                records = connection.execute(
                    "SELECT evidence_json FROM product_approval_events ORDER BY concept_id"
                ).fetchall()
            events = [json.loads(record[0]) for record in records]
            await JSONResponse({
                "application_commit": commit,
                "events": events,
                "scope": "Product approval dates only; not continuing approval or funding evidence",
            })(scope, receive, send)
            return
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
                    b'<p role="note">Historical FDA catalogue candidate. Regulatory, funding and temporal evidence remain unqualified. <a href="/deployment.json">Scope and provenance</a>. <a href="/approval-events.json">Product approval-date evidence</a> (historical events only, not current status). <a href="/submission-events.json">Application-submission source events</a>.</p></header>',
                    1,
                )
            await send(message)

        await application(scope, receive, banner)

    return scoped
