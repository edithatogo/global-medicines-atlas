"""Bounded rehearsal of the donor's historical MBS monthly endpoints.

Historical URLs are compatibility probes, not supported production releases.
Mock-only acquisition reuses the catalogue and destination/receipt controls;
successful transport alone never qualifies a table or reports acquired data.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from hashlib import sha256
from pathlib import Path
from typing import Literal

import httpx
from pydantic import Field, HttpUrl

from .acquisition import AcquisitionPolicy, Receipt, acquire_source
from .adapters._receipt import provenance_from_receipt
from .adapters.au_mbs import MbsNativeField, MbsSourceBatch, MbsSourceRecord
from .models import FrozenModel, Provenance
from .parser_safety import ParserPolicy, parse_xml
from .receipts import EvidenceClass, SourceReceipt
from .reuse_gate import ReuseGateDecision
from .source_catalog import load_source_catalog

MAX_MONTHS = 1200
MAX_TARGETS = 10000
MAX_ITEM_DIGITS = 6
MONTHS_PER_YEAR = 12
MAX_ATTEMPTS = 3
MIN_INTERVAL_SECONDS = 0.1
HISTORICAL_BASE = (
    "https://www.mbsonline.gov.au/internet/mbsonline/publishing.nsf/Content"
)
PROBE_POLICY = AcquisitionPolicy(
    timeout_seconds=30,
    max_bytes=2 * 1024 * 1024,
    max_attempts=MAX_ATTEMPTS,
    max_concurrency_per_host=1,
    max_redirects=0,
    allowed_hosts=("www.mbsonline.gov.au",),
    allowed_content_types=("text/html", "application/xhtml+xml"),
)


class LegacyMbsBatch(FrozenModel):
    """Donor fixture-era items, explicitly distinct from official MBS Data."""

    source_id: Literal["au-mbs"] = "au-mbs"
    schema_era: Literal["donor-fixture-mbs-item-v1"] = (
        "donor-fixture-mbs-item-v1"
    )
    records: tuple[MbsSourceRecord, ...] = Field(min_length=1)
    provenance: Provenance


def parse_legacy_mbs_items(
    payload: bytes, receipt: SourceReceipt
) -> LegacyMbsBatch:
    """Retain the donor's mbs/item schema without relabelling its fields."""
    provenance = provenance_from_receipt(
        receipt,
        payload,
        source_id="au-mbs",
        jurisdiction="AUS",
        transformation="donor-fixture-mbs-item-v1",
    )
    root = parse_xml(
        payload,
        policy=ParserPolicy(
            max_bytes=2 * 1024 * 1024, max_xml_depth=8, max_xml_elements=300000
        ),
    )
    if (
        root.tag != "mbs"
        or not len(root)
        or any(item.tag != "item" for item in root)
    ):
        raise ValueError("legacy MBS profile requires mbs/item records")
    records: list[MbsSourceRecord] = []
    if root.attrib or (root.text or "").strip():
        raise ValueError(
            "legacy MBS root contains unsupported attributes or text"
        )
    for ordinal, item in enumerate(root):
        if (
            item.attrib
            or (item.text or "").strip()
            or (item.tail or "").strip()
        ):
            raise ValueError(
                "legacy MBS item contains unsupported attributes or text"
            )
        if any(len(child) or child.attrib for child in item):
            raise ValueError(
                "legacy MBS fields must be scalar without attributes"
            )
        if any((child.tail or "").strip() for child in item):
            raise ValueError("legacy MBS fields contain unsupported mixed text")
        fields = tuple(
            MbsNativeField(name=child.tag, value=child.text or None)
            for child in item
        )
        item_number = next(
            (field.value for field in fields if field.name == "ItemNum"), None
        )
        if item_number is None or not item_number.strip():
            raise ValueError("legacy MBS item requires ItemNum")
        records.append(
            MbsSourceRecord(
                source_record_id=f"au-mbs:legacy:{ordinal}:{item_number}",
                source_ordinal=ordinal,
                fields=fields,
                provenance=provenance,
            )
        )
    return LegacyMbsBatch(records=tuple(records), provenance=provenance)


def select_p7_records(
    batch: MbsSourceBatch | LegacyMbsBatch,
) -> tuple[MbsSourceRecord, ...]:
    """Retain donor P7 selection over the admitted native MBS source batch."""
    return tuple(
        record for record in batch.records if record.value("Group") == "P7"
    )


