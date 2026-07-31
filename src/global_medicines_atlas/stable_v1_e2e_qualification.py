"""Deterministic stable-v1 end-to-end product qualification.

This module composes the public API, CLI and Atlas over one read-only DuckDB
fixture.  The resulting receipt records bounded semantic projections rather
than volatile response timestamps or complete rendered pages.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Literal, Protocol, Self, cast

import duckdb
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typer.testing import CliRunner

from .api import create_app
from .atlas import create_atlas_app
from .cli import app as cli_app
from .comparison_validity import evaluate_comparison_validity
from .product_contracts import (
    ComparisonDimensionState,
    ComparisonQuery,
    ComparisonValidityDimension,
    ComparisonValidityDimensions,
    ComparisonValidityOutcome,
    EvidenceDimension,
)
from .query_service import ReadOnlyQueryService

_CLOCK = "2026-07-31T12:00:00+00:00"
_CURSOR_SECRET = b"stable-v1-e2e-qualification"
_HTTP_OK = 200
_CLI_ENV = {"GMA_CURSOR_SECRET": _CURSOR_SECRET.decode()}
_SAFE_FALSE_KEYS = (
    "establishes_medicine_equivalence",
    "establishes_substitutability",
    "establishes_therapeutic_interchangeability",
    "establishes_equal_benefit",
)
_AFFIRMATIVE_TEXT = (
    "establishes medicine equivalence",
    "establishes substitutability",
    "establishes therapeutic interchangeability",
    "establishes equal benefit",
)
_FIXTURE_SQL = """
CREATE TABLE temporal_assertions (
    assertion_id VARCHAR NOT NULL, concept_id VARCHAR NOT NULL,
    jurisdiction VARCHAR NOT NULL, kind VARCHAR NOT NULL,
    authority VARCHAR NOT NULL, status_code VARCHAR NOT NULL,
    evidence_status VARCHAR NOT NULL, restrictions VARCHAR[] NOT NULL,
    valid_from TIMESTAMPTZ NOT NULL, valid_to TIMESTAMPTZ,
    observed_from TIMESTAMPTZ NOT NULL, observed_to TIMESTAMPTZ,
    supersedes_assertion_id VARCHAR, conflict_id VARCHAR,
    source_id VARCHAR NOT NULL, source_uri VARCHAR NOT NULL,
    retrieved_at TIMESTAMPTZ, source_effective_at TIMESTAMPTZ,
    source_path VARCHAR, source_sha256 VARCHAR, source_version VARCHAR,
    transformation VARCHAR
);
CREATE TABLE temporal_coverage (
    jurisdiction VARCHAR NOT NULL, source_id VARCHAR NOT NULL,
    receipt_id VARCHAR NOT NULL, observation_id VARCHAR NOT NULL,
    population_partition_id VARCHAR NOT NULL, dimension VARCHAR NOT NULL,
    medicine_concept_id VARCHAR, assertion_type VARCHAR NOT NULL,
    assertion_status VARCHAR NOT NULL, concept_population VARCHAR NOT NULL,
    valid_from TIMESTAMPTZ NOT NULL, valid_to TIMESTAMPTZ,
    observed_from TIMESTAMPTZ NOT NULL, observed_to TIMESTAMPTZ,
    assertion_count BIGINT NOT NULL, concept_numerator BIGINT NOT NULL,
    eligible_denominator BIGINT, exclusion_count BIGINT NOT NULL,
    exclusion_reasons VARCHAR[] NOT NULL,
    conflicting_assertion_count BIGINT NOT NULL
);
CREATE TABLE medicine_concepts (
    concept_id VARCHAR NOT NULL, preferred_name VARCHAR NOT NULL,
    concept_type VARCHAR NOT NULL
);
CREATE TABLE medicine_identifiers (
    concept_id VARCHAR NOT NULL, identifier_system VARCHAR NOT NULL,
    identifier_value VARCHAR NOT NULL
);
CREATE TABLE medicine_names (
    concept_id VARCHAR NOT NULL, name VARCHAR NOT NULL,
    name_type VARCHAR NOT NULL, normalized_name VARCHAR NOT NULL
);
CREATE TABLE medicine_concept_jurisdictions (
    concept_id VARCHAR NOT NULL, jurisdiction VARCHAR NOT NULL
);
CREATE TABLE medicine_sources (
    source_id VARCHAR NOT NULL, jurisdiction VARCHAR NOT NULL,
    authority VARCHAR NOT NULL, regulatory_system BOOLEAN NOT NULL,
    funding_system BOOLEAN NOT NULL
);
INSERT INTO temporal_assertions VALUES
    ('nz-reg', 'gma:aspirin', 'NZ', 'regulatory', 'Medsafe', 'approved',
     'confirmed', [], TIMESTAMPTZ '2026-07-01 00:00:00+00', NULL,
     TIMESTAMPTZ '2026-07-01 00:00:00+00', NULL, NULL, NULL, 'medsafe',
     'https://example.test/medsafe/aspirin',
     TIMESTAMPTZ '2026-07-01 00:00:00+00', NULL, NULL,
     'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
     '2026-07', 'qualification-v1'),
    ('nz-fund', 'gma:aspirin', 'NZ', 'funding', 'Pharmac', 'funded',
     'confirmed', [], TIMESTAMPTZ '2026-07-01 00:00:00+00', NULL,
     TIMESTAMPTZ '2026-07-01 00:00:00+00', NULL, NULL, NULL, 'pharmac',
     'https://example.test/pharmac/aspirin',
     TIMESTAMPTZ '2026-07-01 00:00:00+00', NULL, NULL,
     'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
     '2026-07', 'qualification-v1'),
    ('au-reg', 'gma:aspirin', 'AU', 'regulatory', 'TGA', 'registered',
     'confirmed', [], TIMESTAMPTZ '2026-07-01 00:00:00+00', NULL,
     TIMESTAMPTZ '2026-07-01 00:00:00+00', NULL, NULL, NULL, 'artg',
     'https://example.test/artg/aspirin',
     TIMESTAMPTZ '2026-07-01 00:00:00+00', NULL, NULL,
     'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc',
     '2026-07', 'qualification-v1');
