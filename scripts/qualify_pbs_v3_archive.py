"""Qualify a hosted PBS v3 archive into immutable Bronze products."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import UTC, date, datetime
from pathlib import Path

from pydantic import AnyUrl

from global_medicines_atlas.adapters.au_pbs import (
    inspect_pbs_v3_tags,
    parse_pbs_v3_archive,
    pbs_v3_source_parquet,
)
from global_medicines_atlas.bronze_admission import (
    BronzeAdmissionState,
    ValidationResult,
    create_admission_decision,
)
from global_medicines_atlas.receipts import (
    AcquisitionMethod,
    AcquisitionStatus,
    DataSensitivity,
    EvidenceClass,
    HttpRetrievalEvidence,
    PayloadEvidence,
    PersonalDataState,
    PublicationDisposition,
    RetrievalEvidence,
    RightsState,
    SensitivityClassification,
    SourceIdentity,
    SourceReceipt,
    TransformationEvidence,
    require_temporal,
)
from global_medicines_atlas.reuse_gate import (
    ReuseDisposition,
    ReuseGateDecision,
)

AUTHORIZATION_REF = (
    "conductor/decisions/"
    "0009-australian-health-authority-and-public-data-plane.md#rights-and-publication-authority"
)
RIGHTS_REFERENCE = AnyUrl(
    "https://github.com/edithatogo/global-medicines-atlas/issues/340"
)


def qualify(  # ruff: ignore[too-many-locals] - atomic qualification event
    archive_path: Path,
    output_dir: Path,
    *,
    source_url: str,
    dataset: str,
    retrieved_at: datetime,
    http_metadata: dict[str, object],
) -> dict[str, object]:
    """Admit exact source bytes and write deterministic hosted-stage products."""
    archive = parse_pbs_v3_archive(archive_path.read_bytes())
    if archive.effective_date is None:
        raise ValueError("PBS effective date must be an ISO calendar date")
    try:
        effective_date = date.fromisoformat(archive.effective_date).isoformat()
    except ValueError as error:
        raise ValueError(
            "PBS effective date must be an ISO calendar date"
        ) from error
    # Use the historical source identity for this qualification context
    source_id = "au-pbs-historical-xml"
    parquet = pbs_v3_source_parquet(archive.records, source_id=source_id)
    output_dir.mkdir(parents=True, exist_ok=False)
    raw_dir = output_dir / "raw" / effective_date
    bronze_dir = output_dir / "bronze" / effective_date
    raw_dir.mkdir(parents=True)
    bronze_dir.mkdir(parents=True)
    raw_path = raw_dir / f"{effective_date}-XML-V3.zip"
    xml_path = bronze_dir / Path(archive.member.path).name
    parquet_path = bronze_dir / "pbs-v3-source.parquet"
    shutil.copyfile(archive_path, raw_path)
    xml_path.write_bytes(archive.xml_payload)
    parquet_path.write_bytes(parquet)
    payload = archive_path.read_bytes()
    payload_evidence = PayloadEvidence.from_bytes(payload)
    final_url = str(http_metadata.get("url_effective") or source_url)
    http_code = http_metadata.get("http_code")
    if not isinstance(http_code, (int, str)):
        raise TypeError("HTTP metadata must include a numeric http_code")
    receipt = SourceReceipt(
        receipt_id=(
            f"hosted-pbs-v3:{payload_evidence.sha256}:"
            f"{retrieved_at.isoformat()}"
        ),
        source=SourceIdentity(
            catalog_id="au-pbs-historical-xml",
            source_id="au-pbs-historical-xml",
            jurisdiction="AUS",
            authority="Australian Government Department of Health",
            dataset_title="Final public PBS XML v3 schedule archive",
            catalog_version=effective_date,
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl(source_url),
            retrieved_at=retrieved_at,
            acquisition_method=AcquisitionMethod.DOWNLOAD,
            status=AcquisitionStatus.SUCCEEDED,
            http=HttpRetrievalEvidence(
                original_uri=AnyUrl(source_url),
                final_uri=AnyUrl(final_url),
                http_method="GET",
                http_status=int(http_code),
                content_type=str(http_metadata.get("content_type") or "")
                or None,
                observed_byte_length=payload_evidence.byte_count,
                source_native_version=effective_date,
                source_native_date=datetime.combine(
                    date.fromisoformat(effective_date),
                    datetime.min.time(),
                    tzinfo=UTC,
                ),
                acquisition_agent_version="curl-hosted-pbs-v1",
            ),
        ),
        payload=payload_evidence,
        reuse=ReuseGateDecision(
            source_id="au-pbs-historical-xml",
            disposition=ReuseDisposition.MIRROR,
            searched_surfaces=(
                "local_clones",
                "github",
                "hugging_face",
                "source_registry",
            ),
            candidates=(),
            rationale=(
                "Mirror the final official public PBS XML v3 archive into the "
                "approved hosted-only public recovery plane."
            ),
        ),
        rights_state=RightsState.PERMITTED,
        rights_reference=RIGHTS_REFERENCE,
        sensitivity=SensitivityClassification(
            data_sensitivity=DataSensitivity.NON_SENSITIVE,
            personal_data=PersonalDataState.NONE,
            publication=PublicationDisposition.PERMITTED,
            reason_codes=("official_public_schedule", "decision_0009"),
        ),
        evidence_class=EvidenceClass.LIVE,
        transformation=TransformationEvidence(
            transformation_id="au-pbs-v3-source-parquet-v2",
            # Bind both the qualification script and the adapter implementation
            transformation_sha256=hashlib.sha256(
                Path(__file__).read_bytes()
                + b"
                + (
                    Path(__file__).parent.parent
                    / "src/global_medicines_atlas/adapters/au_pbs.py"
                ).read_bytes()
            output_sha256=hashlib.sha256(parquet).hexdigest(),
            output_byte_count=len(parquet),
        ),
    )
    temporal = require_temporal(receipt.temporal)
    if temporal.content_id is None:
        raise ValueError("source receipt must bind a content identity")
    admission = create_admission_decision(
        acquisition_id=temporal.acquisition_id,
        content_id=temporal.content_id,
        state=BronzeAdmissionState.ACCEPTED,
        reason_codes=("official_archive_parsed", "effective_date_valid"),
        validation_results=(
            ValidationResult(
                check_id="pbs-v3-archive",
                passed=True,
                message="official PBS v3 archive and XML member parsed",
            ),
            ValidationResult(
                check_id="source-effective-date",
                passed=True,
                message=f"source effective date is {effective_date}",
            ),
            ValidationResult(
                check_id="source-faithful-parquet",
                passed=True,
                message=f"projected {len(archive.records)} source records",
            ),
        ),
        decided_at=retrieved_at,
    )
    receipt_path = bronze_dir / "source-receipt.json"
    admission_path = bronze_dir / "admission.json"
    receipt_path.write_text(receipt.model_dump_json(indent=2) + "\n")
    admission_path.write_text(admission.model_dump_json(indent=2) + "\n")
    manifest: dict[str, object] = {
        "schema_id": "global-medicines-atlas.australian-pbs-source-archive",
        "schema_version": 1,
        "source_id": "au-pbs-historical-xml",
        "source_url": source_url,
        "source_effective_date": archive.effective_date,
        "destination_dataset": dataset,
        "authorization_ref": AUTHORIZATION_REF,
        "archive": {
            "path": raw_path.relative_to(output_dir).as_posix(),
            "sha256": archive.archive_sha256,
            "size_bytes": raw_path.stat().st_size,
        },
        "member": {
            "source_path": archive.member.path,
            "path": xml_path.relative_to(output_dir).as_posix(),
            "sha256": archive.member.sha256,
            "size_bytes": archive.member.size_bytes,
        },
        "source_parquet": {
            "path": parquet_path.relative_to(output_dir).as_posix(),
            "sha256": hashlib.sha256(parquet).hexdigest(),
            "size_bytes": len(parquet),
        },
        "source_receipt": {
            "path": receipt_path.relative_to(output_dir).as_posix(),
            "sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
            "acquisition_id": temporal.acquisition_id,
            "retrieved_at": retrieved_at.isoformat(),
        },
        "admission": {
            "path": admission_path.relative_to(output_dir).as_posix(),
            "sha256": hashlib.sha256(admission_path.read_bytes()).hexdigest(),
            "decision_id": admission.decision_id,
            "state": admission.state.value,
        },
        "namespace_uri": archive.namespace_uri,
        "record_count": len(archive.records),
        "tag_sample": list(inspect_pbs_v3_tags(archive.xml_payload)),
        "raw_bytes_are_source_of_truth": True,
        "parquet_is_rebuildable_projection": True,
        "amt_terminology_bytes_included": False,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    (output_dir / "README.md").write_text(
        "---\npretty_name: Australian PBS source archive\n"
        "license: other\n---\n\n"
        "# Australian PBS source archive\n\n"
        "Exact final public PBS XML v3 schedule archive and receipt-bound "
        "Bronze projections. PBS listing is funding/formulary evidence, not "
        "Australian regulatory approval. The source-native ZIP and XML are "
        "evidentiary truth; Parquet is rebuildable. Redistribution authority "
        f"is recorded in `{AUTHORIZATION_REF}`.\n"
    )
    return manifest


def main() -> int:
    """Run the hosted qualification command."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--retrieved-at", required=True)
    parser.add_argument("--http-metadata", required=True, type=Path)
    arguments = parser.parse_args()
    retrieved_at = datetime.fromisoformat(arguments.retrieved_at)
    if retrieved_at.tzinfo is None:
        raise ValueError("--retrieved-at must include a timezone")
    manifest = qualify(
        arguments.archive,
        arguments.output,
        source_url=arguments.source_url,
        dataset=arguments.dataset,
        retrieved_at=retrieved_at,
        http_metadata=json.loads(arguments.http_metadata.read_text()),
    )
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
