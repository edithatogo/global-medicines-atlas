"""Actual aggregate receipts support only native-unresolved PBS field states."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from scripts import reconcile_pbs_native_silver_receipts as module

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = (
    ROOT
    / "quality/qualifications/pbs-native-value-package-v2-20261022-39721534876.json"
)
SCREEN = (
    ROOT
    / "quality/qualifications/pbs-native-reference-screen-20261022-39730665004.json"
)


def _changed(tmp_path, source, update):
    target = tmp_path / source.name
    shutil.copyfile(source, target)
    envelope = json.loads(target.read_bytes())
    update(envelope["report"])
    if source == PACKAGE:
        manifest = envelope["report"]["qualification"]["package"]
        identity = {
            key: value for key, value in manifest.items() if key != "output_id"
        }
        manifest["output_id"] = hashlib.sha256(
            module.canonical_package_json(identity)
        ).hexdigest()
    encoded = json.dumps(
        envelope["report"],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    envelope["report_sha256"] = hashlib.sha256(encoded).hexdigest()
    target.write_text(json.dumps(envelope))
    return target


def test_exact_actual_receipts_bind_candidate_output_and_all_field_states():
    report = module.reconcile(PACKAGE, SCREEN)
    assert report["status"] == "passed"
    assert report["package_run_id"] == "39721534876"
    assert report["screen_run_id"] == "39730665004"
    assert report["package_workflow_commit"] != report["screen_workflow_commit"]
    assert report["field_state_coverage"] == {
        "source_fields": 18_208_758,
        "native_unresolved_fields": 18_208_758,
        "interpreted_fields": 0,
        "unavailable_patient_rates": True,
    }
    output = report["candidate_output"]
    assert output["parquet_bytes"] == 637_012_122
    assert output["rights_qualified"] is False
    assert output["admitted"] is False
    assert output["published"] is False
    assert report["source_local_reference_screen"]["reference_fields"] == (
        2_160_066
    )
    assert (
        sum(
            report["source_local_reference_screen"][
                "reference_status_counts"
            ].values()
        )
        == 2_160_066
    )
    assert (
        report["source_local_reference_screen"][
            "semantic_relationships_qualified"
        ]
        is False
    )
    assert report["domain_semantics_qualified"] is False


@pytest.mark.parametrize(
    ("source", "update", "error"),
    [
        (
            "package",
            lambda report: report["qualification"]["package"][
                "coverage"
            ].update(native_fields=1),
            "identity",
        ),
        (
            "package",
            lambda report: report["qualification"]["package"][
                "boundaries"
            ].update(admitted=True),
            "qualification",
        ),
        (
            "screen",
            lambda report: report["qualification"][
                "reference_status_counts"
            ].update(no_exact_literal=1),
            "denominator",
        ),
        (
            "screen",
            lambda report: report["qualification"].update(
                semantic_relationships_qualified=True
            ),
            "denominator",
        ),
    ],
)
def test_rejects_identity_count_and_semantic_promotion(
    tmp_path, source, update, error
):
    if source == "package":
        package = _changed(tmp_path, PACKAGE, update)
        screen = SCREEN
    else:
        package = PACKAGE
        screen = _changed(tmp_path, SCREEN, update)
    with pytest.raises(ValueError, match=error):
        module.reconcile(package, screen)


def test_rejects_tampered_envelope_and_symlink(tmp_path):
    copied = tmp_path / PACKAGE.name
    shutil.copyfile(PACKAGE, copied)
    envelope = json.loads(copied.read_bytes())
    envelope["report_sha256"] = "0" * 64
    copied.write_text(json.dumps(envelope))
    with pytest.raises(ValueError, match="envelope digest"):
        module.reconcile(copied, SCREEN)
    copied.unlink()
    copied.symlink_to(PACKAGE)
    with pytest.raises(ValueError, match="file"):
        module.reconcile(copied, SCREEN)


def test_rejects_array_digest_with_rehashed_output_id(tmp_path):
    def change(report):
        package = report["qualification"]["package"]
        digest = ["a"] * 64
        package["parquet"]["sha256"] = digest
        report["qualification"]["restored_file_digest"]["sha256"] = digest

    package = _changed(tmp_path, PACKAGE, change)
    with pytest.raises(ValueError, match="identity"):
        module.reconcile(package, SCREEN)


def test_cli_preserves_existing_output(tmp_path):
    output = tmp_path / "reconciled.json"
    args = [
        "--package-receipt",
        str(PACKAGE),
        "--screen-receipt",
        str(SCREEN),
        "--output",
        str(output),
    ]
    assert module.main(args) == 0
    assert json.loads(output.read_bytes())["status"] == "passed"
    with pytest.raises(SystemExit):
        module.main(args)
