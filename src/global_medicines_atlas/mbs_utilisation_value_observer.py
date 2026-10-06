"""Bounded, value-free diagnostics for pinned MBS utilisation CSVs."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from .mbs_utilisation_header_inventory import (
    load_header_inventory_contract,
)

HEADER_INVENTORY_QUALIFICATION_PATH = Path(
    "quality/qualifications/australian-mbs-utilisation-header-inventory-20261006.json"
)
HEADER_INVENTORY_QUALIFICATION_SHA256 = (
    "7760909d98d4d9723c0f02de72269c9e88296a80e641e3af5eec5766737b5fbf"
)
DEMOGRAPHICS_HEADERS = (
    "Year",
    "Month of Processing",
    "Item Number",
    "State",
    "Age Range",
    "Gender",
    "Services",
    "Benefit",
)
GROUP_HEADERS = (
    "Year",
    "Month of Processing",
    "Group",
    "Sub-Group",
    "Item Number",
    "State",
    "Services",
    "Benefit",
)
SERVICES_HEADER = "Services"
BENEFIT_HEADER = "Benefit"
MAX_CSV_BYTES = 32 * 1024 * 1024
MAX_CSV_ROWS = 10_000_000
MAX_CSV_COLUMNS = 10_000
MAX_CSV_FIELD_BYTES = 1024 * 1024
MAX_NUMERIC_TOKEN_CHARS = 256
MAX_CANDIDATE_KEYS = 1_000_000
SEMANTIC_REQUIREMENTS_PATH = Path(
    "quality/qualifications/australian-mbs-utilisation-semantic-requirements-20261005.json"
)
SEMANTIC_REQUIREMENTS_SHA256 = (
    "af64e7ac68e0e67587ca153023e2dd3ea8779046407f257f9babd425513afdc2"
)
INVALID_TOKEN_CATEGORIES = (
    "overlength",
    "whitespace",
    "exponent_notation",
    "comma_triplet_pattern",
    "underscore_triplet_pattern",
    "other_separator",
    "alphabetic",
    "other_non_decimal",
)
TOKEN_SHAPE_CATEGORIES: tuple[str, ...] = (
    "empty",
    "ascii_digits",
    "ascii_letters",
    "ascii_alphanumeric",
    "whitespace",
    "other_nonempty",
)
EXPECTED_CSV_SOURCE_COUNT = 4
_DECIMAL_TOKEN = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)\Z")
_YEAR_TOKEN = re.compile(r"[0-9]{4}\Z")
_MONTH_NAMES = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)
_MONTH_NUMBER_BY_TOKEN = {
    spelling: number
    for number, full_name in enumerate(_MONTH_NAMES, start=1)
    for spelling in (full_name, full_name[:3])
}
_PERIOD_POLICY_BY_RESOURCE_ID: dict[str, tuple[str, frozenset[int]]] = {
    "ff6d0692-4c6f-466b-9d93-015224d80b14": (
        "1401931d5f9bbfa6e128196b02ef19016da67bd52b78ebf03b3fda6002abc676",
        frozenset({1, 2, 3}),
    ),
    "c3e6f879-be6c-41b9-9cf1-c74feb928b83": (
        "7b494fda71b8df57e332006d9b8388528b8aeb517ad92c741b3420a3e3980de6",
        frozenset({1, 2, 3, 4, 5}),
    ),
    "492b39de-8c97-4bbf-880e-e97d933daa9c": (
        "c8b4114771ad59b2dfc6c2172e94ec4ad3922b739c26d02178efb4355e44d758",
        frozenset({7}),
    ),
    "663a7fac-114c-47b5-9017-a9dbb9073260": (
        "040bc3649754be306a5b76f3d342e040fc2bdad5fbde477e0845e9368302e37f",
        frozenset({1, 2, 3, 4, 5, 6, 7}),
    ),
}


@dataclass(frozen=True)
class NumericObservation:
    """Aggregate parse outcomes for one exact-decimal source field."""

    valid_count: int
    invalid_count: int
    empty_count: int
    negative_count: int
    max_scale: int | None
    max_integer_digits: int | None
    invalid_category_counts: dict[str, int]

    def to_public_summary(self) -> dict[str, Any]:
        """Return only aggregate decimal-shape metadata."""
        return {
            "valid_count": self.valid_count,
            "invalid_count": self.invalid_count,
            "empty_count": self.empty_count,
            "negative_count": self.negative_count,
            "max_scale": self.max_scale,
            "max_integer_digits": self.max_integer_digits,
            "invalid_category_counts": self.invalid_category_counts,
        }


@dataclass(frozen=True)
class CsvValueObservation:
    """Value-free row-shape and scalar-shape findings for one pinned CSV."""

    headers: tuple[str, ...]
    header_sha256: str
    record_count: int
    rectangular_record_count: int
    row_width_error_count: int
    empty_cell_counts: dict[str, int]
    token_shapes: dict[str, dict[str, int]]
    candidate_key_headers: tuple[str, ...]
    candidate_key_duplicate_records: int
    processing_period_observation: dict[str, Any] | None
    services: NumericObservation
    benefit: NumericObservation

    def to_public_summary(self) -> dict[str, Any]:
        """Serialize reviewed headers and aggregate findings only."""
        result = {
            "status": "row_shape_findings"
            if self.row_width_error_count
            else "observed",
            "headers": list(self.headers),
            "header_sha256": self.header_sha256,
            "column_count": len(self.headers),
            "record_count": self.record_count,
            "rectangular_record_count": self.rectangular_record_count,
            "row_width_error_count": self.row_width_error_count,
            "empty_cell_counts": self.empty_cell_counts,
            "non_measure_token_shape_counts": self.token_shapes,
            "candidate_grain_diagnostic": {
                "key_headers": list(self.candidate_key_headers),
                "duplicate_records": self.candidate_key_duplicate_records,
                "grain_verified": False,
            },
            "numeric_observations": {
                SERVICES_HEADER: self.services.to_public_summary(),
                BENEFIT_HEADER: self.benefit.to_public_summary(),
            },
            "semantic_mapping_selected": False,
            "processing_admitted": False,
            "silver_published": False,
        }
        if self.processing_period_observation is not None:
            result["processing_period_observation"] = (
                self.processing_period_observation
            )
        return result


@dataclass(frozen=True)
class ProcessingPeriodPolicy:
    """Candidate period bounds tied to an exact catalogue resource record."""

    resource_id: str
    resource_description_sha256: str
    expected_year: str
    allowed_month_numbers: frozenset[int]


@dataclass
class _PeriodCounters:
    policy: ProcessingPeriodPolicy
    expected_year_count: int = 0
    year_mismatch_count: int = 0
    year_invalid_count: int = 0
    recognized_month_count: int = 0
    unrecognized_month_count: int = 0
    outside_documented_month_count: int = 0
    month_counts: dict[str, int] = field(
        default_factory=lambda: dict.fromkeys(
            (f"{number:02d}" for number in range(1, 13)), 0
        )
    )

    def add(self, year_token: str, month_token: str) -> None:
        if not _YEAR_TOKEN.fullmatch(year_token):
            self.year_invalid_count += 1
            return
        if year_token != self.policy.expected_year:
            self.year_mismatch_count += 1
            return
        self.expected_year_count += 1
        month_number = _MONTH_NUMBER_BY_TOKEN.get(month_token.casefold())
        if month_number is None:
            self.unrecognized_month_count += 1
            return
        self.recognized_month_count += 1
        self.month_counts[f"{month_number:02d}"] += 1
        if month_number not in self.policy.allowed_month_numbers:
            self.outside_documented_month_count += 1

    def to_public_observation(self) -> dict[str, Any]:
        return {
            "resource_id": self.policy.resource_id,
            "candidate_policy": {
                "evidence_path": SEMANTIC_REQUIREMENTS_PATH.as_posix(),
                "evidence_sha256": SEMANTIC_REQUIREMENTS_SHA256,
                "resource_description_sha256": (
                    self.policy.resource_description_sha256
                ),
                "expected_year": self.policy.expected_year,
                "allowed_month_numbers": sorted(
                    self.policy.allowed_month_numbers
                ),
                "accepted_token_forms": [
                    "English full month name",
                    "English three-letter month abbreviation",
                ],
                "state": "candidate_observation_only",
            },
            "expected_year_count": self.expected_year_count,
            "year_mismatch_count": self.year_mismatch_count,
            "year_invalid_count": self.year_invalid_count,
            "recognized_month_count": self.recognized_month_count,
            "unrecognized_month_count": self.unrecognized_month_count,
            "outside_documented_month_count": (
                self.outside_documented_month_count
            ),
            "month_record_counts": dict(self.month_counts),
            "period_semantics_verified": False,
        }


@dataclass
class _NumericCounters:
    valid_count: int = 0
    invalid_count: int = 0
    empty_count: int = 0
    negative_count: int = 0
    max_scale: int | None = None
    max_integer_digits: int | None = None
    invalid_category_counts: dict[str, int] = field(
        default_factory=lambda: dict.fromkeys(INVALID_TOKEN_CATEGORIES, 0)
    )

    def add(self, token: str) -> None:
        if not token:
            self.empty_count += 1
            return
        number = _parse_decimal_token(token)
        if number is None:
            self.invalid_count += 1
            category = _classify_invalid_token(token)
            self.invalid_category_counts[category] += 1
            return
        digits = len(number.as_tuple().digits)
        exponent = cast("int", number.as_tuple().exponent)
        self.valid_count += 1
        if number < 0:
            self.negative_count += 1
        scale = max(-exponent, 0)
        integer_digits = max(digits - scale, 0)
        self.max_scale = max(self.max_scale or 0, scale)
        self.max_integer_digits = max(
            self.max_integer_digits or 0, integer_digits
        )

    def freeze(self) -> NumericObservation:
        return NumericObservation(
            valid_count=self.valid_count,
            invalid_count=self.invalid_count,
            empty_count=self.empty_count,
            negative_count=self.negative_count,
            max_scale=self.max_scale,
            max_integer_digits=self.max_integer_digits,
            invalid_category_counts=dict(self.invalid_category_counts),
        )


def load_value_observer_cohort(root: Path) -> list[dict[str, Any]]:
    """Bind four exact source profiles to their prior hosted header receipts."""
    qualification_bytes = (
        root / HEADER_INVENTORY_QUALIFICATION_PATH
    ).read_bytes()
    if (
        hashlib.sha256(qualification_bytes).hexdigest()
        != HEADER_INVENTORY_QUALIFICATION_SHA256
    ):
        raise ValueError("header inventory qualification digest differs")
    qualification = json.loads(qualification_bytes)
    if (
        qualification.get("candidate_source_count") != EXPECTED_CSV_SOURCE_COUNT
        or qualification.get("receipts_independently_read_back") is not True
        or qualification.get("processing_admitted") is not False
        or qualification.get("semantic_validation") is not False
        or qualification.get("source_inventory_expanded") is not False
    ):
        raise ValueError("header inventory qualification is out of scope")
    selected, schemas = load_header_inventory_contract(root)
    prior_by_path = {
        record["path"]: record for record in qualification["records"]
    }
    if (
        len(prior_by_path) != EXPECTED_CSV_SOURCE_COUNT
        or len(selected) != EXPECTED_CSV_SOURCE_COUNT
    ):
        raise ValueError(
            "exactly four previously inventoried CSVs are required"
        )
    bound: list[dict[str, Any]] = []
    for row in selected:
        reference = row["raw_reference"]
        prior = prior_by_path.get(reference["path"])
        if prior is None:
            raise ValueError("header inventory source set differs")
        schema_matches = prior["schema_matches"]
        if (
            len(schema_matches) != 1
            or schema_matches[0] not in row["schema_candidate_ids"]
        ):
            raise ValueError("header inventory has no unique reviewed schema")
        observed_schema_id = schema_matches[0]
        expected_headers = schemas[observed_schema_id]
        canonical = json.dumps(
            list(expected_headers), ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        identity_differs = (
            prior["acquisition_id"] != row["acquisition_id"]
            or prior["source_revision"] != reference["revision"]
            or prior["source_sha256"] != reference["sha256"]
            or prior["byte_count"] != reference["byte_count"]
        )
        schema_differs = (
            prior["header_sha256"] != hashlib.sha256(canonical).hexdigest()
            or prior["column_count"] != len(expected_headers)
            or prior["unexpected_field_count"] != 0
        )
        receipt_differs = (
            prior["anonymous_digest_verified"] is not True
            or prior["cache_removed_after_receipt"] is not True
        )
        if identity_differs or schema_differs or receipt_differs:
            raise ValueError("header inventory source binding differs")
        bound.append({
            **row,
            "expected_headers": expected_headers,
            "observed_schema_id": observed_schema_id,
            "prior_header_receipt_url": prior["receipt_url"],
            "period_policy": load_processing_period_policy(
                root, row["resource_id"], reference["path"]
            ),
        })
    return bound


def load_processing_period_policy(
    root: Path, resource_id: str, source_path: str
) -> ProcessingPeriodPolicy:
    """Bind a candidate month window to the pinned official metadata record."""
    policy_identity = _PERIOD_POLICY_BY_RESOURCE_ID.get(resource_id)
    if policy_identity is None or not source_path.endswith(".csv"):
        raise ValueError("processing-period resource is outside exact scope")
    qualification_bytes = (root / SEMANTIC_REQUIREMENTS_PATH).read_bytes()
    if (
        hashlib.sha256(qualification_bytes).hexdigest()
        != SEMANTIC_REQUIREMENTS_SHA256
    ):
        raise ValueError("processing-period metadata digest differs")
    qualification = json.loads(qualification_bytes)
    if (
        qualification.get("source_revision")
        != "dee9a5b0580dfe394474dc26b372559462e157e7"
        or qualification.get("boundaries", {}).get(
            "source_payload_bytes_acquired_locally"
        )
        is not False
        or qualification.get("boundaries", {}).get("processing_admitted")
        is not False
    ):
        raise ValueError("processing-period metadata is out of scope")
    matching = [
        record
        for record in qualification.get("records", [])
        if record.get("resource_id") == resource_id
        and record.get("path") == source_path
    ]
    description_sha256, allowed_month_numbers = policy_identity
    if (
        len(matching) != 1
        or matching[0].get("resource_description_sha256") != description_sha256
        or matching[0].get("payload_period_verified") is not False
        or matching[0].get("processing_admitted") is not False
    ):
        raise ValueError("processing-period source binding differs")
    return ProcessingPeriodPolicy(
        resource_id=resource_id,
        resource_description_sha256=description_sha256,
        expected_year="2016",
        allowed_month_numbers=allowed_month_numbers,
    )


def observe_utilisation_csv_values(
    path: Path,
    *,
    expected_headers: tuple[str, ...],
    period_policy: ProcessingPeriodPolicy | None = None,
) -> CsvValueObservation:
    """Observe row shape and exact-decimal parse profiles without retaining values.

    Args:
        path: Exact staged source object, identity checked by the caller.
        expected_headers: Reviewed ordered headers from the exact source profile.

    Returns:
        Aggregate counts and digests suitable for a public-safe receipt.

    Raises:
        ValueError: If the file exceeds bounds, is malformed, or has a different
            header profile.
    """
    if (
        not expected_headers
        or len(expected_headers) > MAX_CSV_COLUMNS
        or len(set(expected_headers)) != len(expected_headers)
        or SERVICES_HEADER not in expected_headers
        or BENEFIT_HEADER not in expected_headers
    ):
        raise ValueError("reviewed CSV profile is invalid")
    if period_policy is not None and not {
        "Year",
        "Month of Processing",
    }.issubset(expected_headers):
        raise ValueError("processing-period CSV profile is invalid")
    size = path.stat().st_size
    if size <= 0 or size > MAX_CSV_BYTES:
        raise ValueError("CSV byte limit exceeded")

    empty_cells = dict.fromkeys(expected_headers, 0)
    token_shapes = {
        header: dict.fromkeys(TOKEN_SHAPE_CATEGORIES, 0)
        for header in expected_headers
        if header not in {SERVICES_HEADER, BENEFIT_HEADER}
    }
    candidate_key_headers = tuple(
        header
        for header in expected_headers
        if header not in {SERVICES_HEADER, BENEFIT_HEADER}
    )
    candidate_key_indices = tuple(
        expected_headers.index(header) for header in candidate_key_headers
    )
    candidate_keys: set[bytes] = set()
    candidate_key_duplicate_records = 0
    periods = (
        _PeriodCounters(policy=period_policy)
        if period_policy is not None
        else None
    )
    services = _NumericCounters()
    benefit = _NumericCounters()
    old_limit = csv.field_size_limit()
    csv.field_size_limit(MAX_CSV_FIELD_BYTES)
    try:
        with path.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.reader(source, strict=True)
            record_count, rectangular_count = _observe_rows(
                reader,
                expected_headers,
                empty_cells,
                token_shapes,
                candidate_key_indices,
                candidate_keys,
                periods,
                services,
                benefit,
            )
            candidate_key_duplicate_records = rectangular_count - len(
                candidate_keys
            )
    except (UnicodeDecodeError, csv.Error) as error:
        raise ValueError("CSV cannot be decoded or parsed") from error
    finally:
        csv.field_size_limit(old_limit)

    canonical_header = json.dumps(
        list(expected_headers), ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return CsvValueObservation(
        headers=expected_headers,
        header_sha256=hashlib.sha256(canonical_header).hexdigest(),
        record_count=record_count,
        rectangular_record_count=rectangular_count,
        row_width_error_count=record_count - rectangular_count,
        empty_cell_counts=empty_cells,
        token_shapes=token_shapes,
        candidate_key_headers=candidate_key_headers,
        candidate_key_duplicate_records=candidate_key_duplicate_records,
        processing_period_observation=(
            periods.to_public_observation() if periods is not None else None
        ),
        services=services.freeze(),
        benefit=benefit.freeze(),
    )


def _observe_rows(
    reader: Iterator[list[str]],
    expected_headers: tuple[str, ...],
    empty_cells: dict[str, int],
    token_shapes: dict[str, dict[str, int]],
    candidate_key_indices: tuple[int, ...],
    candidate_keys: set[bytes],
    periods: _PeriodCounters | None,
    services: _NumericCounters,
    benefit: _NumericCounters,
) -> tuple[int, int]:
    """Count explicit empties and inspect scalar shapes in rectangular rows."""
    headers = next(reader, None)
    if headers is None:
        raise ValueError("CSV header is missing")
    if tuple(headers) != expected_headers:
        raise ValueError("reviewed CSV header differs")
    services_index = expected_headers.index(SERVICES_HEADER)
    benefit_index = expected_headers.index(BENEFIT_HEADER)
    year_index = expected_headers.index("Year") if periods is not None else None
    month_index = (
        expected_headers.index("Month of Processing")
        if periods is not None
        else None
    )
    record_count = 0
    rectangular_count = 0
    for row in reader:
        record_count += 1
        if record_count > MAX_CSV_ROWS:
            raise ValueError("CSV row limit exceeded")
        for index, header in enumerate(expected_headers):
            if index < len(row):
                token = row[index]
                if not token:
                    empty_cells[header] += 1
                if header in token_shapes:
                    token_shapes[header][_token_shape(token)] += 1
        if len(row) != len(expected_headers):
            continue
        rectangular_count += 1
        key_bytes = json.dumps(
            [row[index] for index in candidate_key_indices],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        candidate_key_digest = hashlib.sha256(key_bytes).digest()
        if (
            candidate_key_digest not in candidate_keys
            and len(candidate_keys) >= MAX_CANDIDATE_KEYS
        ):
            raise ValueError("candidate key bound exceeded")
        if candidate_key_digest not in candidate_keys:
            candidate_keys.add(candidate_key_digest)
        if periods is not None:
            periods.add(
                row[cast("int", year_index)],
                row[cast("int", month_index)],
            )
        services.add(row[services_index])
        benefit.add(row[benefit_index])
    return record_count, rectangular_count


def _token_shape(token: str) -> str:
    """Classify token character shape without retaining or returning it."""
    if not token:
        return "empty"
    if any(character.isspace() for character in token):
        return "whitespace"
    if token.isascii() and token.isdigit():
        return "ascii_digits"
    if token.isascii() and token.isalpha():
        return "ascii_letters"
    if token.isascii() and token.isalnum():
        return "ascii_alphanumeric"
    return "other_nonempty"


def _parse_decimal_token(token: str) -> Decimal | None:
    if len(token) > MAX_NUMERIC_TOKEN_CHARS or not _DECIMAL_TOKEN.fullmatch(
        token
    ):
        return None
    return Decimal(token)


def _classify_invalid_token(token: str) -> str:
    """Return a disjoint lexical class without retaining the token."""
    if len(token) > MAX_NUMERIC_TOKEN_CHARS:
        category = "overlength"
    elif any(character.isspace() for character in token):
        category = "whitespace"
    elif re.fullmatch(r"[+-]?[0-9]+(?:\.[0-9]*)?[eE][+-]?[0-9]+", token):
        category = "exponent_notation"
    elif "," in token and "_" not in token:
        category = (
            "comma_triplet_pattern"
            if re.fullmatch(
                r"[+-]?[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]*)?", token
            )
            else "other_separator"
        )
    elif "_" in token and "," not in token:
        category = (
            "underscore_triplet_pattern"
            if re.fullmatch(
                r"[+-]?[0-9]{1,3}(?:_[0-9]{3})+(?:\.[0-9]*)?", token
            )
            else "other_separator"
        )
    elif "," in token or "_" in token:
        category = "other_separator"
    elif any(character.isalpha() for character in token):
        category = "alphabetic"
    else:
        category = "other_non_decimal"
    return category
