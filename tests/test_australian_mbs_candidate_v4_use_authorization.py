from __future__ import annotations

import copy
import json
from importlib import import_module
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

AUTHORIZATION_PATH = (
    ROOT
    / "quality/qualifications/australian-mbs-v4-candidate-use-authorization-20261017.json"
)
ADMISSION_PATH = (
    ROOT
    / "quality/qualifications/australian-mbs-silver-admission-20261017.json"
)


def _inputs() -> tuple[dict, dict]:
    return (
        json.loads(ADMISSION_PATH.read_text(encoding="utf-8")),
        json.loads(AUTHORIZATION_PATH.read_text(encoding="utf-8")),
    )


def test_candidate_v4_use_authorization_binds_only_the_exact_six(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admission, authorization = _inputs()

    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    helper = import_module(
        "scripts.qualify_australian_mbs_gold_candidate_consumers"
    ).candidate_v4_use_binding
    binding = helper(admission, authorization, "a" * 64)

    assert binding["authorized_object_count"] == 6
    assert binding["candidate_only"] is True
    assert binding["scope"].endswith("qualification_and_consumer_canaries")


@pytest.mark.parametrize(
    "mutation",
    [
        "extra_object",
        "changed_digest",
        "changed_revision",
        "broader_boundary",
        "extra_scope_field",
    ],
)
def test_candidate_v4_use_authorization_rejects_scope_expansion(
    mutation: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    admission, authorization = _inputs()
    changed = copy.deepcopy(authorization)
    if mutation == "extra_object":
        changed["authorized_objects"].append(
            copy.deepcopy(changed["authorized_objects"][0])
        )
    elif mutation == "changed_digest":
        changed["authorized_objects"][0]["sha256"] = "0" * 64
    elif mutation == "changed_revision":
        changed["dataset_identity"]["revision"] = "different"
    elif mutation == "broader_boundary":
        changed["boundaries"]["public_release_or_publication"] = True
    else:
        changed["independent_gold_review_complete"] = True

    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    helper = import_module(
        "scripts.qualify_australian_mbs_gold_candidate_consumers"
    ).candidate_v4_use_binding
    with pytest.raises(ValueError, match=r"authorization|candidate v4"):
        helper(admission, changed, "a" * 64)
