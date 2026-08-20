"""Deterministic bronze scale benchmarks and Rust-justification gates.

Identify bottlenecks with measurements before changing hot paths. Python
remains orchestration. Native OpenSSL, zlib, orjson, and pydantic-core are
not reasons to add a custom Rust crate.
"""

from __future__ import annotations

import json
import platform
import time
import zipfile
import zlib
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Any, Literal, cast

import orjson
from pydantic import AnyUrl

from .archive_safety import extract_zip
from .bronze_landing import (
    BronzeLanding,
    bronze_table_spec,
    land_bronze_payload,
    regenerate_parquet,
)
from .iceberg_ready import iceberg_rest_create_body
from .openlineage_projection import project_openlineage_event
from .receipts import (
    AcquisitionMethod,
    AcquisitionStatus,
    EvidenceClass,
    PayloadEvidence,
    RetrievalEvidence,
    RightsState,
    SourceIdentity,
    SourceReceipt,
    TransformationEvidence,
    temporal_identity_from_source,
)
from .reuse_gate import acquire_new_decision

SYNTHETIC_RETRIEVED_AT = datetime(2026, 8, 20, 6, 47, tzinfo=UTC)

FIXTURE_RELATIVE = "benchmarks/fixtures/bronze_scale.json"
BUDGETS_RELATIVE = "quality/bronze-scale-budgets.json"
MEBIBYTE = 1024 * 1024
RUST_MIN_WALL_SHARE = 0.2
RUST_MIN_SPEEDUP = 2.0
IMPLEMENTATION_OPENSSL = "openssl_c"
IMPLEMENTATION_ZLIB = "zlib_c"
IMPLEMENTATION_ZIPFILE = "cpython_zipfile_zlib"
IMPLEMENTATION_ORJSON = "orjson_rust"
IMPLEMENTATION_PYDANTIC = "pydantic_core_rust"
IMPLEMENTATION_PYTHON = "pure_python"
SHA256_HEX_LENGTH = 64


@dataclass(frozen=True, slots=True)
class SyntheticArtefacts:
    """Seeded synthetic payloads; never treated as source evidence."""

    json_payload: bytes
    csv_payload: bytes
    zip_payload: bytes


@dataclass(frozen=True, slots=True)
class StageMeasurement:
    """One timed bronze primitive or pipeline stage."""

    name: str
    elapsed_seconds: float
    wall_share: float
    implementation: str
    accelerator: str | None
    bytes_processed: int


@dataclass(frozen=True, slots=True)
class BudgetResult:
    """Pass/fail for one published bronze scale budget."""

    metric: str
    observed: float
    threshold: float
    comparison: Literal["minimum", "maximum"]
    unit: str
    passed: bool


def load_bronze_scale_fixture(path: Path) -> dict[str, Any]:
    """Load the committed synthetic scale fixture."""

    payload: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("bronze scale fixture must be a JSON object")
    return cast("dict[str, Any]", payload)


def load_bronze_scale_budgets(path: Path) -> dict[str, Any]:
    """Load published bronze scale performance budgets."""

    payload: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("bronze scale budgets must be a JSON object")
    return cast("dict[str, Any]", payload)


def generate_synthetic_artefacts(
    fixture: dict[str, Any],
    *,
    profile: str,
) -> SyntheticArtefacts:
    """Build deterministic JSON, CSV, and ZIP payloads for one profile."""

    seed = int(fixture["seed"])
    spec = _profile(fixture, profile)
    json_payload = _json_payload(int(spec["json_bytes"]), seed)
    csv_payload = _csv_payload(int(spec["csv_bytes"]), seed)
    zip_payload = _zip_payload(
        int(spec["zip_members"]),
        int(spec["zip_member_bytes"]),
        seed,
    )
    return SyntheticArtefacts(
        json_payload=json_payload,
        csv_payload=csv_payload,
        zip_payload=zip_payload,
    )