INSERT INTO temporal_coverage VALUES
    ('AU', 'pbs', 'receipt-pbs', 'pbs-aspirin', 'all', 'funding',
     'gma:aspirin', 'medicine', 'not_covered', 'listed medicines',
     TIMESTAMPTZ '2026-07-01 00:00:00+00', NULL,
     TIMESTAMPTZ '2026-07-01 00:00:00+00', NULL,
     0, 0, 100, 0, [], 0),
    ('US', 'fda', 'receipt-fda', 'fda-aspirin', 'all', 'regulatory',
     'gma:aspirin', 'medicine', 'unknown', 'observed medicines',
     TIMESTAMPTZ '2026-07-01 00:00:00+00', NULL,
     TIMESTAMPTZ '2026-07-01 00:00:00+00', NULL,
     0, 0, NULL, 0, [], 0);
INSERT INTO medicine_concepts VALUES
    ('gma:aspirin', 'Aspirin', 'substance'),
    ('gma:aspirin-product', 'Aspirin 100 mg tablet', 'product');
INSERT INTO medicine_identifiers VALUES
    ('gma:aspirin', 'rxnorm', '1191');
INSERT INTO medicine_names VALUES
    ('gma:aspirin', 'Aspirin', 'preferred', 'aspirin'),
    ('gma:aspirin', 'Acetylsalicylic acid', 'alias',
     'acetylsalicylic acid'),
    ('gma:aspirin-product', 'Aspirin 100 mg tablet', 'preferred',
     'aspirin 100 mg tablet');
INSERT INTO medicine_concept_jurisdictions VALUES
    ('gma:aspirin', 'AU'), ('gma:aspirin', 'NZ'),
    ('gma:aspirin-product', 'NZ');
INSERT INTO medicine_sources VALUES
    ('artg', 'AU', 'TGA', true, false),
    ('pbs', 'AU', 'Australian Government', false, true),
    ('medsafe', 'NZ', 'Medsafe', true, false),
    ('pharmac', 'NZ', 'Pharmac', false, true);
"""

type ControlName = Literal["aligned", "compatible", "mismatch", "unknown"]


class QualificationError(RuntimeError):
    """Raised when a stable-v1 qualification invariant is not met."""


class _HttpResponse(Protocol):
    status_code: int
    text: str

    def json(self) -> object: ...


class _HttpClient(Protocol):
    def get(
        self,
        url: str,
        *,
        params: Mapping[str, str | int]
        | Sequence[tuple[str, str]]
        | None = None,
    ) -> _HttpResponse: ...


class QualificationModel(BaseModel):
    """Immutable, closed model used by the qualification receipt."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class SafetyClaims(QualificationModel):
    """All clinical interpretation claims that the product must deny."""

    establishes_medicine_equivalence: Literal[False] = False
    establishes_substitutability: Literal[False] = False
    establishes_therapeutic_interchangeability: Literal[False] = False
    establishes_equal_benefit: Literal[False] = False


