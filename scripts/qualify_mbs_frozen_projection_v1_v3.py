"""Build four value-free projection profiles and v3 registration receipts.

All inputs are hash-bound repository metadata or fixed Git code blobs. V3
plans are reconstructed and schema-validated in memory, not persisted. The
source v1 document restates an existing raw B2 decision; no projection or new
source is admitted, no payloads are read, and no dataset is published.
"""

from __future__ import annotations

import argparse
import copy
from dataclasses import asdict
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import scripts.prepare_mbs_august_projection_admission as preparation
import scripts.qualify_mbs_august_projection_field_lineage as lineage
import scripts.qualify_mbs_august_projection_replay as replay
import scripts.qualify_mbs_frozen_projection_roles as previous
from jsonschema import Draft202012Validator

from global_medicines_atlas.mbs_projection_role_profile import (
    PROFILE_SCHEMA_SHA256,
    RECEIPT_SCHEMA_SHA256,
    RECIPE_LINEAGE_BUILDER,
    RECIPE_PLAN_BUILDER,
    RECIPE_V3_BUILDER,
    MetadataReference,
    ObjectIdentity,
    ProjectionEvidence,
    ProjectionRoleTrust,
    verify_v1_projection_profile,
    verify_v3_registration_receipt,
)

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = (
    "quality/qualifications/australian-mbs-frozen-projection-v1-v3-20261116"
)
SOURCE_V1 = f"{DIRECTORY}/source-v1-conformance.json"
REPORT = f"{DIRECTORY}/qualification.json"
PROFILE_SCHEMA = (
    "contracts/medallion/v1-projection/projection-profile.schema.json"
)
RECEIPT_SCHEMA = (
    "contracts/medallion/v3-registration/metadata-receipt.schema.json"
)
RAW_ADMISSION = "quality/bronze/admissions/au-mbs/fd32879190b69ad98cd2f207ec3b70b725ab8f524218f783ec08bf98b7ffcecd/39df4d1a14f1b90d1be41ae9e1fab7b99c9c75385f735b00831c8c199a1350f0.json"
RAW_ADMISSION_SHA = (
    "25dcc63b950ee330b28cfdd66747e4708891701703f8a91bda3c3b569d5fee7a"
)
RAW_CONTRACT = "quality/qualifications/australian-mbs-august-frozen-v4-20261115/canonical-contract.json"
RAW_CONTRACT_SHA = (
    "426eacd374a60cdff95e05047d5498ce80e5f0420e93df905ebb90f23b8299cc"
)
RAW_HOSTED = "quality/qualifications/australian-mbs-august-frozen-v4-20261115/hosted-43705630353/qualification.json"
RAW_HOSTED_SHA = (
    "42b38094fe116f9aaaadf1a88264a95a3ca8c0b3102dacb10d333897adf9ff29"
)
RAW_AUTHORIZATION = "quality/qualifications/australian-mbs-harvest-publication-authorization.json"
RAW_AUTHORIZATION_SHA = (
    "0fdc4d147d637c679ba0cc3eb165642974e533bb3ba044c99ee01f86127eb41b"
)
PRIOR_REPORT_SHA = (
    "e562f4652599a0e03a1c000da5837b1db84180b807c0854506747a882715eeeb"
)
RAW_ACQUISITION = (
    "fd32879190b69ad98cd2f207ec3b70b725ab8f524218f783ec08bf98b7ffcecd"
)
RECEIPT_ADAPTER = "src/global_medicines_atlas/adapters/_receipt.py"
RECEIPT_ADAPTER_SHA = (
    "afa94ba955c4723b275addb0b55200636aaf82eeaabcd5ac0b23aefcf2684020"
)
PBS_LINEAGE = "quality/qualifications/australian-m112-reimbursement-medallion-projection-lineage-20261019.json"
PBS_LINEAGE_SHA = (
    "a9146e11c71f3d031135dc395d84589497a4aa50e9e10f15acbca08498fc7f97"
)
PBS_PRIVACY = (
    "quality/qualifications/australian-pbs-unmatched-provenance-20261116.json"
)
PBS_PRIVACY_SHA = (
    "cf311f72d259b3b228ed7aac7294ea13f6f539e077b46be5d408c0f2f3991cd5"
)
PBS_RECEIPT_READBACK = "quality/qualifications/australian-pbs-m107-known-object-manifest-readback-20261018.json"
PBS_RECEIPT_READBACK_SHA = (
    "2d98096e51f498a8c243f0ca34601da1041973ce24dc9a931b88d683a8eb0a6b"
)
PLAN_BUILDER = RECIPE_PLAN_BUILDER
V3_BUILDER = RECIPE_V3_BUILDER
LINEAGE_BUILDER = RECIPE_LINEAGE_BUILDER


