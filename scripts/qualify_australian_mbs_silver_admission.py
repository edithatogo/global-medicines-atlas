"""Qualify the exact July 2025 MBS Silver source era for M-110 graph input."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker

from global_medicines_atlas.australian_source_contracts import (
    TargetTable,
    mbs_field_contracts,
)
from global_medicines_atlas.mbs_silver import mbs_silver_schema
from global_medicines_atlas.mbs_typed_values import CONVERSION_VERSION

ROOT = Path(__file__).resolve().parents[1]
QUALIFICATION_PATH = Path(
    "quality/qualifications/australian-mbs-silver-candidate-qualification-20261017-8c0090db.json"
)
PUBLIC_MANIFEST_PATH = Path(
    "quality/qualifications/australian-mbs-v4-candidate-2025-07/manifest.json"
)
PARITY_PATH = Path(
    "quality/qualifications/mbs-source-silver-tables-parity-2025-07-v3.json"
)
AUTHORIZATION_PATH = Path(
    "quality/qualifications/australian-health-legacy-publication-authorization.json"
)
DECISION_PATH = Path(
    "conductor/decisions/0009-australian-health-authority-and-public-data-plane.md"
)
SEMANTICS_PATH = Path("docs/qualification/mbs-xml-v3-field-semantics.md")
DATE_PROFILE_PATH = Path(
    "quality/qualifications/mbs-xml-v3-date-profile-qualification-20260929.json"
)
TRANSFORM_PATH = Path("src/global_medicines_atlas/mbs_silver.py")
CONVERSION_PATH = Path("src/global_medicines_atlas/mbs_typed_values.py")
SEMANTIC_SCHEMA_PATH = Path(
    "schemas/australian-mbs-silver-semantic-manifest-v1.json"
)
ADMISSION_SCHEMA_PATH = Path("schemas/australian-mbs-silver-admission-v1.json")
SEMANTIC_OUTPUT_PATH = Path(
    "quality/qualifications/australian-mbs-silver-semantic-manifest-20261017.json"
)
ADMISSION_OUTPUT_PATH = Path(
    "quality/qualifications/australian-mbs-silver-admission-20261017.json"
)
EXPECTED_MAIN_COMMIT = "8c0090db41bb4ad2a4de20090a5e0895fffd91ec"
EXPECTED_PUBLIC_REVISION = "3d2d528439bddf6f42e8e700c88917f0960a9f38"
EXPECTED_SOURCE_SHA256 = (
    "db873768c5795222455033e2bad28586f19bbf2a10c7d58f06a0671d9111a556"
)
EXPECTED_TABLE_COUNT = 6
EXPECTED_RECORD_COUNT = 5989

_NUMERIC_WIDTHS = {
    "ScheduleFee": 5,
    "Benefit75": 5,
    "Benefit85": 5,
    "Benefit100": 5,
    "EMSNFixedCapAmount": 7,
    "EMSNPercentageCap": 7,
    "EMSNMaximumCap": 7,
}
_MARKDOWN_TABLE_COLUMNS = 2
_DATE_ROLES = {
    "BenefitStartDate": "commencement of the current benefit level(s)",
    "DerivedFeeStartDate": "commencement of the derived-fee description",
    "DescriptionStartDate": "commencement of the current item description",
    "EMSNChangeDate": "source-recorded safety-net cap change date",
    "EMSNEndDate": "end of the stated safety-net cap period",
    "EMSNStartDate": "commencement of the stated safety-net cap period",
    "FeeStartDate": "commencement of the current schedule or derived fee",
    "ItemEndDate": "cessation date of the MBS item in this source snapshot",
    "ItemStartDate": "commencement date of the MBS item in this source snapshot",
    "QFEEndDate": "end of the time-limited listing evaluation period",
    "QFEStartDate": "start of the time-limited listing evaluation period",
}
_TYPE_DETAILS = {
    "identifier": ("string", "not_applicable"),
    "source_code": ("string", "not_applicable"),
    "source_text": ("string", "not_applicable"),
    "source_date": ("date32[day]", "not_applicable"),
    "aud_decimal": ("decimal128(38,9)", "AUD"),
    "decimal": ("decimal128(38,9)", "not_applicable"),
    "percentage": ("decimal128(38,9)", "not_applicable"),
}


def _bytes(path: Path) -> bytes:
    return (ROOT / path).read_bytes()


def _sha256(path: Path) -> str:
    return hashlib.sha256(_bytes(path)).hexdigest()


def _json(path: Path) -> dict[str, Any]:
    value: Any = json.loads(_bytes(path))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return cast("dict[str, Any]", value)


def _source_meanings() -> dict[str, str]:
    meanings: dict[str, str] = {}
    in_table = False
    for line in (
        (ROOT / SEMANTICS_PATH).read_text(encoding="utf-8").splitlines()
    ):
        if line == "## Field meaning and transformation boundary":
            in_table = True
            continue
        if in_table and line.startswith("## "):
            break
        if not in_table or not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != _MARKDOWN_TABLE_COLUMNS or cells[0].startswith("---"):
            continue
        names = re.findall(r"`([^`]+)`", cells[0])
        if not names:
            continue
        for name in names:
            if name in meanings:
                if cells[1] not in meanings[name]:
                    meanings[name] = f"{meanings[name]} {cells[1]}"
            else:
                meanings[name] = cells[1]
    contracts = {field.native_name for field in mbs_field_contracts()}
    if set(meanings) != contracts:
        raise ValueError(
            "official MBS meaning denominator differs from field contract"
        )
    return meanings


def _validate_json_schema(
    schema: dict[str, Any], value: dict[str, Any]
) -> None:
    validator_type: Any = Draft202012Validator
    validator_type.check_schema(schema)
    validator_type(schema, format_checker=FormatChecker()).validate(value)


def _verified_inputs() -> tuple[
    dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]
]:
    report = _json(QUALIFICATION_PATH)
    public_manifest = _json(PUBLIC_MANIFEST_PATH)
    parity = _json(PARITY_PATH)
    authorization = _json(AUTHORIZATION_PATH)
    identity = report["public_v4_identity"]
    if report["exact_commit"] != EXPECTED_MAIN_COMMIT:
        raise ValueError(
            "candidate qualification is not for the exact merged main commit"
        )
    if report["current_blockers"]:
        raise ValueError("candidate qualification has current blockers")
    if (
        identity["status"] != "verified"
        or identity["candidate_only"] is not True
    ):
        raise ValueError("public identity or candidate boundary changed")
    if identity["current_revision"] != EXPECTED_PUBLIC_REVISION:
        raise ValueError("public MBS v4 revision changed")
    if identity["manifest_sha256"] != _sha256(PUBLIC_MANIFEST_PATH):
        raise ValueError(
            "public manifest digest differs from hosted qualification"
        )
    if identity["dataset"] != public_manifest["dataset"]:
        raise ValueError("public dataset identity differs")
    if public_manifest["candidate_only"] is not True:
        raise ValueError("public candidate state changed")
    if report["source_bytes_retained"] is not False:
        raise ValueError("qualification retained source bytes")
    if report["publication_performed"] is not False:
        raise ValueError("qualification performed publication")
    profile = report["profiled_schema_compatibility"]
    if (
        profile["status"] != "verified"
        or profile["source_values_included"] is not False
        or profile["table_count"] != EXPECTED_TABLE_COUNT
    ):
        raise ValueError("exact-era schema compatibility is not qualified")
    if authorization["dataset"] != identity["dataset"]:
        raise ValueError(
            "source authorization does not cover the exact dataset"
        )
    if authorization["external_publication_authorized"] is not True:
        raise ValueError(
            "existing source-specific publication authority is absent"
        )
    if (
        authorization["maintainer_asserted_redistribution_permission"]
        is not True
    ):
        raise ValueError("existing source-specific reuse authority is absent")
    basis = public_manifest["authorization_basis"]
    producer_commit = public_manifest["producer_commit"]
    if re.fullmatch(r"[0-9a-f]{40}", producer_commit) is None:
        raise ValueError(
            "public manifest producer commit is not a pinned Git object"
        )
    git_executable = shutil.which("git")
    if git_executable is None:
        raise RuntimeError(
            "git is required to verify the public manifest authority history"
        )
    for path, key in (
        (DECISION_PATH, "decision_sha256"),
        (AUTHORIZATION_PATH, "source_authorization_sha256"),
    ):
        historical_bytes = subprocess.run(
            [git_executable, "show", f"{producer_commit}:{path.as_posix()}"],
            shell=False,
            check=True,
            capture_output=True,
        ).stdout
        if hashlib.sha256(historical_bytes).hexdigest() != basis[key]:
            raise ValueError(
                "public manifest authorization basis is not historical-source bound"
            )
    if (
        parity["source_object_sha256"]
        != report["official_release_check"]["source_sha256"]
    ):
        raise ValueError(
            "source-to-Silver parity receipt binds another release"
        )
    if parity["production_admission"] is not False:
        raise ValueError("historical parity receipt must remain unmodified")
    if parity["rights_conclusion"] is not False:
        raise ValueError("parity receipt rights boundary changed")
    if (
        report["official_release_check"]["source_sha256"]
        != EXPECTED_SOURCE_SHA256
    ):
        raise ValueError(
            "candidate qualification binds another MBS source payload"
        )
    return report, public_manifest, parity, authorization


def build_semantic_manifest(
    report: dict[str, Any],
    public_manifest: dict[str, Any],
    parity: dict[str, Any],
) -> dict[str, Any]:
    meanings = _source_meanings()
    identity = report["public_v4_identity"]
    parity_tables = {table["table"]: table for table in parity["tables"]}
    objects = {
        item["path"].rsplit("/", 1)[-1].removesuffix(".parquet"): item
        for item in public_manifest["objects"]
        if item["role"] == "source_faithful_silver_table"
    }
    contracts_by_table: dict[str, list[Any]] = {}
    for field in mbs_field_contracts():
        contracts_by_table.setdefault(field.target_table, []).append(field)
    tables: list[dict[str, Any]] = []
    for table_name in sorted(contracts_by_table):
        parity_table = parity_tables[table_name]
        object_identity = objects[table_name]
        if (
            parity_table["silver_object_sha256"] != object_identity["sha256"]
            or parity_table["silver_object_bytes"]
            != object_identity["byte_count"]
            or parity_table["row_count"] != EXPECTED_RECORD_COUNT
        ):
            raise ValueError(
                "manifest table identity differs from parity receipt"
            )
        schema: Any = mbs_silver_schema(cast("TargetTable", table_name))
        field_specs: list[dict[str, Any]] = []
        for contract in contracts_by_table[table_name]:
            typed_type, unit = _TYPE_DETAILS[contract.value_type]
            arrow_type = schema.field(contract.native_name).type
            typed_value_type = str(arrow_type.field("typed_value").type)
            if typed_value_type.replace(" ", "") != typed_type.replace(" ", ""):
                raise ValueError(
                    "typed schema differs from the semantic mapping"
                )
            field_specs.append({
                "native_name": contract.native_name,
                "source_path": f"/MBS_XML/Data/{contract.native_name}",
                "target_table": table_name,
                "value_type": contract.value_type,
                "official_meaning": meanings[contract.native_name],
                "native_value_type": "string|null",
                "native_state_values": ["missing_field", "null", "value"],
                "conversion_status_values": [
                    "missing_field",
                    "null",
                    "blank",
                    "preserved",
                    "converted",
                    "invalid",
                    "unsupported_format",
                ],
                "typed_value_type": typed_value_type,
                "unit": unit,
                "date_format": "DD.MM.YYYY"
                if contract.value_type == "source_date"
                else "not_applicable",
                "temporal_role": _DATE_ROLES.get(
                    contract.native_name, "not_a_temporal_field"
                ),
                "max_integer_digits": _NUMERIC_WIDTHS.get(contract.native_name),
            })
        tables.append({
            "name": table_name,
            "path": object_identity["path"],
            "sha256": object_identity["sha256"],
            "byte_count": object_identity["byte_count"],
            "row_count": parity_table["row_count"],
            "schema_field_count": parity_table["field_count"],
            "schema_fields": [
                {"name": field.name, "type": str(field.type)}
                for field in schema
            ],
            "native_fields": field_specs,
        })
    if set(objects) != set(contracts_by_table):
        raise ValueError("public object and semantic table denominators differ")
    date_profile = _json(DATE_PROFILE_PATH)
    if (
        date_profile["source"]["sha256"]
        != report["official_release_check"]["source_sha256"]
        or date_profile["date_profile"]["format"] != "DD.MM.YYYY"
        or date_profile["date_profile"]["invalid_or_unsupported_date_values"]
        != 0
        or set(date_profile["date_profile"]["date_fields"]) != set(_DATE_ROLES)
    ):
        raise ValueError("source-era date semantics are not qualified")
    return {
        "schema_id": "global-medicines-atlas.australian-mbs-silver-semantic-manifest",
        "schema_version": 1,
        "status": "qualified_exact_source_era_semantics",
        "source_identity": {
            "source_id": "au-mbs",
            "schema_era": "2025-07-version-3",
            "source_sha256": report["official_release_check"]["source_sha256"],
            "source_byte_count": report["official_release_check"][
                "source_byte_count"
            ],
            "source_record_count": report["qualification"][
                "source_record_count"
            ],
            "release_id": report["official_release_check"]["release_id"],
            "effective_at": report["official_release_check"]["effective_at"],
        },
        "public_dataset_identity": {
            "dataset": identity["dataset"],
            "current_revision": identity["current_revision"],
            "manifest_sha256": identity["manifest_sha256"],
            "prefix": identity["prefix"],
            "candidate_only": True,
        },
        "domain_contract": {
            "subject_kind": "service",
            "dimension": "service_benefit",
            "mapping_status": "source_native",
            "absence_interpretation": "unknown",
        },
        "evidence": {
            "qualification_run": "https://github.com/edithatogo/global-medicines-atlas/actions/runs/38953649119",
            "qualification_commit": report["exact_commit"],
            "qualification_report_path": str(QUALIFICATION_PATH),
            "qualification_report_sha256": _sha256(QUALIFICATION_PATH),
            "candidate_report_sha256": report["candidate_report_sha256"],
            "parity_receipt_path": str(PARITY_PATH),
            "parity_receipt_sha256": _sha256(PARITY_PATH),
            "field_semantics_path": str(SEMANTICS_PATH),
            "field_semantics_sha256": _sha256(SEMANTICS_PATH),
            "date_profile_path": str(DATE_PROFILE_PATH),
            "date_profile_sha256": _sha256(DATE_PROFILE_PATH),
            "transformation_path": str(TRANSFORM_PATH),
            "transformation_sha256": _sha256(TRANSFORM_PATH),
            "conversion_path": str(CONVERSION_PATH),
            "conversion_sha256": _sha256(CONVERSION_PATH),
            "conversion_version": CONVERSION_VERSION,
        },
        "row_identity_fields": [
            {"name": "source_record_id", "type": "string", "nullable": False},
            {"name": "source_ordinal", "type": "int64", "nullable": False},
            {"name": "source_sha256", "type": "string", "nullable": False},
            {"name": "receipt_sha256", "type": "string", "nullable": False},
        ],
        "temporal_contract": {
            "date_format": "DD.MM.YYYY",
            "date_profile_id": "mbs-dmy",
            "date_field_count": len(_DATE_ROLES),
            "date_profile_path": str(DATE_PROFILE_PATH),
            "null_and_missing_remain_distinct": True,
            "snapshot_relative_validity": True,
        },
        "numeric_width_contract": {
            "official_profile_id": "mbs-xml-official-field-length-v1",
            "max_integer_digits": _NUMERIC_WIDTHS,
            "native_text_preserved": True,
            "out_of_width_values_are_invalid": True,
            "percentage_values_are_not_divided_or_rescaled": True,
        },
        "tables": tables,
        "boundaries": {
            "source_values_included": False,
            "source_bytes_retained": False,
            "publication_performed": False,
            "public_candidate_promoted": False,
            "M109_full_denominator_accepted": False,
            "M110_gold_graph_accepted": False,
            "M112_federation_accepted": False,
            "includes_patient_denominator": False,
            "makes_pbs_or_clinical_equivalence_claim": False,
        },
    }


def build_admission(
    report: dict[str, Any],
    semantic: dict[str, Any],
    admitted_at: str,
    semantic_manifest_sha256: str,
) -> dict[str, Any]:
    authorization = _json(AUTHORIZATION_PATH)
    public_manifest = _json(PUBLIC_MANIFEST_PATH)
    return {
        "schema_id": "global-medicines-atlas.australian-mbs-silver-admission",
        "schema_version": 1,
        "status": "admitted_scoped_source_era_for_m110_graph_qualification",
        "recorded_at": admitted_at,
        "admission_scope": "M-110 Gold graph qualification input only",
        "admission_basis": "Existing Decision 0009 and exact-source publication authorization; no new licensing interpretation",
        "source_identity": semantic["source_identity"],
        "public_dataset_identity": semantic["public_dataset_identity"],
        "semantic_manifest": {
            "path": str(SEMANTIC_OUTPUT_PATH),
            "sha256": semantic_manifest_sha256,
        },
        "qualification_evidence": {
            "run": "https://github.com/edithatogo/global-medicines-atlas/actions/runs/38953649119",
            "exact_commit": report["exact_commit"],
            "report_path": str(QUALIFICATION_PATH),
            "report_sha256": _sha256(QUALIFICATION_PATH),
            "artifact_id": "12070470185",
            "artifact_name": "australian-mbs-silver-candidate-38953649119-1",
            "candidate_report_sha256": report["candidate_report_sha256"],
            "current_blockers": report["current_blockers"],
            "source_bytes_retained": report["source_bytes_retained"],
            "publication_performed": report["publication_performed"],
        },
        "authority": {
            "decision_path": str(DECISION_PATH),
            "decision_sha256": _sha256(DECISION_PATH),
            "source_authorization_path": str(AUTHORIZATION_PATH),
            "source_authorization_sha256": _sha256(AUTHORIZATION_PATH),
            "existing_external_publication_authorization": authorization[
                "external_publication_authorized"
            ],
            "existing_maintainer_redistribution_assertion": authorization[
                "maintainer_asserted_redistribution_permission"
            ],
            "rights_conclusion_made_by_this_receipt": False,
            "public_manifest_authority_basis_matches": True,
        },
        "tables": [
            {
                "name": table["name"],
                "path": table["path"],
                "sha256": table["sha256"],
                "byte_count": table["byte_count"],
                "row_count": table["row_count"],
                "schema_field_count": table["schema_field_count"],
            }
            for table in semantic["tables"]
        ],
        "separation": {
            "public_candidate_remains_candidate_only": public_manifest[
                "candidate_only"
            ],
            "production_admission_or_promotion": False,
            "public_dataset_mutation": False,
            "source_payload_retention": False,
            "M109_full_denominator_accepted": False,
            "M110_gold_graph_accepted": False,
            "M112_federation_accepted": False,
        },
        "limitations": [
            "Only the exact July 2025 MBS XML v3 source identity and six named tables are admitted for M-110 graph qualification.",
            "P7, other MBS eras, PBS, terminology, and participant denominators are excluded.",
            "Admission does not establish an MBS-to-medicine clinical, therapeutic-equivalence, regulatory, funding, or formulary claim.",
            "Full M-109, M-110 Gold graph, and M-112 acceptance remain incomplete.",
        ],
    }


def _validate(schema_path: Path, value: dict[str, Any]) -> None:
    schema = _json(schema_path)
    _validate_json_schema(schema, value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail unless committed manifest and receipt match the verified inputs",
    )
    args = parser.parse_args(argv)
    report, public_manifest, parity, _ = _verified_inputs()
    semantic = build_semantic_manifest(report, public_manifest, parity)
    _validate(SEMANTIC_SCHEMA_PATH, semantic)
    semantic_bytes = (
        json.dumps(semantic, indent=2, ensure_ascii=False) + "\n"
    ).encode()
    semantic_sha = hashlib.sha256(semantic_bytes).hexdigest()
    admission = build_admission(
        report,
        semantic,
        datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        semantic_sha,
    )
    _validate(ADMISSION_SCHEMA_PATH, admission)
    admission_bytes = (
        json.dumps(admission, indent=2, ensure_ascii=False) + "\n"
    ).encode()
    if args.check:
        if (ROOT / SEMANTIC_OUTPUT_PATH).read_bytes() != semantic_bytes:
            raise SystemExit(
                "semantic manifest is stale; regenerate from current exact evidence"
            )
        current_admission = _json(ADMISSION_OUTPUT_PATH)
        _validate(ADMISSION_SCHEMA_PATH, current_admission)
        for key, value in admission.items():
            if key == "recorded_at":
                continue
            if current_admission.get(key) != value:
                raise SystemExit(
                    "MBS Silver admission receipt is stale or mismatched"
                )
        print("MBS Silver semantic manifest and scoped admission checks passed")
        return 0
    (ROOT / SEMANTIC_OUTPUT_PATH).write_bytes(semantic_bytes)
    (ROOT / ADMISSION_OUTPUT_PATH).write_bytes(admission_bytes)
    print(
        f"wrote exact-era MBS semantic manifest and M-110 scoped admission "
        f"for {len(semantic['tables'])} tables"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