class ComparisonControl(QualificationModel):
    """One deterministic comparison-validity negative control."""

    name: ControlName
    outcome: ComparisonValidityOutcome
    abstained: bool
    safety_claims: SafetyClaims


class SurfaceCheck(QualificationModel):
    """Content-bound semantic evidence for one public surface capability."""

    surface: Literal["api", "cli", "atlas"]
    capability: Literal[
        "comparison_validity",
        "concept_search",
        "concept_detail",
        "jurisdictions",
        "sources",
    ]
    evidence: tuple[str, ...] = Field(min_length=1)
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def evidence_is_content_bound(self) -> Self:
        if self.evidence_sha256 != _digest(self.evidence):
            raise ValueError("surface evidence digest does not match evidence")
        return self


class QualificationBody(QualificationModel):
    """Deterministic evidence body sealed by the outer receipt."""

    schema_id: Literal["global-medicines-atlas.stable-v1-e2e-qualification"] = (
        "global-medicines-atlas.stable-v1-e2e-qualification"
    )
    schema_version: Literal[1] = 1
    fixture_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    controls: tuple[ComparisonControl, ...]
    surfaces: tuple[SurfaceCheck, ...]
    unknown_evidence_abstains: Literal[True] = True
    regulatory_and_funding_remain_separate: Literal[True] = True
    external_actions_performed: Literal[False] = False

    @model_validator(mode="after")
    def matrix_is_complete(self) -> Self:
        expected_controls = {
            "aligned": ComparisonValidityOutcome.VALID,
            "compatible": ComparisonValidityOutcome.VALID_WITH_CAVEATS,
            "mismatch": ComparisonValidityOutcome.INAPPROPRIATE_COMPARISON,
            "unknown": ComparisonValidityOutcome.INSUFFICIENT_EVIDENCE,
        }
        observed_controls = {item.name: item.outcome for item in self.controls}
        if observed_controls != expected_controls:
            raise ValueError("comparison-validity control matrix is incomplete")
        expected_surfaces = {
            (surface, capability)
            for surface in ("api", "cli", "atlas")
            for capability in (
                "comparison_validity",
                "concept_search",
                "concept_detail",
                "jurisdictions",
                "sources",
            )
        }
        observed_surfaces = {
            (item.surface, item.capability) for item in self.surfaces
        }
        if observed_surfaces != expected_surfaces:
            raise ValueError(
                "public-surface qualification matrix is incomplete"
            )
        return self


class QualificationReceipt(QualificationModel):
    """Digest-bound stable-v1 end-to-end qualification receipt."""

    body: QualificationBody
    receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def receipt_is_content_bound(self) -> Self:
        if self.receipt_sha256 != _digest(self.body.model_dump(mode="json")):
            raise ValueError("qualification receipt digest does not match body")
        return self


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _require(condition: bool, message: str) -> None:  # ruff: ignore[boolean-type-hint-positional-argument]
    if not condition:
        raise QualificationError(message)


def _surface_check(
    surface: Literal["api", "cli", "atlas"],
    capability: Literal[
        "comparison_validity",
        "concept_search",
        "concept_detail",
        "jurisdictions",
        "sources",
    ],
    evidence: Sequence[str],
) -> SurfaceCheck:
    values = tuple(evidence)
    return SurfaceCheck(
        surface=surface,
        capability=capability,
        evidence=values,
        evidence_sha256=_digest(values),
    )


def _dimension(
    state: ComparisonDimensionState,
    *,
    left: str | None = None,
    right: str | None = None,
) -> ComparisonValidityDimension:
    evidence = ("qualification:evidence",) if left and right else ()
    return ComparisonValidityDimension(
        state=state,
        left_value=left,
        right_value=right,
        evidence_ids=evidence,
    )


