"""Consumer package and OpenAPI compatibility contracts."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from tests.test_product_api import StubService

from global_medicines_atlas import consumer_qualification
from global_medicines_atlas.api import create_app
from global_medicines_atlas.consumer_qualification import (
    CompatibilityError,
    assert_openapi_compatible,
    installed_package_identity,
)

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "contracts/openapi-v1.json"


def _baseline() -> dict[str, object]:
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def test_installed_metadata_is_complete_and_dynamic_version_matches() -> None:
    identity = installed_package_identity()
    assert identity.name == "global-medicines-atlas"
    assert identity.version
    assert identity.summary
    assert set(identity.requires_python.split(",")) == {">=3.14", "<3.15"}


def test_installed_metadata_rejects_missing_required_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        consumer_qualification,
        "metadata",
        lambda _name: {
            "Name": "global-medicines-atlas",
            "Version": "1.0.0",
            "Summary": "",
            "Requires-Python": ">=3.14,<3.15",
        },
    )
    with pytest.raises(CompatibilityError, match="Summary"):
        installed_package_identity()


def test_installed_metadata_rejects_runtime_version_disagreement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        consumer_qualification,
        "metadata",
        lambda _name: {
            "Name": "global-medicines-atlas",
            "Version": "1.0.0",
            "Summary": "summary",
            "Requires-Python": ">=3.14,<3.15",
        },
    )
    monkeypatch.setattr(
        consumer_qualification, "version", lambda _name: "2.0.0"
    )
    with pytest.raises(CompatibilityError, match="versions disagree"):
        installed_package_identity()


def test_current_openapi_is_compatible_with_committed_baseline() -> None:
    current = (
        TestClient(create_app(StubService())).get("/api/v1/openapi.json").json()
    )
    assert_openapi_compatible(_baseline(), current)


@pytest.mark.parametrize("mutation", ["path", "method", "identity", "write"])
def test_openapi_compatibility_fails_closed(mutation: str) -> None:
    baseline = _baseline()
    current = copy.deepcopy(baseline)
    path = next(iter(baseline["paths"]))
    if mutation == "path":
        del current["paths"][path]
    elif mutation == "method":
        method = next(
            key for key in baseline["paths"][path] if key in {"get", "head"}
        )
        del current["paths"][path][method]
    elif mutation == "identity":
        method = next(
            key for key in baseline["paths"][path] if key in {"get", "head"}
        )
        current["paths"][path][method]["operationId"] = "breaking_change"
    else:
        current["paths"][path]["post"] = {"operationId": "forbidden"}
    with pytest.raises(CompatibilityError):
        assert_openapi_compatible(baseline, current)


@pytest.mark.parametrize(
    ("baseline_paths", "current_paths"),
    [
        ([], {}),
        ({}, []),
        ({"/api/v1/concepts": []}, {"/api/v1/concepts": {}}),
        ({"/api/v1/concepts": {}}, {"/api/v1/concepts": []}),
    ],
)
def test_openapi_compatibility_rejects_non_object_contract_shapes(
    baseline_paths: object,
    current_paths: object,
) -> None:
    with pytest.raises(CompatibilityError, match=r"must be (?:an )?object"):
        assert_openapi_compatible(
            {"paths": baseline_paths},
            {"paths": current_paths},
        )
