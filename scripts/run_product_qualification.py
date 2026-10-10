"""Execute fixture product qualification and emit atomic durable receipts."""
# ruff: file-ignore[module-import-not-at-top-of-file]

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from statistics import quantiles
from time import perf_counter_ns
from typing import TYPE_CHECKING, Literal, cast
from unittest.mock import patch

# Support direct repository-root execution before the package is installed.
ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

import duckdb
from fastapi.testclient import TestClient
from typer.testing import CliRunner

if TYPE_CHECKING:
    from httpx import Response

if __package__:
    from scripts.qualify_product_release import build_evidence
else:
    from qualify_product_release import build_evidence

from global_medicines_atlas.api import create_app
from global_medicines_atlas.atlas import create_atlas_app
from global_medicines_atlas.cli import app as cli_app
from global_medicines_atlas.historical_change import (
    HistoricalChangePage,
    HistoricalChangeService,
    compare_historical_snapshots,
)
from global_medicines_atlas.historical_change_configuration import (
    HistoricalChangeDocument,
    load_historical_change_service,
)
from global_medicines_atlas.historical_comparison import (
    NativeField,
    NativeRow,
    NativeSnapshot,
)
from global_medicines_atlas.product_contracts import (
    ComparisonQuery,
    EvidenceDimension,
)
from global_medicines_atlas.product_release import (
    QualificationReceipt,
    ReceiptResult,
    create_qualification_receipt,
)
from global_medicines_atlas.query_service import (
    InvalidCursorError,
    InvalidDatabaseError,
    QueryServiceError,
    ReadOnlyQueryService,
)

NOW = datetime(2026, 7, 29, tzinfo=UTC)
SECRET = b"product-qualification-secret"
SAMPLES = 20
METHOD_NOT_ALLOWED = 405
HTTP_OK = 200
CLEAN_START_ROWS = 3
IMPLEMENTATION_FILES = (
    "scripts/qualify_product_release.py",
    "scripts/run_product_qualification.py",
    ".python-version",
    "pixi.lock",
    "pixi.toml",
    "pylock.toml",
    "pyproject.toml",
    "uv.lock",
)
IMPLEMENTATION_TREES = (
    ("src/global_medicines_atlas", "*.py"),
    ("src/global_medicines_atlas/templates", "*"),
    ("src/global_medicines_atlas/static", "*"),
    ("schemas", "*.json"),
)


def implementation_manifest(root: Path = ROOT) -> tuple[str, ...]:
    """Return the stable, source-only manifest governing qualification."""
    paths: set[str] = set(IMPLEMENTATION_FILES)
    for directory, pattern in IMPLEMENTATION_TREES:
        base = root / directory
        if not base.is_dir():
            raise FileNotFoundError(
                f"qualification manifest directory missing: {directory}"
            )
        paths.update(
            path.relative_to(root).as_posix()
            for path in base.rglob(pattern)
            # hatch-vcs generates this ignored file during builds; it is not
            # part of the committed runtime implementation.
            if path.is_file() and path.name != "_version.py"
        )
    missing = sorted(path for path in paths if not (root / path).is_file())
    if missing:
        raise FileNotFoundError(
            f"qualification manifest files missing: {missing}"
        )
    return tuple(sorted(paths))