def _comparison_controls() -> tuple[ComparisonControl, ...]:
    states: tuple[tuple[ControlName, ComparisonDimensionState], ...] = (
        ("aligned", ComparisonDimensionState.ALIGNED),
        ("compatible", ComparisonDimensionState.COMPATIBLE),
        ("mismatch", ComparisonDimensionState.MISMATCH),
        ("unknown", ComparisonDimensionState.UNKNOWN),
    )
    controls: list[ComparisonControl] = []
    for name, state in states:
        observed = state is not ComparisonDimensionState.UNKNOWN
        controlled = _dimension(
            state,
            left="left" if observed else None,
            right="right" if observed else None,
        )
        aligned = _dimension(
            ComparisonDimensionState.ALIGNED,
            left="left",
            right="left",
        )
        verdict = evaluate_comparison_validity(
            left_subject_id=f"qualification:{name}:left",
            right_subject_id=f"qualification:{name}:right",
            dimensions=ComparisonValidityDimensions(
                granularity=controlled,
                indication=aligned,
                population=aligned,
                mapping=aligned,
                normalization=aligned,
            ),
        )
        controls.append(
            ComparisonControl(
                name=name,
                outcome=verdict.outcome,
                abstained=(
                    verdict.outcome
                    is ComparisonValidityOutcome.INSUFFICIENT_EVIDENCE
                ),
                safety_claims=SafetyClaims.model_validate(
                    verdict.model_dump(include=set(_SAFE_FALSE_KEYS))
                ),
            )
        )
    return tuple(controls)


def _create_fixture(path: Path) -> Path:
    connection = duckdb.connect(str(path))
    try:
        connection.execute(_FIXTURE_SQL)
    finally:
        connection.close()
    return path


def _mapping(value: object, context: str) -> Mapping[str, Any]:
    _require(isinstance(value, dict), f"{context} is not an object")
    return cast("Mapping[str, Any]", value)


def _sequence(value: object, context: str) -> Sequence[Any]:
    _require(isinstance(value, list), f"{context} is not an array")
    return cast("Sequence[Any]", value)


def _claims_are_false(validity: Sequence[Any], context: str) -> None:
    _require(bool(validity), f"{context} has no validity assessments")
    for raw in validity:
        item = _mapping(raw, context)
        _require(
            all(item.get(key) is False for key in _SAFE_FALSE_KEYS),
            f"{context} contains a prohibited clinical interpretation claim",
        )


def _api_checks(  # ruff: ignore[too-many-locals]
    service: ReadOnlyQueryService,
) -> tuple[SurfaceCheck, ...]:
    client = cast("_HttpClient", TestClient(create_app(service)))
    search = client.get(
        "/api/v1/concepts",
        params={"q": "aspirin", "jurisdictions": "NZ", "limit": 1},
    )
    detail = client.get("/api/v1/concepts/gma:aspirin")
    jurisdictions = client.get("/api/v1/jurisdictions")
    sources = client.get("/api/v1/sources")
    comparison = client.get(
        "/api/v1/comparisons",
        params=[
            ("concept_id", "gma:aspirin"),
            ("jurisdictions", "NZ"),
            ("jurisdictions", "AU"),
            ("jurisdictions", "US"),
            ("valid_at", _CLOCK),
            ("observed_at", _CLOCK),
        ],
    )
    for response in (search, detail, jurisdictions, sources, comparison):
        _require(
            response.status_code == _HTTP_OK,
            "API qualification request failed",
        )

    search_body = _mapping(search.json(), "API search")
    concepts = _sequence(search_body.get("concepts"), "API concepts")
    search_ids = tuple(
        str(_mapping(item, "API concept")["concept_id"]) for item in concepts
    )
    _require(search_ids == ("gma:aspirin",), "API search changed")
    _require(
        all(
            _mapping(
                _mapping(item, "API concept")["explanation"], "API explanation"
            ).get("establishes_equivalence")
            is False
            for item in concepts
        ),
        "API search implied equivalence",
    )
    detail_body = _mapping(detail.json(), "API detail")
    jurisdiction_rows = _sequence(jurisdictions.json(), "API jurisdictions")
    source_rows = _sequence(sources.json(), "API sources")
    comparison_body = _mapping(comparison.json(), "API comparison")
    validity = _sequence(comparison_body.get("validity"), "API validity")
    conclusions = _sequence(
        comparison_body.get("conclusions"), "API conclusions"
    )
    _claims_are_false(validity, "API validity")
    outcomes = tuple(
        sorted(
            str(_mapping(item, "API validity")["outcome"]) for item in validity
        )
    )
    _require(
        bool(outcomes) and set(outcomes) == {"insufficient_evidence"},
        "API unknown evidence did not abstain",
    )
    dimensions = tuple(
        sorted({
            str(_mapping(item, "API conclusion")["dimension"])
            for item in conclusions
        })
    )
    _require(
        dimensions == ("funding", "regulatory"),
        "API merged regulatory and funding dimensions",
    )
    return (
        _surface_check("api", "concept_search", search_ids),
        _surface_check(
            "api", "concept_detail", (str(detail_body["concept_id"]),)
        ),
        _surface_check(
            "api",
            "jurisdictions",
            tuple(
                str(_mapping(item, "API jurisdiction")["jurisdiction"])
                for item in jurisdiction_rows
            ),
        ),
        _surface_check(
            "api",
            "sources",
            tuple(
                sorted(
                    str(_mapping(item, "API source")["source_id"])
                    for item in source_rows
                )
            ),
        ),
        _surface_check("api", "comparison_validity", (*dimensions, *outcomes)),
    )


