"""Synthetic MBS profile/federation bindings grant no admission or rights."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError
from test_mbs_silver import (
    _receipt,  # ruff: ignore[import-private-name] - shared synthetic fixture
    _xml,  # ruff: ignore[import-private-name] - shared synthetic fixture
)

import global_medicines_atlas.mbs_federation_profile as subject
from global_medicines_atlas.mbs_historical_comparison import (
    MbsNativeKey,
    build_mbs_comparison_cohort,
)
from global_medicines_atlas.mbs_schema_profile import (
    MbsNativeProfileBinding,
    MbsSchemaProfileDeclaration,
    bind_mbs_profile_to_native_cohort,
)

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "contracts/medallion/v4/fixtures/valid.json"
)


def declaration() -> MbsSchemaProfileDeclaration:
    return MbsSchemaProfileDeclaration(
        source_id="au-mbs",
        source_revision="2026-08-01",
        b1_sha256="a" * 64,
        b2_sha256="b" * 64,
        comparison_schema_profile="mbs-xml-dmy-v1",
    )


def document(source_revision: str = "2026-08-01") -> dict:
    value = json.loads(FIXTURE.read_text())
    value["source"].update(
        source_id="au-mbs",
        layer="silver",
        bronze_stratum=None,
        representation="projection",
        schema_era=source_revision,
    )
    value["lineage"]["inputs"] = [value["verification"]["receipt"]]
    value["lineage"]["promotion_receipt"] = value["verification"]["receipt"]
    return value


def native_profile() -> tuple[
    MbsSchemaProfileDeclaration, MbsNativeProfileBinding
]:
    payload = _xml("<ScheduleFee>1.00</ScheduleFee>")
    receipt = _receipt(payload)
    declaration_value = MbsSchemaProfileDeclaration(
        source_id="au-mbs",
        source_revision=receipt.source.catalog_version,
        b1_sha256=receipt.digest(),
        b2_sha256=receipt.payload.sha256,
        comparison_schema_profile="synthetic-mbs-xml-v1",
    )
    cohort = build_mbs_comparison_cohort(
        payload,
        receipt,
        table="fees",
        selected_native_keys=(
            MbsNativeKey(
                item_num="00123",
                sub_item_state="value",
                sub_item_value="00",
            ),
        ),
        schema_era="synthetic-mbs-xml-v1",
        expected_source_revision=receipt.source.catalog_version,
    )
    return declaration_value, bind_mbs_profile_to_native_cohort(
        declaration_value, cohort
    )


def test_binds_profile_without_changing_v4_or_promoting_status():
    value = document()
    before = copy.deepcopy(value)
    result = subject.bind_mbs_profile_to_federation(
        declaration(), cast("dict[str, Any]", value)
    )
    assert value == before
    assert result.status == "declared"
    assert result.source_revision == value["source"]["schema_era"]
    assert result.comparison_schema_profile == "mbs-xml-dmy-v1"
    assert result.dataset == value["location"]["dataset"]
    assert result.b1_sha256 == "a" * 64
    with pytest.raises(ValidationError):
        subject.MbsFederationProfileBinding.model_validate({
            **result.model_dump(),
            "status": "qualified",
        })


def test_pairs_federation_record_with_exact_native_cohort():
    native_declaration, native = native_profile()
    value = document(native.source_revision)
    federation = subject.bind_mbs_profile_to_federation(
        native_declaration, value
    )

    result = subject.bind_mbs_native_profile_to_federation(
        native_declaration, value, native
    )

    assert result.status == "declared"
    assert result.federation.federation_document_sha256 == (
        federation.federation_document_sha256
    )
    assert result.native.native_cohort_sha256 == native.native_cohort_sha256
    assert result.binding_sha256


def test_rejects_federation_to_native_identity_mismatch():
    native_declaration, native = native_profile()
    value = document(native.source_revision)
    mismatched = native.model_copy(
        update={"comparison_schema_profile": "other-mbs-schema-v1"}
    )

    with pytest.raises(ValueError, match="invalid MBS federated native"):
        subject.bind_mbs_native_profile_to_federation(
            native_declaration, value, mismatched
        )


def test_revalidates_federated_native_binding_digest():
    native_declaration, native = native_profile()
    value = document(native.source_revision)
    result = subject.bind_mbs_native_profile_to_federation(
        native_declaration, value, native
    )

    with pytest.raises(ValueError, match="federated native binding digest"):
        subject.MbsFederatedNativeProfileBinding.model_validate({
            **result.model_dump(mode="json"),
            "binding_sha256": "f" * 64,
        })


@pytest.mark.parametrize("cohort", ["legacy", "current", "synthetic"])
def test_accepts_only_native_v4_cohorts(cohort):
    value = document()
    value["source"]["comparison_cohort"] = cohort
    value["evidence_kind"] = "synthetic" if cohort == "synthetic" else "live"
    result = subject.bind_mbs_profile_to_federation(
        declaration(), cast("dict[str, Any]", value)
    )
    assert result.comparison_cohort == cohort


def test_rejects_historical_without_silent_mapping():
    value = document()
    value["source"]["comparison_cohort"] = "historical"
    with pytest.raises(ValueError, match="invalid MBS federation"):
        subject.bind_mbs_profile_to_federation(
            declaration(), cast("dict[str, Any]", value)
        )


def test_rejects_cohort_evidence_class_mismatch():
    value = document()
    value["source"]["comparison_cohort"] = "current"
    with pytest.raises(ValueError, match="invalid MBS federation"):
        subject.bind_mbs_profile_to_federation(
            declaration(), cast("dict[str, Any]", value)
        )


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("version",), "5.0.0"),
        (("authority", "schema_sha256"), "f" * 64),
        (("source", "source_id"), "au-pbs"),
        (("source", "layer"), "gold"),
        (("source", "bronze_stratum"), "B2"),
        (("source", "representation"), "raw"),
        (("source", "schema_era"), "2025-07-01"),
    ],
)
def test_rejects_wrong_federation_identity(path, value):
    candidate = document()
    target = candidate
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError, match="invalid MBS federation"):
        subject.bind_mbs_profile_to_federation(declaration(), candidate)


def test_rejects_semantically_invalid_v4_before_binding():
    candidate = document()
    candidate["verification"]["sha256"] = "f" * 64
    with pytest.raises(ValueError, match="invalid MBS federation"):
        subject.bind_mbs_profile_to_federation(declaration(), candidate)


def test_rejects_invalid_input_without_disclosing_it():
    for value in (None, [], {"secret": "do-not-print"}):
        with pytest.raises(ValueError, match="invalid MBS federation") as error:
            subject.bind_mbs_profile_to_federation(
                declaration(), cast("dict[str, Any]", value)
            )
        assert "secret" not in str(error.value)
        assert error.value.__cause__ is None


def test_bounds_document_before_semantic_traversal(monkeypatch):
    candidate = document()
    monkeypatch.setattr(subject, "MAX_FEDERATION_DOCUMENT_BYTES", 1)
    with pytest.raises(ValueError, match="invalid MBS federation"):
        subject.bind_mbs_profile_to_federation(declaration(), candidate)


def test_revalidates_copied_declaration():
    invalid = declaration().model_copy(update={"status": "qualified"})
    with pytest.raises(ValueError, match="invalid MBS federation"):
        subject.bind_mbs_profile_to_federation(invalid, document())
