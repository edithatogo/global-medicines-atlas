"""Assess existing Australian objects by exact source and replay evidence.

This metadata-only batch records a technical source-profile assessment, not
an exhaustive privacy clearance, admission, rights decision, or publication.
Unknown objects remain blocked. It reads no source or projection payloads.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from operator import itemgetter
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import scripts.qualify_australian_existing_derived_gates as derived
import scripts.qualify_australian_schedule_source_privacy as source_privacy
import scripts.qualify_m112_existing_reimbursement_batch as bounded
import scripts.qualify_mbs_four_projection_dossiers as dossiers
import scripts.reconcile_mbs_privacy_replay as replay

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "quality/qualifications/"
BATCH_DIR = PREFIX + "australian-privacy-batch-20261115/"
JULY_EVENT = "bbd662119ebebfdf08baf14c0b15c0dd5c93465910fd4f5309f37ecd37a82b8d"
AUGUST_EVENT = replay.EVENT_ID
JULY_SHA = "db873768c5795222455033e2bad28586f19bbf2a10c7d58f06a0671d9111a556"
JULY_BYTES = 8_194_522
FROZEN_OBJECTS = 1759
DEFERRED_OBJECTS = 1745
PRIOR_RAW_ADMISSIONS = 14
REIMBURSEMENT_OBJECTS = 1719
OTHER_OBJECTS = 26
MBS_OUTPUTS = 4
EVENT_SCHEMA_VERSION = 3
EVIDENCE = {
    "reimbursement": (
        PREFIX + "australian-m112-reimbursement-batch-readiness-20261115.json",
        "0969afcd6152cd73f5ff53f28ccb6fb9315090a71ba302ebbee74efaf32db4f5",
    ),
    "existing_derived": (
        PREFIX + "australian-existing-derived-gates-20261115.json",
        "df2579195dcfa302e24dbc1307d8f732deb3b8fc4ed8f48fa8a37950ec0fe8f0",
    ),
    "outside_dossiers": (
        PREFIX + "australian-mbs-four-projection-dossiers-20261115.json",
        "0b3e7c53204695148b5b563e4bb7024cad421cc6cfa6ebf2c56f31af3a291d1e",
    ),
    "outside_replay": (
        BATCH_DIR + "mbs-outside-frozen-replay.json",
        "eeb694be498244d41fdec69f16f24a9cd135a54fa0420405b7b71751609717f0",
    ),
    "frozen_replay": (
        PREFIX + "australian-m112-mbs-bronze-projection-lineage-20261019.json",
        "ef32417220d838e2cb625d8d0ab7a34009b99bdf3181314e5a4536442d0f1720",
    ),
    "august_event": source_privacy.SOURCE_RECEIPTS[AUGUST_EVENT],
    "july_event": (
        f"quality/bronze/acquisitions/au-mbs/{JULY_EVENT}.json",
        "e99c0153a57e0b46cf9dfd2c03520aa9ca9aa97415b5d20920c5e8191aa086f9",
    ),
    "july_receipt": (
        f"quality/bronze/receipts/au-mbs/{JULY_EVENT}.json",
        "cbb89dde7e24e790440b7aa3ec70ff8a580801d49b5f0b8839290f63bd64819c",
    ),
    "frozen_6bc_receipt": (
        f"quality/bronze/receipts/au-mbs/{AUGUST_EVENT}.json",
        "ff916b49a4993b523da2f41952805b4e1e2064e0ce21edc8bd6643c1acda77a8",
    ),
    "frozen_99_receipt": (
        BATCH_DIR + "frozen-99-source-receipt.json",
        "4f694fd7364061cd05fee33ea52e6dbeef17d1067b8437f72e726ab168fc2fc7",
    ),
    "historical_zip_0": (
        PREFIX + "mbs-historical-native-formats-0-20261022-39709530322.json",
        "8dbd28dfeb5cb89984e777c76f3af56ba7e5cddc0bf7fd7905ecd4d02f423f18",
    ),
    "historical_zip_1": (
        PREFIX + "mbs-historical-native-formats-1-20261022-39709530322.json",
        "405241993e076072ec9700ec507e9d4aae352ed91a5adf38aff61e1b91a9037f",
    ),
    "historical_zip_2": (
        PREFIX + "mbs-historical-native-formats-2-20261022-39709530322.json",
        "862275a1e9b0538af772506da7ea66b659def5a6ef1ec239fe4b4fe946a84c64",
    ),
    "historical_zip_3": (
        PREFIX + "mbs-historical-native-formats-3-20261022-39709530322.json",
        "7a1663dd79515ca9260006a99cdf064acc386ab2b8972c07be6aba35d80582d1",
    ),
    "historical_zip_5": (
        PREFIX + "mbs-historical-native-formats-5-20261022-39709530322.json",
        "42385651e72d4c71176f2a0fb6514d6be4f7e394677bf07e76e74db45c815bd0",
    ),
    "historical_q2_workbook": (
        PREFIX
        + "mbs-demographic-workbook-q2-native-qualification-20261022-39648296077.json",
        "a7140b482b2890960ff28292a3fe04c16820f4924061d78903e3929cf74e682f",
    ),
}
CODE_BINDINGS = {
    "scripts/reconcile_mbs_privacy_replay.py": "b3be935822e3be33bf6961d4c4898bad10da75cd827641d65c01c4180fcfc90b",
    "src/global_medicines_atlas/adapters/au_mbs.py": "73098a1f6b6fcb1c4c26c75e4c8f6a80f397e697046e4dcc2d23ea39b96069f3",
    "src/global_medicines_atlas/mbs_release.py": "d59e04b58783912b557dff53ee536a3cbf7d39725ebb2e77d11bedfc29417828",
    "src/global_medicines_atlas/adapters/_receipt.py": "afa94ba955c4723b275addb0b55200636aaf82eeaabcd5ac0b23aefcf2684020",
    "src/global_medicines_atlas/mbs_compatibility.py": "3d7a4263a020a7f9569968b3007f5d10a8a52b067154eed67281bd5a52eae111",
}
UNKNOWN = "blocked_unknown_or_unqualified_privacy"
ASSESSED = "source_profile_assessed_non_sensitive"
PRIOR = "previously_assessed_in_separate_silver_contract"


def require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _code_bindings(root: Path) -> None:
    for relative, expected in CODE_BINDINGS.items():
        path = root / relative
        require(
            not path.is_symlink() and path.is_file(),
            "MBS replay code path differs",
        )
        require(
            hashlib.sha256(path.read_bytes()).hexdigest() == expected,
            "MBS replay code digest differs",
        )


def _source_classification(
    event: dict[str, Any],
    receipt: dict[str, Any],
    *,
    event_id: str,
    digest: str,
    size: int,
) -> None:
    sensitivity = event["sensitivity"]
    receipt_sensitivity = receipt["sensitivity"]
    require(
        all((
            event.get("schema_id")
            == "global-medicines-atlas.bronze-acquisition-event",
            event.get("schema_version") == EVENT_SCHEMA_VERSION,
            event.get("acquisition_id") == event_id,
            event.get("source_id")
            == receipt["source"]["source_id"]
            == "au-mbs",
            event.get("content_id") == event.get("payload_sha256") == digest,
            receipt["payload"]["sha256"] == digest,
            receipt["payload"]["byte_count"] == size,
            receipt["temporal"]["acquisition_id"] == event_id,
            sensitivity == receipt_sensitivity,
            sensitivity.get("schema_id")
            == "global-medicines-atlas.bronze-sensitivity-classification",
            sensitivity.get("schema_version") == 1,
            sensitivity.get("data_sensitivity") == "non_sensitive",
            sensitivity.get("personal_data") == "none",
            sensitivity.get("publication") == "permitted",
            set(sensitivity.get("reason_codes", []))
            == {"qualified_official_mbs_schedule", "exact_release_approval"},
        )),
        "MBS source privacy evidence differs",
    )


def _safe_schedule_receipt(
    receipt: dict[str, Any],
    *,
    acquisition_id: str,
    receipt_id: str,
    digest: str,
) -> None:
    uri_text: object = receipt["retrieval"]["uri"]
    require(isinstance(uri_text, str), "MBS receipt URI differs")
    uri = urlsplit(str(uri_text))
    sensitivity = receipt["sensitivity"]
    require(
        all((
            uri.scheme == "https",
            uri.hostname == "www.mbsonline.gov.au",
            uri.username is None,
            uri.password is None,
            not uri.query,
            not uri.fragment,
            receipt.get("receipt_id") == receipt_id,
            receipt["source"]["source_id"] == "au-mbs",
            receipt["payload"]["sha256"] == digest,
            receipt["payload"]["byte_count"] == source_privacy.SOURCE_BYTES,
            receipt["temporal"]["acquisition_id"] == acquisition_id,
            sensitivity.get("data_sensitivity") == "non_sensitive",
            sensitivity.get("personal_data") == "none",
            sensitivity.get("publication") == "permitted",
        )),
        "MBS projection source receipt differs",
    )


def _identity(row: dict[str, Any], *, frozen: bool) -> dict[str, Any]:
    digest, size = bounded.metadata_identity(row)
    return {
        "dataset": row["dataset"],
        "revision": row["frozen_revision"]
        if frozen and "frozen_revision" in row
        else row["revision"],
        "path": row["path"],
        "sha256": digest,
        "byte_count": size,
        "frozen_member": frozen,
    }


def _pbs_group(row: dict[str, Any], event: dict[str, Any]) -> str:
    sensitivity = event["sensitivity"]
    uri_text: object = event["retrieval"]["uri"]
    require(isinstance(uri_text, str), "PBS source URI differs")
    uri = urlsplit(str(uri_text))
    source = uri
    archived = uri.hostname == "web.archive.org"
    if archived:
        match = re.fullmatch(
            r"/web/\d{1,14}[a-z_]*?/(https?://.*)", uri.path, re.IGNORECASE
        )
        require(match is not None, "PBS archived URI differs")
        source = urlsplit(match.group(1) if match else "")
    ext = Path(row["path"]).suffix.lower()
    require(
        all((
            uri.scheme == "https",
            uri.username is None,
            uri.password is None,
            source.hostname == "www.pbs.gov.au",
            source.path.startswith("/publication/schedule/"),
            ext in {".pdf", ".zip", ".csv"},
            event.get("payload_sha256")
            == event.get("content_id")
            == row["sha256"],
            event.get("evidence_class") == "historical",
            sensitivity.get("data_sensitivity") == "unknown",
            sensitivity.get("personal_data") == "unknown",
            sensitivity.get("publication") == "review_required",
        )),
        "PBS source privacy or provenance differs",
    )
    if archived:
        require(ext == ".pdf", "PBS archived file kind differs")
        return "pbs_schedule_archived_pdf_unassessed"
    return {
        ".pdf": "pbs_schedule_pdf_unassessed",
        ".zip": "pbs_schedule_zip_unassessed",
        ".csv": "pbs_schedule_csv_unassessed",
    }[ext]


def _historical_mbs_profiles(
    evidence: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Identify prior structural profiles without treating them as privacy clearance."""
    profiles: dict[str, dict[str, Any]] = {}
    for index in (0, 1, 2, 3, 5):
        name = f"historical_zip_{index}"
        document = evidence[name]
        result = document["result"]
        members = bounded.metadata_rows(result["members"])
        require(
            all((
                document.get("dataset")
                == "edithatogo/australian-mbs-utilisation-archive",
                document.get("status") == "passed",
                result.get("container_integrity_verified") is True,
                result.get("all_native_format_profiles_passed") is True,
                result.get("members_parsed")
                == result.get("member_count")
                == len(members),
                result.get("members_held") == 0,
                result.get("member_formats_qualified") is False,
                result.get("native_values_or_names_emitted") is False,
                result.get("semantics_qualified") is False,
                all(member.get("status") == "parsed" for member in members),
            )),
            "Historical MBS ZIP structural evidence differs",
        )
        path = result["source_path"]
        require(path not in profiles, "Duplicate historical MBS source profile")
        profiles[path] = {
            "sha256": result["source_sha256"],
            "byte_count": result["source_bytes"],
            "evidence": name,
            "batch": "mbs_historical_zip_structurally_profiled_unassessed",
        }
    workbook = evidence["historical_q2_workbook"]
    result = workbook["result"]
    require(
        all((
            workbook.get("dataset")
            == "edithatogo/australian-mbs-utilisation-archive",
            result.get("candidate_only") is True,
            result.get("rebuild_equal") is True,
            result.get("unqualified_pooling_blocked") is True,
            workbook["boundaries"]["new_admissions"] == 0,
            workbook["boundaries"]["publications"] == 0,
        )),
        "Historical MBS workbook structural evidence differs",
    )
    path = workbook["source_path"]
    require(path not in profiles, "Duplicate historical MBS workbook profile")
    profiles[path] = {
        "sha256": result["source_sha256"],
        "byte_count": None,
        "evidence": "historical_q2_workbook",
        "batch": "mbs_demographic_workbook_profiled_unassessed",
    }
    return profiles


