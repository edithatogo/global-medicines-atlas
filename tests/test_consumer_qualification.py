"""Consumer package and OpenAPI compatibility contracts."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from global_medicines_atlas import consumer_qualification
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
    with pytest.raises(CompatibilityError) as exc_info:
        installed_package_identity()
    assert str(exc_info.value) == (
        "installed package metadata is incomplete: Summary"
    )


@pytest.mark.parametrize("missing_value", [None, ""])
def test_installed_metadata_reports_all_missing_fields_in_required_order(
    monkeypatch: pytest.MonkeyPatch, missing_value: object
) -> None:
    observed_names: list[str] = []
    monkeypatch.setattr(
        consumer_qualification,
        "metadata",
        lambda name: (
            observed_names.append(name)
            or {
                "Name": missing_value,
                "Version": "1.0.0",
                "Summary": missing_value,
                "Requires-Python": missing_value,
            }
        ),
    )

    with pytest.raises(CompatibilityError) as exc_info:
        installed_package_identity()

    assert observed_names == ["global-medicines-atlas"]
    assert str(exc_info.value) == (
        "installed package metadata is incomplete: "
        "Name, Summary, Requires-Python"
    )


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
    with pytest.raises(CompatibilityError) as exc_info:
        installed_package_identity()
    assert str(exc_info.value) == "metadata and runtime versions disagree"


def test_installed_metadata_returns_exact_validated_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed_metadata_names: list[str] = []
    observed_version_names: list[str] = []
    monkeypatch.setattr(
        consumer_qualification,
        "metadata",
        lambda name: (
            observed_metadata_names.append(name)
            or {
                "Name": "distribution-name",
                "Version": "3.4.5rc1",
                "Summary": "A precise summary",
                "Requires-Python": ">=3.14,<3.15",
            }
        ),
    )
    monkeypatch.setattr(
        consumer_qualification,
        "version",
        lambda name: observed_version_names.append(name) or "3.4.5rc1",
    )

    identity = installed_package_identity()

    assert observed_metadata_names == ["global-medicines-atlas"]
    assert observed_version_names == ["global-medicines-atlas"]
    assert identity == consumer_qualification.PackageIdentity(
        name="distribution-name",
        version="3.4.5rc1",
        summary="A precise summary",
        requires_python=">=3.14,<3.15",
    )


def test_current_openapi_is_compatible_with_committed_baseline() -> None:
    from fastapi.testclient import TestClient
    from tests.test_product_api import StubService

    from global_medicines_atlas.api import create_app

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


def test_openapi_compatibility_accepts_additive_read_only_contract() -> None:
    baseline = {
        "paths": {
            "/z": {
                "get": {"operationId": "get_z"},
                "parameters": [],
            }
        }
    }
    current = {
        "paths": {
            "/z": {
                "get": {"operationId": "get_z"},
                "head": {"operationId": "head_z"},
                "parameters": [{"name": "trace"}],
            },
            "/new": {"options": {"operationId": "options_new"}},
        }
    }

    assert assert_openapi_compatible(baseline, current) is None


def test_openapi_compatibility_reports_sorted_removed_paths() -> None:
    baseline = {"paths": {"/z": {}, "/a": {}, "/kept": {}}}
    current = {"paths": {"/kept": {}}}

    with pytest.raises(CompatibilityError) as exc_info:
        assert_openapi_compatible(baseline, current)

    assert str(exc_info.value) == "public OpenAPI paths removed: ['/a', '/z']"


@pytest.mark.parametrize("invalid_side", ["baseline", "current"])
def test_openapi_compatibility_reports_exact_invalid_path_item(
    invalid_side: str,
) -> None:
    baseline: dict[str, object] = {"paths": {"/items": {}}}
    current: dict[str, object] = {"paths": {"/items": {}}}
    target = baseline if invalid_side == "baseline" else current
    target["paths"]["/items"] = []  # type: ignore[index]

    with pytest.raises(CompatibilityError) as exc_info:
        assert_openapi_compatible(baseline, current)

    assert str(exc_info.value) == (
        "OpenAPI path item must be an object: /items"
    )


def test_openapi_compatibility_reports_sorted_removed_read_methods() -> None:
    baseline = {
        "paths": {
            "/items": {
                "options": {"operationId": "options_items"},
                "get": {"operationId": "get_items"},
                "head": {"operationId": "head_items"},
            }
        }
    }
    current = {"paths": {"/items": {}}}

    with pytest.raises(CompatibilityError) as exc_info:
        assert_openapi_compatible(baseline, current)

    assert str(exc_info.value) == (
        "public OpenAPI methods removed from /items: ['get', 'head', 'options']"
    )


def test_openapi_compatibility_reports_sorted_forbidden_mutations() -> None:
    baseline = {"paths": {"/items": {}}}
    current = {
        "paths": {
            "/items": {
                "put": {},
                "post": {},
                "patch": {},
                "delete": {},
            }
        }
    }

    with pytest.raises(CompatibilityError) as exc_info:
        assert_openapi_compatible(baseline, current)

    assert str(exc_info.value) == (
        "mutation operations are forbidden on /items: "
        "['delete', 'patch', 'post', 'put']"
    )


@pytest.mark.parametrize(
    ("method", "expected_method"),
    [("get", "GET"), ("head", "HEAD"), ("options", "OPTIONS")],
)
def test_openapi_compatibility_reports_exact_operation_identity_change(
    method: str, expected_method: str
) -> None:
    baseline = {"paths": {"/items": {method: {"operationId": "stable"}}}}
    current = {"paths": {"/items": {method: {"operationId": "changed"}}}}

    with pytest.raises(CompatibilityError) as exc_info:
        assert_openapi_compatible(baseline, current)

    assert str(exc_info.value) == (
        f"operation identity changed for {expected_method} /items"
    )


def test_openapi_compatibility_accepts_matching_absent_operation_ids() -> None:
    contract = {"paths": {"/items": {"get": {"description": "read"}}}}

    assert assert_openapi_compatible(contract, copy.deepcopy(contract)) is None
