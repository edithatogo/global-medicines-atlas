"""The July 2025 MBS candidate has a narrow, hash-bound M-110 admission."""

from __future__ import annotations

import copy
import hashlib
import json

import pytest
from jsonschema import Draft202012Validator, ValidationError
from scripts import qualify_australian_mbs_silver_admission as qualification


def test_exact_source_semantics_and_admission_are_bound_to_six_real_tables() -> (
    None
):
    report, public_manifest, parity, _ = qualification._verified_inputs()
    semantic = qualification.build_semantic_manifest(
        report, public_manifest, parity
    )
    semantic_bytes = (
        qualification.ROOT / qualification.SEMANTIC_OUTPUT_PATH
    ).read_bytes()
    admission = qualification._json(qualification.ADMISSION_OUTPUT_PATH)

    assert json.loads(semantic_bytes) == semantic
    assert (
        admission["semantic_manifest"]["sha256"]
        == hashlib.sha256(semantic_bytes).hexdigest()
    )
    assert [table["name"] for table in semantic["tables"]] == [
        "benefits",
        "caps",
        "descriptions",
        "fees",
        "hierarchy",
        "services",
    ]
    assert (
        sum(len(table["native_fields"]) for table in semantic["tables"]) == 40
    )
    assert all(table["row_count"] == 5989 for table in semantic["tables"])
    assert semantic["boundaries"]["M110_gold_graph_accepted"] is False
    assert semantic["public_dataset_identity"]["candidate_only"] is True
    assert (
        admission["authority"]["rights_conclusion_made_by_this_receipt"]
        is False
    )
    assert admission["separation"]["public_dataset_mutation"] is False


@pytest.mark.parametrize(
    ("document", "mutator"),
    [
        (
            "semantic",
            lambda value: value["source_identity"].update(
                source_sha256="0" * 64
            ),
        ),
        (
            "semantic",
            lambda value: value["boundaries"].update(
                M110_gold_graph_accepted=True
            ),
        ),
        (
            "semantic",
            lambda value: value["public_dataset_identity"].update(
                candidate_only=False
            ),
        ),
        ("admission", lambda value: value["tables"].pop()),
        (
            "admission",
            lambda value: value["authority"].update(
                rights_conclusion_made_by_this_receipt=True
            ),
        ),
        (
            "admission",
            lambda value: value["separation"].update(
                public_dataset_mutation=True
            ),
        ),
    ],
)
def test_schema_rejects_identity_or_scope_widening(
    document: str, mutator
) -> None:
    if document == "semantic":
        path = qualification.SEMANTIC_OUTPUT_PATH
        schema_path = qualification.SEMANTIC_SCHEMA_PATH
    else:
        path = qualification.ADMISSION_OUTPUT_PATH
        schema_path = qualification.ADMISSION_SCHEMA_PATH
    value = copy.deepcopy(qualification._json(path))
    mutator(value)
    with pytest.raises(ValidationError):
        qualification._validate(schema_path, value)


def test_semantic_and_admission_schemas_validate_current_receipts() -> None:
    for schema_path, receipt_path in (
        (
            qualification.SEMANTIC_SCHEMA_PATH,
            qualification.SEMANTIC_OUTPUT_PATH,
        ),
        (
            qualification.ADMISSION_SCHEMA_PATH,
            qualification.ADMISSION_OUTPUT_PATH,
        ),
    ):
        schema = qualification._json(schema_path)
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(qualification._json(receipt_path))


def test_admission_binds_exact_serialized_semantic_manifest_bytes() -> None:
    semantic = qualification._json(qualification.SEMANTIC_OUTPUT_PATH)
    admission = qualification._json(qualification.ADMISSION_OUTPUT_PATH)
    semantic_bytes = (
        qualification.ROOT / qualification.SEMANTIC_OUTPUT_PATH
    ).read_bytes()
    assert (
        admission["semantic_manifest"]["sha256"]
        == hashlib.sha256(semantic_bytes).hexdigest()
    )
    assert (
        admission["qualification_evidence"]["report_sha256"]
        == semantic["evidence"]["qualification_report_sha256"]
    )


def test_current_assessment_supersedes_pre_fix_snapshot_without_accepting_graph() -> (
    None
):
    path = qualification.ROOT / (
        "quality/qualifications/"
        "australian-m110-mbs-july-2025-silver-assessment-20261017-8c0090db.json"
    )
    assessment = json.loads(path.read_text(encoding="utf-8"))
    admission = qualification._json(qualification.ADMISSION_OUTPUT_PATH)
    assert assessment["supersedes_assessment"]["path"].endswith(
        "australian-m110-mbs-july-2025-silver-assessment-20261017.json"
    )
    assert (
        assessment["evidence"]["admission_receipt_sha256"]
        == hashlib.sha256(
            (
                qualification.ROOT / qualification.ADMISSION_OUTPUT_PATH
            ).read_bytes()
        ).hexdigest()
    )
    assert assessment["status"] == (
        "scoped_mbs_silver_admitted_for_m110_gold_graph_qualification_only"
    )
    assert assessment["gate_assessment"]["gold_graph_qualification"].startswith(
        "pending_"
    )
    assert admission["separation"]["M110_gold_graph_accepted"] is False


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.update(recorded_at="not-a-date"),
        lambda value: value.update(unexpected_property="forged"),
    ],
)
def test_check_rejects_malformed_or_open_stored_admission(
    monkeypatch, mutate
) -> None:
    read_json = qualification._json

    def read_forged(path):
        value = read_json(path)
        if path == qualification.ADMISSION_OUTPUT_PATH:
            mutate(value)
        return value

    monkeypatch.setattr(qualification, "_json", read_forged)
    with pytest.raises(ValidationError):
        qualification.main(["--check"])
