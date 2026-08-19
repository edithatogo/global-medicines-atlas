"""Receipt-backed acquisition entry points for United States sources."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from ..acquisition import (
    AcquisitionPolicy,
    Clock,
    Receipt,
    acquire_source,
)
from ..receipts import EvidenceClass
from ..reuse_gate import (
    ReuseGateDecision,
    evaluate_reuse_gate,
    require_reuse_decision,
)
from ..source_catalog import (
    AccessMode,
    MedicineDataSource,
    load_source_catalog,
)

if TYPE_CHECKING:
    import httpx

DRUGSFDA_BULK_URL = "https://www.fda.gov/media/89850/download?attachment"
DRUGSFDA_API_URL = "https://api.fda.gov/drug/drugsfda.json?limit=100"
DRUGSFDA_ACQUISITION_POLICY = AcquisitionPolicy(
    allowed_hosts=("api.fda.gov", "www.fda.gov")
)


def _drugsfda_source(
    *,
    access_mode: AccessMode,
    uri: str,
    catalog: Iterable[MedicineDataSource] | None,
) -> MedicineDataSource:
    sources = load_source_catalog() if catalog is None else tuple(catalog)
    matches = [
        source for source in sources if source.source_id == "us-drugsfda"
    ]
    if len(matches) != 1:
        raise LookupError(
            "catalog source_id must resolve exactly once: us-drugsfda"
        )
    source = matches[0]
    updates: dict[str, object] = {"access_mode": access_mode}
    if access_mode is AccessMode.API:
        updates.update(api_url=uri, download_url=None)
    else:
        updates.update(download_url=uri, api_url=None)
    return source.model_copy(update=updates)


def _drugsfda_reuse_decision(
    decision: ReuseGateDecision | None,
    *,
    search_root: Path,
    catalog: Iterable[MedicineDataSource] | None,
) -> ReuseGateDecision:
    """Search the ecosystem before any Drugs@FDA download."""

    if decision is not None:
        return require_reuse_decision(decision, "us-drugsfda")
    return evaluate_reuse_gate(
        "us-drugsfda",
        repository_root=search_root,
        catalog=catalog,
    )


def acquire_drugsfda_bulk(
    destination: Path,
    *,
    repository_root: Path,
    bulk_url: str = DRUGSFDA_BULK_URL,
    policy: AcquisitionPolicy = DRUGSFDA_ACQUISITION_POLICY,
    catalog: Iterable[MedicineDataSource] | None = None,
    transport: httpx.BaseTransport | None = None,
    evidence_class: EvidenceClass = EvidenceClass.FIXTURE,
    clock: Clock = lambda: datetime.now(UTC),
    reuse_decision: ReuseGateDecision | None = None,
    reuse_search_root: Path | None = None,
) -> Receipt:
    """Acquire the official Drugs@FDA bulk archive with a durable receipt."""
    source = _drugsfda_source(
        access_mode=AccessMode.DOWNLOAD,
        uri=bulk_url,
        catalog=catalog,
    )
    decision = _drugsfda_reuse_decision(
        reuse_decision,
        search_root=reuse_search_root or repository_root,
        catalog=catalog,
    )
    return acquire_source(
        "us-drugsfda",
        destination,
        repository_root=repository_root,
        policy=policy,
        catalog=(source,),
        transport=transport,
        evidence_class=evidence_class,
        clock=clock,
        reuse_decision=decision,
    )


def acquire_drugsfda_api(
    destination: Path,
    *,
    repository_root: Path,
    api_url: str = DRUGSFDA_API_URL,
    policy: AcquisitionPolicy = DRUGSFDA_ACQUISITION_POLICY,
    catalog: Iterable[MedicineDataSource] | None = None,
    transport: httpx.BaseTransport | None = None,
    evidence_class: EvidenceClass = EvidenceClass.FIXTURE,
    clock: Clock = lambda: datetime.now(UTC),
    reuse_decision: ReuseGateDecision | None = None,
    reuse_search_root: Path | None = None,
) -> Receipt:
    """Acquire one bounded openFDA Drugs@FDA response with a durable receipt."""
    source = _drugsfda_source(
        access_mode=AccessMode.API,
        uri=api_url,
        catalog=catalog,
    )
    decision = _drugsfda_reuse_decision(
        reuse_decision,
        search_root=reuse_search_root or repository_root,
        catalog=catalog,
    )
    return acquire_source(
        "us-drugsfda",
        destination,
        repository_root=repository_root,
        policy=policy,
        catalog=(source,),
        transport=transport,
        evidence_class=evidence_class,
        clock=clock,
        reuse_decision=decision,
    )