def _invoke_cli(database: Path, arguments: Sequence[str]) -> Mapping[str, Any]:
    result = CliRunner().invoke(
        cli_app,
        [*arguments, "--database", str(database)],
        env=_CLI_ENV,
    )
    _require(
        result.exit_code == 0, f"CLI qualification failed: {result.stderr}"
    )
    return _mapping(json.loads(result.stdout), "CLI response")


def _cli_checks(database: Path) -> tuple[SurfaceCheck, ...]:
    search = _invoke_cli(
        database,
        ("concept", "search", "aspirin", "--limit", "1", "--max-rows", "1"),
    )
    detail = _invoke_cli(database, ("concept", "show", "gma:aspirin"))
    jurisdictions = _invoke_cli(database, ("jurisdiction", "list"))
    sources = _invoke_cli(database, ("source", "list"))
    comparison = _invoke_cli(
        database,
        (
            "comparison",
            "--concept-id",
            "gma:aspirin",
            "--jurisdiction",
            "NZ",
            "--jurisdiction",
            "AU",
            "--jurisdiction",
            "US",
            "--valid-at",
            _CLOCK,
            "--observed-at",
            _CLOCK,
        ),
    )
    concepts = _sequence(search.get("concepts"), "CLI concepts")
    search_ids = tuple(
        str(_mapping(item, "CLI concept")["concept_id"]) for item in concepts
    )
    _require(search_ids[0] == "gma:aspirin", "CLI search changed")
    _require(
        all(
            _mapping(
                _mapping(item, "CLI concept")["explanation"], "CLI explanation"
            ).get("establishes_equivalence")
            is False
            for item in concepts
        ),
        "CLI search implied equivalence",
    )
    validity = _sequence(comparison.get("validity"), "CLI validity")
    conclusions = _sequence(comparison.get("conclusions"), "CLI conclusions")
    _claims_are_false(validity, "CLI validity")
    outcomes = tuple(
        sorted(
            str(_mapping(item, "CLI validity")["outcome"]) for item in validity
        )
    )
    _require(
        bool(outcomes) and set(outcomes) == {"insufficient_evidence"},
        "CLI unknown evidence did not abstain",
    )
    dimensions = tuple(
        sorted({
            str(_mapping(item, "CLI conclusion")["dimension"])
            for item in conclusions
        })
    )
    _require(
        dimensions == ("funding", "regulatory"),
        "CLI merged regulatory and funding dimensions",
    )
    jurisdiction_rows = _sequence(
        jurisdictions.get("jurisdictions"), "CLI jurisdictions"
    )
    source_rows = _sequence(sources.get("sources"), "CLI sources")
    return (
        _surface_check("cli", "concept_search", search_ids),
        _surface_check("cli", "concept_detail", (str(detail["concept_id"]),)),
        _surface_check(
            "cli",
            "jurisdictions",
            tuple(
                str(_mapping(item, "CLI jurisdiction")["jurisdiction"])
                for item in jurisdiction_rows
            ),
        ),
        _surface_check(
            "cli",
            "sources",
            tuple(
                sorted(
                    str(_mapping(item, "CLI source")["source_id"])
                    for item in source_rows
                )
            ),
        ),
        _surface_check("cli", "comparison_validity", (*dimensions, *outcomes)),
    )


