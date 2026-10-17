"""Build canonical historical source receipts for the approved MBS cohort.

This is a metadata-only reconstruction from preserved harvest receipts,
acquisition events, and the exact-scope maintainer rights decision. It does not
fetch or inspect source payload bytes, create a new acquisition, or admit data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import AnyUrl

from global_medicines_atlas.receipts import (
    AcquisitionEvent,
    DataSensitivity,
    EvidenceClass,
    PayloadEvidence,
    PersonalDataState,
    PublicationDisposition,
    RightsState,
    SensitivityClassification,
    SourceIdentity,
    SourceReceipt,
    TemporalIdentity,
    TransformationEvidence,
)

ROOT = Path(__file__).resolve().parents[1]
ACQUISITION_IMPORT = Path(
    "quality/qualifications/"
    "australian-mbs-utilisation-acquisition-import-20261004.json"
)
RAW_REFERENCE_IMPORT = Path(
    "quality/qualifications/"
    "australian-mbs-utilisation-raw-reference-import-20261004.json"
)
RIGHTS_DECISION = Path(
    "quality/qualifications/"
    "australian-mbs-utilisation-exact-scope-rights-decision-20261004.json"
)
OBJECT_RIGHTS_METADATA = Path(
    "quality/qualifications/"
    "australian-mbs-utilisation-object-rights-metadata-20261004.json"
)
RECEIPT_JOIN_AUDIT = Path(
    "quality/qualifications/"
    "australian-m112-receipt-sidecar-join-audit-20260930.json"
)
PER_OBJECT_GATES = Path(
    "quality/qualifications/"
    "australian-m112-per-object-gate-reconciliation-20261005.json"
)
QUALIFICATION = Path(
    "quality/qualifications/"
    "australian-m112-historical-source-receipts-20261017.json"
)
OUTPUT_ROOT = Path("quality/bronze/receipts/historical_imports")
RIGHTS_DECISION_COMMIT = "1bdff3ba4e0d84f29180f9ac31d9a079f242a9a7"
TRANSFORMATION_ID = "raw-acquisition-v1"
TRANSFORMATION_SHA256 = hashlib.sha256(
    TRANSFORMATION_ID.encode("utf-8")
).hexdigest()
EXPECTED_OBJECT_COUNT = 14
EXPECTED_DATASET = "edithatogo/australian-mbs-utilisation-archive"
EXPECTED_REVISION = "dee9a5b0580dfe394474dc26b372559462e157e7"
EXPECTED_MANIFEST_SHA256 = (
    "9e9848f32287cdb8141d65f2f2741916cf7e391e396ac2fcaf5794eccdaa3bab"
)
EXPECTED_SOURCE_COUNTS = {
    "au-data-gov-mbs-demographics": 10,
    "au-data-gov-mbs-group": 4,
}

SOURCE_IDENTITIES: dict[str, dict[str, str]] = {
    "au-data-gov-mbs-demographics": {
        "catalog_id": "8a19a28f-35b0-4035-8cd5-5b611b3cfa6f",
        "catalog_version": (
            "data.gov.au-package-show-sha256-"
            "f3dca2e513359dacfcb9f248b4870b7fdb96ec717d6b6f6fe793efb12232d13a"
        ),
        "dataset_title": (
            "Medicare Benefits Schedule (MBS) - Items by Patient "
            "Demographics Report"
        ),
    },
    "au-data-gov-mbs-group": {
        "catalog_id": "5335e112-d91e-47ba-b5f8-5364c8e428dc",
        "catalog_version": (
            "data.gov.au-package-show-sha256-"
            "f6246c66c58e6a82835c99b3528720076b83f55689caadd273f495fd2c8adfe7"
        ),
        "dataset_title": "Medicare Benefits Schedule (MBS) - Group Statistics Report",
    },
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pinned_rights_url() -> str:
    return (
        "https://github.com/edithatogo/global-medicines-atlas/blob/"
        f"{RIGHTS_DECISION_COMMIT}/{RIGHTS_DECISION.as_posix()}"
    )


def validate_approved_manifest_scope(  # ruff: ignore[too-many-branches] -- fail-closed rights and manifest identity validation
    rights_decision: dict[str, Any],
    rights_bytes: bytes,
    object_rights_metadata: dict[str, Any],
    receipt_join_audit: dict[str, Any],
    receipt_join_bytes: bytes,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Bind each permitted object to the maintainer-approved manifest row."""

    scope = rights_decision["scope"]
    if (
        scope["dataset"] != EXPECTED_DATASET
        or scope["revision"] != EXPECTED_REVISION
        or scope["manifest_path"] != "manifest.json"
        or scope["manifest_sha256"] != EXPECTED_MANIFEST_SHA256
    ):
        raise ValueError("rights decision manifest identity changed")
    if (
        scope["candidate_paths"] != EXPECTED_OBJECT_COUNT
        or scope["raw_paths"] != EXPECTED_OBJECT_COUNT
        or scope["projection_paths"] != 0
        or scope["source_id_counts"] != EXPECTED_SOURCE_COUNTS
    ):
        raise ValueError("rights decision no longer covers the exact cohort")
    if (
        rights_decision["disposition"]["redistribute"] != "permitted"
        or rights_decision["disposition"]["transform"]
        != "permitted_with_attribution"
        or rights_decision["disposition"]["publish_source_bytes"]
        != "permitted_for_exact_manifest_scope"
    ):
        raise ValueError("exact-scope rights decision is not permissive")

    decision_sha256 = _sha256(rights_bytes)
    if (
        object_rights_metadata["dataset"] != EXPECTED_DATASET
        or object_rights_metadata["source_revision"] != EXPECTED_REVISION
        or object_rights_metadata["manifest_sha256"] != EXPECTED_MANIFEST_SHA256
        or object_rights_metadata["rights_decision"]
        != {"path": RIGHTS_DECISION.as_posix(), "sha256": decision_sha256}
        or object_rights_metadata["historical_receipts_modified"] is not False
    ):
        raise ValueError("per-object rights metadata is not bound to approval")
    join_binding = object_rights_metadata["receipt_join_audit"]
    if join_binding["path"] != RECEIPT_JOIN_AUDIT.as_posix() or join_binding[
        "sha256"
    ] != _sha256(receipt_join_bytes):
        raise ValueError("per-object rights metadata join audit changed")
    if (
        object_rights_metadata["complete_b1_b2_lineage"] is not False
        or object_rights_metadata["v4_admission"] is not False
        or object_rights_metadata["consumer_canaries"] is not False
    ):
        raise ValueError("historical rights metadata overstates open gates")

    manifest_audit = next(
        (
            item
            for item in receipt_join_audit["datasets"]
            if item["dataset"] == EXPECTED_DATASET
        ),
        None,
    )
    if manifest_audit is None or any((
        manifest_audit["revision"] != EXPECTED_REVISION,
        manifest_audit["manifest_path"] != scope["manifest_path"],
        manifest_audit["manifest_sha256"] != EXPECTED_MANIFEST_SHA256,
        manifest_audit["raw_manifest_rows"] != EXPECTED_OBJECT_COUNT,
        manifest_audit["receipt_sidecar_count"] != EXPECTED_OBJECT_COUNT,
        manifest_audit["joined_sidecar_count"] != EXPECTED_OBJECT_COUNT,
        manifest_audit["unmatched_sidecars"] != [],
        manifest_audit["all_manifest_fields_match"] is not True,
        manifest_audit["objects_outside_authorized_source_category_or_domains"]
        != 0,
    )):
        raise ValueError(
            "receipt join audit does not prove exact manifest scope"
        )

    rights_records = object_rights_metadata["records"]
    manifest_records = manifest_audit["joined_objects"]
    if (
        len(rights_records) != EXPECTED_OBJECT_COUNT
        or len(manifest_records) != EXPECTED_OBJECT_COUNT
    ):
        raise ValueError("approved manifest object rows are incomplete")
    rights_by_path = {item["path"]: item for item in rights_records}
    manifest_by_path = {item["path"]: item for item in manifest_records}
    if (
        len(rights_by_path) != EXPECTED_OBJECT_COUNT
        or len(manifest_by_path) != EXPECTED_OBJECT_COUNT
        or rights_by_path.keys() != manifest_by_path.keys()
    ):
        raise ValueError("approved rights and manifest paths do not match")

    for path, rights_item in rights_by_path.items():
        manifest_item = manifest_by_path[path]
        if (
            rights_item["rights_state"] != "maintainer-approved-exact-object"
            or rights_item["approval_record"]
            != {"path": RIGHTS_DECISION.as_posix(), "sha256": decision_sha256}
            or rights_item["reuse"]["redistribute"] != "permitted"
            or rights_item["reuse"]["transform"] != "permitted_with_attribution"
        ):
            raise ValueError(
                f"object lacks exact-scope rights approval: {path}"
            )
        if any((
            manifest_item["path_matches_manifest"] is not True,
            manifest_item["source_id_matches_manifest"] is not True,
            manifest_item["category_matches_manifest"] is not True,
            manifest_item["sha256_matches_manifest"] is not True,
            manifest_item["byte_count_matches_manifest"] is not True,
            manifest_item["authorization_scope_match"] is not True,
        )):
            raise ValueError(f"object does not match approved manifest: {path}")
        for key in ("source_id", "category", "sha256", "byte_count"):
            if rights_item[key] != manifest_item[key]:
                raise ValueError(f"rights/manifest {key} mismatch: {path}")
    return rights_by_path, manifest_by_path