def require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def ref(path: str, digest: str) -> dict[str, str]:
    return {"path": path, "sha256": digest}


def identity(row: dict[str, Any]) -> ObjectIdentity:
    return ObjectIdentity(**{key: row[key] for key in preparation.IDENTITY})


def source_v1(root: Path) -> tuple[dict[str, Any], ObjectIdentity]:
    """Restate the existing raw decision as an adjacent v1 source transition."""
    old = previous.checked_json(root, previous.V1, previous.V1_SHA)
    raw_contract = previous.checked_json(root, RAW_CONTRACT, RAW_CONTRACT_SHA)
    hosted = previous.checked_json(root, RAW_HOSTED, RAW_HOSTED_SHA)
    admission = previous.checked_json(root, RAW_ADMISSION, RAW_ADMISSION_SHA)
    raw = identity({
        "dataset": raw_contract["location"]["dataset"],
        "revision": raw_contract["location"]["revision"],
        "path": raw_contract["location"]["path"],
        "sha256": raw_contract["location"]["sha256"],
        "byte_count": raw_contract["location"]["bytes"],
    })
    source_id = f"m112:{raw.dataset}@{raw.revision}:{raw.path}"
    matches = [a for a in old["artifacts"] if a["artifact_id"] == source_id]
    hosted_objects = [o for o in hosted["objects"] if o["path"] == raw.path]
    source = raw_contract["source"]
    rights = raw_contract["rights"]
    require(
        raw.dataset == lineage.DATASET
        and raw.revision == lineage.FROZEN_REVISION
        and raw.path == lineage.SOURCE
        and raw.sha256 == lineage.SOURCE_SHA
        and raw.byte_count == lineage.SOURCE_BYTES
        and source["acquisition_id"] == RAW_ACQUISITION
        and source["representation"] == "raw"
        and source["bronze_stratum"] == "B2"
        and rights["dataset"] == raw.dataset
        and rights["path"] == raw.path
        and rights["subject_sha256"] == raw.sha256
        and rights["publication"] == "approved_exact_scope"
        and rights["sensitivity"] == "non_sensitive"
        and rights["basis"]
        == "maintainer_attested_exact_scope_permission_not_independently_reviewed"
        and admission["state"] == "accepted"
        and admission["reviewer_status"] == "unreviewed"
        and admission["acquisition_id"] == RAW_ACQUISITION
        and admission["content_id"] == raw.sha256
        and hosted["status"] == "passed"
        and len(hosted_objects) == 1
        and hosted_objects[0]["contract_sha256"] == RAW_CONTRACT_SHA
        and hosted_objects[0]["admission"]["sha256"] == raw.sha256
        and hosted_objects[0]["admission"]["acquisition_id"] == RAW_ACQUISITION
        and len(matches) == 1,
        "existing raw source decision or identity differs",
    )
    artifact = copy.deepcopy(matches[0])
    require(
        artifact["sha256"] == raw.sha256
        and artifact["layer"] == "bronze_b2"
        and artifact["lineage"]
        == {
            "input_artifact_ids": [f"b1-acquisition:{RAW_ACQUISITION}"],
            "input_sha256": [raw.sha256],
        }
        and artifact["rights_decision"]["status"] == "approved",
        "existing raw v1 artifact differs",
    )
    artifact["promotion_status"] = "approved_within_scope"
    gates = [
        "existing_raw_b2_acceptance",
        "existing_exact_source_rights",
        "source_b1_b2_lineage",
    ]
    decision = {
        "decision_id": f"restated-raw-b1-b2:{raw.sha256}:2026-11-16",
        "subject_artifact_id": source_id,
        "from_layer": "bronze_b1",
        "to_layer": "bronze_b2",
        "input_sha256": [raw.sha256],
        "required_gate_ids": gates,
        "passed_gate_ids": gates,
        "rights_decision": artifact["rights_decision"],
        "status": "approved",
        "fail_closed": True,
        "reason_codes": [
            "restates_existing_accepted_raw_source_not_projection"
        ],
    }
    document = {
        "vocabulary_version": "1.0.0",
        "repository": "global-medicines-atlas",
        "artifacts": [artifact],
        "promotion_decisions": [decision],
    }
    schema = previous.checked_schema(
        root, previous.V1_SCHEMA, previous.V1_SCHEMA_SHA
    )
    Draft202012Validator(schema).validate(document)  # pyright: ignore[reportUnknownMemberType]
    require(
        not previous.semantic_errors(document),
        "restated raw v1 is nonconformant",
    )
    return document, raw


