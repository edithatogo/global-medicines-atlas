"""Pure metadata history plans never perform or authorize publication."""

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from global_medicines_atlas.donor_delta import DeltaObservation
from global_medicines_atlas.donor_history_publication import (
    DonorHistoryPublicationContract,
    DurableHistoryReceipt,
    HistoryAppendPlan,
    HistoryVerification,
    cleanup_preconditions_match,
    observation_digest,
    require_donor_history_hosted_authority,
    validate_append_plan,
    verification_digest,
)


def test_empty_history_plan_fails_closed():
    with pytest.raises(ValueError, match="validation errors"):
        HistoryAppendPlan.model_validate({})


def test_checked_in_publication_contract_is_exact_and_inert(monkeypatch):
    raw = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "quality/qualifications/australian-donor-history-publication-contract.json"
        ).read_text()
    )
    contract = DonorHistoryPublicationContract.model_validate(raw)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", "edithatogo/global-medicines-atlas")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    with pytest.raises(ValueError, match="not authorized"):
        require_donor_history_hosted_authority(contract)


def test_history_authority_rejects_non_hosted_context(monkeypatch):
    raw = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "quality/qualifications/australian-donor-history-publication-contract.json"
        ).read_text()
    )
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with pytest.raises(ValueError, match="GitHub Actions on main"):
        require_donor_history_hosted_authority(
            DonorHistoryPublicationContract.model_validate(raw)
        )


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("GITHUB_REPOSITORY", "edithatogo/another-repository"),
        ("GITHUB_REF", "refs/heads/not-main"),
    ],
)
def test_history_authority_rejects_hosted_scope_drift(
    monkeypatch, variable, value
):
    raw = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "quality/qualifications/australian-donor-history-publication-contract.json"
        ).read_text()
    )
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", "edithatogo/global-medicines-atlas")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv(variable, value)
    with pytest.raises(ValueError, match="GitHub Actions on main"):
        require_donor_history_hosted_authority(
            DonorHistoryPublicationContract.model_validate(raw)
        )


def test_history_authority_accepts_exact_authorized_hosted_contract(
    monkeypatch,
):
    raw = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "quality/qualifications/australian-donor-history-publication-contract.json"
        ).read_text()
    )
    raw["publication_authorized"] = True
    raw["authorization_reference"] = (
        "https://github.com/edithatogo/global-medicines-atlas/"
        "issues/339#issuecomment-123"
    )
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", "edithatogo/global-medicines-atlas")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    assert (
        require_donor_history_hosted_authority(
            DonorHistoryPublicationContract.model_validate(raw)
        )
        is None
    )


def test_history_contract_requires_exact_authorization_receipt():
    raw = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "quality/qualifications/australian-donor-history-publication-contract.json"
        ).read_text()
    )
    raw["publication_authorized"] = True
    with pytest.raises(ValidationError, match="must agree"):
        DonorHistoryPublicationContract.model_validate(raw)
    raw["authorization_reference"] = (
        "https://github.com/edithatogo/global-medicines-atlas/"
        "issues/340#issuecomment-123"
    )
    with pytest.raises(ValidationError):
        DonorHistoryPublicationContract.model_validate(raw)


def test_history_contract_rejects_different_donor_heads():
    raw = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "quality/qualifications/australian-donor-history-publication-contract.json"
        ).read_text()
    )
    raw["heads"][0][1] = "f" * 40
    with pytest.raises(ValidationError, match="heads differ"):
        DonorHistoryPublicationContract.model_validate(raw)


def plan():
    fixture = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "quality/qualifications/australian-donor-delta.json"
        ).read_text()
    )
    extensions = []
    baseline_objects = []
    for review in fixture["reviews"]:
        observed = review["observation"]
        name = observed["repository"].split("/")[1]
        baseline_objects.append({
            "path": f"history/{name}-{observed['baseline']}.bundle",
            "sha256": "a" * 64,
            "byte_count": 100,
        })
        extensions.append({
            "observation": observed,
            "delta_sha256": observation_digest(
                DeltaObservation.model_validate(observed)
            ),
            "bundle": {
                "path": f"history/{name}-{observed['head']}.bundle",
                "sha256": "b" * 64,
                "byte_count": 10,
            },
            "manifest": {
                "path": f"provenance/donor-deltas/{name}-{observed['head']}.json",
                "sha256": "c" * 64,
                "byte_count": 20,
            },
        })
    return {
        "before": {
            "dataset": "edithatogo/australian-mbs-source-archive",
            "revision": "d" * 40,
            "private": False,
            "gated": False,
            "objects": baseline_objects,
        },
        "extensions": extensions,
    }