def build_receipts() -> tuple[dict[str, SourceReceipt], dict[str, Any]]:  # ruff: ignore[too-many-branches, too-many-locals, too-many-statements] -- one auditable 14-object historical join
    acquisition_bytes = (ROOT / ACQUISITION_IMPORT).read_bytes()
    reference_bytes = (ROOT / RAW_REFERENCE_IMPORT).read_bytes()
    rights_bytes = (ROOT / RIGHTS_DECISION).read_bytes()
    object_rights_bytes = (ROOT / OBJECT_RIGHTS_METADATA).read_bytes()
    receipt_join_bytes = (ROOT / RECEIPT_JOIN_AUDIT).read_bytes()
    gates_bytes = (ROOT / PER_OBJECT_GATES).read_bytes()
    acquisition_import = json.loads(acquisition_bytes)
    reference_import = json.loads(reference_bytes)
    rights_decision = json.loads(rights_bytes)
    object_rights_metadata = json.loads(object_rights_bytes)
    receipt_join_audit = json.loads(receipt_join_bytes)
    gates = json.loads(gates_bytes)
    approved_rights, approved_manifest = validate_approved_manifest_scope(
        rights_decision,
        rights_bytes,
        object_rights_metadata,
        receipt_join_audit,
        receipt_join_bytes,
    )

    acquisition_by_id = {
        item["acquisition_id"]: item for item in acquisition_import["records"]
    }
    reference_index = {
        item["path"]: item["sha256"] for item in reference_import["records"]
    }
    gate_by_path = {
        item["path"]: item
        for item in gates["objects"]
        if item["dataset"] == "edithatogo/australian-mbs-utilisation-archive"
    }
    rights_reference = _pinned_rights_url()
    receipts: dict[str, SourceReceipt] = {}
    receipt_inputs: list[dict[str, str]] = []

    for imported in acquisition_import["records"]:
        acquisition_id = imported["acquisition_id"]
        event_record = acquisition_by_id.get(acquisition_id)
        if event_record is None:
            raise ValueError(f"missing acquisition import: {acquisition_id}")
        event_bytes = (ROOT / event_record["event_path"]).read_bytes()
        if _sha256(event_bytes) != event_record["event_sha256"]:
            raise ValueError(
                f"acquisition event digest mismatch: {acquisition_id}"
            )
        event = AcquisitionEvent.model_validate_json(event_bytes)

        sidecar_path = (
            Path("quality/bronze/historical-raw-references")
            / event.source_id
            / f"{acquisition_id}.json"
        )
        sidecar_bytes = (ROOT / sidecar_path).read_bytes()
        sidecar_sha256 = _sha256(sidecar_bytes)
        if reference_index.get(sidecar_path.as_posix()) != sidecar_sha256:
            raise ValueError(
                f"raw-reference sidecar digest mismatch: {acquisition_id}"
            )
        sidecar = json.loads(sidecar_bytes)
        if sidecar["evidence_kind"] != EvidenceClass.HISTORICAL.value:
            raise ValueError(
                f"raw-reference sidecar is not historical: {acquisition_id}"
            )

        historical_receipt_info = imported["historical_receipt"]
        historical_receipt_path = Path(historical_receipt_info["local_path"])
        harvest_bytes = (ROOT / historical_receipt_path).read_bytes()
        if _sha256(harvest_bytes) != historical_receipt_info["sha256"]:
            raise ValueError(
                f"harvest receipt digest mismatch: {acquisition_id}"
            )
        harvest = json.loads(harvest_bytes)

        raw_reference = sidecar["raw_reference"]
        source_record = sidecar["source"]
        approved_rights_row = approved_rights.get(raw_reference["path"])
        approved_manifest_row = approved_manifest.get(raw_reference["path"])
        if approved_rights_row is None or approved_manifest_row is None:
            raise ValueError(
                f"object is outside the exact rights-approved manifest: {acquisition_id}"
            )
        if (
            sidecar["acquisition_event"]["sha256"]
            != event_record["event_sha256"]
        ):
            raise ValueError(
                f"sidecar acquisition identity mismatch: {acquisition_id}"
            )
        if sidecar["historical_receipt"] != historical_receipt_info:
            raise ValueError(
                f"sidecar harvest receipt mismatch: {acquisition_id}"
            )
        for key in (
            "dataset",
            "revision",
            "path",
            "sha256",
            "byte_count",
            "url",
        ):
            if imported["b2_raw_reference"].get(key) != raw_reference.get(key):
                raise ValueError(
                    f"B2 reference import mismatch ({key}): {acquisition_id}"
                )
        observed_identity = {
            "source_id": source_record["source_id"],
            "category": source_record["category"],
            "sha256": raw_reference["sha256"],
            "byte_count": raw_reference["byte_count"],
        }
        for key, observed_value in observed_identity.items():
            expected_value = approved_manifest_row[key]
            if (
                observed_value != expected_value
                or approved_rights_row.get(key) != expected_value
                or (key == "source_id" and event.source_id != expected_value)
            ):
                raise ValueError(
                    f"approved manifest object mismatch ({key}): {acquisition_id}"
                )
        if sidecar["acquisition_event"]["acquisition_id"] != acquisition_id:
            raise ValueError(
                f"source acquisition ID mismatch: {acquisition_id}"
            )
        if raw_reference["sha256"] != event.payload_sha256:
            raise ValueError(
                f"source payload digest mismatch: {acquisition_id}"
            )
        if raw_reference["byte_count"] != harvest["byte_count"]:
            raise ValueError(f"source byte count mismatch: {acquisition_id}")
        if harvest["sha256"] != event.payload_sha256:
            raise ValueError(
                f"harvest and event digest differ: {acquisition_id}"
            )
        if harvest["source_url"] != source_record["original_uri"]:
            raise ValueError(f"source URL identity mismatch: {acquisition_id}")
        if harvest["final_url"] != source_record["final_uri"]:
            raise ValueError(f"final URL identity mismatch: {acquisition_id}")
        if harvest["retrieved_at"] != source_record["retrieved_at"]:
            raise ValueError(f"retrieval time mismatch: {acquisition_id}")

        gate = gate_by_path.get(raw_reference["path"])
        if gate is None or not gate["approved_denominator_member"]:
            raise ValueError(
                f"object not in approved M-112 denominator: {acquisition_id}"
            )
        if gate["rights"]["state"] != (
            "approved_exact_scope_CC_BY_3_0_AU_publicly_readback_verified"
        ):
            raise ValueError(
                f"exact-scope rights do not match: {acquisition_id}"
            )
        if gate["rights"]["decision_evidence"]["sha256"] != _sha256(
            rights_bytes
        ):
            raise ValueError(
                f"rights decision digest mismatch: {acquisition_id}"
            )
        if (
            gate["identity"]["sha256"] != approved_manifest_row["sha256"]
            or gate["identity"]["byte_count"]
            != approved_manifest_row["byte_count"]
            or gate["path"] != approved_manifest_row["path"]
        ):
            raise ValueError(
                f"M-112 gate identity differs from approved manifest: {acquisition_id}"
            )
        if raw_reference["sha256"] != event.payload_sha256:
            raise ValueError(f"B2 content identity mismatch: {acquisition_id}")
        if raw_reference["byte_count"] != harvest["byte_count"]:
            raise ValueError(f"B2 byte count mismatch: {acquisition_id}")

        source_metadata = SOURCE_IDENTITIES.get(event.source_id)
        if source_metadata is None:
            raise ValueError(
                f"source catalog identity is not qualified: {event.source_id}"
            )
        source = SourceIdentity(
            catalog_id=source_metadata["catalog_id"],
            source_id=event.source_id,
            jurisdiction="AUS",
            authority="Services Australia",
            dataset_title=source_metadata["dataset_title"],
            catalog_version=source_metadata["catalog_version"],
        )
        retrieval = event.retrieval
        if retrieval is None:
            raise ValueError(
                f"historical acquisition lacks retrieval evidence: {acquisition_id}"
            )
        if str(retrieval.uri) != source_record["original_uri"]:
            raise ValueError(f"retrieval URI mismatch: {acquisition_id}")
        if retrieval.http is not None:
            # The source-sidecar URI and acquisition event must agree; the
            # historic event remains the source of transport observations.
            if (
                str(retrieval.http.original_uri)
                != source_record["original_uri"]
            ):
                raise ValueError(f"retrieval origin mismatch: {acquisition_id}")
            if (
                retrieval.http.final_uri is not None
                and str(retrieval.http.final_uri) != source_record["final_uri"]
            ):
                raise ValueError(
                    f"retrieval final URI mismatch: {acquisition_id}"
                )
        temporal = TemporalIdentity(
            retrieved_at=event.retrieved_at,
            source_published_at=event.source_published_at,
            source_effective_at=event.source_effective_at,
            valid_from=event.valid_from,
            valid_to=event.valid_to,
            acquisition_id=event.acquisition_id,
            content_id=event.content_id,
            source_version=event.source_version,
        )
        receipt = SourceReceipt(
            receipt_id=f"historical-import:{acquisition_id}",
            source=source,
            retrieval=retrieval,
            payload=PayloadEvidence(
                sha256=event.payload_sha256,
                byte_count=harvest["byte_count"],
            ),
            temporal=temporal,
            rights_state=RightsState.PERMITTED,
            rights_reference=AnyUrl(rights_reference),
            evidence_class=EvidenceClass.HISTORICAL,
            transformation=TransformationEvidence(
                transformation_id=TRANSFORMATION_ID,
                transformation_sha256=TRANSFORMATION_SHA256,
                output_sha256=event.payload_sha256,
                output_byte_count=harvest["byte_count"],
            ),
            sensitivity=SensitivityClassification(
                data_sensitivity=DataSensitivity.UNKNOWN,
                personal_data=PersonalDataState.UNKNOWN,
                publication=PublicationDisposition.REVIEW_REQUIRED,
                reason_codes=("historical_source_bytes_not_reinspected",),
            ),
        )
        if (
            receipt.temporal is None
            or receipt.temporal.acquisition_id != event.acquisition_id
        ):
            raise ValueError(
                f"receipt event identity mismatch: {acquisition_id}"
            )
        receipts[acquisition_id] = receipt
        receipt_inputs.append({
            "acquisition_id": acquisition_id,
            "event_path": event_record["event_path"],
            "event_sha256": event_record["event_sha256"],
            "raw_reference_sidecar_path": sidecar_path.as_posix(),
            "raw_reference_sidecar_sha256": sidecar_sha256,
            "harvest_receipt_path": historical_receipt_path.as_posix(),
            "harvest_receipt_sha256": historical_receipt_info["sha256"],
            "b2_reference": raw_reference["url"],
            "content_sha256": event.payload_sha256,
        })

    if len(receipts) != EXPECTED_OBJECT_COUNT:
        raise ValueError(
            f"expected 14 exact-scope receipts, found {len(receipts)}"
        )

    input_hashes = {
        "acquisition_import_sha256": _sha256(acquisition_bytes),
        "raw_reference_import_sha256": _sha256(reference_bytes),
        "rights_decision_sha256": _sha256(rights_bytes),
        "object_rights_metadata_sha256": _sha256(object_rights_bytes),
        "receipt_join_audit_sha256": _sha256(receipt_join_bytes),
        "per_object_gate_reconciliation_sha256": _sha256(gates_bytes),
    }
    qualification = {
        "schema_id": "global-medicines-atlas.australian-m112-historical-source-receipts",
        "schema_version": 1,
        "status": "historical_source_receipts_reconstructed_b2_and_storage_gates_open",
        "observed_at": "2026-10-17",
        "scope": {
            "approved_m112_denominator": 1759,
            "selected_exact_scope_objects": len(receipts),
            "source_payload_bytes_read": False,
            "source_payload_values_read": False,
            "new_acquisition_performed": False,
            "rights_scope_changed": False,
            "m112_admission_changed": False,
            "m112_federation_accepted": False,
        },
        "inputs": input_hashes,
        "transformation": {
            "id": TRANSFORMATION_ID,
            "sha256": TRANSFORMATION_SHA256,
            "meaning": "identity-preserving historical source acquisition",
        },
        "counts": {
            "historical_canonical_source_receipts": len(receipts),
            "live_source_receipts": 0,
            "independent_storage_receipts": 0,
            "admission_histories": 0,
        },
        "outputs": [
            {
                "acquisition_id": acquisition_id,
                "path": (
                    OUTPUT_ROOT
                    / receipts[acquisition_id].source.source_id
                    / f"{acquisition_id}.json"
                ).as_posix(),
                "sha256": receipts[acquisition_id].digest(),
                "source_id": receipts[acquisition_id].source.source_id,
                "content_sha256": receipts[acquisition_id].payload.sha256,
                "byte_count": receipts[acquisition_id].payload.byte_count,
                "evidence_class": EvidenceClass.HISTORICAL.value,
                "satisfies_live_gate": receipts[
                    acquisition_id
                ].satisfies_live_gate,
            }
            for acquisition_id in sorted(receipts)
        ],
        "source_records": receipt_inputs,
        "unresolved": [
            "independent geographic replica identity and checksum receipts",
            "RPO/RTO and inventory restore evidence",
            "v4 admission histories and consumer canaries",
            "full 1,759-object rights, lineage, and digest reconciliation",
        ],
        "boundary": (
            "Receipts are explicitly historical projections from exact source, "
            "acquisition-event, and maintainer-approved rights metadata. They "
            "are not new acquisitions, do not certify current source state, "
            "and cannot satisfy live-source gates. No raw bytes or values were "
            "read; independent storage, admission, and federation remain open."
        ),
    }
    return receipts, qualification


def render_outputs() -> dict[Path, bytes]:
    receipts, qualification = build_receipts()
    outputs: dict[Path, bytes] = {}
    for acquisition_id, receipt in receipts.items():
        path = OUTPUT_ROOT / receipt.source.source_id / f"{acquisition_id}.json"
        outputs[path] = receipt.canonical_json() + b"\n"
    outputs[QUALIFICATION] = (
        json.dumps(qualification, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    outputs = render_outputs()
    if args.check:
        mismatches = [
            path.as_posix()
            for path, expected in outputs.items()
            if not (ROOT / path).is_file()
            or (ROOT / path).read_bytes() != expected
        ]
        if mismatches:
            raise SystemExit(
                "stale or missing historical receipts: " + ", ".join(mismatches)
            )
        return 0
    for path, data in outputs.items():
        destination = ROOT / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