def rust_rewrite_justified(
    stage: StageMeasurement,
    *,
    speedup: float,
    min_wall_share: float = RUST_MIN_WALL_SHARE,
    min_speedup: float = RUST_MIN_SPEEDUP,
) -> bool:
    """A custom Rust crate is justified only for a hot pure-Python path."""

    if stage.implementation != IMPLEMENTATION_PYTHON:
        return False
    if stage.wall_share < min_wall_share:
        return False
    return speedup >= min_speedup


def evaluate_bronze_scale_budgets(
    observed: dict[str, float],
    budgets: dict[str, Any],
) -> tuple[BudgetResult, ...]:
    """Compare measured primitives against the published CI budgets."""

    specs: tuple[tuple[str, Literal["minimum", "maximum"], str], ...] = (
        ("pipeline_seconds", "maximum", "seconds"),
        ("hashing_mib_per_second", "minimum", "mib_per_second"),
        ("archive_inspect_seconds", "maximum", "seconds"),
        ("parquet_seconds", "maximum", "seconds"),
        ("receipt_validation_seconds", "maximum", "seconds"),
        ("lineage_seconds", "maximum", "seconds"),
        ("catalogue_ops_per_second", "minimum", "operations_per_second"),
    )
    results: list[BudgetResult] = []
    for metric, comparison, unit in specs:
        threshold = float(budgets[metric][comparison])
        value = float(observed[metric])
        passed = (
            value <= threshold
            if comparison == "maximum"
            else value >= threshold
        )
        results.append(
            BudgetResult(
                metric=metric,
                observed=value,
                threshold=threshold,
                comparison=comparison,
                unit=unit,
                passed=passed,
            )
        )
    return tuple(results)


@dataclass(frozen=True, slots=True)
class _CapturedRun:
    stages: tuple[StageMeasurement, ...]
    observed: dict[str, float]
    parse_speedup: float
    source_count: int
    json_bytes: int
    csv_bytes: int
    zip_bytes: int
    seed: int
    catalog_count: int


def run_bronze_scale(
    *,
    output_directory: Path,
    fixture_path: Path,
    budgets_path: Path,
    profile: str = "ci",
) -> dict[str, Any]:
    """Measure bronze primitives, rank bottlenecks, and persist a receipt."""

    output_directory.mkdir(parents=True, exist_ok=True)
    fixture = load_bronze_scale_fixture(fixture_path)
    budgets = load_bronze_scale_budgets(budgets_path)
    captured = _capture_run(output_directory, fixture, profile)
    evaluations = evaluate_bronze_scale_budgets(captured.observed, budgets)
    rust_candidates = _rust_candidates(
        captured.stages,
        parse_speedup=captured.parse_speedup,
        min_wall_share=float(budgets["rust_rewrite"]["min_wall_share"]),
        min_speedup=float(budgets["rust_rewrite"]["min_speedup"]),
    )
    receipt = _receipt_document(
        profile=profile,
        captured=captured,
        budgets_path=budgets_path,
        evaluations=evaluations,
        rust_candidates=rust_candidates,
    )
    encoded = orjson.dumps(
        receipt,
        option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS,
    )
    output = output_directory / "bronze-scale-receipt.json"
    output.write_bytes(encoded + b"\n")
    return cast("dict[str, Any]", orjson.loads(encoded))