def privacy_context(root: Path, producer: str) -> dict[str, Any]:
    """Check only URI components and fixed public-safe source metadata."""
    receipt = previous.checked_json(
        root, *lineage.INPUTS["receipt_" + producer]
    )
    uri_text: str = receipt["retrieval"]["uri"]
    uri = urlsplit(uri_text)
    require(
        receipt["payload"]["sha256"] == lineage.SOURCE_SHA
        and receipt["sensitivity"]["personal_data"] == "none"
        and receipt["sensitivity"]["data_sensitivity"] == "non_sensitive",
        "source sensitivity context differs",
    )
    previous.check_code(
        root,
        str(lineage.PRODUCERS[producer]["commit"]),
        {
            RECEIPT_ADAPTER: RECEIPT_ADAPTER_SHA,
        },
    )
    return {
        "uri_scheme_https": uri.scheme == "https",
        "uri_userinfo_present": bool(uri.username or uri.password),
        "uri_query_present": bool(uri.query),
        "uri_fragment_present": bool(uri.fragment),
        "historical_provenance_preserves_source_uri": True,
        "source_receipt_classification": "non_sensitive_source_only",
        "output_privacy": "unknown_output_values_not_screened",
    }


def pbs_privacy_context(root: Path) -> dict[str, Any]:
    """Bind the prior PBS Bronze source state without transferring it to output."""
    report = previous.checked_json(root, PBS_LINEAGE, PBS_LINEAGE_SHA)
    privacy = previous.checked_json(root, PBS_PRIVACY, PBS_PRIVACY_SHA)
    readback = previous.checked_json(
        root, PBS_RECEIPT_READBACK, PBS_RECEIPT_READBACK_SHA
    )
    source = report["pbs_source_parquet_lineage"]
    matching = [
        row
        for row in privacy["objects"]
        if row["kind"] == "pbs_bronze_projection"
    ]
    require(
        len(matching) == 1
        and source["projection_path"] == matching[0]["path"]
        and source["projection_sha256"] == matching[0]["sha256"]
        and source["projection_byte_count"] == matching[0]["byte_count"]
        and source["dataset"] == matching[0]["dataset"]
        and source["revision"] == matching[0]["revision"]
        and source["source_of_truth_sha256"]
        == matching[0]["source_archive_sha256"]
        and source["source_admission_state"] == "accepted"
        and source["source_rights_evidence"] == "permitted"
        and readback["dataset"] == source["dataset"]
        and readback["revision"] == source["revision"]
        and readback["source_receipt"]["path"] == source["source_receipt_path"]
        and readback["source_receipt"]["sha256"]
        == source["source_receipt_sha256"]
        and readback["source_receipt"]["acquisition_id"]
        == source["source_b1_acquisition_id"]
        and readback["source_receipt_metadata_readback"]["sha256"]
        == source["source_receipt_sha256"]
        and readback["source_receipt_metadata_readback"]["anonymous"] is True
        and readback["source_receipt"]["rights_state_claimed_by_receipt"]
        == "permitted"
        and readback["bronze_admission"]["sha256"]
        == source["source_admission_sha256"]
        and readback["bronze_admission"]["state"] == "accepted"
        and "sensitivity" not in readback["source_receipt"]
        and matching[0]["ready_for_payload_read"] is False,
        "PBS Bronze provenance or privacy differs",
    )
    return {
        "projection": {key: matching[0][key] for key in preparation.IDENTITY},
        "source_archive_sha256": source["source_of_truth_sha256"],
        "existing_source_parser_admission": "accepted_not_output_privacy_clearance",
        "existing_source_rights": "permitted_not_output_privacy_clearance",
        "source_receipt_readback": ref(
            PBS_RECEIPT_READBACK, PBS_RECEIPT_READBACK_SHA
        ),
        "source_receipt_sensitivity": "not_in_retained_metadata_readback",
        "output_privacy": "unknown_output_values_not_screened",
        "producer_code_identity": "not_bound_by_this_evidence",
    }


