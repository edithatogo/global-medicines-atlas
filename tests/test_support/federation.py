"""Synthetic typed admission records for federation boundary tests."""

import hashlib
import json

from global_medicines_atlas.federation_admission import AdmissionRecord


def admission_record(contract: bytes) -> AdmissionRecord:
    """Bind a synthetic contract identity into the reader's typed input."""
    document = json.loads(contract)
    authority = document["authority"]
    source = document["source"]
    location = document["location"]
    return AdmissionRecord(
        producer_repository=authority["producer_repository"],
        contract_repository=authority["contract_repository"],
        contract_commit=authority["contract_commit"],
        schema_sha256=authority["schema_sha256"],
        evidence_kind=document["evidence_kind"],
        dataset=location["dataset"],
        revision=location["revision"],
        path=location["path"],
        byte_count=location["bytes"],
        sha256=location["sha256"],
        layer=source["layer"],
        bronze_stratum=source["bronze_stratum"],
        representation=source["representation"],
        source_id=source["source_id"],
        acquisition_id=source["acquisition_id"],
        schema_era=source["schema_era"],
        comparison_cohort=source["comparison_cohort"],
        effective_date=source["effective_date"],
        retrieved_at=source["retrieved_at"],
        contract_sha256=hashlib.sha256(contract).hexdigest(),
    )
