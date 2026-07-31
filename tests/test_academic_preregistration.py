"""Phase 3 contracts for the offline OSF-ready preregistration package."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError
from scripts.build_academic_preregistration import build_bundle

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "research/preregistration/osf-preregistration-v1.json"
SCHEMA = ROOT / "schemas/osf-preregistration-package-v1.json"
MANIFEST_SCHEMA = ROOT / "schemas/osf-submission-manifest-v1.json"
MANIFEST = ROOT / "dist/preregistration/osf-submission-manifest.json"
OUTPUT = ROOT / "dist/preregistration"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_preregistration_contract_is_strict_and_offline_only() -> None:
    schema = _load(SCHEMA)
    Draft202012Validator.check_schema(schema)
    package = _load(PACKAGE)
    Draft202012Validator(schema).validate(package)
    assert package["status"] == "draft_not_submitted"
    assert package["external_actions_permitted"] is False
    assert package["maintainer_review"]["complete"] is False
    assert package["outcome_dimensions"] == ["regulatory_status", "funding_status"]
    with pytest.raises(ValidationError, match="Additional properties"):
        Draft202012Validator(schema).validate({**package, "osf_id": "invented"})


def test_governance_statements_and_append_only_registers_are_present() -> None:
    package = _load(PACKAGE)
    assert package["ethics"]["individual_participant_data"] is False
    assert package["ethics"]["clinical_decision_support"] is False
    assert package["data_management"]["restricted_payload_redistribution"] is False
    for register in ("amendments", "deviations"):
        path = ROOT / package["registers"][register]
        assert path.is_file()
        assert path.read_text(encoding="utf-8").startswith("#")


def test_bundle_is_deterministic_and_manifest_checks_every_attachment(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    build_bundle(PACKAGE, first, ROOT)
    build_bundle(PACKAGE, second, ROOT)
    assert {p.relative_to(first): p.read_bytes() for p in first.rglob("*") if p.is_file()} == {
        p.relative_to(second): p.read_bytes() for p in second.rglob("*") if p.is_file()
    }
    manifest = _load(first / MANIFEST.name)
    Draft202012Validator(_load(MANIFEST_SCHEMA)).validate(manifest)
    assert manifest["network_access"] == "prohibited"
    assert manifest["submission_state"] == "offline_rehearsal_only"
    for artifact in manifest["artifacts"]:
        content = (first / artifact["path"]).read_bytes()
        assert artifact["sha256"] == hashlib.sha256(content).hexdigest()
        assert artifact["bytes"] == len(content)


def test_citations_are_resolvable_and_have_stable_identifiers() -> None:
    citations = _load(ROOT / "research/preregistration/citations.json")
    keys = {item["citation_id"] for item in citations["citations"]}
    assert keys == set(_load(PACKAGE)["citation_ids"])
    assert all(item.get("doi") or item.get("url") for item in citations["citations"])


def test_committed_bundle_matches_builder() -> None:
    expected = build_bundle(PACKAGE, None, ROOT)
    actual = {p.relative_to(OUTPUT).as_posix(): p.read_bytes() for p in OUTPUT.rglob("*") if p.is_file()}
    assert actual == expected


def test_documented_offline_commands_run_in_clean_output_directory(tmp_path: Path) -> None:
    output = tmp_path / "rehearsal"
    subprocess.run(
        [sys.executable, "-m", "scripts.build_academic_preregistration", "--output", str(output)],
        cwd=ROOT,
        check=True,
        timeout=60,
    )
    subprocess.run(
        [sys.executable, "-m", "scripts.validate_academic_preregistration", "--bundle", str(output)],
        cwd=ROOT,
        check=True,
        timeout=60,
    )