def _atlas_checks(service: ReadOnlyQueryService) -> tuple[SurfaceCheck, ...]:
    client = cast("_HttpClient", TestClient(create_atlas_app(service)))
    search = client.get(
        "/",
        params={"concept_search": "aspirin", "jurisdiction": "NZ"},
    )
    selected = client.get(
        "/",
        params=[
            ("concept_id", "gma:aspirin"),
            ("concept_search", "aspirin"),
            ("jurisdiction", "NZ"),
            ("jurisdiction", "AU"),
            ("jurisdiction", "US"),
            ("valid_at", _CLOCK),
            ("observed_at", _CLOCK),
        ],
    )
    _require(search.status_code == _HTTP_OK, "Atlas search failed")
    _require(selected.status_code == _HTTP_OK, "Atlas selection failed")
    search_text = search.text
    selected_text = selected.text
    lowered = f"{search_text}\n{selected_text}".lower()
    _require(
        "candidate match does not establish clinical equivalence" in lowered,
        "Atlas omitted its explicit non-equivalence explanation",
    )
    _require(
        not any(phrase in lowered for phrase in _AFFIRMATIVE_TEXT),
        "Atlas contains an affirmative clinical interpretation claim",
    )
    _require(
        "gma:aspirin" in search_text and "gma:aspirin" in selected_text,
        "Atlas did not preserve canonical concept identity",
    )
    _require(
        all(
            value in selected_text
            for value in ("NZ — regulatory", "NZ — funding")
        ),
        "Atlas merged regulatory and funding dimensions",
    )
    _require(
        all(
            value in selected_text
            for value in ("AU — regulatory", "US — regulatory")
        ),
        "Atlas did not render requested jurisdictions",
    )
    _require(
        all(value in selected_text for value in ("medsafe", "pharmac", "artg")),
        "Atlas did not render source evidence labels",
    )
    _require(
        "This is explicitly unknown. It is not evidence of a negative regulatory or funding decision."
        in selected_text,
        "Atlas unknown evidence did not abstain",
    )
    validity = service.comparisons(_comparison_query_for_atlas()).model_dump(
        mode="json"
    )["validity"]
    _claims_are_false(cast("Sequence[Any]", validity), "Atlas service validity")
    outcomes = tuple(
        sorted(
            str(_mapping(item, "Atlas validity")["outcome"])
            for item in cast("Sequence[Any]", validity)
        )
    )
    return (
        _surface_check("atlas", "concept_search", ("gma:aspirin",)),
        _surface_check("atlas", "concept_detail", ("gma:aspirin",)),
        _surface_check("atlas", "jurisdictions", ("AU", "NZ", "US")),
        _surface_check("atlas", "sources", ("artg", "medsafe", "pharmac")),
        _surface_check(
            "atlas",
            "comparison_validity",
            ("funding", "regulatory", *outcomes),
        ),
    )


def _comparison_query_for_atlas() -> ComparisonQuery:
    clock = datetime.fromisoformat(_CLOCK)
    return ComparisonQuery(
        concept_id="gma:aspirin",
        jurisdictions=("NZ", "AU", "US"),
        dimensions=(EvidenceDimension.REGULATORY, EvidenceDimension.FUNDING),
        valid_at=clock,
        observed_at=clock,
    )


def build_stable_v1_e2e_receipt() -> QualificationReceipt:
    """Run all deterministic checks and return a content-bound receipt."""
    controls = _comparison_controls()
    with TemporaryDirectory(prefix="gma-stable-v1-e2e-") as directory:
        root = Path(directory)
        database = _create_fixture(root / "qualification.duckdb")
        service = ReadOnlyQueryService(
            database,
            cursor_secret=_CURSOR_SECRET,
            allowed_root=root,
        )
        surfaces = (
            *_api_checks(service),
            *_cli_checks(database),
            *_atlas_checks(service),
        )
    body = QualificationBody(
        fixture_sha256=_digest(_FIXTURE_SQL),
        controls=controls,
        surfaces=surfaces,
    )
    return QualificationReceipt(
        body=body,
        receipt_sha256=_digest(body.model_dump(mode="json")),
    )


def write_stable_v1_e2e_receipt(output: Path) -> QualificationReceipt:
    """Run qualification and atomically write its canonical JSON receipt."""
    receipt = build_stable_v1_e2e_receipt()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(f"{output.suffix}.tmp")
    temporary.write_bytes(
        _canonical_json(receipt.model_dump(mode="json")) + b"\n"
    )
    temporary.replace(output)
    return receipt