def reconstruct_plan(
    root: Path, receipt: dict[str, Any]
) -> tuple[bytes, dict[str, Any]]:
    """Rebuild the committed v3 plan using only pinned metadata and code."""
    recipe = {
        "recipe": "mbs-august-v3-metadata-registration-v1",
        "python": "3.15.1",
        "lineage_report": ref(*preparation.INPUTS["lineage"]),
        "plan_builder": ref(*PLAN_BUILDER),
        "v3_builder": ref(*V3_BUILDER),
        "lineage_builder": ref(*LINEAGE_BUILDER),
    }
    require(
        receipt["reconstruction"] == recipe, "v3 reconstruction recipe differs"
    )
    for path, digest in (PLAN_BUILDER, V3_BUILDER, LINEAGE_BUILDER):
        require(
            previous.sha((root / path).read_bytes()) == digest,
            "v3 builder code differs",
        )
    lineage_report = previous.checked_json(root, *preparation.INPUTS["lineage"])
    prior_report = previous.checked_json(root, *preparation.INPUTS["replay"])
    subject = receipt["projection"]
    rows = [
        row
        for row in lineage_report["objects"]
        if row["path"] == subject["path"]
    ]
    priors = [
        row for row in prior_report["objects"] if row["path"] == subject["path"]
    ]
    require(
        len(rows) == len(priors) == 1
        and rows[0]["frozen_member"] is True
        and all(
            rows[0][key] == priors[0][key] == value
            for key, value in subject.items()
        )
        and receipt["prior_replay"] == ref(*preparation.INPUTS["replay"])
        and receipt["v2_lineage"] == ref(*preparation.INPUTS["v2"]),
        "v3 reconstruction subject differs",
    )
    rebuilt = replay._plan(  # pyright: ignore[reportPrivateUsage]
        root, rows[0], priors[0]["source"], receipt["v2_lineage"]["sha256"]
    )
    plan_bytes = previous.serialized(rebuilt["plan"])
    require(
        previous.sha(plan_bytes) == receipt["reconstructed_plan_sha256"],
        "reconstructed v3 plan differs",
    )
    return plan_bytes, rebuilt["metadata"]


def _check_prior_report(root: Path) -> None:
    old_report = previous.checked_json(root, previous.REPORT, PRIOR_REPORT_SHA)
    require(
        len(old_report["objects"]) == preparation.FROZEN_COUNT,
        "prior frozen report differs",
    )