def verified():
    raw = plan()
    objects = copy.deepcopy(raw["before"]["objects"])
    restored = []
    for extension in raw["extensions"]:
        observed = extension["observation"]
        objects.extend([extension["bundle"], extension["manifest"]])
        restored.append({
            "repository": observed["repository"],
            "head": observed["head"],
            "baseline": observed["baseline"],
            "baseline_bundle_sha256": "a" * 64,
            "bundle_sha256": "b" * 64,
            "delta_sha256": extension["delta_sha256"],
            "prerequisites": [observed["baseline"]],
            "baseline_is_ancestor": True,
            "clean_restore": True,
        })
    return {
        "plan": raw,
        "parent_revision": raw["before"]["revision"],
        "after": {**raw["before"], "revision": "e" * 40, "objects": objects},
        "anonymous_objects": copy.deepcopy(objects),
        "restored": restored,
    }


def test_valid_plan_and_durable_receipt_match_without_authority():
    checked = HistoryVerification.model_validate(verified())
    receipt = DurableHistoryReceipt(
        issue_comment="https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-123",
        verification_sha256=verification_digest(checked),
    )
    assert cleanup_preconditions_match(checked, receipt)
    assert not cleanup_preconditions_match(
        checked, receipt.model_copy(update={"verification_sha256": "f" * 64})
    )
    assert "archive_authorized" not in checked.model_dump()


@pytest.mark.parametrize("field", ["private", "gated"])
def test_nonpublic_target_rejected(field):
    raw = plan()
    raw["before"][field] = True
    with pytest.raises(ValidationError):
        HistoryAppendPlan.model_validate(raw)


@pytest.mark.parametrize(
    "case", ["head", "digest", "bundle", "manifest", "donor", "baseline"]
)
def test_wrong_extension_or_baseline(case):
    raw = plan()
    first = raw["extensions"][0]
    if case == "head":
        first["observation"]["head"] = "f" * 40
    elif case == "digest":
        first["delta_sha256"] = "f" * 64
    elif case in {"bundle", "manifest"}:
        first[case]["path"] = "other/path"
    elif case == "donor":
        raw["extensions"][1] = copy.deepcopy(first)
    else:
        raw["before"]["objects"].pop()
    with pytest.raises(ValidationError):
        HistoryAppendPlan.model_validate(raw)


def test_identical_existing_objects_are_reusable_not_overwritten():
    raw = plan()
    raw["before"]["objects"].append(raw["extensions"][0]["bundle"])
    HistoryAppendPlan.model_validate(raw)
    raw["before"]["objects"][-1] = {
        **raw["before"]["objects"][-1],
        "byte_count": 11,
    }
    with pytest.raises(ValidationError, match="overwrite"):
        HistoryAppendPlan.model_validate(raw)


@pytest.mark.parametrize(
    "case",
    [
        "cas",
        "revision",
        "sibling",
        "bytes",
        "anonymous",
        "duplicate",
        "restore",
    ],
)
def test_invalid_verification(case):
    raw = verified()
    if case == "cas":
        raw["parent_revision"] = "f" * 40
    elif case == "revision":
        raw["after"]["revision"] = raw["parent_revision"]
    elif case == "sibling":
        raw["after"]["objects"].pop()
    elif case == "bytes":
        raw["after"]["objects"][0]["byte_count"] += 1
    elif case == "anonymous":
        raw["anonymous_objects"][0]["sha256"] = "f" * 64
    elif case == "duplicate":
        raw["restored"][1] = raw["restored"][0]
    else:
        raw["restored"][0]["prerequisites"] = ["f" * 40]
    with pytest.raises(ValidationError):
        HistoryVerification.model_validate(raw)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("head", "f" * 40),
        ("baseline", "f" * 40),
        ("baseline_bundle_sha256", "f" * 64),
        ("bundle_sha256", "f" * 64),
        ("delta_sha256", "f" * 64),
        ("baseline_is_ancestor", False),
        ("clean_restore", False),
    ],
)
def test_restoration_must_match_every_binding(field, value):
    raw = verified()
    raw["restored"][0][field] = value
    with pytest.raises(ValidationError):
        HistoryVerification.model_validate(raw)


def test_duplicate_inventory_paths_rejected():
    raw = plan()
    raw["before"]["objects"].append(raw["before"]["objects"][0])
    with pytest.raises(ValidationError, match="duplicate"):
        HistoryAppendPlan.model_validate(raw)