def _month_index(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("month must be an integer YYYYMM")
    year, month = divmod(value, 100)
    date(year, month, 1)
    return year * MONTHS_PER_YEAR + month - 1


def month_range(start: int, end: int) -> tuple[int, ...]:
    """Return an inclusive, bounded YYYYMM range with valid calendar months."""
    first, last = _month_index(start), _month_index(end)
    if last < first or last - first >= MAX_MONTHS:
        raise ValueError("month range must be ordered and at most 1200 months")
    return tuple(
        (index // MONTHS_PER_YEAR) * 100 + index % MONTHS_PER_YEAR + 1
        for index in range(first, last + 1)
    )


@dataclass(frozen=True, slots=True)
class HistoricalTarget:
    """Validated donor request identity; paths cannot be supplied separately."""

    month: int
    item_number: str | None = None

    def __post_init__(self) -> None:
        _month_index(self.month)
        item = self.item_number
        if item is not None and (
            not item.isascii()
            or not item.isdecimal()
            or len(item) > MAX_ITEM_DIGITS
        ):
            raise ValueError("item must contain 1 to 6 ASCII digits")

    @property
    def url(self) -> str:
        """Reproduce the donor's historical URL without asserting currency."""
        stem = (
            f"item{self.item_number}"
            if self.item_number is not None
            else "participants"
        )
        return f"{HISTORICAL_BASE}/{stem}-{self.month}"

    @property
    def filename(self) -> str:
        """Preserve original item and participant naming for comparison."""
        stem = (
            f"item_{self.item_number}"
            if self.item_number is not None
            else "participants"
        )
        return f"{stem}_{self.month}.html"


def historical_targets(
    item_numbers: tuple[str, ...], start: int, end: int
) -> tuple[HistoricalTarget, ...]:
    """Build the donor's item-first then participant request sequence."""
    months = month_range(start, end)
    if len(set(item_numbers)) != len(item_numbers):
        raise ValueError("duplicate item identity")
    if (len(item_numbers) + 1) * len(months) > MAX_TARGETS:
        raise ValueError("historical request count exceeds 10000")
    return tuple(
        HistoricalTarget(month, item)
        for month in months
        for item in item_numbers
    ) + tuple(HistoricalTarget(month) for month in months)


@dataclass(frozen=True, slots=True)
class ProbeRehearsal:
    """Every attempt is retained; transport is separate from admission."""

    attempts: tuple[Receipt, ...]
    downloaded_count: int
    failed_count: int
    empty_count: int
    data_acquired: Literal[False] = field(default=False, init=False)
    qualification_status: Literal["table_admission_pending"] = field(
        default="table_admission_pending", init=False
    )


def rehearse_probes(
    targets: tuple[HistoricalTarget, ...],
    repository_root: Path,
    *,
    transport: httpx.BaseTransport,
    reuse_decision: ReuseGateDecision,
    clock: Callable[[], datetime],
    sleep: Callable[[float], None],
) -> ProbeRehearsal:
    """Exercise bounded serial acquisition using synthetic responses only.

    The required MockTransport prevents this rehearsal from downloading live
    bytes. A future hosted runner must also provide table admission and public
    publication receipts before reporting a successful monthly data update.
    """
    if not isinstance(transport, httpx.MockTransport):
        raise TypeError("rehearsal requires a synthetic MockTransport")
    if (
        not targets
        or len(targets) > MAX_TARGETS
        or len(set(targets)) != len(targets)
    ):
        raise ValueError("probe targets must be nonempty, unique and bounded")
    source = next(
        item for item in load_source_catalog() if item.source_id == "au-mbs"
    )
    attempts: list[Receipt] = []
    downloaded = 0
    empty = 0
    for target in targets:
        historical_source = source.model_copy(
            update={"download_url": HttpUrl(target.url)}
        )
        for attempt_index in range(MAX_ATTEMPTS):
            if attempts:
                sleep(MIN_INTERVAL_SECONDS)
            receipt = acquire_source(
                "au-mbs",
                Path("artifacts/mbs-compatibility") / target.filename,
                repository_root=repository_root,
                policy=PROBE_POLICY,
                catalog=(historical_source,),
                transport=transport,
                resolver=lambda _: ("8.8.8.8",),
                evidence_class=EvidenceClass.SYNTHETIC,
                clock=clock,
                reuse_decision=reuse_decision,
            )
            identity = sha256(
                f"{target.url}:{attempt_index}:{receipt.receipt_id}".encode()
            ).hexdigest()
            receipt = receipt.model_copy(
                update={
                    "receipt_id": f"mbs-rehearsal:{identity}",
                    "evidence_class": EvidenceClass.SYNTHETIC,
                }
            )
            attempts.append(receipt)
            if isinstance(receipt, SourceReceipt):
                if receipt.payload.byte_count:
                    downloaded += 1
                else:
                    empty += 1
                break
            if not receipt.retryable:
                break
    return ProbeRehearsal(
        tuple(attempts), downloaded, len(targets) - downloaded, empty
    )