def implementation_digest(
    root: Path = ROOT,
    *,
    manifest: Iterable[str] | None = None,
) -> str:
    """Digest a path-framed manifest without build products or secret state."""
    digest = sha256()
    digest.update(b"global-medicines-atlas-product-qualification-manifest-v1\0")
    entries = tuple(sorted(manifest or implementation_manifest(root)))
    if not entries:
        raise ValueError(
            "qualification implementation manifest cannot be empty"
        )
    for relative in entries:
        normalized = Path(relative).as_posix()
        if normalized.startswith("../") or Path(normalized).is_absolute():
            raise ValueError(
                f"qualification manifest path escapes root: {relative}"
            )
        payload = (root / normalized).read_bytes()
        encoded_path = normalized.encode()
        digest.update(len(encoded_path).to_bytes(8, "big"))
        digest.update(encoded_path)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def _database(path: Path) -> Path:
    connection = duckdb.connect(str(path))
    connection.execute(
        """
        CREATE TABLE temporal_assertions (
          assertion_id VARCHAR, concept_id VARCHAR, jurisdiction VARCHAR,
          kind VARCHAR, authority VARCHAR, status_code VARCHAR,
          evidence_status VARCHAR, restrictions VARCHAR[], valid_from TIMESTAMPTZ,
          valid_to TIMESTAMPTZ, observed_from TIMESTAMPTZ,
          observed_to TIMESTAMPTZ, supersedes_assertion_id VARCHAR,
          conflict_id VARCHAR, source_id VARCHAR, source_uri VARCHAR,
          retrieved_at TIMESTAMPTZ, source_effective_at TIMESTAMPTZ,
          source_path VARCHAR, source_sha256 VARCHAR, source_version VARCHAR,
          transformation VARCHAR
        );
        CREATE TABLE temporal_coverage (
          jurisdiction VARCHAR, source_id VARCHAR, receipt_id VARCHAR,
          observation_id VARCHAR, population_partition_id VARCHAR,
          dimension VARCHAR, medicine_concept_id VARCHAR,
          assertion_type VARCHAR, assertion_status VARCHAR,
          concept_population VARCHAR, valid_from TIMESTAMPTZ,
          valid_to TIMESTAMPTZ, observed_from TIMESTAMPTZ,
          observed_to TIMESTAMPTZ, assertion_count BIGINT,
          concept_numerator BIGINT, eligible_denominator BIGINT,
          exclusion_count BIGINT, exclusion_reasons VARCHAR[],
          conflicting_assertion_count BIGINT
        )
        """
    )
    rows: list[tuple[object, ...]] = [
        (
            f"a-{country}",
            "rx:fixture",
            country,
            "regulatory",
            "Authority",
            "approved",
            "confirmed",
            cast("list[str]", []),
            NOW,
            None,
            NOW,
            None,
            None,
            None,
            "fixture",
            "https://example.test/evidence",
            NOW,
            None,
            None,
            None,
            "1",
            "qualification",
        )
        for country in ("AU", "NZ", "US")
    ]
    connection.executemany(
        "INSERT INTO temporal_assertions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    connection.close()
    return path


def _query(
    *,
    limit: int = 3,
    cursor: str | None = None,
    concept: str = "rx:fixture",
) -> ComparisonQuery:
    return ComparisonQuery(
        concept_id=concept,
        jurisdictions=("AU", "NZ", "US"),
        dimensions=(EvidenceDimension.REGULATORY,),
        valid_at=NOW,
        observed_at=NOW,
        limit=limit,
        cursor=cursor,
    )


def _synthetic_history(root: Path):
    """Create one deterministic synthetic historical change in the clean root."""
    snapshots = tuple(
        NativeSnapshot(
            source_id="synthetic:clean-start",
            table="items",
            dimension="funding",
            schema_era="synthetic-v1",
            identity_profile="synthetic-item-id",
            source_revision=revision,
            source_path="fixture/items.json",
            b1_sha256=sha256(f"receipt:{revision}".encode()).hexdigest(),
            b2_sha256=sha256(f"payload:{revision}".encode()).hexdigest(),
            observed_at=NOW,
            cohort="synthetic",
            declared_rows=1,
            complete=True,
            rows=(
                NativeRow(
                    native_id="item-1",
                    occurrence_id=f"{revision}:item-1",
                    fields=(
                        NativeField(
                            name="description",
                            state="value",
                            value=value,
                        ),
                    ),
                ),
            ),
        )
        for revision, value in (
            ("synthetic-before", "before"),
            ("synthetic-after", "after"),
        )
    )
    change = compare_historical_snapshots(*snapshots)
    history_file = root / "history.json"
    history_file.write_text(
        HistoricalChangeDocument(
            version="1.0", changes=(change,)
        ).model_dump_json(),
        encoding="utf-8",
    )
    return history_file, load_historical_change_service(history_file)


def _qualify_history_api(
    service: ReadOnlyQueryService, history_service: HistoricalChangeService
) -> HistoricalChangePage:
    with TestClient(
        create_app(service, historical_changes=history_service)
    ) as client:
        response = cast(
            "Response",
            client.get(  # pyright: ignore[reportUnknownMemberType]
                "/api/v1/history", params={"limit": 1}
            ),
        )
    if response.status_code != HTTP_OK:
        raise RuntimeError("clean-start historical API query failed")
    page = HistoricalChangePage.model_validate_json(response.content)
    if page.total != 1 or len(page.items) != 1:
        raise RuntimeError("clean-start historical API result was incomplete")
    item = page.items[0]
    if (
        item.comparison_state != "compared"
        or item.absence_interpretation != "unknown"
    ):
        raise RuntimeError("clean-start historical semantics were incomplete")
    if not item.changes or item.changes[0].kind != "field_changed":
        raise RuntimeError("clean-start historical change was incomplete")
    return page


def _qualify_history_cli(
    history_file: Path, expected: HistoricalChangePage
) -> None:
    result = CliRunner().invoke(
        cli_app,
        [
            "history",
            "--history-file",
            str(history_file),
            "--limit",
            "1",
        ],
    )
    if result.exit_code != 0:
        raise RuntimeError("clean-start historical CLI query failed")
    try:
        page = HistoricalChangePage.model_validate_json(result.stdout)
    except ValueError as error:
        raise RuntimeError(
            "clean-start historical CLI query did not return valid JSON"
        ) from error
    if page != expected:
        raise RuntimeError(
            "clean-start historical CLI results did not match the API"
        )


def _qualify_history_atlas(
    service: ReadOnlyQueryService, history_service: HistoricalChangeService
) -> None:
    with TestClient(
        create_atlas_app(service, historical_changes=history_service)
    ) as client:
        response = cast(
            "Response",
            client.get("/history?limit=1"),  # pyright: ignore[reportUnknownMemberType]
        )
    if (
        response.status_code != HTTP_OK
        or "Historical comparison 1" not in response.text
        or "unknown, not a negative status" not in response.text
        or "before" not in response.text
        or "after" not in response.text
    ):
        raise RuntimeError(
            "clean-start Atlas did not render the historical change"
        )


def _p95(workload: Callable[[], object]) -> float:
    samples: list[float] = []
    for _ in range(SAMPLES):
        started = perf_counter_ns()
        workload()
        samples.append((perf_counter_ns() - started) / 1_000_000)
    return quantiles(samples, n=100, method="inclusive")[94]


def _receipt(
    kind: Literal["performance", "threat", "clean_start"],
    subject: str,
    detail: str,
    digest: str,
    *,
    observed: float | None = None,
) -> QualificationReceipt:
    return create_qualification_receipt(
        receipt_id=f"{kind}-{subject.lower()}-{digest[:12]}",
        kind=kind,
        subject_id=subject,
        executed_at=datetime.now(UTC),
        implementation_digest=digest,
        result=ReceiptResult(
            passed=True,
            observed_ms=observed,
            sample_size=SAMPLES if observed is not None else None,
            detail=detail,
        ),
    )


def _clean_start_receipt(digest: str) -> QualificationReceipt:
    """Verify a fresh synthetic root across API, CLI, and Atlas."""
    with tempfile.TemporaryDirectory(prefix="gma-product-clean-start-") as raw:
        root = Path(raw)
        if any(root.iterdir()):
            raise RuntimeError("clean-start root was not empty")
        database = _database(root / "atlas.duckdb")
        service = ReadOnlyQueryService(
            database, cursor_secret=SECRET, allowed_root=root
        )
        history_file, history_service = _synthetic_history(root)
        service.readiness_probe()
        direct = service.comparisons(_query())
        if len(direct.conclusions) != CLEAN_START_ROWS:
            raise RuntimeError("clean-start fixture query was incomplete")

        with TestClient(create_app(service)) as client:
            readiness = cast(
                "Response",
                client.get(  # pyright: ignore[reportUnknownMemberType]
                    "/api/v1/readiness"
                ),
            )
            response = cast(
                "Response",
                client.get(  # pyright: ignore[reportUnknownMemberType]
                    "/api/v1/comparisons",
                    params={
                        "concept_id": "rx:fixture",
                        "jurisdictions": ["AU", "NZ", "US"],
                        "dimensions": ["regulatory"],
                        "valid_at": NOW.isoformat(),
                        "observed_at": NOW.isoformat(),
                        "limit": 3,
                    },
                ),
            )
        if readiness.status_code != HTTP_OK or response.status_code != HTTP_OK:
            raise RuntimeError("clean-start API did not become ready")
        api_result = response.json()
        if len(api_result.get("conclusions", [])) != CLEAN_START_ROWS:
            raise RuntimeError("clean-start API query was incomplete")
        history_api_page = _qualify_history_api(service, history_service)

        cli_arguments = [
            "comparison",
            "--database",
            str(database),
            "--allowed-root",
            str(root),
            "--concept-id",
            "rx:fixture",
            "--jurisdiction",
            "AU",
            "--jurisdiction",
            "NZ",
            "--jurisdiction",
            "US",
            "--valid-at",
            NOW.isoformat(),
            "--observed-at",
            NOW.isoformat(),
            "--dimension",
            "regulatory",
            "--limit",
            str(CLEAN_START_ROWS),
        ]
        with patch.dict(
            os.environ, {"GMA_CURSOR_SECRET": SECRET.decode("utf-8")}
        ):
            cli = CliRunner().invoke(cli_app, cli_arguments)
        if cli.exit_code != 0:
            raise RuntimeError("clean-start CLI comparison failed")
        try:
            cli_result = json.loads(cli.stdout)
        except json.JSONDecodeError as error:
            raise RuntimeError(
                "clean-start CLI comparison did not return JSON"
            ) from error
        if (
            cli_result.get("conclusions") != api_result.get("conclusions")
            or cli_result.get("validity") != api_result.get("validity")
            or cli_result.get("metadata", {}).get("page")
            != api_result.get("metadata", {}).get("page")
        ):
            raise RuntimeError(
                "clean-start CLI comparison did not match the API"
            )

        _qualify_history_cli(history_file, history_api_page)

        with TestClient(create_atlas_app(service)) as client:
            atlas = cast(
                "Response",
                client.get("/"),  # pyright: ignore[reportUnknownMemberType]
            )
        if (
            atlas.status_code != HTTP_OK
            or "Global Medicines Atlas" not in atlas.text
        ):
            raise RuntimeError("clean-start Atlas did not render")
        _qualify_history_atlas(service, history_service)

    return _receipt(
        "clean_start",
        "CLEAN-START",
        "Fresh temporary synthetic database passed readiness and bounded API "
        "comparison. CLI comparison matched the API; historical API/CLI "
        "results matched, and Atlas rendered the historical change with unknown "
        "absence semantics. No live deployment or production data was exercised.",
        digest,
    )


def _performance_receipts(
    service: ReadOnlyQueryService, digest: str
) -> list[QualificationReceipt]:
    checks = (
        (
            "PERF-CONTRACT",
            25.0,
            lambda: ComparisonQuery.model_validate(_query().model_dump()),
        ),
        ("PERF-QUERY", 250.0, lambda: service.comparisons(_query())),
        ("PERF-EXPORT-PAGE", 1000.0, lambda: _traverse(service)),
    )
    receipts: list[QualificationReceipt] = []
    for subject, budget, workload in checks:
        observed = _p95(workload)
        if observed > budget:
            raise RuntimeError(
                f"{subject} observed p95 {observed:.3f} ms exceeded "
                f"its {budget:.1f} ms budget"
            )
        receipts.append(
            _receipt(
                "performance",
                subject,
                f"observed p95 {observed:.3f} ms against {budget:.1f} ms budget",
                digest,
                observed=observed,
            )
        )
    return receipts


def _threat_receipts(
    service: ReadOnlyQueryService,
    database: Path,
    work: Path,
    digest: str,
) -> list[QualificationReceipt]:
    receipts: list[QualificationReceipt] = []
    outside = work.parent / "outside.duckdb"
    _database(outside)
    try:
        ReadOnlyQueryService(outside, cursor_secret=SECRET, allowed_root=work)
    except InvalidDatabaseError:
        receipts.append(
            _receipt("threat", "THREAT-001", "path escape rejected", digest)
        )
    finally:
        outside.unlink(missing_ok=True)

    cursor = service.comparisons(_query(limit=1)).metadata.page.next_cursor
    if cursor is None:
        raise RuntimeError("fixture did not produce a pagination cursor")
    attempts = (
        (cursor[:-1] + ("A" if cursor[-1] != "A" else "B"), "rx:fixture"),
        (cursor, "rx:other"),
    )
    rejected = 0
    for token, concept in attempts:
        try:
            service.comparisons(_query(limit=1, cursor=token, concept=concept))
        except InvalidCursorError:
            rejected += 1
    if rejected != len(attempts):
        raise RuntimeError("cursor tamper/replay was not rejected")
    receipts.append(
        _receipt(
            "threat",
            "THREAT-002",
            "tamper and cross-query replay rejected",
            digest,
        )
    )

    mutation_response = cast(
        "Response",
        TestClient(create_app(service)).post(  # pyright: ignore[reportUnknownMemberType]
            "/api/v1/comparisons"
        ),
    )
    if mutation_response.status_code != METHOD_NOT_ALLOWED:
        raise RuntimeError("mutation method was accepted")
    receipts.append(
        _receipt(
            "threat", "THREAT-003", "POST mutation method rejected", digest
        )
    )

    hostile = "<script>alert(1)</script>"
    atlas_response = cast(
        "Response",
        TestClient(create_atlas_app(service)).get(  # pyright: ignore[reportUnknownMemberType]
            "/", params={"concept_id": hostile}
        ),
    )
    html = atlas_response.text
    if hostile in html or "&lt;script&gt;" not in html:
        raise RuntimeError("hostile HTML was not escaped")
    receipts.append(
        _receipt("threat", "THREAT-004", "script content escaped", digest)
    )

    database.unlink()
    try:
        service.readiness_probe()
    except QueryServiceError:
        receipts.append(
            _receipt(
                "threat",
                "THREAT-005",
                "missing database failed closed",
                digest,
            )
        )
    else:
        raise RuntimeError("missing database remained ready")
    return receipts


def run(output: Path, receipts_dir: Path) -> None:
    digest = implementation_digest()
    with tempfile.TemporaryDirectory(
        prefix="gma-product-qualification-"
    ) as raw:
        work = Path(raw)
        database = _database(work / "atlas.duckdb")
        service = ReadOnlyQueryService(
            database, cursor_secret=SECRET, allowed_root=work
        )
        receipts = [_clean_start_receipt(digest)]
        receipts.extend(_performance_receipts(service, digest))
        receipts.extend(_threat_receipts(service, database, work, digest))

        staged = work / "receipts"
        staged.mkdir()
        for receipt in receipts:
            (staged / f"{receipt.subject_id}.json").write_text(
                receipt.model_dump_json(indent=2) + "\n", encoding="utf-8"
            )
        evidence = build_evidence(
            receipts_dir=staged,
            implementation_digest=digest,
            now=datetime.now(UTC),
        )
        if (
            not evidence.gates["performance_budgets_verified"]
            or not evidence.gates["abuse_cases_verified"]
        ):
            raise RuntimeError(
                "executed receipts did not qualify fixture gates"
            )
        receipts_dir.mkdir(parents=True, exist_ok=True)
        output.parent.mkdir(parents=True, exist_ok=True)
        for source in staged.glob("*.json"):
            source.replace(receipts_dir / source.name)
        temporary_output = output.with_suffix(output.suffix + ".tmp")
        temporary_output.write_bytes(evidence.canonical_json())
        temporary_output.replace(output)


def _traverse(service: ReadOnlyQueryService) -> int:
    cursor: str | None = None
    count = 0
    while True:
        response = service.comparisons(_query(limit=1, cursor=cursor))
        count += len(response.conclusions)
        cursor = response.metadata.page.next_cursor
        if cursor is None:
            return count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipts", type=Path)
    args = parser.parse_args()
    output = args.output
    receipts = args.receipts
    if receipts is None:
        receipts = output / "receipts"
        output /= "evidence.json"
    run(output, receipts)
    print(
        json.dumps(
            {"evidence": str(output), "receipts": str(receipts)}, sort_keys=True
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
