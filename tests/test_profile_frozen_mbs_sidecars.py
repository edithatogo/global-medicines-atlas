"""Exact-main sidecar inventory uses anonymous pins and aggregate-only output."""

import hashlib
import json
from pathlib import Path

import httpx
import pytest
import yaml
from scripts import profile_frozen_mbs_sidecars as module

from global_medicines_atlas.mbs_sidecar_inventory import (
    BoundSidecar,
    MetadataPin,
)

ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 40


def test_local_context_stops_before_transport(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)

    def refuse(_):
        raise AssertionError("source transport must not run locally")

    with pytest.raises(ValueError, match="exact main Actions"):
        module.qualify(SHA, transport=httpx.MockTransport(refuse))


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("GITHUB_REPOSITORY", "other/repo"),
        ("GITHUB_REF", "refs/heads/other"),
        ("GITHUB_SHA", "b" * 40),
    ],
)
def test_wrong_runner_identity_stops_before_read(monkeypatch, key, value):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", "edithatogo/global-medicines-atlas")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_SHA", SHA)
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError, match="exact main Actions"):
        module.qualify(SHA)


@pytest.fixture
def synthetic(monkeypatch):
    for key, value in {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": "edithatogo/global-medicines-atlas",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_SHA": SHA,
    }.items():
        monkeypatch.setenv(key, value)
    responses = {
        module.INFO_URL: json.dumps({
            "id": module.DATASET,
            "sha": module.REVISION,
            "private": False,
            "gated": False,
        }).encode()
    }
    sources = []
    for index, (kind, payload) in enumerate((
        ("csv", b"A,B\nSYNTHETIC,1\n"),
        ("xml", b"<r>SYNTHETIC</r>"),
        ("text", b"SYNTHETIC\n"),
    )):
        pins = []
        for role in (
            "acquisition",
            "source_receipt",
            "b2_reference",
            "landed_admission",
            "path_receipt",
        ):
            path = f"bronze/fixture/{index}/{role}.json"
            pins.append(
                MetadataPin(role, path, hashlib.sha256(b"{}").hexdigest(), 2)
            )
            responses[module._url(path)] = b"{}"
        path = f"raw/fixture/{index}"
        sources.append(
            BoundSidecar(
                module.DATASET,
                module.REVISION,
                path,
                hashlib.sha256(payload).hexdigest(),
                len(payload),
                kind,
                str(index) * 64,
                tuple(pins),
            )
        )
        responses[module._url(path)] = payload
    monkeypatch.setattr(module, "load_sidecars", lambda _: tuple(sources))
    calls = []

    def handle(request):
        assert "authorization" not in request.headers
        assert "cookie" not in request.headers
        calls.append(str(request.url))
        return httpx.Response(200, content=responses[str(request.url)])

    return sources, responses, calls, httpx.MockTransport(handle)


def test_hosted_sequence_checks_all_original_metadata_before_source(synthetic):
    sources, _, calls, transport = synthetic
    report = module.qualify(SHA, transport=transport)
    assert len(calls) == 20
    assert len(report["objects"]) == 3
    assert report["native_values_emitted"] is False
    assert report["typed_output_qualified"] is False
    assert "SYNTHETIC" not in json.dumps(report)
    for source in sources:
        raw_index = calls.index(module._url(source.source_path))
        assert all(
            calls.index(module._url(pin.path)) < raw_index
            for pin in source.metadata
        )


def test_changed_source_bytes_fail_exact_pin(synthetic):
    sources, responses, _, transport = synthetic
    responses[module._url(sources[0].source_path)] = b"changed"
    with pytest.raises(ValueError, match=r"digest|size"):
        module.qualify(SHA, transport=transport)


def test_private_revision_rejects_before_any_payload(synthetic):
    _, responses, calls, transport = synthetic
    responses[module.INFO_URL] = json.dumps({
        "id": module.DATASET,
        "sha": module.REVISION,
        "private": True,
        "gated": False,
    }).encode()
    with pytest.raises(ValueError, match="public revision"):
        module.qualify(SHA, transport=transport)
    assert calls == [module.INFO_URL]


def test_cli_preserves_existing_receipt(tmp_path):
    output = tmp_path / "receipt.json"
    output.write_text("human evidence")
    with pytest.raises(SystemExit):
        module.main(["--exact-commit", SHA, "--output", str(output)])
    assert output.read_text() == "human evidence"


def test_cli_withholds_source_exception_text(tmp_path, monkeypatch):
    def fail(_):
        raise ValueError("SYNTHETIC SECRET VALUE")

    monkeypatch.setattr(module, "qualify", fail)
    output = tmp_path / "receipt.json"
    assert module.main(["--exact-commit", SHA, "--output", str(output)]) == 1
    assert "SYNTHETIC SECRET" not in output.read_text()
    assert json.loads(output.read_bytes())["status"] == "failed"


def test_registered_sidecar_mode_is_read_only_and_exact_main():
    document = yaml.load(
        (
            ROOT / ".github/workflows/mbs-q1-source-meaning-diagnostics.yml"
        ).read_text(),
        Loader=yaml.BaseLoader,
    )
    job = document["jobs"]["sidecar-layout"]
    assert job["permissions"] == {"contents": "read"}
    assert job["timeout-minutes"] == "20"
    run = next(step["run"] for step in job["steps"] if "run" in step)
    assert "scripts/profile_frozen_mbs_sidecars.py" in run
    assert 'test "${GITHUB_SHA}" = "${REQUESTED_COMMIT}"' in run
    assert job["steps"][-1]["if"] == "always()"
    assert job["steps"][-1]["with"]["path"] == "sidecar-layout.json"


def test_failure_classification_never_renders_exception_text():
    class NeverRenderError(ValueError):
        def __str__(self):
            raise AssertionError("source exception text rendered")

    assert module._failure_category(NeverRenderError()) == "validation"