def _other_frozen_group(row: dict[str, Any]) -> str:
    if (
        row["dataset"] == derived.DATASET
        and row["representation"] == "raw_source_payload"
    ):
        return "other_mbs_schedule_raw_unassessed"
    if row["dataset"] == "edithatogo/australian-pbs-source-archive":
        if row["representation"] == "raw_source_payload":
            return "pbs_frozen_raw_unassessed"
        if row["representation"] == "existing_data_projection":
            return "pbs_frozen_projection_unassessed"
        raise ValueError("unrecognized frozen PBS representation")
    raise ValueError("unrecognized frozen privacy group")


def _check_frozen_replay(
    lineage: dict[str, Any], receipts: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    require(
        all((
            lineage.get("schema_id")
            == "global-medicines-atlas.australian-m112-mbs-bronze-projection-lineage",
            lineage.get("status")
            == "four_frozen_mbs_bronze_projection_lineages_reproduced",
            lineage["scope"]["dataset"] == derived.DATASET,
            lineage["scope"]["raw_source_sha256"] == source_privacy.SOURCE_SHA,
            lineage["scope"]["raw_source_byte_count"]
            == source_privacy.SOURCE_BYTES,
            lineage["scope"]["output_count"] == MBS_OUTPUTS,
            lineage["input_bindings"][
                "src/global_medicines_atlas/adapters/au_mbs.py"
            ]
            == CODE_BINDINGS["src/global_medicines_atlas/adapters/au_mbs.py"],
            lineage["input_bindings"][
                "src/global_medicines_atlas/mbs_release.py"
            ]
            == CODE_BINDINGS["src/global_medicines_atlas/mbs_release.py"],
        )),
        "Frozen MBS replay scope differs",
    )
    outputs = bounded.metadata_index(
        bounded.metadata_rows(lineage.get("outputs"))
    )
    require(
        len(outputs) == MBS_OUTPUTS, "Frozen MBS replay output count differs"
    )
    for row in outputs.values():
        run = row["run_id"]
        name = (
            "frozen_6bc_receipt"
            if run.startswith("6bc9")
            else "frozen_99_receipt"
            if run.startswith("99fa")
            else ""
        )
        require(name in receipts, "Frozen MBS replay producer differs")
        receipt = receipts[name]
        _safe_schedule_receipt(
            receipt,
            acquisition_id=row["acquisition_id"],
            receipt_id=row["source_receipt_id"],
            digest=row["source_sha256"],
        )
        transformation = row["transformation"]
        require(
            all((
                row["source_sha256"] == source_privacy.SOURCE_SHA,
                row["source_byte_count"] == source_privacy.SOURCE_BYTES,
                row["source_receipt_sha256"] == EVIDENCE[name][1],
                transformation.get("adapter") == "parse_mbs_source_xml",
                transformation.get("projection") == "mbs_source_parquet",
                transformation.get("reproduced_exact_bytes_in_memory") is True,
                transformation.get("projection_selection")
                == (
                    "Group=P7" if row["path"].endswith("/p7.parquet") else "all"
                ),
            )),
            "Frozen MBS projection replay binding differs",
        )
    return outputs


def _check_outside_replay(
    observation: dict[str, Any], prior: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    writer, source, boundaries = (
        observation["writer"],
        observation["source"],
        observation["boundaries"],
    )
    require(
        all((
            observation.get("schema_id")
            == "global-medicines-atlas.mbs-classified-schedule-in-memory-replay",
            source.get("sha256") == source_privacy.SOURCE_SHA,
            source.get("byte_count") == source_privacy.SOURCE_BYTES,
            source.get("classification_event") == AUGUST_EVENT,
            writer.get("python") == "3.15.1",
            writer.get("current_pyarrow") == "26.0.0",
            writer.get("historical_pyarrow") == "25.0.0",
            writer.get("historical_lock_sha256")
            == replay.HISTORICAL_LOCK_SHA256,
            observation.get("implementation_sha256") == CODE_BINDINGS,
            writer.get("historical_commits")
            == {
                name: product["commit"]
                for name, product in dossiers.PRODUCTS.items()
            },
            boundaries.get("classified_source_read_in_memory") is True,
            boundaries.get("source_or_output_bytes_written") is False,
            boundaries.get("source_values_emitted") is False,
            boundaries.get("participant_or_cohort_data_accessed") is False,
            boundaries.get("dataset_published") is False,
        )),
        "Outside MBS replay scope differs",
    )
    outputs = bounded.metadata_index(
        bounded.metadata_rows(observation.get("objects"))
    )
    expected = bounded.metadata_index(
        bounded.metadata_rows(prior.get("dossiers"))
    )
    require(
        len(outputs) == MBS_OUTPUTS and set(outputs) == set(expected),
        "Outside MBS replay output identities differ",
    )
    for path, row in outputs.items():
        original = expected[path]
        require(
            all((
                row["dataset"] == original["dataset"],
                row["revision"] == original["revision"],
                row["sha256"]
                == row["footer_adjusted_sha256"]
                == original["sha256"],
                row["byte_count"] == original["byte_count"],
                row["unadjusted_sha256"] != row["sha256"],
                row["writer_marker_occurrences"] == 1,
                len(replay.PARQUET_MAGIC)
                <= row["footer_start"]
                <= row["marker_offset"],
                row["marker_offset"] + len(replay.NEW_MARKER)
                <= row["byte_count"] - replay.TRAILER_BYTES,
                row["exact_digest_after_footer_substitution"] is True,
            )),
            "Outside MBS replay object or footer differs",
        )
    return outputs


def build_report(root: Path = ROOT) -> dict[str, Any]:  # ruff: ignore[too-many-locals,too-many-statements] -- Preserve distinct object gates.
    """Assess or defer each previously identified object without reading payloads."""
    _code_bindings(root)
    evidence = {
        name: bounded.read_bound_metadata(root, *binding)
        for name, binding in EVIDENCE.items()
    }
    batch = evidence["reimbursement"]
    require(
        all((
            batch["scope"]["frozen_objects"] == FROZEN_OBJECTS,
            batch["scope"]["deferred_objects"] == DEFERRED_OBJECTS,
            batch["scope"]["selected_reimbursement_objects"]
            == REIMBURSEMENT_OBJECTS,
            batch["scope"]["prior_raw_admissions"] == PRIOR_RAW_ADMISSIONS,
            batch["scope"]["prior_raw_canaries"] == PRIOR_RAW_ADMISSIONS,
            batch["result"]["new_admissions"] == 0,
            len(batch["objects"]) == REIMBURSEMENT_OBJECTS,
            len(batch["other_frozen_objects"]) == OTHER_OBJECTS,
            batch["boundaries"][
                "individual_participant_or_cohort_data_accessed"
            ]
            is False,
        )),
        "Frozen privacy batch scope differs",
    )
    _source_classification(
        evidence["august_event"],
        evidence["frozen_6bc_receipt"],
        event_id=AUGUST_EVENT,
        digest=source_privacy.SOURCE_SHA,
        size=source_privacy.SOURCE_BYTES,
    )
    _source_classification(
        evidence["july_event"],
        evidence["july_receipt"],
        event_id=JULY_EVENT,
        digest=JULY_SHA,
        size=JULY_BYTES,
    )
    frozen_replayed = _check_frozen_replay(evidence["frozen_replay"], evidence)
    outside_replayed = _check_outside_replay(
        evidence["outside_replay"], evidence["outside_dossiers"]
    )
    prior_silver = bounded.metadata_index(
        bounded.metadata_rows(
            evidence["existing_derived"]["prior_mbs_consumer_objects"]
        )
    )
    historical_profiles = _historical_mbs_profiles(evidence)
    records: list[dict[str, Any]] = []
    for row in bounded.metadata_rows(batch["objects"]):
        identity = _identity(row, frozen=True)
        require(
            row["privacy_gate"]
            == "blocked_no_source_specific_sensitivity_assessment"
            and row["ready_for_payload_read"] is False,
            "Reimbursement privacy state differs",
        )
        if row["representation"] == "raw_source_payload":
            refs = row["metadata_references"]
            event = bounded.read_bound_metadata(
                root,
                refs["acquisition_event_path"],
                refs["acquisition_event_sha256"],
            )
            group = _pbs_group(row, event)
            evidence_ref = refs["acquisition_event_path"]
        else:
            require(
                row["representation"] == "existing_data_projection",
                "Reimbursement representation differs",
            )
            group = (
                "reimbursement_projection_"
                + (
                    "byte_identical"
                    if row["lineage_evidence"]
                    == "byte_identical_producer_projection_metadata_linked"
                    else "layer_partition"
                )
                + "_unassessed"
            )
            require(
                row["lineage_evidence"]
                in {
                    "byte_identical_producer_projection_metadata_linked",
                    "exact_layer_partition_metadata_linked",
                },
                "Reimbursement projection evidence differs",
            )
            evidence_ref = "reimbursement"
        records.append({
            **identity,
            "batch": group,
            "privacy": UNKNOWN,
            "evidence": evidence_ref,
        })
    for row in bounded.metadata_rows(batch["other_frozen_objects"]):
        identity = _identity(row, frozen=True)
        path, digest = row["path"], row["sha256"]
        if (
            row["dataset"] == derived.DATASET
            and row["representation"] == "raw_source_payload"
            and digest in {JULY_SHA, source_privacy.SOURCE_SHA}
        ):
            expected_size = (
                JULY_BYTES
                if digest == JULY_SHA
                else source_privacy.SOURCE_BYTES
            )
            require(
                row["byte_count"] == expected_size,
                "MBS raw classified byte count differs",
            )
            group, decision, ref = (
                "mbs_exact_classified_raw",
                ASSESSED,
                "july_event" if digest == JULY_SHA else "august_event",
            )
        elif path in frozen_replayed:
            proof = frozen_replayed[path]
            require(
                row["dataset"] == derived.DATASET
                and row["sha256"] == proof["sha256"]
                and row["byte_count"] == proof["byte_count"],
                "Frozen MBS object differs from replay",
            )
            group, decision, ref = (
                "mbs_frozen_exact_replay",
                ASSESSED,
                "frozen_replay",
            )
        elif path in prior_silver:
            prior = prior_silver[path]
            require(
                row["dataset"] == prior["dataset"]
                and row["sha256"] == prior["sha256"]
                and row["byte_count"] == prior["byte_count"]
                and prior["privacy"]
                == "non_sensitive_in_exact_previously_admitted_contract",
                "Prior MBS Silver profile differs",
            )
            group, decision, ref = (
                "mbs_silver_prior_separate_profile",
                PRIOR,
                "existing_derived",
            )
        elif path in historical_profiles:
            profile = historical_profiles[path]
            require(
                row["dataset"]
                == "edithatogo/australian-mbs-utilisation-archive"
                and row["sha256"] == profile["sha256"]
                and (
                    profile["byte_count"] is None
                    or row["byte_count"] == profile["byte_count"]
                ),
                "Historical MBS structural profile object differs",
            )
            group, decision, ref = (
                profile["batch"],
                UNKNOWN,
                profile["evidence"],
            )
        else:
            group = _other_frozen_group(row)
            decision, ref = UNKNOWN, "reimbursement"
        records.append({
            **identity,
            "batch": group,
            "privacy": decision,
            "evidence": ref,
        })
    for row in bounded.metadata_rows(evidence["outside_dossiers"]["dossiers"]):
        require(
            row["path"] in outside_replayed,
            "Outside MBS privacy replay missing",
        )
        records.append({
            **_identity(row, frozen=False),
            "batch": "mbs_outside_footer_adjusted_replay",
            "privacy": ASSESSED,
            "evidence": "outside_replay",
        })
    pbs = evidence["existing_derived"]["pbs_candidate"]
    records.append({
        **_identity(pbs, frozen=False),
        "batch": "pbs_reproduced_silver_unassessed",
        "privacy": UNKNOWN,
        "evidence": "existing_derived",
    })
    keys = {(r["dataset"], r["path"], r["sha256"]) for r in records}
    require(
        len(records) == DEFERRED_OBJECTS + MBS_OUTPUTS + 1
        and len(keys) == len(records),
        "Privacy batch objects overlap or are missing",
    )
    counts = Counter(r["batch"] for r in records)
    expected = {
        "pbs_schedule_pdf_unassessed": 1047,
        "pbs_schedule_archived_pdf_unassessed": 5,
        "pbs_schedule_zip_unassessed": 652,
        "pbs_schedule_csv_unassessed": 3,
        "reimbursement_projection_byte_identical_unassessed": 9,
        "reimbursement_projection_layer_partition_unassessed": 3,
        "mbs_exact_classified_raw": 3,
        "mbs_frozen_exact_replay": 4,
        "mbs_silver_prior_separate_profile": 6,
        "mbs_historical_zip_structurally_profiled_unassessed": 5,
        "mbs_demographic_workbook_profiled_unassessed": 1,
        "other_mbs_schedule_raw_unassessed": 5,
        "pbs_frozen_raw_unassessed": 1,
        "pbs_frozen_projection_unassessed": 1,
        "mbs_outside_footer_adjusted_replay": 4,
        "pbs_reproduced_silver_unassessed": 1,
    }
    require(dict(counts) == expected, "Privacy batch disposition counts differ")
    return {
        "schema_id": "global-medicines-atlas.australian-existing-archive-privacy-batch",
        "schema_version": 1,
        "recorded_on": "2026-11-15",
        "inputs": {
            name: {"path": path, "sha256": digest}
            for name, (path, digest) in EVIDENCE.items()
        },
        "code_sha256": CODE_BINDINGS,
        "scope": {
            "frozen_objects": FROZEN_OBJECTS,
            "prior_raw_admitted": PRIOR_RAW_ADMISSIONS,
            "frozen_deferred": DEFERRED_OBJECTS,
            "additional_outside_frozen": 5,
        },
        "summary": {
            "newly_assessed_non_sensitive_frozen": 7,
            "newly_assessed_non_sensitive_outside_frozen": 4,
            "prior_separate_silver_profiles": 6,
            "frozen_unassessed": 1732,
            "outside_unassessed": 1,
            "new_admissions": 0,
            "new_consumer_checks": 0,
        },
        "batches": dict(sorted(counts.items())),
        "objects": sorted(records, key=itemgetter("dataset", "path")),
        "limitations": [
            "The non-sensitive decisions are technical source-profile assessments, not exhaustive privacy clearance or proof that every possible personal datum is absent.",
            "The four outside-frozen outputs match after a single equal-length writer-version footer substitution; the historical PyArrow 25 writer was not executed.",
            "A public publisher URL, file extension or rights attestation alone does not qualify the 1,707 PBS objects or the other unassessed outputs.",
            "Prior separate Silver contracts do not create raw-ledger admissions or qualify a different revision's consumer path.",
            "No rights, publication, v4 admission, consumer, independent recovery or federation gate is changed.",
        ],
        "boundaries": {
            "new_source_added": False,
            "unclassified_archived_payload_read": False,
            "participant_or_cohort_data_accessed": False,
            "source_or_projection_bytes_written": False,
            "source_values_emitted": False,
            "dataset_published": False,
            "rights_changed": False,
            "new_admission": False,
            "consumer_check": False,
            "frozen_inventory_changed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--report", type=Path)
    group.add_argument("--check", type=Path)
    args = parser.parse_args()
    report = build_report()
    if args.report:
        with args.report.open("x", encoding="utf-8") as target:
            json.dump(report, target, indent=2, sort_keys=True)
            target.write("\n")
    elif json.loads(args.check.read_text(encoding="utf-8")) != report:
        raise ValueError("stored Australian privacy batch differs")
    print(json.dumps(report["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