def test_revalidates_copied_verification_before_cleanup_check():
    parsed = HistoryVerification.model_validate(verified())
    unsafe = parsed.model_copy(update={"parent_revision": "f" * 40})
    receipt = DurableHistoryReceipt(
        issue_comment="https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-123",
        verification_sha256="f" * 64,
    )
    with pytest.raises(ValidationError, match="CAS"):
        cleanup_preconditions_match(unsafe, receipt)


def test_plan_requires_independently_supplied_exact_observations():
    parsed = HistoryAppendPlan.model_validate(plan())
    observations = tuple(item.observation for item in parsed.extensions)
    assert validate_append_plan(parsed, observations) == parsed
    unsafe = observations[0].model_copy(update={"files": ()})
    with pytest.raises(ValidationError):
        validate_append_plan(parsed, (unsafe, observations[1]))
    raw = observations[0].model_dump()
    raw["files"][0]["blob"] = "f" * 40
    changed = DeltaObservation.model_validate(raw)
    with pytest.raises(ValueError, match="independent observation"):
        validate_append_plan(parsed, (changed, observations[1]))
    with pytest.raises(ValueError, match="independent observation"):
        validate_append_plan(parsed, (observations[0], observations[0]))
    with pytest.raises(ValueError, match="denominator"):
        validate_append_plan(parsed, observations[:1])


@pytest.mark.parametrize("case", ["count", "length"])
def test_delta_metadata_bounds(case):
    raw = plan()
    first = raw["extensions"][0]
    if case == "count":
        first["observation"]["files"] = [
            {"path": f"src/{index}.py", "blob": "a" * 40, "status": "added"}
            for index in range(257)
        ]
    else:
        first["observation"]["files"][0]["path"] = "a" * 1025
    first["delta_sha256"] = observation_digest(
        DeltaObservation.model_validate(first["observation"])
    )
    with pytest.raises(ValidationError, match="bounded profile"):
        HistoryAppendPlan.model_validate(raw)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("byte_count", True),
        ("byte_count", 0),
        ("byte_count", 1073741825),
        ("path", "../outside"),
        ("sha256", "a" * 64 + "\n"),
    ],
)
def test_object_metadata_rejects_unsafe_values(field, value):
    raw = plan()
    raw["extensions"][0]["bundle"][field] = value
    with pytest.raises(ValidationError):
        HistoryAppendPlan.model_validate(raw)


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/edithatogo/global-medicines-atlas/issues/339#issuecomment-123",
        "https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-123\n",
        "https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-123?token=fixture",
    ],
)
def test_durable_receipt_requires_exact_safe_issue_identity(url):
    with pytest.raises(ValidationError):
        DurableHistoryReceipt(issue_comment=url, verification_sha256="f" * 64)


@pytest.mark.parametrize("field", ["private", "gated"])
def test_visibility_flags_reject_integer_zero(field):
    raw = plan()
    raw["before"][field] = 0
    with pytest.raises(ValidationError, match="boolean"):
        HistoryAppendPlan.model_validate(raw)


@pytest.mark.parametrize("field", ["baseline_is_ancestor", "clean_restore"])
def test_restore_flags_reject_integer_one(field):
    raw = verified()
    raw["restored"][0][field] = 1
    with pytest.raises(ValidationError, match="boolean"):
        HistoryVerification.model_validate(raw)


def test_direct_model_revalidates_copied_private_state():
    good = HistoryAppendPlan.model_validate(plan())
    raw = good.model_dump()
    raw["before"] = good.before.model_copy(update={"private": True})
    with pytest.raises(ValidationError):
        HistoryAppendPlan.model_validate(raw)


def test_foreign_observation_is_immutable_after_direct_validation():
    good = HistoryAppendPlan.model_validate(plan())
    raw = good.model_dump()
    fields = list(good.extensions[0].observation.files)
    raw["extensions"][0]["observation"] = good.extensions[
        0
    ].observation.model_copy(update={"files": fields})
    checked = HistoryAppendPlan.model_validate(raw)
    fields.clear()
    assert isinstance(checked.extensions[0].observation.files, tuple)
    assert checked.extensions[0].observation.files


def test_direct_model_rejects_constructed_unsafe_object():
    good = HistoryAppendPlan.model_validate(plan())
    raw = good.model_dump()
    raw["extensions"][0]["bundle"] = good.extensions[0].bundle.model_copy(
        update={"byte_count": -1}
    )
    with pytest.raises(ValidationError):
        HistoryAppendPlan.model_validate(raw)