def assemble(  # ruff: ignore[too-many-locals] -- separate frozen evidence roles
    root: Path = ROOT,
) -> tuple[dict[str, bytes], list[dict[str, Any]]]:
    """Produce receipts and in-memory verifier inputs from existing metadata."""
    _check_prior_report(root)
    evidence = preparation.load(root)
    preparation.reconcile(evidence)
    vocabulary, crosswalk = lineage.build(root)
    v2_bytes = (root / lineage.OUTPUT).read_bytes()
    require(previous.serialized(vocabulary) == v2_bytes, "v2 bytes differ")
    plans = {row["path"]: row for row in evidence["replay"]["objects"]}
    sources = replay._sources(root)  # pyright: ignore[reportPrivateUsage]
    raw_source = sources["f9f9"]
    require(
        raw_source["acquisition_id"] == RAW_ACQUISITION,
        "raw acquisition differs",
    )
    source_document, raw = source_v1(root)
    source_bytes = previous.serialized(source_document)
    source_ref = ref(SOURCE_V1, previous.sha(source_bytes))
    v2_ref = ref(*preparation.INPUTS["v2"])
    replay_ref = ref(*preparation.INPUTS["replay"])
    raw_admission_ref = ref(RAW_ADMISSION, RAW_ADMISSION_SHA)
    outputs: dict[str, bytes] = {SOURCE_V1: source_bytes}
    packets: list[dict[str, Any]] = []
    for row in crosswalk["objects"]:
        if not row["frozen_member"]:
            continue
        names = [
            name
            for name in ("6bc9", "99fa")
            if str(lineage.PRODUCERS[name]["id"]) in row["path"]
        ]
        require(len(names) == 1, "frozen producer identity differs")
        name = names[0]
        producer = lineage.PRODUCERS[name]
        source = sources[name]
        previous.check_code(
            root, str(producer["commit"]), lineage.code_hashes(name)
        )
        packet = replay._plan(root, row, source, v2_ref["sha256"])  # pyright: ignore[reportPrivateUsage]
        registration = replay._register(packet["plan"], packet["metadata"])  # pyright: ignore[reportPrivateUsage]
        require(
            registration
            == replay._register(packet["plan"], packet["metadata"]),  # pyright: ignore[reportPrivateUsage]
            "registration differs",
        )
        plan_bytes = previous.serialized(packet["plan"])
        prior = plans[row["path"]]
        require(
            all(row[k] == prior[k] for k in preparation.IDENTITY)
            and previous.sha(plan_bytes) == prior["plan"]["sha256"]
            and replay._hash(registration) == prior["registration_sha256"],  # pyright: ignore[reportPrivateUsage]
            "prior v3 replay binding differs",
        )
        projection = identity(row)
        profile = {
            "schema_id": "global-medicines-atlas.v1-b2-projection-profile",
            "schema_version": 1,
            "source": asdict(raw)
            | {
                "acquisition_id": RAW_ACQUISITION,
                "representation": "raw",
                "stratum": "B2",
                "artifact_id": source_document["artifacts"][0]["artifact_id"],
                "acquisition_event": raw_source["event"],
                "b2_reference": raw_source["b2"],
            },
            "projection": asdict(projection)
            | {"representation": "projection", "stratum": "B2"},
            "producer": {
                "commit": producer["commit"],
                "acquisition_id": source["acquisition_id"],
                "event": source["event"],
                "b2_reference": source["b2"],
                "source_receipt": row["source_receipt"],
                "reconstructed_event": source["reconstructed_now"],
            },
            "source_rights_context": {
                "basis": "maintainer_attested_exact_scope",
                "instrument_independently_reviewed": False,
                "scope": "raw_source_only",
                "new_decision": False,
                "authorization": ref(RAW_AUTHORIZATION, RAW_AUTHORIZATION_SHA),
                "source_contract": ref(RAW_CONTRACT, RAW_CONTRACT_SHA),
            },
            "source_v1": source_ref,
            "v2_lineage": v2_ref,
            "raw_admission": raw_admission_ref,
            "projection_rights": row["rights_evidence"],
            "derivation": {
                "kind": "same_stratum_source_faithful_projection",
                "is_promotion": False,
                "producer_and_reference_acquisitions_are_distinct": True,
            },
            "boundaries": {
                "new_source_admission": False,
                "projection_admission": False,
                "output_privacy_cleared": False,
                "source_or_projection_payload_read": False,
                "dataset_publication": False,
            },
        }
        receipt = {
            "schema_id": "global-medicines-atlas.v3-metadata-registration-receipt",
            "schema_version": 1,
            "projection": asdict(projection),
            "producer_acquisition_id": source["acquisition_id"],
            "source_sha256": lineage.SOURCE_SHA,
            "source_event": source["event"],
            "source_b2": source["b2"],
            "source_receipt": row["source_receipt"],
            "projection_rights": row["rights_evidence"],
            "v2_lineage": v2_ref,
            "prior_replay": replay_ref,
            "reconstructed_plan_sha256": prior["plan"]["sha256"],
            "registration_sha256": prior["registration_sha256"],
            "metadata_sha256": packet["plan"]["snapshots"][0][
                "metadata_sha256"
            ],
            "reconstruction": {
                "recipe": "mbs-august-v3-metadata-registration-v1",
                "python": "3.15.1",
                "lineage_report": ref(*preparation.INPUTS["lineage"]),
                "plan_builder": ref(*PLAN_BUILDER),
                "v3_builder": ref(*V3_BUILDER),
                "lineage_builder": ref(*LINEAGE_BUILDER),
            },
            "replay_schema_sha256": previous.V3_SCHEMA_SHA,
            "scope": "deterministic_metadata_registration_only",
            "boundaries": {
                "source_or_projection_payload_read": False,
                "payload_replayed": False,
                "projection_admission": False,
                "consumer_canary": False,
                "dataset_publication": False,
            },
        }
        profile_bytes, receipt_bytes = (
            previous.serialized(profile),
            previous.serialized(receipt),
        )
        prefix = f"{DIRECTORY}/{name}-{Path(row['path']).stem}"
        profile_path, receipt_path = (
            f"{prefix}-v1-profile.json",
            f"{prefix}-v3-receipt.json",
        )
        outputs[profile_path], outputs[receipt_path] = (
            profile_bytes,
            receipt_bytes,
        )
        trust = ProjectionRoleTrust(
            source=raw,
            projection=projection,
            source_acquisition_id=RAW_ACQUISITION,
            source_event=MetadataReference(**raw_source["event"]),
            source_b2=MetadataReference(**raw_source["b2"]),
            source_authorization=MetadataReference(
                RAW_AUTHORIZATION, RAW_AUTHORIZATION_SHA
            ),
            source_contract=MetadataReference(RAW_CONTRACT, RAW_CONTRACT_SHA),
            producer_acquisition_id=source["acquisition_id"],
            producer_commit=str(producer["commit"]),
            producer_event=MetadataReference(**source["event"]),
            producer_b2=MetadataReference(**source["b2"]),
            producer_receipt=MetadataReference(**row["source_receipt"]),
            producer_event_reconstructed=source["reconstructed_now"],
            source_v1=MetadataReference(**source_ref),
            v2_lineage=MetadataReference(**v2_ref),
            source_admission=MetadataReference(**raw_admission_ref),
            prior_replay=MetadataReference(**replay_ref),
            lineage_report=MetadataReference(*preparation.INPUTS["lineage"]),
            plan_builder=MetadataReference(*PLAN_BUILDER),
            v3_builder=MetadataReference(*V3_BUILDER),
            lineage_builder=MetadataReference(*LINEAGE_BUILDER),
            projection_rights=MetadataReference(**row["rights_evidence"]),
            v3_plan_sha256=prior["plan"]["sha256"],
            v3_registration_sha256=prior["registration_sha256"],
            profile_sha256=previous.sha(profile_bytes),
            v3_receipt_sha256=previous.sha(receipt_bytes),
        )
        role_evidence = ProjectionEvidence(
            source_v1=source_bytes,
            v2_lineage=v2_bytes,
            source_admission=(root / RAW_ADMISSION).read_bytes(),
            source_event=(root / raw_source["event"]["path"]).read_bytes(),
            source_b2=(root / raw_source["b2"]["path"]).read_bytes(),
            source_authorization=(root / RAW_AUTHORIZATION).read_bytes(),
            source_contract=(root / RAW_CONTRACT).read_bytes(),
            producer_event=(root / source["event"]["path"]).read_bytes(),
            producer_b2=(root / source["b2"]["path"]).read_bytes(),
            producer_receipt=(
                root / row["source_receipt"]["path"]
            ).read_bytes(),
            projection_rights=(
                root / row["rights_evidence"]["path"]
            ).read_bytes(),
            prior_replay=(root / replay.REPORT).read_bytes(),
            lineage_report=(
                root / preparation.INPUTS["lineage"][0]
            ).read_bytes(),
            plan_builder=(root / PLAN_BUILDER[0]).read_bytes(),
            v3_builder=(root / V3_BUILDER[0]).read_bytes(),
            lineage_builder=(root / LINEAGE_BUILDER[0]).read_bytes(),
        )
        rebuilt_bytes, rebuilt_metadata = reconstruct_plan(root, receipt)
        require(
            rebuilt_bytes == plan_bytes
            and rebuilt_metadata == packet["metadata"],
            "v3 reconstruction differs from original metadata plan",
        )
        verify_v1_projection_profile(
            profile_bytes,
            role_evidence,
            (root / PROFILE_SCHEMA).read_bytes(),
            (root / previous.V1_SCHEMA).read_bytes(),
            (root / lineage.SCHEMA).read_bytes(),
            trusted=trust,
        )
        verify_v3_registration_receipt(
            receipt_bytes,
            plan_bytes,
            packet["metadata"],
            role_evidence,
            (root / RECEIPT_SCHEMA).read_bytes(),
            (root / previous.V3_SCHEMA).read_bytes(),
            trusted=trust,
        )
        packets.append({
            "projection": asdict(projection),
            "profile": ref(profile_path, previous.sha(profile_bytes)),
            "v3_receipt": ref(receipt_path, previous.sha(receipt_bytes)),
            "source_acquisition_id": RAW_ACQUISITION,
            "producer_acquisition_id": source["acquisition_id"],
            "privacy": privacy_context(root, name),
            "trust": trust,
            "evidence": role_evidence,
            "plan_bytes": plan_bytes,
            "metadata": packet["metadata"],
        })
    require(
        len(packets) == preparation.FROZEN_COUNT, "frozen object count differs"
    )
    report = {
        "schema_id": "global-medicines-atlas.frozen-mbs-projection-v1-v3-qualification",
        "schema_version": 1,
        "recorded_on": "2026-11-16",
        "source_v1": source_ref,
        "raw_admission": raw_admission_ref,
        "raw_v1_decision": "restates_existing_accepted_source_only_not_projection",
        "raw_source_reviewer_status": "unreviewed",
        "profile_schema": ref(PROFILE_SCHEMA, PROFILE_SCHEMA_SHA256),
        "v3_receipt_schema": ref(RECEIPT_SCHEMA, RECEIPT_SCHEMA_SHA256),
        "objects": [
            {
                key: value
                for key, value in packet.items()
                if key not in {"trust", "evidence", "plan_bytes", "metadata"}
            }
            for packet in packets
        ],
        "pbs_bronze": pbs_privacy_context(root),
        "boundaries": {
            "source_or_projection_payload_read": False,
            "participant_or_cohort_data_accessed": False,
            "dataset_acquired_or_published": False,
            "new_source_or_projection_admission": False,
            "output_privacy_cleared": False,
            "consumer_canary": False,
        },
    }
    outputs[REPORT] = previous.serialized(report)
    return outputs, packets


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    outputs, _packets = assemble()
    for relative, raw in outputs.items():
        path = ROOT / relative
        if args.check:
            require(
                path.is_file() and path.read_bytes() == raw,
                f"stale: {relative}",
            )
        else:
            require(
                not path.exists() or path.read_bytes() == raw,
                f"immutable conflict: {relative}",
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    print(
        "Four v1 profiles and durable v3 metadata receipts verified; privacy and admission remain open"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