def _receipt_document(
    *,
    profile: str,
    captured: _CapturedRun,
    budgets_path: Path,
    evaluations: tuple[BudgetResult, ...],
    rust_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    bottleneck = max(captured.stages, key=lambda item: item.elapsed_seconds)
    rust_justified = any(item["justified"] for item in rust_candidates)
    return {
        "schema_version": "1.0.0",
        "evidence_class": "synthetic",
        "profile": profile,
        "workload": {
            "source_count": captured.source_count,
            "seed": captured.seed,
            "catalog_source_count_observed": captured.catalog_count,
            "json_bytes": captured.json_bytes,
            "csv_bytes": captured.csv_bytes,
            "zip_bytes": captured.zip_bytes,
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "stages": [asdict(item) for item in captured.stages],
        "bottleneck": asdict(bottleneck),
        "observed": captured.observed,
        "budget_source": str(budgets_path),
        "budget_results": [asdict(item) for item in evaluations],
        "rust_candidates": rust_candidates,
        "rust_rewrite_justified": rust_justified,
        "python_remains_orchestration": True,
        "parse_json_vs_orjson_speedup": captured.parse_speedup,
        "passed": all(item.passed for item in evaluations),
    }


def _time_primitives(
    artefacts: SyntheticArtefacts,
    spec: dict[str, Any],
    output_directory: Path,
) -> tuple[tuple[float, int], float, float, tuple[float, float]]:
    hashing = _measure_hashing(
        artefacts.zip_payload,
        int(spec["hash_iterations"]),
    )
    compression = _measure_compression(artefacts.csv_payload)
    archive = _measure_archive(artefacts.zip_payload, output_directory)
    parsing = _measure_parsing(
        artefacts.json_payload,
        int(spec["parse_iterations"]),
    )
    return hashing, compression, archive, parsing


def _time_pipeline(
    artefacts: SyntheticArtefacts,
    spec: dict[str, Any],
    bronze_root: Path,
) -> tuple[
    tuple[BronzeLanding, ...], float, float, float, float, tuple[float, int]
]:
    source_count = int(spec["source_count"])
    ingest_started = time.perf_counter()
    landings = _land_sources(
        artefacts.json_payload,
        source_count=source_count,
        bronze_root=bronze_root,
    )
    ingest_seconds = time.perf_counter() - ingest_started
    parquet_started = time.perf_counter()
    for landing in landings:
        regenerate_parquet(landing)
    parquet_seconds = time.perf_counter() - parquet_started
    receipt_seconds = _measure_receipts(
        artefacts.json_payload,
        landings[0].receipt,
        int(spec["receipt_iterations"]),
    )
    lineage_seconds = _measure_lineage(landings)
    catalogue = _measure_catalogue(
        landings[0],
        int(spec["catalogue_iterations"]),
    )
    return (
        landings,
        ingest_seconds,
        parquet_seconds,
        receipt_seconds,
        lineage_seconds,
        catalogue,
    )


def _stages_from_timings(
    artefacts: SyntheticArtefacts,
    spec: dict[str, Any],
    hashing: tuple[float, int],
    compression: float,
    archive: float,
    parsing: tuple[float, float],
    landings: tuple[BronzeLanding, ...],
    ingest_seconds: float,
    parquet_seconds: float,
    receipt_seconds: float,
    lineage_seconds: float,
    catalogue: tuple[float, int],
) -> tuple[StageMeasurement, ...]:
    source_count = int(spec["source_count"])
    json_bytes = len(artefacts.json_payload)
    parquet_bytes = sum(item.parquet_path.stat().st_size for item in landings)
    raw_stages = (
        (
            "ingestion",
            ingest_seconds,
            IMPLEMENTATION_PYTHON,
            None,
            json_bytes * source_count,
        ),
        (
            "hashing",
            hashing[0],
            IMPLEMENTATION_OPENSSL,
            "hashlib.sha256",
            hashing[1],
        ),
        (
            "compression",
            compression,
            IMPLEMENTATION_ZLIB,
            "zlib",
            len(artefacts.csv_payload),
        ),
        (
            "archive_inspection",
            archive,
            IMPLEMENTATION_ZIPFILE,
            "zipfile+zlib",
            len(artefacts.zip_payload),
        ),
        (
            "parsing",
            parsing[0],
            IMPLEMENTATION_ORJSON,
            "orjson",
            json_bytes * int(spec["parse_iterations"]),
        ),
        (
            "parquet_generation",
            parquet_seconds,
            "pyarrow_c_plus_plus",
            "pyarrow.parquet",
            parquet_bytes,
        ),
        (
            "receipt_validation",
            receipt_seconds,
            IMPLEMENTATION_PYDANTIC,
            "pydantic-core",
            json_bytes * int(spec["receipt_iterations"]),
        ),
        (
            "lineage_generation",
            lineage_seconds,
            IMPLEMENTATION_ORJSON,
            "orjson",
            source_count,
        ),
        (
            "catalogue_operations",
            catalogue[0],
            IMPLEMENTATION_PYTHON,
            None,
            int(spec["catalogue_iterations"]),
        ),
    )
    total = sum(item[1] for item in raw_stages) or 1.0
    return tuple(
        StageMeasurement(
            name=name,
            elapsed_seconds=elapsed,
            wall_share=elapsed / total,
            implementation=implementation,
            accelerator=accelerator,
            bytes_processed=bytes_processed,
        )
        for (
            name,
            elapsed,
            implementation,
            accelerator,
            bytes_processed,
        ) in raw_stages
    )


def _observed_metrics(
    hashing: tuple[float, int],
    archive: float,
    ingest: float,
    parquet: float,
    receipts: float,
    lineage: float,
    catalogue: tuple[float, int],
    parsing: tuple[float, float],
) -> tuple[dict[str, float], float]:
    hashing_mib = (hashing[1] / MEBIBYTE) / hashing[0] if hashing[0] else 0.0
    catalogue_rate = catalogue[1] / catalogue[0] if catalogue[0] else 0.0
    orjson_s = parsing[0]
    parse_speedup = parsing[1] / orjson_s if orjson_s else 1.0
    observed = {
        "pipeline_seconds": ingest + parquet,
        "hashing_mib_per_second": hashing_mib,
        "archive_inspect_seconds": archive,
        "parquet_seconds": parquet,
        "receipt_validation_seconds": receipts,
        "lineage_seconds": lineage,
        "catalogue_ops_per_second": catalogue_rate,
    }
    return observed, parse_speedup


def _capture_run(
    output_directory: Path,
    fixture: dict[str, Any],
    profile: str,
) -> _CapturedRun:
    spec = _profile(fixture, profile)
    artefacts = generate_synthetic_artefacts(fixture, profile=profile)
    hashing, compression, archive, parsing = _time_primitives(
        artefacts,
        spec,
        output_directory,
    )
    landings, ingest, parquet, receipts, lineage, catalogue = _time_pipeline(
        artefacts,
        spec,
        output_directory / "bronze",
    )
    stages = _stages_from_timings(
        artefacts,
        spec,
        hashing,
        compression,
        archive,
        parsing,
        landings,
        ingest,
        parquet,
        receipts,
        lineage,
        catalogue,
    )
    observed, parse_speedup = _observed_metrics(
        hashing,
        archive,
        ingest,
        parquet,
        receipts,
        lineage,
        catalogue,
        parsing,
    )
    return _CapturedRun(
        stages=stages,
        observed=observed,
        parse_speedup=parse_speedup,
        source_count=int(spec["source_count"]),
        json_bytes=len(artefacts.json_payload),
        csv_bytes=len(artefacts.csv_payload),
        zip_bytes=len(artefacts.zip_payload),
        seed=int(fixture["seed"]),
        catalog_count=int(fixture["catalog_source_count_observed"]),
    )


def _profile(fixture: dict[str, Any], profile: str) -> dict[str, Any]:
    profiles = fixture["profiles"]
    if profile not in profiles:
        raise KeyError(f"unknown bronze scale profile: {profile}")
    spec = profiles[profile]
    if not isinstance(spec, dict):
        raise TypeError("profile must be a JSON object")
    return cast("dict[str, Any]", spec)


def _expand(seed: int, label: str, size: int) -> bytes:
    material = sha256(f"{seed}:{label}".encode()).digest()
    output = bytearray()
    counter = 0
    while len(output) < size:
        material = sha256(material + counter.to_bytes(8, "big")).digest()
        output.extend(material)
        counter += 1
    return bytes(output[:size])


def _json_payload(size: int, seed: int) -> bytes:
    prefix = b'{"synthetic":true,"pad":"'
    suffix = b'"}'
    pad_length = size - len(prefix) - len(suffix)
    if pad_length < 1:
        raise ValueError("json_bytes is too small")
    pad = _expand(seed, "json", pad_length).hex()[:pad_length]
    return prefix + pad.encode("ascii") + suffix


def _csv_payload(size: int, seed: int) -> bytes:
    header = b"source_id,ingredient,strength\n"
    row = (_expand(seed, "csv", 48).hex()[:40] + ",paracetamol,500\n").encode()
    body_length = size - len(header)
    if body_length < len(row):
        raise ValueError("csv_bytes is too small")
    repeats = body_length // len(row)
    payload = header + (row * repeats)
    return payload + b" " * (size - len(payload))


def _zip_payload(members: int, member_bytes: int, seed: int) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(
        buffer,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for index in range(members):
            name = f"member-{index:03d}.bin"
            info = zipfile.ZipInfo(
                filename=name, date_time=(1980, 1, 1, 0, 0, 0)
            )
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, _expand(seed, name, member_bytes))
    return buffer.getvalue()


def _measure_hashing(payload: bytes, iterations: int) -> tuple[float, int]:
    started = time.perf_counter()
    for _ in range(iterations):
        oneshot = sha256(payload).digest()
        digest = sha256()
        view = memoryview(payload)
        step = 1024 * 1024
        for offset in range(0, len(payload), step):
            digest.update(view[offset : offset + step])
        if digest.digest() != oneshot:
            raise ValueError("streaming digest diverged")
    elapsed = time.perf_counter() - started
    return elapsed, len(payload) * iterations * 2


def _measure_compression(payload: bytes) -> float:
    started = time.perf_counter()
    compressed = zlib.compress(payload, level=6)
    restored = zlib.decompress(compressed)
    if restored != payload:
        raise ValueError("zlib round-trip failed")
    return time.perf_counter() - started


def _measure_archive(payload: bytes, output_directory: Path) -> float:
    destination = output_directory / "archive-extracted"
    started = time.perf_counter()
    extract_zip(payload, destination)
    return time.perf_counter() - started


def _measure_parsing(
    payload: bytes,
    iterations: int,
) -> tuple[float, float]:
    started = time.perf_counter()
    for _ in range(iterations):
        parsed = orjson.loads(payload)
        if parsed["synthetic"] is not True:
            raise ValueError("orjson parse failed")
    orjson_seconds = time.perf_counter() - started
    started = time.perf_counter()
    for _ in range(iterations):
        parsed_json = json.loads(payload)
        if parsed_json["synthetic"] is not True:
            raise ValueError("json parse failed")
    json_seconds = time.perf_counter() - started
    return orjson_seconds, json_seconds


def _landable_receipt(source_id: str, payload: bytes) -> SourceReceipt:
    evidence = PayloadEvidence.from_bytes(payload)
    return SourceReceipt(
        receipt_id=f"receipt-{source_id}",
        source=SourceIdentity(
            catalog_id=source_id,
            source_id=source_id,
            jurisdiction="NZ",
            authority="synthetic-scale",
            dataset_title="Bronze scale fixture",
            catalog_version="2026-08-20",
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl("https://example.invalid/synthetic-scale"),
            retrieved_at=SYNTHETIC_RETRIEVED_AT,
            acquisition_method=AcquisitionMethod.DOWNLOAD,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=evidence,
        effective_from=None,
        rights_state=RightsState.PERMITTED,
        rights_reference=AnyUrl("https://example.invalid/rights"),
        evidence_class=EvidenceClass.SYNTHETIC,
        transformation=TransformationEvidence(
            transformation_id="bronze-scale-v1",
            transformation_sha256="b" * 64,
            output_sha256="c" * 64,
            output_byte_count=1,
        ),
        reuse=acquire_new_decision(source_id),
        temporal=temporal_identity_from_source(
            retrieved_at=SYNTHETIC_RETRIEVED_AT,
            source_id=source_id,
            payload_sha256=evidence.sha256,
        ),
    )


def _land_sources(
    payload: bytes,
    *,
    source_count: int,
    bronze_root: Path,
) -> tuple[BronzeLanding, ...]:
    landings: list[BronzeLanding] = []
    for index in range(source_count):
        source_id = f"synthetic-scale-{index:03d}"
        outcome = land_bronze_payload(
            payload,
            _landable_receipt(source_id, payload),
            bronze_root=bronze_root,
            media_hint="json",
        )
        if not isinstance(outcome, BronzeLanding):
            raise TypeError("synthetic scale payload was not admitted")
        landings.append(outcome)
    return tuple(landings)


def _measure_receipts(
    payload: bytes,
    receipt: SourceReceipt,
    iterations: int,
) -> float:
    started = time.perf_counter()
    for _ in range(iterations):
        if not receipt.payload.matches(payload):
            raise ValueError("payload digest mismatch")
        digest = receipt.digest()
        if len(digest) != SHA256_HEX_LENGTH:
            raise ValueError("receipt digest is not sha256")
        SourceReceipt.model_validate(receipt.model_dump(mode="json"))
    return time.perf_counter() - started


def _measure_lineage(landings: tuple[BronzeLanding, ...]) -> float:
    started = time.perf_counter()
    for landing in landings:
        event = project_openlineage_event(
            landing.receipt,
            payload_uri=landing.payload_path.as_uri(),
            parquet_uri=landing.parquet_path.as_uri(),
            transformation_run=landing.transformation_run,
            table=landing.table,
            parquet_product="acquisition_manifest",
        )
        if event["eventType"] != "COMPLETE":
            raise ValueError("lineage eventType is not COMPLETE")
    return time.perf_counter() - started


def _measure_catalogue(
    landing: BronzeLanding,
    iterations: int,
) -> tuple[float, int]:
    spec = bronze_table_spec(landing.receipt, landing.parquet_path)
    started = time.perf_counter()
    for _ in range(iterations):
        body = iceberg_rest_create_body(spec)
        if body["name"] != spec.table_name:
            raise ValueError("catalogue identity diverged")
    elapsed = time.perf_counter() - started
    return elapsed, iterations


def _rust_candidates(
    stages: tuple[StageMeasurement, ...],
    *,
    parse_speedup: float,
    min_wall_share: float,
    min_speedup: float,
) -> list[dict[str, Any]]:
    by_name = {item.name: item for item in stages}
    mapping = (
        ("streaming_hashing", "hashing", 1.0),
        ("archive_inspection", "archive_inspection", 1.0),
        ("parsing", "parsing", parse_speedup),
        ("compression_decompression", "compression", 1.0),
        ("high_volume_validation", "receipt_validation", 1.0),
    )
    candidates: list[dict[str, Any]] = []
    for capability, stage_name, speedup in mapping:
        stage = by_name[stage_name]
        justified = rust_rewrite_justified(
            stage,
            speedup=speedup,
            min_wall_share=min_wall_share,
            min_speedup=min_speedup,
        )
        candidates.append({
            "capability": capability,
            "stage": stage_name,
            "implementation": stage.implementation,
            "accelerator": stage.accelerator,
            "wall_share": stage.wall_share,
            "speedup_versus_alternative": speedup,
            "justified": justified,
            "reason": _rust_reason(stage, justified=justified),
        })
    return candidates


def _rust_reason(stage: StageMeasurement, *, justified: bool) -> str:
    if justified:
        return "hot pure-Python path exceeds the wall-share and speedup gates"
    if stage.implementation != IMPLEMENTATION_PYTHON:
        return (
            "path already delegates to a native library; keep Python "
            "orchestration"
        )
    return "stage is below the wall-share or speedup gate"
