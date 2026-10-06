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
EXPECTED_CSV_SOURCE_COUNT = 4
_DECIMAL_TOKEN = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)\Z")


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
    services: NumericObservation
    benefit: NumericObservation

    def to_public_summary(self) -> dict[str, Any]:
        """Serialize reviewed headers and aggregate findings only."""
        return {
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
            "numeric_observations": {
                SERVICES_HEADER: self.services.to_public_summary(),
                BENEFIT_HEADER: self.benefit.to_public_summary(),
            },
            "semantic_mapping_selected": False,
            "processing_admitted": False,
            "silver_published": False,
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
        })
    return bound


def observe_utilisation_csv_values(
    path: Path, *, expected_headers: tuple[str, ...]
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
    size = path.stat().st_size
    if size <= 0 or size > MAX_CSV_BYTES:
        raise ValueError("CSV byte limit exceeded")

    empty_cells = dict.fromkeys(expected_headers, 0)
    services = _NumericCounters()
    benefit = _NumericCounters()
    old_limit = csv.field_size_limit()
    csv.field_size_limit(MAX_CSV_FIELD_BYTES)
    try:
        with path.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.reader(source, strict=True)
            record_count, rectangular_count = _observe_rows(
                reader, expected_headers, empty_cells, services, benefit
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
        services=services.freeze(),
        benefit=benefit.freeze(),
    )


def _observe_rows(
    reader: Iterator[list[str]],
    expected_headers: tuple[str, ...],
    empty_cells: dict[str, int],
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
    record_count = 0
    rectangular_count = 0
    for row in reader:
        record_count += 1
        if record_count > MAX_CSV_ROWS:
            raise ValueError("CSV row limit exceeded")
        for index, header in enumerate(expected_headers):
            if index < len(row) and not row[index]:
                empty_cells[header] += 1
        if len(row) != len(expected_headers):
            continue
        rectangular_count += 1
        services.add(row[services_index])
        benefit.add(row[benefit_index])
    return record_count, rectangular_count


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
